from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import F, Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from .forms import AttendanceRecordForm, ClassRoomForm, FeeRecordForm, StudentForm, SchoolOnboardingForm, StaffAccountForm, ParentStudentLinkForm, StudentAccountLinkForm, SubscriptionUpdateForm
from .models import AttendanceRecord, ClassRoom, FeeRecord, Membership, Student, School, SchoolSubscription, ParentStudentLink
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
    return render(request, "schools/students.html", {"membership": membership, "form": form, "students": rows[:200], "query": query})


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
    return render(request, "schools/attendance.html", {"membership": membership, "form": form, "records": rows, "selected_date": selected_date})


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
        form = BulkAttendanceSelectionForm(request.GET or None, school=membership.school, initial=initial)

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
            messages.error(request, "Choose a valid attendance status for every student.")
        else:
            with transaction.atomic():
                for student in students:
                    status = request.POST[f"status_{student.pk}"]
                    note = request.POST.get(f"note_{student.pk}", "").strip()[:250]
                    AttendanceRecord.objects.update_or_create(
                        school=membership.school, student=student, date=form.cleaned_data["date"],
                        defaults={"status": status, "note": note, "marked_by": request.user},
                    )
            messages.success(request, f"Attendance saved for {students.count()} students on {selected_date}.")
            return redirect(f"/attendance/bulk/?school={membership.school_id}&classroom={classroom.pk}&date={selected_date}")
    elif request.method == "GET" and form.is_valid():
        classroom = form.cleaned_data["classroom"]
        selected_date = form.cleaned_data["date"].isoformat()
        students = Student.objects.filter(
            school=membership.school, classroom=classroom, is_active=True
        ).order_by("first_name", "last_name")
    else:
        form = BulkAttendanceSelectionForm(
            school=membership.school,
            initial={"date": selected_date, "classroom": request.GET.get("classroom") or None},
        )

    if students.exists():
        existing = {
            row.student_id: row
            for row in AttendanceRecord.objects.filter(
                school=membership.school, student__in=students, date=selected_date
            )
        }
    return render(request, "schools/attendance_bulk.html", {
        "membership": membership, "form": form, "students": students,
        "existing": existing, "selected_date": selected_date,
        "status_choices": AttendanceRecord.Status.choices,
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
    rows = FeeRecord.objects.filter(school=membership.school).select_related("student", "student__classroom")
    totals = rows.aggregate(total=Sum("amount"), collected=Sum("paid_amount"))
    return render(request, "schools/fees.html", {"membership": membership, "form": form, "fees": rows[:200], "total_amount": totals["total"] or 0, "collected_amount": totals["collected"] or 0})



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
    if report == "students":
        require_roles(membership, MANAGEMENT_ROLES)
        rows = Student.objects.filter(school=membership.school).select_related("classroom")
        filename = "students.csv"
        headers = ["Admission number", "First name", "Last name", "Class", "Section", "Active", "Admission date"]
        values = ((s.admission_number, s.first_name, s.last_name, s.classroom.name, s.classroom.section, s.is_active, s.admitted_at or "") for s in rows)
    elif report == "attendance":
        require_roles(membership, ACADEMIC_ROLES)
        rows = AttendanceRecord.objects.filter(school=membership.school).select_related("student", "student__classroom")
        date_filter = request.GET.get("date")
        if date_filter:
            rows = rows.filter(date=date_filter)
        filename = "attendance.csv"
        headers = ["Date", "Admission number", "Student", "Class", "Status", "Note"]
        values = ((r.date, r.student.admission_number, str(r.student), r.student.classroom.name, r.get_status_display(), r.note) for r in rows)
    elif report == "fees":
        require_roles(membership, FEE_ROLES)
        rows = FeeRecord.objects.filter(school=membership.school).select_related("student")
        filename = "fee-ledger.csv"
        headers = ["Admission number", "Student", "Fee head", "Amount", "Paid", "Balance", "Due date", "Status", "Reference"]
        values = ((r.student.admission_number, str(r.student), r.title, r.amount, r.paid_amount, r.balance, r.due_date or "", r.get_status_display(), r.payment_reference) for r in rows)
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
