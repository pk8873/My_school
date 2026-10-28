from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from .forms import AttendanceRecordForm, ClassRoomForm, FeeRecordForm, FeePaymentForm, StudentForm, SchoolOnboardingForm, StaffAccountForm, ParentStudentLinkForm, StudentAccountLinkForm, SubscriptionUpdateForm
from .models import AttendanceRecord, AttendanceChangeLog, ClassRoom, FeeRecord, FeePayment, Membership, Student, School, SchoolSubscription, ParentStudentLink, StaffLeaveRequest, StaffAttendance, StudentClassHistory
from .tenant import active_memberships

STAFF_ROLES = {Membership.Role.SCHOOL_ADMIN, Membership.Role.PRINCIPAL, Membership.Role.TEACHER, Membership.Role.ACCOUNTANT}
MANAGEMENT_ROLES = {Membership.Role.SCHOOL_ADMIN, Membership.Role.PRINCIPAL}
ACADEMIC_ROLES = {Membership.Role.SCHOOL_ADMIN, Membership.Role.PRINCIPAL, Membership.Role.TEACHER}
FEE_ROLES = {Membership.Role.SCHOOL_ADMIN, Membership.Role.PRINCIPAL, Membership.Role.ACCOUNTANT}


def get_membership(request):
    memberships = active_memberships(request.user).select_related("school")
    selected_id = request.GET.get("school") or request.POST.get("school")
    membership = memberships.filter(school_id=selected_id).first() if selected_id else memberships.first()
    if membership is None:
        raise Http404("No active school membership found.")
    return membership


def require_roles(membership, allowed):
    if membership.role not in allowed:
        raise PermissionDenied("Your school role does not have permission to access this page.")


@login_required
@require_GET
def dashboard(request):
    memberships = active_memberships(request.user).select_related("school")
    selected_id = request.GET.get("school")
    membership = memberships.filter(school_id=selected_id).first() if selected_id else memberships.first()
    if membership is None:
        if request.user.is_superuser:
            return render(request, "schools/dashboard.html", {"platform_admin": True, "memberships": memberships})
        return render(request, "schools/dashboard.html", {"memberships": memberships, "no_school_access": True})
    school, role = membership.school, membership.role
    context = {"memberships": memberships, "membership": membership, "school": school, "role": role}
    if role in STAFF_ROLES:
        students = Student.objects.filter(school=school, is_active=True)
        fees = FeeRecord.objects.filter(school=school)
        context.update({
            "class_count": ClassRoom.objects.filter(school=school, is_active=True).count(),
            "student_count": students.count(),
            "present_today": AttendanceRecord.objects.filter(school=school, date=timezone.localdate(), status=AttendanceRecord.Status.PRESENT).count(),
            "pending_fees": fees.exclude(status=FeeRecord.Status.WAIVED).aggregate(total=Sum(F("amount") - F("paid_amount")))["total"] or 0,
            "recent_students": students.select_related("classroom")[:8],
        })
    elif role == Membership.Role.PARENT:
        children = Student.objects.filter(parent_links__parent=request.user, parent_links__is_active=True, school=school, is_active=True).select_related("classroom").distinct()
        context["children"] = children
        child_ids = children.values_list("id", flat=True)
        context["child_attendance"] = AttendanceRecord.objects.filter(school=school, student_id__in=child_ids).select_related("student").order_by("-date")[:12]
        context["child_fees"] = FeeRecord.objects.filter(school=school, student_id__in=child_ids, student__parent_links__parent=request.user, student__parent_links__is_active=True, student__parent_links__can_view_fees=True).select_related("student").order_by("due_date")[:12]
    elif role == Membership.Role.STUDENT:
        profile = Student.objects.filter(school=school, portal_user=request.user, is_active=True).select_related("classroom").first()
        context["student_profile"] = profile
        context["student_profile_pending"] = profile is None
        if profile:
            context["attendance_history"] = AttendanceRecord.objects.filter(school=school, student=profile).order_by("-date")[:10]
            context["fee_statement"] = FeeRecord.objects.filter(school=school, student=profile).exclude(status=FeeRecord.Status.WAIVED).order_by("due_date")[:10]
    return render(request, "schools/dashboard.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def classrooms(request):
    membership = get_membership(request)
    require_roles(membership, MANAGEMENT_ROLES)
    form = ClassRoomForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        classroom = form.save(commit=False)
        classroom.school = membership.school
        classroom.save()
        messages.success(request, "Class created successfully.")
        return redirect(f"{request.path}?school={membership.school_id}")
    rows = ClassRoom.objects.filter(school=membership.school).select_related("class_teacher")
    return render(request, "schools/classrooms.html", {"membership": membership, "form": form, "classrooms": rows})



@login_required
@require_http_methods(["GET", "POST"])
def student_promotions(request):
    """Bulk-promote active students between classes and retain a per-student audit history."""
    from django.utils.dateparse import parse_date

    membership = get_membership(request)
    require_roles(membership, MANAGEMENT_ROLES)
    school = membership.school
    classrooms = ClassRoom.objects.filter(school=school, is_active=True).order_by("academic_year", "name", "section")
    error = ""
    if request.method == "POST":
        source_id = request.POST.get("from_classroom", "").strip()
        target_id = request.POST.get("to_classroom", "").strip()
        effective_date = parse_date(request.POST.get("effective_date", "").strip())
        note = request.POST.get("note", "").strip()
        if len(note) > 500:
            error = "Note must be 500 characters or fewer."
        elif not source_id.isdigit() or not target_id.isdigit():
            error = "Please select both the current class and the destination class."
        elif not effective_date:
            error = "Please provide a valid effective date in YYYY-MM-DD format."
        else:
            source = classrooms.filter(pk=int(source_id)).first()
            target = classrooms.filter(pk=int(target_id)).first()
            if source is None or target is None:
                error = "The selected class is not active or does not belong to this school."
            elif source.pk == target.pk:
                error = "Choose a different destination class."
            else:
                students = Student.objects.filter(
                    school=school, classroom=source, is_active=True
                ).order_by("pk")
                student_list = list(students[:2001])
                if not student_list:
                    error = "No active students were found in the selected current class."
                elif len(student_list) > 2000:
                    error = "This class has more than 2,000 active students. Please contact support before proceeding."
                else:
                    with transaction.atomic():
                        StudentClassHistory.objects.bulk_create([
                            StudentClassHistory(
                                school=school, student=student, from_classroom=source,
                                to_classroom=target, effective_date=effective_date,
                                promoted_by=request.user, note=note,
                            )
                            for student in student_list
                        ])
                        students.update(classroom=target)
                    messages.success(request, f"{len(student_list)} students moved from {source} to {target}. Class-change history has been saved.")
                    return redirect(f"{request.path}?school={school.pk}")
    history = StudentClassHistory.objects.filter(school=school).select_related(
        "student", "from_classroom", "to_classroom", "promoted_by"
    )[:100]
    source_counts = {
        classroom.pk: Student.objects.filter(school=school, classroom=classroom, is_active=True).count()
        for classroom in classrooms
    }
    return render(request, "schools/student_promotions.html", {
        "membership": membership, "classrooms": classrooms, "history": history,
        "source_counts": source_counts, "today": timezone.localdate().isoformat(), "error": error,
    })


@login_required
@require_http_methods(["GET", "POST"])
def students(request):
    membership = get_membership(request)
    require_roles(membership, MANAGEMENT_ROLES)
    form = StudentForm(request.POST or None, school=membership.school)
    if request.method == "POST" and form.is_valid():
        subscription = getattr(membership.school, "subscription", None)
        if subscription and subscription.student_limit and Student.objects.filter(school=membership.school).count() >= subscription.student_limit:
            form.add_error(None, f"This school's plan limit of {subscription.student_limit} students has been reached. Ask the platform administrator to review the plan.")
        else:
            student = form.save(commit=False)
            student.school = membership.school
            student.full_clean()
            student.save()
            messages.success(request, "Student admission saved.")
            return redirect(f"{request.path}?school={membership.school_id}")
    query = request.GET.get("q", "").strip()
    rows = Student.objects.filter(school=membership.school).select_related("classroom")
    if query:
        from django.db.models import Q
        rows = rows.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(admission_number__icontains=query))
    return render(request, "schools/students.html", {"membership": membership, "form": form, "students": rows[:200], "query": query, "classrooms": ClassRoom.objects.filter(school=membership.school, is_active=True)})


@login_required
@require_http_methods(["GET", "POST"])
def attendance(request):
    membership = get_membership(request)
    require_roles(membership, ACADEMIC_ROLES)
    form = AttendanceRecordForm(request.POST or None, school=membership.school)
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.school = membership.school
        record.marked_by = request.user
        record.full_clean()
        record.save()
        messages.success(request, "Attendance saved.")
        return redirect(f"{request.path}?school={membership.school_id}")
    selected_date = request.GET.get("date") or timezone.localdate().isoformat()
    rows = AttendanceRecord.objects.filter(school=membership.school, date=selected_date).select_related("student", "student__classroom")
    return render(request, "schools/attendance.html", {"membership": membership, "form": form, "records": rows, "selected_date": selected_date, "classrooms": ClassRoom.objects.filter(school=membership.school, is_active=True).order_by("name", "section")})


@login_required
@require_http_methods(["GET", "POST"])
def attendance_bulk(request):
    """Mark or update attendance for all active students in one school class."""
    from datetime import date
    from django.db import transaction
    from .forms import BulkAttendanceSelectionForm
    from .models import AttendanceRecord

    membership = get_membership(request)
    require_roles(membership, ACADEMIC_ROLES)
    selected_date = request.GET.get("date") or timezone.localdate().isoformat()
    initial = {"date": selected_date}
    if request.method == "POST":
        form = BulkAttendanceSelectionForm(request.POST, school=membership.school)
    else:
        query_data = request.GET if ("classroom" in request.GET or "date" in request.GET) else None
        form = BulkAttendanceSelectionForm(query_data, school=membership.school, initial=initial)

    students = Student.objects.none()
    existing = {}
    if request.method == "POST" and form.is_valid():
        classroom = form.cleaned_data["classroom"]
        selected_date = form.cleaned_data["date"].isoformat()
        students = Student.objects.filter(
            school=membership.school, classroom=classroom, is_active=True
        ).order_by("first_name", "last_name")
        valid_statuses = {choice[0] for choice in AttendanceRecord.Status.choices}
        invalid = any(
            request.POST.get(f"status_{student.pk}") not in valid_statuses
            for student in students
        )
        if not students.exists():
            messages.error(request, "There are no active students in this class.")
        elif invalid:
            form.add_error(None, "Choose a valid attendance status for every student.")
            messages.error(request, "Choose a valid attendance status for every student.")
        else:
            with transaction.atomic():
                for student in students:
                    status = request.POST[f"status_{student.pk}"]
                    note = request.POST.get(f"note_{student.pk}", "").strip()[:250]
                    record = AttendanceRecord.objects.filter(
                        school=membership.school, student=student, date=form.cleaned_data["date"]
                    ).first()
                    old_status = record.status if record else ""
                    old_note = record.note if record else ""
                    if record is None or old_status != status or old_note != note:
                        record, _created = AttendanceRecord.objects.update_or_create(
                            school=membership.school, student=student, date=form.cleaned_data["date"],
                            defaults={"status": status, "note": note, "marked_by": request.user},
                        )
                        AttendanceChangeLog.objects.create(
                            school=membership.school, attendance=record,
                            student_name=str(student), admission_number=student.admission_number,
                            attendance_date=form.cleaned_data["date"], old_status=old_status,
                            new_status=status, old_note=old_note, new_note=note, changed_by=request.user,
                        )
            messages.success(request, f"Attendance saved for {students.count()} students on {selected_date}.")
            return redirect(f"/attendance/bulk/?school={membership.school_id}&classroom={classroom.pk}&date={selected_date}")
    elif request.method == "GET" and form.is_valid():
        classroom = form.cleaned_data["classroom"]
        selected_date = form.cleaned_data["date"].isoformat()
        students = Student.objects.filter(
            school=membership.school, classroom=classroom, is_active=True
        ).order_by("first_name", "last_name")
    elif request.method == "GET":
        query_data = request.GET if ("classroom" in request.GET or "date" in request.GET) else None
        form = BulkAttendanceSelectionForm(
            query_data, school=membership.school,
            initial={"date": selected_date, "classroom": request.GET.get("classroom") or None},
        )

    if students.exists():
        existing = {
            row.student_id: row
            for row in AttendanceRecord.objects.filter(
                school=membership.school, student__in=students, date=selected_date
            )
        }
    student_rows = [{"student": student, "record": existing.get(student.pk)} for student in students]
    return render(request, "schools/attendance_bulk.html", {
        "membership": membership, "form": form, "students": students, "student_rows": student_rows,
        "existing": existing, "selected_date": selected_date,
        "status_choices": AttendanceRecord.Status.choices,
    })


@login_required
@require_GET
def attendance_history(request):
    """Show a school-scoped audit trail for attendance entries and corrections."""
    membership = get_membership(request)
    require_roles(membership, ACADEMIC_ROLES)
    rows = AttendanceChangeLog.objects.filter(school=membership.school).select_related("changed_by", "attendance")
    selected_date = request.GET.get("date", "").strip()
    if selected_date:
        rows = rows.filter(attendance_date=selected_date)
    query = request.GET.get("q", "").strip()
    if query:
        rows = rows.filter(Q(student_name__icontains=query) | Q(admission_number__icontains=query))
    return render(request, "schools/attendance_history.html", {
        "membership": membership, "history": rows[:250], "selected_date": selected_date, "query": query,
    })


@login_required
@require_http_methods(["GET", "POST"])
def fees(request):
    membership = get_membership(request)
    require_roles(membership, FEE_ROLES)
    form = FeeRecordForm(request.POST or None, school=membership.school)
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.school = membership.school
        record.recorded_by = request.user
        record.full_clean()
        if record.paid_amount >= record.amount and record.amount > 0:
            record.status = FeeRecord.Status.PAID
        elif record.paid_amount > 0 and record.status == FeeRecord.Status.PENDING:
            record.status = FeeRecord.Status.PARTIAL
        record.save()
        messages.success(request, "Fee record saved. This is a manual record; no online payment was processed.")
        return redirect(f"{request.path}?school={membership.school_id}")
    all_rows = FeeRecord.objects.filter(school=membership.school).select_related("student", "student__classroom")
    totals = all_rows.aggregate(total=Sum("amount"), collected=Sum("paid_amount"))
    rows = all_rows
    query = request.GET.get("q", "").strip()[:100]
    selected_status = request.GET.get("status", "").strip()
    overdue_only = request.GET.get("overdue") == "1"
    valid_statuses = {value for value, _label in FeeRecord.Status.choices}
    if selected_status in valid_statuses:
        rows = rows.filter(status=selected_status)
    else:
        selected_status = ""
    if overdue_only:
        rows = rows.filter(
            due_date__lt=timezone.localdate(),
            paid_amount__lt=F("amount"),
            status__in=[FeeRecord.Status.PENDING, FeeRecord.Status.PARTIAL],
        )
    if query:
        rows = rows.filter(
            Q(student__first_name__icontains=query)
            | Q(student__last_name__icontains=query)
            | Q(student__admission_number__icontains=query)
            | Q(title__icontains=query)
        )
    return render(request, "schools/fees.html", {
        "membership": membership, "form": form, "fees": rows[:200],
        "total_amount": totals["total"] or 0, "collected_amount": totals["collected"] or 0,
        "fee_query": query, "selected_status": selected_status, "overdue_only": overdue_only,
        "fee_result_count": rows.count(),
    })



@login_required
@require_http_methods(["GET", "POST"])
def academics(request):
    membership = get_membership(request)
    role = membership.role
    can_manage = role in ACADEMIC_ROLES
    if role not in ACADEMIC_ROLES and role not in {Membership.Role.PARENT, Membership.Role.STUDENT}:
        raise PermissionDenied("Your role cannot access academic records.")

    from .forms import AnnouncementForm, ExamForm, ExamResultForm, HomeworkForm, HomeworkSubmissionForm, HomeworkFeedbackForm
    from .models import Announcement, Exam, ExamResult, Homework, HomeworkSubmission

    exam_form = ExamForm(request.POST or None, school=membership.school, prefix="exam") if can_manage else None
    result_form = ExamResultForm(request.POST or None, school=membership.school, prefix="result") if can_manage else None
    homework_form = HomeworkForm(request.POST or None, school=membership.school, prefix="homework") if can_manage else None
    announcement_form = AnnouncementForm(request.POST or None, prefix="announcement") if role in MANAGEMENT_ROLES else None

    if request.method == "POST":
        action = request.POST.get("action", "")
        selected_form = {"exam": exam_form, "result": result_form, "homework": homework_form, "announcement": announcement_form}.get(action)
        if selected_form is None:
            raise PermissionDenied("This action is not available for your role.")
        if selected_form.is_valid():
            if action == "exam":
                obj = selected_form.save(commit=False)
                obj.school, obj.created_by = membership.school, request.user
                obj.full_clean()
                obj.save()
                messages.success(request, "Exam created.")
            elif action == "result":
                obj = selected_form.save(commit=False)
                obj.school, obj.entered_by = membership.school, request.user
                obj.full_clean()
                obj.save()
                messages.success(request, "Exam result saved.")
            elif action == "homework":
                obj = selected_form.save(commit=False)
                obj.school, obj.assigned_by = membership.school, request.user
                obj.full_clean()
                obj.save()
                messages.success(request, "Homework published.")
            elif action == "announcement":
                obj = selected_form.save(commit=False)
                obj.school, obj.created_by = membership.school, request.user
                obj.save()
                messages.success(request, "Announcement saved.")
            return redirect(f"{request.path}?school={membership.school_id}")
    if role in {Membership.Role.PARENT, Membership.Role.STUDENT}:
        if role == Membership.Role.PARENT:
            child_ids = Student.objects.filter(parent_links__parent=request.user, parent_links__is_active=True, school=membership.school).values_list("id", flat=True)
            result_child_ids = Student.objects.filter(parent_links__parent=request.user, parent_links__is_active=True, parent_links__can_view_results=True, school=membership.school).values_list("id", flat=True)
        else:
            child_ids = Student.objects.filter(school=membership.school, portal_user=request.user, is_active=True).values_list("id", flat=True)
            result_child_ids = child_ids
        results = ExamResult.objects.filter(school=membership.school, student_id__in=result_child_ids).select_related("exam", "student")
        homework_rows = Homework.objects.filter(school=membership.school, is_published=True).filter(Q(classroom__isnull=True) | Q(classroom__students__id__in=child_ids)).distinct()
        announcements = Announcement.objects.filter(school=membership.school, is_published=True, audience__in=["everyone", "parents" if role == Membership.Role.PARENT else "students"])
    else:
        results = ExamResult.objects.filter(school=membership.school).select_related("exam", "student")[:100]
        homework_rows = Homework.objects.filter(school=membership.school).select_related("classroom")[:100]
        announcements = Announcement.objects.filter(school=membership.school)[:100]
    exams = Exam.objects.filter(school=membership.school).select_related("classroom")[:100]
    if role == Membership.Role.STUDENT:
        my_submissions = HomeworkSubmission.objects.filter(
            school=membership.school, student__portal_user=request.user
        ).select_related("homework")
    elif role == Membership.Role.PARENT:
        my_submissions = HomeworkSubmission.objects.filter(
            school=membership.school, student__parent_links__parent=request.user,
            student__parent_links__is_active=True
        ).select_related("homework", "student").distinct()
    else:
        my_submissions = HomeworkSubmission.objects.none()
    review_rows = []
    if can_manage:
        for submission in HomeworkSubmission.objects.filter(
            school=membership.school
        ).select_related("homework", "student", "student__classroom")[:100]:
            review_rows.append({"submission": submission, "form": HomeworkFeedbackForm(instance=submission)})
    return render(request, "schools/academics.html", {
        "membership": membership, "role": role, "can_manage": can_manage,
        "exam_form": exam_form, "result_form": result_form, "homework_form": homework_form,
        "announcement_form": announcement_form, "exams": exams, "results": results,
        "homework_items": homework_rows, "announcements": announcements,
        "my_submissions": my_submissions, "review_rows": review_rows,
    })


@login_required
@require_http_methods(["GET", "POST"])
def homework_submit(request, homework_id):
    """A student may submit only for their linked profile and assigned school/class."""
    membership = get_membership(request)
    if membership.role != Membership.Role.STUDENT:
        raise PermissionDenied("Only student accounts can submit homework.")
    from .forms import HomeworkSubmissionForm
    from .models import Homework, HomeworkSubmission

    student = Student.objects.filter(
        school=membership.school, portal_user=request.user, is_active=True
    ).select_related("classroom").first()
    if student is None:
        raise PermissionDenied("Your student account is not linked to an active student profile.")
    homework = Homework.objects.filter(
        pk=homework_id, school=membership.school, is_published=True
    ).filter(Q(classroom__isnull=True) | Q(classroom=student.classroom)).first()
    if homework is None:
        raise Http404("Homework not found for this student.")
    submission = HomeworkSubmission.objects.filter(
        school=membership.school, homework=homework, student=student
    ).first()
    if request.method == "POST":
        form = HomeworkSubmissionForm(request.POST, instance=submission)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.school = membership.school
            obj.homework = homework
            obj.student = student
            obj.status = HomeworkSubmission.Status.SUBMITTED
            obj.teacher_feedback = ""
            obj.graded_by = None
            obj.graded_at = None
            obj.full_clean()
            obj.save()
            messages.success(request, "Homework submitted. Your teacher can now review it.")
            return redirect(f"/academics/?school={membership.school_id}")
    else:
        form = HomeworkSubmissionForm(instance=submission)
    return render(request, "schools/homework_submit.html", {
        "membership": membership, "homework": homework, "form": form,
        "submission": submission,
    })


@login_required
@require_http_methods(["GET", "POST"])
def homework_review(request, submission_id):
    """School academic staff may review only submissions belonging to their school."""
    membership = get_membership(request)
    require_roles(membership, ACADEMIC_ROLES)
    from .forms import HomeworkFeedbackForm
    from .models import HomeworkSubmission

    submission = HomeworkSubmission.objects.filter(
        pk=submission_id, school=membership.school
    ).select_related("homework", "student", "student__classroom").first()
    if submission is None:
        raise Http404("Submission not found.")
    form = HomeworkFeedbackForm(request.POST or None, instance=submission)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.graded_by = request.user
        obj.graded_at = timezone.now()
        obj.full_clean()
        obj.save()
        messages.success(request, "Homework feedback saved.")
        return redirect(f"/academics/?school={membership.school_id}")
    return render(request, "schools/homework_review.html", {
        "membership": membership, "submission": submission, "form": form,
    })


@login_required
@require_http_methods(["GET", "POST"])
def timetable(request):
    membership = get_membership(request)
    role = membership.role
    allowed_view_roles = ACADEMIC_ROLES | {Membership.Role.PARENT, Membership.Role.STUDENT}
    require_roles(membership, allowed_view_roles)
    from .forms import TimetableSlotForm
    from .models import TimetableSlot

    can_edit = role in MANAGEMENT_ROLES
    form = TimetableSlotForm(request.POST or None, school=membership.school) if can_edit else None
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied("Only school admins and principals can change the timetable.")
        if form.is_valid():
            slot = form.save(commit=False)
            slot.school = membership.school
            slot.full_clean()
            slot.save()
            messages.success(request, "Timetable slot saved.")
            return redirect(f"{request.path}?school={membership.school_id}")
    slots = TimetableSlot.objects.filter(school=membership.school, is_active=True).select_related("classroom", "teacher")
    if role == Membership.Role.TEACHER:
        slots = slots.filter(teacher=request.user)
    elif role == Membership.Role.STUDENT:
        own_student = Student.objects.filter(
            school=membership.school, portal_user=request.user, is_active=True
        ).first()
        if own_student is None:
            slots = slots.none()
        else:
            slots = slots.filter(classroom_id=own_student.classroom_id)
    elif role == Membership.Role.PARENT:
        child_class_ids = Student.objects.filter(
            school=membership.school, is_active=True,
            parent_links__parent=request.user, parent_links__is_active=True,
        ).values_list("classroom_id", flat=True).distinct()
        slots = slots.filter(classroom_id__in=child_class_ids)
    weekday_order = {key: i for i, (key, label) in enumerate(TimetableSlot.Weekday.choices)}
    slots = sorted(slots, key=lambda slot: (weekday_order[slot.weekday], slot.start_time, slot.classroom.name))
    return render(request, "schools/timetable.html", {
        "membership": membership, "role": role, "form": form, "can_edit": can_edit, "slots": slots,
        "weekdays": TimetableSlot.Weekday.choices,
        "weekday_groups": [(key, label, [slot for slot in slots if slot.weekday == key]) for key, label in TimetableSlot.Weekday.choices],
    })



def safe_csv_cell(value):
    """Neutralize spreadsheet formula prefixes in user-controlled text cells."""
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@" , "\t", "\r"}:
        return "'" + value
    return value


@login_required
@require_GET
def export_csv(request, report):
    import csv
    from django.http import HttpResponse

    membership = get_membership(request)
    if report == "staff-directory":
        require_roles(membership, MANAGEMENT_ROLES)
        rows = Membership.objects.filter(school=membership.school).select_related("user").order_by("role", "user__username")
        role_filter = request.GET.get("role", "").strip()
        valid_roles = {value for value, _label in Membership.Role.choices}
        if role_filter:
            if role_filter not in valid_roles:
                return HttpResponse("Invalid role filter.", status=400)
            rows = rows.filter(role=role_filter)
        status_filter = request.GET.get("status", "").strip()
        if status_filter:
            if status_filter not in {"active", "inactive"}:
                return HttpResponse("Invalid status filter.", status=400)
            rows = rows.filter(is_active=(status_filter == "active"))
        filename = "school-account-directory.csv"
        headers = ["Username", "First name", "Last name", "Full name", "Email", "School role", "Membership status", "Membership created"]
        values = ((
            row.user.get_username(), row.user.first_name, row.user.last_name,
            row.user.get_full_name(), row.user.email, row.get_role_display(),
            "Active" if row.is_active else "Inactive", row.created_at,
        ) for row in rows)
    elif report == "upcoming-birthdays":
        from datetime import date, timedelta

        require_roles(membership, MANAGEMENT_ROLES)
        days_raw = request.GET.get("days", "30").strip()
        if not days_raw.isdigit() or not 1 <= int(days_raw) <= 365:
            return HttpResponse("days must be a whole number from 1 to 365.", status=400)
        days = int(days_raw)
        today = timezone.localdate()
        last_day = today + timedelta(days=days)
        rows = Student.objects.filter(
            school=membership.school, is_active=True, date_of_birth__isnull=False,
            classroom__school=membership.school,
        ).select_related("classroom").order_by("classroom__name", "first_name", "last_name")[:10000]
        birthday_values = []
        for student in rows:
            dob = student.date_of_birth
            try:
                next_birthday = date(today.year, dob.month, dob.day)
            except ValueError:
                # Celebrate 29 February birthdays on 28 February in non-leap years.
                next_birthday = date(today.year, 2, 28)
            if next_birthday < today:
                try:
                    next_birthday = date(today.year + 1, dob.month, dob.day)
                except ValueError:
                    next_birthday = date(today.year + 1, 2, 28)
            if today <= next_birthday <= last_day:
                birthday_values.append((
                    next_birthday, student.admission_number, str(student),
                    student.classroom.name, student.classroom.section, dob,
                    next_birthday.year - dob.year,
                ))
        birthday_values.sort(key=lambda row: (row[0], row[3], row[2]))
        filename = "upcoming-student-birthdays.csv"
        headers = ["Birthday date", "Admission number", "Student", "Class", "Section", "Date of birth", "Turning age"]
        values = birthday_values
    elif report == "students":
        require_roles(membership, MANAGEMENT_ROLES)
        rows = Student.objects.filter(school=membership.school).select_related("classroom")
        filename = "students.csv"
        headers = ["Admission number", "First name", "Last name", "Class", "Section", "Active", "Admission date"]
        values = ((s.admission_number, s.first_name, s.last_name, s.classroom.name, s.classroom.section, s.is_active, s.admitted_at or "") for s in rows)
    elif report == "low-attendance":
        from django.db.models import Count
        from django.utils.dateparse import parse_date

        require_roles(membership, ACADEMIC_ROLES)
        threshold_raw = request.GET.get("threshold", "75").strip()
        min_days_raw = request.GET.get("min_days", "5").strip()
        if not threshold_raw.isdigit() or not 1 <= int(threshold_raw) <= 100:
            return HttpResponse("threshold must be a whole number from 1 to 100.", status=400)
        if not min_days_raw.isdigit() or not 1 <= int(min_days_raw) <= 366:
            return HttpResponse("min_days must be a whole number from 1 to 366.", status=400)
        threshold = int(threshold_raw)
        min_days = int(min_days_raw)
        record_filter = Q(attendance_records__school=membership.school)
        parsed_dates = {}
        for parameter, lookup in (("date_from", "attendance_records__date__gte"), ("date_to", "attendance_records__date__lte")):
            raw_date = request.GET.get(parameter, "").strip()
            if raw_date:
                parsed = parse_date(raw_date)
                if parsed is None:
                    return HttpResponse("Invalid date filter. Use YYYY-MM-DD.", status=400)
                parsed_dates[parameter] = parsed
                record_filter &= Q(**{lookup: parsed})
        if parsed_dates.get("date_from") and parsed_dates.get("date_to") and parsed_dates["date_from"] > parsed_dates["date_to"]:
            return HttpResponse("date_from must be on or before date_to.", status=400)
        classroom_id = request.GET.get("classroom", "").strip()
        if classroom_id and not classroom_id.isdigit():
            return HttpResponse("Invalid classroom filter.", status=400)
        students = Student.objects.filter(school=membership.school, is_active=True).select_related("classroom")
        if classroom_id:
            students = students.filter(classroom_id=int(classroom_id), classroom__school=membership.school)
        students = students.annotate(
            total_days=Count("attendance_records", filter=record_filter),
            present_days=Count("attendance_records", filter=record_filter & Q(attendance_records__status=AttendanceRecord.Status.PRESENT)),
            late_days=Count("attendance_records", filter=record_filter & Q(attendance_records__status=AttendanceRecord.Status.LATE)),
            absent_days=Count("attendance_records", filter=record_filter & Q(attendance_records__status=AttendanceRecord.Status.ABSENT)),
        ).order_by("classroom__name", "classroom__section", "first_name", "last_name")
        filename = "low-attendance.csv"
        headers = ["Admission number", "Student", "Class", "Section", "Marked days", "Present", "Late", "Absent", "Attendance percentage", "Threshold percentage"]
        def low_attendance_values():
            for student in students:
                total = student.total_days
                if total < min_days or not total:
                    continue
                attended = student.present_days + student.late_days
                percentage = attended * 100 / total
                if percentage < threshold:
                    yield (
                        student.admission_number, str(student), student.classroom.name, student.classroom.section,
                        total, student.present_days, student.late_days, student.absent_days,
                        f"{percentage:.2f}", threshold,
                    )
        values = low_attendance_values()
    elif report == "attendance-summary":
        from django.db.models import Count
        from django.utils.dateparse import parse_date

        require_roles(membership, ACADEMIC_ROLES)
        record_filter = Q(attendance_records__school=membership.school)
        parsed_dates = {}
        for parameter, lookup in (("date_from", "attendance_records__date__gte"), ("date_to", "attendance_records__date__lte")):
            raw_date = request.GET.get(parameter, "").strip()
            if raw_date:
                parsed = parse_date(raw_date)
                if parsed is None:
                    return HttpResponse("Invalid date filter. Use YYYY-MM-DD.", status=400)
                parsed_dates[parameter] = parsed
                record_filter &= Q(**{lookup: parsed})
        if parsed_dates.get("date_from") and parsed_dates.get("date_to") and parsed_dates["date_from"] > parsed_dates["date_to"]:
            return HttpResponse("date_from must be on or before date_to.", status=400)
        classroom_id = request.GET.get("classroom", "").strip()
        if classroom_id:
            if not classroom_id.isdigit():
                return HttpResponse("Invalid classroom filter.", status=400)
        students = Student.objects.filter(school=membership.school, is_active=True).select_related("classroom")
        if classroom_id:
            students = students.filter(classroom_id=int(classroom_id), classroom__school=membership.school)
        students = students.annotate(
            total_days=Count("attendance_records", filter=record_filter),
            present_days=Count("attendance_records", filter=record_filter & Q(attendance_records__status=AttendanceRecord.Status.PRESENT)),
            absent_days=Count("attendance_records", filter=record_filter & Q(attendance_records__status=AttendanceRecord.Status.ABSENT)),
            late_days=Count("attendance_records", filter=record_filter & Q(attendance_records__status=AttendanceRecord.Status.LATE)),
            leave_days=Count("attendance_records", filter=record_filter & Q(attendance_records__status=AttendanceRecord.Status.LEAVE)),
        ).order_by("classroom__name", "classroom__section", "first_name", "last_name")
        filename = "attendance-summary.csv"
        headers = ["Admission number", "Student", "Class", "Section", "Marked days", "Present", "Absent", "Late", "On leave", "Present + late percentage"]
        def summary_values():
            for student in students:
                total = student.total_days
                attended = student.present_days + student.late_days
                percentage = f"{(attended * 100 / total):.2f}" if total else "N/A"
                yield (
                    student.admission_number, str(student), student.classroom.name, student.classroom.section,
                    total, student.present_days, student.absent_days, student.late_days, student.leave_days, percentage,
                )
        values = summary_values()
    elif report == "attendance":
        from django.utils.dateparse import parse_date

        require_roles(membership, ACADEMIC_ROLES)
        rows = AttendanceRecord.objects.filter(school=membership.school).select_related("student", "student__classroom")
        parsed_dates = {}
        for parameter, lookup in (("date_from", "date__gte"), ("date_to", "date__lte")):
            raw_date = request.GET.get(parameter, "").strip()
            if raw_date:
                parsed = parse_date(raw_date)
                if parsed is None:
                    return HttpResponse("Invalid date filter. Use YYYY-MM-DD.", status=400)
                parsed_dates[parameter] = parsed
                rows = rows.filter(**{lookup: parsed})
        if parsed_dates.get("date_from") and parsed_dates.get("date_to") and parsed_dates["date_from"] > parsed_dates["date_to"]:
            return HttpResponse("date_from must be on or before date_to.", status=400)
        date_filter = request.GET.get("date", "").strip()
        if date_filter:
            parsed_day = parse_date(date_filter)
            if parsed_day is None:
                return HttpResponse("Invalid date filter. Use YYYY-MM-DD.", status=400)
            rows = rows.filter(date=parsed_day)
        classroom_id = request.GET.get("classroom", "").strip()
        if classroom_id:
            if not classroom_id.isdigit():
                return HttpResponse("Invalid classroom filter.", status=400)
            rows = rows.filter(student__classroom_id=int(classroom_id), student__classroom__school=membership.school)
        filename = "attendance.csv"
        headers = ["Date", "Admission number", "Student", "Class", "Status", "Note"]
        values = ((r.date, r.student.admission_number, str(r.student), r.student.classroom.name, r.get_status_display(), r.note) for r in rows)
    elif report == "exam-results":
        from .models import ExamResult
        from django.utils.dateparse import parse_date

        require_roles(membership, ACADEMIC_ROLES)
        rows = ExamResult.objects.filter(
            school=membership.school, exam__school=membership.school, student__school=membership.school,
        ).select_related("exam", "student", "student__classroom").order_by("exam__exam_date", "exam__title", "student__first_name", "student__last_name")
        exam_id = request.GET.get("exam", "").strip()
        if exam_id:
            if not exam_id.isdigit():
                return HttpResponse("Invalid exam filter.", status=400)
            rows = rows.filter(exam_id=int(exam_id))
        classroom_id = request.GET.get("classroom", "").strip()
        if classroom_id:
            if not classroom_id.isdigit():
                return HttpResponse("Invalid classroom filter.", status=400)
            rows = rows.filter(student__classroom_id=int(classroom_id), student__classroom__school=membership.school)
        date_from = request.GET.get("date_from", "").strip()
        date_to = request.GET.get("date_to", "").strip()
        parsed_dates = {}
        for parameter, lookup in (("date_from", "exam__exam_date__gte"), ("date_to", "exam__exam_date__lte")):
            raw_date = request.GET.get(parameter, "").strip()
            if raw_date:
                parsed = parse_date(raw_date)
                if parsed is None:
                    return HttpResponse("Invalid date filter. Use YYYY-MM-DD.", status=400)
                parsed_dates[parameter] = parsed
                rows = rows.filter(**{lookup: parsed})
        if parsed_dates.get("date_from") and parsed_dates.get("date_to") and parsed_dates["date_from"] > parsed_dates["date_to"]:
            return HttpResponse("date_from must be on or before date_to.", status=400)
        filename = "exam-results.csv"
        headers = ["Exam", "Exam date", "Admission number", "Student", "Class", "Section", "Marks obtained", "Maximum marks", "Percentage", "Remarks"]
        values = ((
            r.exam.title, r.exam.exam_date, r.student.admission_number, str(r.student),
            r.student.classroom.name, r.student.classroom.section, r.marks_obtained,
            r.exam.max_marks, r.percentage, r.remarks,
        ) for r in rows)
    elif report == "homework-submissions":
        from django.utils.dateparse import parse_date
        from .models import HomeworkSubmission

        require_roles(membership, ACADEMIC_ROLES)
        rows = HomeworkSubmission.objects.filter(
            school=membership.school,
            homework__school=membership.school,
            student__school=membership.school,
        ).select_related(
            "homework", "homework__classroom", "student", "student__classroom", "graded_by",
        ).order_by("-submitted_at")
        homework_id = request.GET.get("homework", "").strip()
        if homework_id:
            if not homework_id.isdigit():
                return HttpResponse("Invalid homework filter.", status=400)
            rows = rows.filter(homework_id=int(homework_id))
        classroom_id = request.GET.get("classroom", "").strip()
        if classroom_id:
            if not classroom_id.isdigit():
                return HttpResponse("Invalid classroom filter.", status=400)
            rows = rows.filter(student__classroom_id=int(classroom_id), student__classroom__school=membership.school)
        status = request.GET.get("status", "").strip()
        valid_statuses = {value for value, _label in HomeworkSubmission.Status.choices}
        if status:
            if status not in valid_statuses:
                return HttpResponse("Invalid submission status filter.", status=400)
            rows = rows.filter(status=status)
        parsed_dates = {}
        for parameter, lookup in (("date_from", "submitted_at__date__gte"), ("date_to", "submitted_at__date__lte")):
            raw_date = request.GET.get(parameter, "").strip()
            if raw_date:
                parsed = parse_date(raw_date)
                if parsed is None:
                    return HttpResponse("Invalid date filter. Use YYYY-MM-DD.", status=400)
                parsed_dates[parameter] = parsed
                rows = rows.filter(**{lookup: parsed})
        if parsed_dates.get("date_from") and parsed_dates.get("date_to") and parsed_dates["date_from"] > parsed_dates["date_to"]:
            return HttpResponse("date_from must be on or before date_to.", status=400)
        filename = "homework-submissions.csv"
        headers = ["Homework", "Due date", "Admission number", "Student", "Class", "Section", "Submitted at", "Status", "Submission text", "Teacher feedback", "Reviewed by", "Reviewed at"]
        values = ((
            row.homework.title, row.homework.due_date or "", row.student.admission_number,
            str(row.student), row.student.classroom.name, row.student.classroom.section,
            row.submitted_at, row.get_status_display(), row.submission_text,
            row.teacher_feedback, row.graded_by.get_username() if row.graded_by else "", row.graded_at or "",
        ) for row in rows)
    elif report == "overdue-fees":
        from django.utils.dateparse import parse_date

        require_roles(membership, FEE_ROLES)
        rows = FeeRecord.objects.filter(
            school=membership.school,
            student__school=membership.school,
            due_date__lt=timezone.localdate(),
            paid_amount__lt=F("amount"),
            status__in=[FeeRecord.Status.PENDING, FeeRecord.Status.PARTIAL],
        ).select_related("student", "student__classroom").order_by("due_date", "student__first_name")
        classroom_id = request.GET.get("classroom", "").strip()
        if classroom_id:
            if not classroom_id.isdigit():
                return HttpResponse("Invalid classroom filter.", status=400)
            rows = rows.filter(student__classroom_id=int(classroom_id), student__classroom__school=membership.school)
        due_before_raw = request.GET.get("due_before", "").strip()
        if due_before_raw:
            due_before = parse_date(due_before_raw)
            if due_before is None:
                return HttpResponse("Invalid due_before date. Use YYYY-MM-DD.", status=400)
            rows = rows.filter(due_date__lt=due_before)
        filename = "overdue-fees.csv"
        headers = ["Admission number", "Student", "Class", "Section", "Fee head", "Amount", "Paid", "Outstanding balance", "Due date", "Days overdue", "Payment status", "Reference"]
        today = timezone.localdate()
        values = ((
            row.student.admission_number, str(row.student), row.student.classroom.name,
            row.student.classroom.section, row.title, row.amount, row.paid_amount,
            row.balance, row.due_date or "", (today - row.due_date).days if row.due_date else "",
            row.get_status_display(), row.payment_reference,
        ) for row in rows)
    elif report == "fees":
        require_roles(membership, FEE_ROLES)
        rows = FeeRecord.objects.filter(school=membership.school).select_related("student")
        filename = "fee-ledger.csv"
        headers = ["Admission number", "Student", "Fee head", "Amount", "Paid", "Balance", "Due date", "Status", "Reference"]
        values = ((r.student.admission_number, str(r.student), r.title, r.amount, r.paid_amount, r.balance, r.due_date or "", r.get_status_display(), r.payment_reference) for r in rows)
    elif report == "fee-collection-summary":
        from django.db.models import Count, Sum
        from django.utils.dateparse import parse_date

        require_roles(membership, FEE_ROLES)
        rows = FeePayment.objects.filter(
            school=membership.school, fee_record__school=membership.school,
        )
        parsed_dates = {}
        for parameter, lookup in (("date_from", "payment_date__gte"), ("date_to", "payment_date__lte")):
            raw_date = request.GET.get(parameter, "").strip()
            if raw_date:
                parsed = parse_date(raw_date)
                if parsed is None:
                    return HttpResponse("Invalid date filter. Use YYYY-MM-DD.", status=400)
                parsed_dates[parameter] = parsed
                rows = rows.filter(**{lookup: parsed})
        if parsed_dates.get("date_from") and parsed_dates.get("date_to") and parsed_dates["date_from"] > parsed_dates["date_to"]:
            return HttpResponse("date_from must be on or before date_to.", status=400)
        summary = rows.values("payment_date", "method").annotate(
            transaction_count=Count("id"), total_amount=Sum("amount"),
        ).order_by("payment_date", "method")
        filename = "fee-collection-summary.csv"
        headers = ["Payment date", "Payment method", "Transaction count", "Total collected"]
        values = ((
            item["payment_date"], dict(FeePayment.Method.choices).get(item["method"], item["method"]),
            item["transaction_count"], item["total_amount"],
        ) for item in summary)
    elif report == "fee-payments":
        from django.utils.dateparse import parse_date

        require_roles(membership, FEE_ROLES)
        rows = FeePayment.objects.filter(
            school=membership.school, fee_record__school=membership.school,
        ).select_related("fee_record", "fee_record__student", "fee_record__student__classroom", "recorded_by")
        fee_id = request.GET.get("fee_id", "").strip()
        if fee_id:
            if not fee_id.isdigit():
                raise Http404("Invalid fee entry.")
            rows = rows.filter(fee_record_id=int(fee_id))
        parsed_dates = {}
        for parameter, lookup in (("date_from", "payment_date__gte"), ("date_to", "payment_date__lte")):
            raw_date = request.GET.get(parameter, "").strip()
            if raw_date:
                parsed = parse_date(raw_date)
                if parsed is None:
                    return HttpResponse("Invalid date filter. Use YYYY-MM-DD.", status=400)
                parsed_dates[parameter] = parsed
                rows = rows.filter(**{lookup: parsed})
        if parsed_dates.get("date_from") and parsed_dates.get("date_to") and parsed_dates["date_from"] > parsed_dates["date_to"]:
            return HttpResponse("date_from must be on or before date_to.", status=400)
        method = request.GET.get("method", "").strip()
        valid_methods = {value for value, _label in FeePayment.Method.choices}
        if method:
            if method not in valid_methods:
                return HttpResponse("Invalid payment method filter.", status=400)
            rows = rows.filter(method=method)
        query = request.GET.get("q", "").strip()[:100]
        if query:
            rows = rows.filter(
                Q(fee_record__student__first_name__icontains=query)
                | Q(fee_record__student__last_name__icontains=query)
                | Q(fee_record__student__admission_number__icontains=query)
                | Q(fee_record__title__icontains=query)
                | Q(reference__icontains=query)
            )
        filename = "fee-payments.csv"
        headers = ["Payment date", "Admission number", "Student", "Class", "Fee head", "Amount", "Method", "Reference", "Note", "Recorded by"]
        values = ((
            p.payment_date, p.fee_record.student.admission_number, str(p.fee_record.student),
            p.fee_record.student.classroom.name, p.fee_record.title, p.amount,
            p.get_method_display(), p.reference, p.note,
            p.recorded_by.get_username() if p.recorded_by else "",
        ) for p in rows)
    else:
        raise Http404("Unknown report.")

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in values:
        writer.writerow([safe_csv_cell(value) for value in row])
    return response


def _pdf_escape(value):
    from xml.sax.saxutils import escape
    return escape(str(value if value is not None else "—"))


def _build_pdf(title, subtitle, rows, *, filename):
    """Build a small, printable PDF report using server-side trusted data."""
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm, title=title,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#183153"), spaceAfter=8))
    story = [Paragraph(_pdf_escape(title), styles["ReportTitle"]), Paragraph(_pdf_escape(subtitle), styles["Normal"]), Spacer(1, 10 * mm)]
    table_data = [[Paragraph(f"<b>{_pdf_escape(cell)}</b>", styles["BodyText"]) for cell in rows[0]]]
    for row in rows[1:]:
        table_data.append([Paragraph(_pdf_escape(cell), styles["BodyText"]) for cell in row])
    table = Table(table_data, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#183153")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    doc.build(story)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_GET
def attendance_report_pdf(request):
    """Download a school-scoped attendance PDF report for a date range and optional class."""
    from django.utils.dateparse import parse_date

    membership = get_membership(request)
    require_roles(membership, ACADEMIC_ROLES)
    rows = AttendanceRecord.objects.filter(
        school=membership.school,
        student__school=membership.school,
    ).select_related("student", "student__classroom").order_by("date", "student__classroom__name", "student__first_name")
    parsed_dates = {}
    for parameter, lookup in (("date_from", "date__gte"), ("date_to", "date__lte")):
        raw = request.GET.get(parameter, "").strip()
        if raw:
            parsed = parse_date(raw)
            if parsed is None:
                return HttpResponse("Invalid date filter. Use YYYY-MM-DD.", status=400)
            parsed_dates[parameter] = parsed
            rows = rows.filter(**{lookup: parsed})
    if parsed_dates.get("date_from") and parsed_dates.get("date_to") and parsed_dates["date_from"] > parsed_dates["date_to"]:
        return HttpResponse("date_from must be on or before date_to.", status=400)
    classroom_id = request.GET.get("classroom", "").strip()
    if classroom_id:
        if not classroom_id.isdigit():
            return HttpResponse("Invalid classroom filter.", status=400)
        rows = rows.filter(student__classroom_id=int(classroom_id), student__classroom__school=membership.school)
    table_rows = [["Date", "Admission no.", "Student", "Class", "Status", "Note"]]
    for record in rows[:2000]:
        table_rows.append([
            record.date.isoformat(), record.student.admission_number, str(record.student),
            f"{record.student.classroom.name} {record.student.classroom.section}".strip(),
            record.get_status_display(), record.note or "—",
        ])
    start = parsed_dates.get("date_from")
    end = parsed_dates.get("date_to")
    period = f"{start or 'All dates'} to {end or 'Today'}"
    if not start and not end:
        period = "All recorded dates"
    if classroom_id and rows.exists():
        period += f" · {rows.first().student.classroom.name}"
    return _build_pdf(
        "Attendance Report", f"{membership.school.name} · {period} · Up to 2,000 records",
        table_rows, filename="attendance-report.pdf",
    )


@login_required
@require_GET
def student_report_card_pdf(request, student_id):
    """Download a school-scoped report card after record-level authorization."""
    membership = get_membership(request)
    student = Student.objects.filter(pk=student_id, school=membership.school, is_active=True).select_related("classroom").first()
    if student is None:
        raise Http404("Student not found.")
    if membership.role in {Membership.Role.PARENT, Membership.Role.STUDENT}:
        if membership.role == Membership.Role.PARENT:
            allowed = ParentStudentLink.objects.filter(
                parent=request.user, student=student, is_active=True, can_view_results=True
            ).exists()
        else:
            allowed = student.portal_user_id == request.user.pk
        if not allowed:
            raise PermissionDenied("You cannot view this student's report card.")
    elif membership.role not in ACADEMIC_ROLES:
        raise PermissionDenied("Your school role cannot download report cards.")

    from .models import ExamResult
    results = ExamResult.objects.filter(school=membership.school, student=student).select_related("exam").order_by("-exam__exam_date", "exam__title")
    table_rows = [["Exam", "Date", "Marks", "Percent", "Remarks"]]
    for result in results:
        table_rows.append([
            result.exam.title, result.exam.exam_date.isoformat(),
            f"{result.marks_obtained} / {result.exam.max_marks}",
            f"{result.percentage}%", result.remarks or "—",
        ])
    if len(table_rows) == 1:
        table_rows.append(["No results recorded", "—", "—", "—", "—"])
    subtitle = f"School: {membership.school.name} | Student: {student.first_name} {student.last_name} | Admission: {student.admission_number} | Class: {student.classroom}"
    return _build_pdf("Student Report Card", subtitle, table_rows, filename=f"report-card-{student.admission_number}.pdf")



@login_required
@require_GET
def student_id_cards_pdf(request):
    """Generate a printable sheet of student ID cards for one school/class."""
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    membership = get_membership(request)
    require_roles(membership, MANAGEMENT_ROLES)
    students = Student.objects.filter(
        school=membership.school, is_active=True,
        classroom__school=membership.school,
    ).select_related("classroom").order_by("classroom__name", "classroom__section", "first_name", "last_name")
    classroom_id = request.GET.get("classroom", "").strip()
    if classroom_id:
        if not classroom_id.isdigit():
            return HttpResponse("Invalid classroom filter.", status=400)
        classroom = ClassRoom.objects.filter(pk=int(classroom_id), school=membership.school, is_active=True).first()
        if classroom is None:
            raise Http404("Classroom not found.")
        students = students.filter(classroom=classroom)
    student_list = list(students[:201])
    if not student_list:
        return HttpResponse("No active students found for the selected school/class.", status=404)
    if len(student_list) > 200:
        return HttpResponse("Please select a class or narrow the list to 200 students or fewer.", status=400)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="IDSchool", parent=styles["Heading3"], fontSize=10, leading=12, alignment=1, textColor=colors.HexColor("#17365D"), spaceAfter=3))
    styles.add(ParagraphStyle(name="IDName", parent=styles["Heading2"], fontSize=11, leading=13, alignment=1, spaceAfter=4))
    styles.add(ParagraphStyle(name="IDText", parent=styles["BodyText"], fontSize=8, leading=10, alignment=1))
    cards = []
    for student in student_list:
        school_name = _pdf_escape(membership.school.name)
        student_name = _pdf_escape(f"{student.first_name} {student.last_name}".strip())
        fields = [
            [Paragraph(f"<b>{school_name}</b>", styles["IDSchool"])],
            [Paragraph(student_name, styles["IDName"])],
            [Paragraph(f"Admission No: {_pdf_escape(student.admission_number)}", styles["IDText"])],
            [Paragraph(f"Class: {_pdf_escape(str(student.classroom))} · {_pdf_escape(student.classroom.academic_year)}", styles["IDText"])],
        ]
        if student.date_of_birth:
            fields.append([Paragraph(f"DOB: {student.date_of_birth.isoformat()}", styles["IDText"])])
        if membership.school.phone:
            fields.append([Paragraph(f"School phone: {_pdf_escape(membership.school.phone)}", styles["IDText"])])
        card = Table(fields, colWidths=[82 * mm])
        card.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#42658A")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF1F8")),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        cards.append(card)
    card_rows = []
    for index in range(0, len(cards), 2):
        card_rows.append([cards[index], cards[index + 1] if index + 1 < len(cards) else ""])
    sheet = Table(card_rows, colWidths=[88 * mm, 88 * mm], hAlign="CENTER")
    sheet.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=12 * mm, leftMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm, title="Student ID Cards")
    doc.build([
        Paragraph(_pdf_escape(membership.school.name) + " — Student ID Cards", styles["Title"]),
        Paragraph(f"Generated {timezone.localdate().isoformat()} · {len(student_list)} cards", styles["Normal"]),
        Spacer(1, 6 * mm), sheet,
    ])
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="student-id-cards.pdf"'
    return response


@login_required
@require_GET
def student_fee_statement_pdf(request, student_id):
    """Download a school-scoped fee statement; it is not a payment receipt."""
    membership = get_membership(request)
    student = Student.objects.filter(pk=student_id, school=membership.school, is_active=True).select_related("classroom").first()
    if student is None:
        raise Http404("Student not found.")
    if membership.role in FEE_ROLES:
        allowed = True
    elif membership.role == Membership.Role.PARENT:
        allowed = ParentStudentLink.objects.filter(
            parent=request.user, student=student, is_active=True, can_view_fees=True
        ).exists()
    elif membership.role == Membership.Role.STUDENT:
        allowed = student.portal_user_id == request.user.pk
    else:
        allowed = False
    if not allowed:
        raise PermissionDenied("You cannot view this student's fee statement.")

    rows = FeeRecord.objects.filter(school=membership.school, student=student).order_by("due_date", "title")
    table_rows = [["Fee head", "Due date", "Amount", "Paid", "Balance", "Status"]]
    total_amount = total_paid = total_balance = 0
    for fee in rows:
        table_rows.append([
            fee.title, fee.due_date.isoformat() if fee.due_date else "—",
            f"INR {fee.amount:.2f}", f"INR {fee.paid_amount:.2f}",
            f"INR {fee.balance:.2f}", fee.get_status_display(),
        ])
        total_amount += fee.amount
        total_paid += fee.paid_amount
        total_balance += fee.balance
    if len(table_rows) == 1:
        table_rows.append(["No fee records", "—", "INR 0.00", "INR 0.00", "INR 0.00", "—"])
    table_rows.append(["TOTAL", "—", f"INR {total_amount:.2f}", f"INR {total_paid:.2f}", f"INR {total_balance:.2f}", ""])
    subtitle = f"School: {membership.school.name} | Student: {student.first_name} {student.last_name} | Admission: {student.admission_number} | Generated: {timezone.localdate().isoformat()} | Statement only — not proof of payment"
    return _build_pdf("Student Fee Statement", subtitle, table_rows, filename=f"fee-statement-{student.admission_number}.pdf")

@login_required
@require_http_methods(["GET", "POST"])
def fee_payment_history(request, fee_id):
    """View an individual fee's manual payment history and record a new collection."""
    membership = get_membership(request)
    require_roles(membership, FEE_ROLES)
    fee = FeeRecord.objects.filter(
        pk=fee_id, school=membership.school
    ).select_related("student", "student__classroom").first()
    if fee is None:
        raise Http404("Fee record not found.")

    form = FeePaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked_fee = FeeRecord.objects.select_for_update().filter(
                pk=fee_id, school=membership.school
            ).first()
            if locked_fee is None:
                raise Http404("Fee record not found.")
            amount = form.cleaned_data["amount"]
            if locked_fee.status == FeeRecord.Status.WAIVED:
                form.add_error(None, "A waived fee cannot accept a payment.")
            elif amount > locked_fee.balance:
                form.add_error("amount", f"Payment cannot exceed the outstanding balance of {locked_fee.balance:.2f}.")
            else:
                payment = form.save(commit=False)
                payment.school = membership.school
                payment.fee_record = locked_fee
                payment.recorded_by = request.user
                payment.full_clean()
                payment.save()
                locked_fee.paid_amount += payment.amount
                locked_fee.status = (
                    FeeRecord.Status.PAID
                    if locked_fee.paid_amount >= locked_fee.amount
                    else FeeRecord.Status.PARTIAL
                )
                locked_fee.full_clean()
                locked_fee.save(update_fields=["paid_amount", "status"])
                messages.success(request, "Manual payment recorded. No bank or online payment was processed by this app.")
                return redirect(f"{request.path}?school={membership.school_id}")

    payments = FeePayment.objects.filter(
        school=membership.school, fee_record=fee
    ).select_related("recorded_by")
    return render(request, "schools/fee_payment_history.html", {
        "membership": membership, "fee": fee, "form": form,
        "payments": payments, "recorded_payment_total": payments.aggregate(total=Sum("amount"))["total"] or 0,
    })



@login_required
@require_GET
def fee_collection_receipt_pdf(request, fee_id):
    """Download a receipt-style acknowledgement for a manually recorded collection."""
    membership = get_membership(request)
    fee = FeeRecord.objects.filter(pk=fee_id, school=membership.school).select_related(
        "student", "student__classroom", "recorded_by"
    ).first()
    if fee is None:
        raise Http404("Fee record not found.")
    if membership.role in FEE_ROLES:
        allowed = True
    elif membership.role == Membership.Role.PARENT:
        allowed = ParentStudentLink.objects.filter(
            parent=request.user, student=fee.student, is_active=True, can_view_fees=True
        ).exists()
    elif membership.role == Membership.Role.STUDENT:
        allowed = fee.student.portal_user_id == request.user.pk
    else:
        allowed = False
    if not allowed:
        raise PermissionDenied("You cannot view this fee record.")
    if fee.paid_amount <= 0:
        raise Http404("No collection has been recorded for this fee entry.")
    table_rows = [
        ["Field", "Recorded details"],
        ["Receipt reference", f"FEE-{fee.school_id}-{fee.pk}"],
        ["Student", f"{fee.student.first_name} {fee.student.last_name}"],
        ["Admission number", fee.student.admission_number],
        ["Class", str(fee.student.classroom)],
        ["Fee head", fee.title],
        ["Total fee", f"INR {fee.amount:.2f}"],
        ["Amount recorded as collected", f"INR {fee.paid_amount:.2f}"],
        ["Outstanding balance", f"INR {fee.balance:.2f}"],
        ["Status", fee.get_status_display()],
        ["Payment reference", fee.payment_reference or "Not provided"],
        ["Record created", timezone.localtime(fee.created_at).strftime("%d %b %Y, %H:%M")],
        ["Recorded by", fee.recorded_by.get_username() if fee.recorded_by else "Unavailable"],
    ]
    subtitle = (
        f"School: {membership.school.name} | This document acknowledges the amount manually recorded in the school ledger. "
        "It does not verify a bank transaction or online payment."
    )
    return _build_pdf(
        "Manual Fee Collection Acknowledgement", subtitle, table_rows,
        filename=f"fee-acknowledgement-{fee.student.admission_number}-{fee.pk}.pdf",
    )


@login_required
@require_http_methods(["GET", "POST"])
def platform_admin(request):
    if not request.user.is_superuser:
        raise PermissionDenied("Only the platform Super Admin can manage school onboarding.")
    form = SchoolOnboardingForm(request.POST or None, prefix="onboard")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update_subscription":
            school_id = request.POST.get("school_id")
            school = School.objects.filter(pk=school_id).first()
            if school is None or not hasattr(school, "subscription"):
                raise Http404("School subscription not found.")
            subscription_form = SubscriptionUpdateForm(request.POST, instance=school.subscription, prefix=f"sub-{school.pk}")
            if subscription_form.is_valid():
                subscription_form.save()
                messages.success(request, f"Subscription metadata updated for {school.name}.")
                return redirect("platform_admin")
        elif action == "onboard" and form.is_valid():
            school = form.save(created_by=request.user)
            messages.success(request, f"School '{school.name}' and its school-admin account were created.")
            return redirect("platform_admin")
    schools = School.objects.select_related("subscription").all()
    subscription_rows = []
    for school in schools:
        sub = getattr(school, "subscription", None)
        if sub:
            bound = request.method == "POST" and request.POST.get("action") == "update_subscription" and str(school.pk) == request.POST.get("school_id")
            sub_form = SubscriptionUpdateForm(request.POST if bound else None, instance=sub, prefix=f"sub-{school.pk}")
            subscription_rows.append({"school": school, "form": sub_form})
    return render(request, "schools/platform_admin.html", {
        "form": form, "schools": schools, "subscription_rows": subscription_rows,
        "school_count": schools.count(), "active_count": schools.filter(is_active=True).count(),
    })


@login_required
@require_http_methods(["GET", "POST"])
def staff_management(request):
    membership = get_membership(request)
    require_roles(membership, MANAGEMENT_ROLES)
    form = StaffAccountForm(request.POST or None, school=membership.school)
    link_form = ParentStudentLinkForm(request.POST or None, school=membership.school, prefix="link")
    student_link_form = StudentAccountLinkForm(request.POST or None, school=membership.school, prefix="student_link")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_staff":
            if form.is_valid():
                try:
                    user = form.save()
                except Exception as exc:
                    from django.db import IntegrityError
                    if isinstance(exc, IntegrityError):
                        form.add_error("username", "That username is already in use.")
                    else:
                        raise
                else:
                    messages.success(request, f"Account '{user.username}' created with school role.")
                    return redirect(f"{request.path}?school={membership.school_id}")
        elif action == "link_parent":
            if link_form.is_valid():
                link_form.save(school=membership.school)
                messages.success(request, "Parent and student profile linked.")
                return redirect(f"{request.path}?school={membership.school_id}")
        elif action == "link_student":
            if student_link_form.is_valid():
                student_link_form.save()
                messages.success(request, "Student portal account linked to the selected student profile.")
                return redirect(f"{request.path}?school={membership.school_id}")
        else:
            raise PermissionDenied("Unknown staff-management action.")
    staff_rows = Membership.objects.filter(school=membership.school).select_related("user").order_by("role", "user__username")
    parent_links = ParentStudentLink.objects.filter(student__school=membership.school).select_related("parent", "student", "student__classroom")
    return render(request, "schools/staff_management.html", {
        "membership": membership, "form": form, "link_form": link_form, "student_link_form": student_link_form,
        "staff_rows": staff_rows, "parent_links": parent_links,
    })



@login_required
@require_http_methods(["GET", "POST"])
def import_students_csv(request):
    """Import a validated CSV batch atomically; never partially import a bad file."""
    import csv
    import io
    from datetime import date
    from django.core.exceptions import ValidationError
    from django.db import IntegrityError

    membership = get_membership(request)
    require_roles(membership, MANAGEMENT_ROLES)
    error = ""
    imported_count = 0
    required_headers = {
        "admission_number", "first_name", "last_name", "class_name",
        "section", "academic_year", "date_of_birth", "admitted_at", "is_active",
    }
    if request.method == "POST":
        upload = request.FILES.get("csv_file")
        if not upload:
            error = "Choose a CSV file to import."
        elif upload.size > 1_000_000:
            error = "CSV file must be 1 MB or smaller."
        else:
            try:
                decoded = upload.read().decode("utf-8-sig")
                reader = csv.DictReader(io.StringIO(decoded, newline=""))
                headers = {h.strip() for h in (reader.fieldnames or []) if h}
                if not required_headers.issubset(headers):
                    error = "CSV headers are missing. Download the sample template and keep all required columns."
                else:
                    raw_rows = list(reader)
                    if not raw_rows:
                        error = "The CSV has no student rows."
                    elif len(raw_rows) > 500:
                        error = "Import is limited to 500 students per file."
                    else:
                        classes = {
                            (c.name.casefold(), c.section.casefold(), c.academic_year.casefold()): c
                            for c in ClassRoom.objects.filter(school=membership.school, is_active=True)
                        }
                        existing_numbers = set(
                            Student.objects.filter(school=membership.school)
                            .values_list("admission_number", flat=True)
                        )
                        seen_numbers = set()
                        prepared = []
                        for line_number, row in enumerate(raw_rows, start=2):
                            row = {str(k).strip(): (v or "").strip() for k, v in row.items() if k is not None}
                            admission_number = row.get("admission_number", "")
                            first_name = row.get("first_name", "")
                            if not admission_number or not first_name:
                                error = f"Row {line_number}: admission_number and first_name are required."
                                break
                            if len(admission_number) > 40 or len(first_name) > 100 or len(row.get("last_name", "")) > 100:
                                error = f"Row {line_number}: a name or admission number is too long."
                                break
                            key_number = admission_number.casefold()
                            if key_number in seen_numbers or admission_number in existing_numbers:
                                error = f"Row {line_number}: duplicate admission number '{admission_number}'. No rows were imported."
                                break
                            seen_numbers.add(key_number)
                            class_key = (row.get("class_name", "").casefold(), row.get("section", "").casefold(), row.get("academic_year", "").casefold())
                            classroom = classes.get(class_key)
                            if classroom is None:
                                error = f"Row {line_number}: class/section/year does not match an active class in this school."
                                break
                            parsed_dates = {}
                            for field in ("date_of_birth", "admitted_at"):
                                raw = row.get(field, "")
                                if raw:
                                    try:
                                        parsed_dates[field] = date.fromisoformat(raw)
                                    except ValueError:
                                        error = f"Row {line_number}: {field} must use YYYY-MM-DD or be blank."
                                        break
                                else:
                                    parsed_dates[field] = None
                            if error:
                                break
                            active_raw = row.get("is_active", "true").casefold()
                            if active_raw not in {"true", "false", "1", "0", "yes", "no"}:
                                error = f"Row {line_number}: is_active must be true/false, yes/no, 1/0, or blank."
                                break
                            prepared.append(Student(
                                school=membership.school, classroom=classroom,
                                admission_number=admission_number, first_name=first_name,
                                last_name=row.get("last_name", ""), date_of_birth=parsed_dates["date_of_birth"],
                                admitted_at=parsed_dates["admitted_at"],
                                is_active=active_raw not in {"false", "0", "no"},
                            ))
                        subscription = getattr(membership.school, "subscription", None)
                        current_count = Student.objects.filter(school=membership.school).count()
                        if not error and subscription and subscription.student_limit and current_count + len(prepared) > subscription.student_limit:
                            error = f"Import would exceed this school's plan limit of {subscription.student_limit} students."
                        if not error:
                            try:
                                with transaction.atomic():
                                    for student in prepared:
                                        student.full_clean()
                                    Student.objects.bulk_create(prepared, batch_size=100)
                            except (ValidationError, IntegrityError) as exc:
                                error = "Import was not completed because one or more rows failed validation. Check class names, admission numbers and required values."
                            else:
                                imported_count = len(prepared)
                                messages.success(request, f"Imported {imported_count} students successfully. No existing records were changed.")
                                return redirect(f"/students/?school={membership.school_id}")
            except (UnicodeDecodeError, csv.Error):
                error = "Could not read this file as a UTF-8 CSV. Save it as CSV UTF-8 and try again."
    return render(request, "schools/student_import.html", {
        "membership": membership, "error": error, "required_headers": sorted(required_headers),
    })


@login_required
@require_http_methods(["GET", "POST"])
def staff_attendance(request):
    """School-scoped staff attendance; only admins/principals may mark records."""
    from datetime import date
    from django.db import IntegrityError

    membership = get_membership(request)
    require_roles(membership, STAFF_ROLES)
    is_manager = membership.role in MANAGEMENT_ROLES
    raw_date = request.GET.get("date") or request.POST.get("date") or timezone.localdate().isoformat()
    try:
        selected_date = date.fromisoformat(raw_date)
    except ValueError:
        if request.method == "POST":
            return HttpResponse("Enter a valid attendance date in YYYY-MM-DD format.", status=400)
        selected_date = timezone.localdate()
        messages.error(request, "Enter a valid attendance date.")

    staff_memberships = membership.school.memberships.filter(
        is_active=True,
        role__in=[Membership.Role.SCHOOL_ADMIN, Membership.Role.PRINCIPAL, Membership.Role.TEACHER, Membership.Role.ACCOUNTANT],
    ).select_related("user").order_by("user__first_name", "user__last_name", "user__username")

    if request.method == "POST":
        if not is_manager:
            raise PermissionDenied("Only school admins and principals can mark staff attendance.")
        if request.POST.get("action") != "save_attendance":
            raise Http404("Unknown staff attendance action.")
        if len(staff_memberships) > 1000:
            return HttpResponse("Too many staff accounts for one bulk attendance submission.", status=400)
        try:
            with transaction.atomic():
                for staff_membership in staff_memberships:
                    staff_user = staff_membership.user
                    raw_status = request.POST.get(f"status_{staff_user.pk}", "").strip()
                    if raw_status not in StaffAttendance.Status.values:
                        continue
                    note = request.POST.get(f"note_{staff_user.pk}", "").strip()[:250]
                    record, created = StaffAttendance.objects.get_or_create(
                        school=membership.school, staff=staff_user, date=selected_date,
                        defaults={"status": raw_status, "note": note, "marked_by": request.user},
                    )
                    if not created:
                        record.status = raw_status
                        record.note = note
                        record.marked_by = request.user
                        record.full_clean()
                        record.save(update_fields=["status", "note", "marked_by", "updated_at"])
                    else:
                        record.full_clean()
                        record.save()
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        except IntegrityError:
            messages.error(request, "Attendance changed concurrently. Reload the page and try again.")
        else:
            messages.success(request, f"Staff attendance saved for {selected_date.isoformat()}.")
            return redirect(f"{request.path}?school={membership.school_id}&date={selected_date.isoformat()}")

    records = StaffAttendance.objects.filter(school=membership.school, date=selected_date).select_related("staff", "marked_by")
    if not is_manager:
        records = records.filter(staff=request.user)
    record_by_user = {record.staff_id: record for record in records}
    roster = []
    if is_manager:
        for staff_membership in staff_memberships:
            staff_user = staff_membership.user
            roster.append({"user": staff_user, "record": record_by_user.get(staff_user.pk)})
    else:
        roster = [{"user": request.user, "record": record_by_user.get(request.user.pk)}]
    month_start = selected_date.replace(day=1)
    month_records = StaffAttendance.objects.filter(
        school=membership.school, date__year=selected_date.year, date__month=selected_date.month,
    )
    if not is_manager:
        month_records = month_records.filter(staff=request.user)
    monthly_counts = {key: month_records.filter(status=key).count() for key, _ in StaffAttendance.Status.choices}
    return render(request, "schools/staff_attendance.html", {
        "membership": membership, "is_manager": is_manager, "selected_date": selected_date,
        "roster": roster, "status_choices": StaffAttendance.Status.choices,
        "monthly_counts": monthly_counts, "month_start": month_start,
    })

@login_required
@require_http_methods(["GET", "POST"])
def staff_leave(request):
    """Staff leave self-service; only school management can review requests."""
    from datetime import date

    membership = get_membership(request)
    require_roles(membership, STAFF_ROLES)
    is_manager = membership.role in MANAGEMENT_ROLES

    if request.method == "POST":
        action = request.POST.get("action", "request_leave")
        if action == "request_leave":
            try:
                start_date = date.fromisoformat(request.POST.get("start_date", "").strip())
                end_date = date.fromisoformat(request.POST.get("end_date", "").strip())
            except ValueError:
                messages.error(request, "Enter valid leave dates.")
            else:
                reason = request.POST.get("reason", "").strip()
                leave = StaffLeaveRequest(
                    school=membership.school, requester=request.user,
                    start_date=start_date, end_date=end_date, reason=reason,
                )
                try:
                    leave.full_clean()
                except ValidationError as exc:
                    for field_errors in exc.message_dict.values():
                        for error in field_errors:
                            messages.error(request, error)
                else:
                    if not reason:
                        messages.error(request, "Please enter a reason for leave.")
                    else:
                        leave.save()
                        messages.success(request, "Leave request submitted.")
                        return redirect(f"{request.path}?school={membership.school_id}")
        elif action == "review_leave":
            if not is_manager:
                raise PermissionDenied("Only school admins and principals can review leave requests.")
            request_id = request.POST.get("request_id", "").strip()
            decision = request.POST.get("decision", "").strip()
            leave = StaffLeaveRequest.objects.filter(pk=request_id, school=membership.school).first()
            if leave is None:
                raise Http404("Leave request not found in this school.")
            if leave.status != StaffLeaveRequest.Status.PENDING:
                messages.error(request, "Only pending leave requests can be reviewed.")
            elif decision not in {StaffLeaveRequest.Status.APPROVED, StaffLeaveRequest.Status.REJECTED}:
                messages.error(request, "Choose approve or reject.")
            else:
                leave.status = decision
                leave.review_note = request.POST.get("review_note", "").strip()[:500]
                leave.reviewed_by = request.user
                leave.reviewed_at = timezone.now()
                leave.full_clean()
                leave.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at", "updated_at"])
                messages.success(request, f"Leave request {leave.get_status_display().lower()}.")
                return redirect(f"{request.path}?school={membership.school_id}")
        else:
            raise Http404("Unknown leave action.")

    rows = StaffLeaveRequest.objects.filter(school=membership.school).select_related("requester", "reviewed_by")
    if not is_manager:
        rows = rows.filter(requester=request.user)
    return render(request, "schools/staff_leave.html", {
        "membership": membership, "is_manager": is_manager, "leave_requests": rows[:200],
    })
