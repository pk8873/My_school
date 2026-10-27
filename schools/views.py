from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import F, Q, Sum
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from .forms import AttendanceRecordForm, ClassRoomForm, FeeRecordForm, StudentForm
from .models import AttendanceRecord, ClassRoom, FeeRecord, Membership, Student
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
        if request.user.is_staff or request.user.is_superuser:
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
        context["children"] = Student.objects.filter(parent_links__parent=request.user, parent_links__is_active=True, school=school, is_active=True).select_related("classroom").distinct()
    elif role == Membership.Role.STUDENT:
        context["student_profile_pending"] = True
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
        return redirect("classrooms")
    rows = ClassRoom.objects.filter(school=membership.school).select_related("class_teacher")
    return render(request, "schools/classrooms.html", {"membership": membership, "form": form, "classrooms": rows})


@login_required
@require_http_methods(["GET", "POST"])
def students(request):
    membership = get_membership(request)
    require_roles(membership, MANAGEMENT_ROLES)
    form = StudentForm(request.POST or None, school=membership.school)
    if request.method == "POST" and form.is_valid():
        student = form.save(commit=False)
        student.school = membership.school
        student.full_clean()
        student.save()
        messages.success(request, "Student admission saved.")
        return redirect("students")
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
        return redirect("attendance")
    selected_date = request.GET.get("date") or timezone.localdate().isoformat()
    rows = AttendanceRecord.objects.filter(school=membership.school, date=selected_date).select_related("student", "student__classroom")
    return render(request, "schools/attendance.html", {"membership": membership, "form": form, "records": rows, "selected_date": selected_date})


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
        return redirect("fees")
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

    from .forms import AnnouncementForm, ExamForm, ExamResultForm, HomeworkForm
    from .models import Announcement, Exam, ExamResult, Homework

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
            return redirect("academics")
    if role in {Membership.Role.PARENT, Membership.Role.STUDENT}:
        if role == Membership.Role.PARENT:
            child_ids = Student.objects.filter(parent_links__parent=request.user, parent_links__is_active=True, school=membership.school).values_list("id", flat=True)
            result_child_ids = Student.objects.filter(parent_links__parent=request.user, parent_links__is_active=True, parent_links__can_view_results=True, school=membership.school).values_list("id", flat=True)
        else:
            child_ids = Student.objects.none().values_list("id", flat=True)
            result_child_ids = child_ids
        results = ExamResult.objects.filter(school=membership.school, student_id__in=result_child_ids).select_related("exam", "student")
        homework_rows = Homework.objects.filter(school=membership.school, is_published=True).filter(Q(classroom__isnull=True) | Q(classroom__students__id__in=child_ids)).distinct()
        announcements = Announcement.objects.filter(school=membership.school, is_published=True, audience__in=["everyone", "parents" if role == Membership.Role.PARENT else "students"])
    else:
        results = ExamResult.objects.filter(school=membership.school).select_related("exam", "student")[:100]
        homework_rows = Homework.objects.filter(school=membership.school).select_related("classroom")[:100]
        announcements = Announcement.objects.filter(school=membership.school)[:100]
    exams = Exam.objects.filter(school=membership.school).select_related("classroom")[:100]
    return render(request, "schools/academics.html", {
        "membership": membership, "role": role, "can_manage": can_manage,
        "exam_form": exam_form, "result_form": result_form, "homework_form": homework_form,
        "announcement_form": announcement_form, "exams": exams, "results": results,
        "homework_items": homework_rows, "announcements": announcements,
    })
