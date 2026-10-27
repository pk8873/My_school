from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET
from .models import ClassRoom, Membership, ParentStudentLink, Student
from .tenant import active_memberships

@login_required
@require_GET
def dashboard(request):
    memberships = active_memberships(request.user)
    selected_id = request.GET.get("school")
    membership = memberships.filter(school_id=selected_id).first() if selected_id else memberships.first()
    if membership is None:
        if request.user.is_staff or request.user.is_superuser:
            return render(request, "schools/dashboard.html", {"platform_admin": True, "memberships": memberships})
        return render(request, "schools/dashboard.html", {"memberships": memberships, "no_school_access": True})
    school, role = membership.school, membership.role
    context = {"memberships": memberships, "membership": membership, "school": school, "role": role}
    if role in {Membership.Role.SCHOOL_ADMIN, Membership.Role.PRINCIPAL, Membership.Role.TEACHER, Membership.Role.ACCOUNTANT}:
        context["class_count"] = ClassRoom.objects.filter(school=school, is_active=True).count()
        context["student_count"] = Student.objects.filter(school=school, is_active=True).count()
        context["recent_students"] = Student.objects.filter(school=school, is_active=True).select_related("classroom")[:8]
    elif role == Membership.Role.PARENT:
        context["children"] = Student.objects.filter(parent_links__parent=request.user, parent_links__is_active=True, school=school, is_active=True).select_related("classroom").distinct()
    elif role == Membership.Role.STUDENT:
        context["student_profile_pending"] = True
    return render(request, "schools/dashboard.html", context)
