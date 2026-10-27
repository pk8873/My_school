from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from .models import Membership, ParentStudentLink, Student

def active_memberships(user):
    if not user.is_authenticated:
        return Membership.objects.none()
    return Membership.objects.filter(user=user, is_active=True, school__is_active=True).select_related("school")

def require_membership(user, school_id, allowed_roles=None):
    qs = active_memberships(user).filter(school_id=school_id)
    if allowed_roles:
        qs = qs.filter(role__in=allowed_roles)
    membership = qs.first()
    if membership is None:
        raise PermissionDenied("You do not have access to this school.")
    return membership

def students_for_membership(membership):
    """Only use with a membership validated for the current request."""
    return Student.objects.filter(school_id=membership.school_id)

def children_for_parent(user, school_id=None):
    links = ParentStudentLink.objects.filter(parent=user, is_active=True, student__is_active=True, student__school__is_active=True)
    if school_id is not None:
        links = links.filter(student__school_id=school_id)
    return Student.objects.filter(parent_links__in=links).distinct().select_related("school", "classroom")
