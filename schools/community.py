from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .models import Announcement, AnnouncementRead, Membership
from .tenant import active_memberships


STAFF_ROLES = {
    Membership.Role.SCHOOL_ADMIN,
    Membership.Role.PRINCIPAL,
    Membership.Role.TEACHER,
    Membership.Role.ACCOUNTANT,
}
MANAGEMENT_ROLES = {Membership.Role.SCHOOL_ADMIN, Membership.Role.PRINCIPAL}


@login_required
@require_http_methods(["GET", "POST"])
def community_feed(request):
    """School-scoped communication feed reusing announcements and read receipts."""
    memberships = active_memberships(request.user).select_related("school")
    selected_id = request.GET.get("school") or request.POST.get("school")
    membership = memberships.filter(school_id=selected_id).first() if selected_id else memberships.first()
    if membership is None:
        raise Http404("No active school membership found.")

    role = membership.role
    if role not in STAFF_ROLES and role not in {Membership.Role.PARENT, Membership.Role.STUDENT}:
        raise PermissionDenied("Your role cannot access the school community.")

    management = role in MANAGEMENT_ROLES
    if management:
        allowed_audiences = [choice[0] for choice in Announcement.Audience.choices]
    elif role == Membership.Role.PARENT:
        allowed_audiences = ["everyone", "parents"]
    elif role == Membership.Role.STUDENT:
        allowed_audiences = ["everyone", "students"]
    else:
        allowed_audiences = ["everyone", "staff"]

    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        if action == "mark_read":
            announcement_id = request.POST.get("announcement_id", "").strip()
            available = Announcement.objects.filter(
                school=membership.school,
                is_published=True,
                audience__in=allowed_audiences,
            )
            item = available.filter(pk=announcement_id).first() if announcement_id.isdigit() else None
            if item is None:
                raise Http404("Announcement not found.")
            AnnouncementRead.objects.get_or_create(announcement=item, user=request.user)
            messages.success(request, "Notice marked as read. / सूचना पढ़ी हुई चिह्नित की गई।")
            return redirect(f"{request.path}?school={membership.school_id}")

        if action != "create_announcement" or not management:
            raise PermissionDenied("Only school admins and principals can publish school notices.")

        title = request.POST.get("title", "").strip()
        body = request.POST.get("body", "").strip()
        audience = request.POST.get("audience", Announcement.Audience.EVERYONE).strip()
        status = request.POST.get("status", "published").strip()
        errors = []
        if not title or len(title) > 160:
            errors.append("Title is required and must be 160 characters or fewer.")
        if not body or len(body) > 20000:
            errors.append("Notice text is required and must be 20,000 characters or fewer.")
        if audience not in Announcement.Audience.values:
            errors.append("Choose a valid audience.")
        if status not in {"draft", "published"}:
            errors.append("Choose draft or publish.")
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect(f"{request.path}?school={membership.school_id}")

        Announcement.objects.create(
            school=membership.school,
            title=title,
            body=body,
            audience=audience,
            is_published=(status == "published"),
            created_by=request.user,
        )
        messages.success(
            request,
            "Notice published. / सूचना प्रकाशित हुई।"
            if status == "published"
            else "Draft saved. / ड्राफ्ट सहेजा गया।",
        )
        suffix = "&show_drafts=1" if status == "draft" else ""
        return redirect(f"{request.path}?school={membership.school_id}{suffix}")

    search_query = request.GET.get("q", "").strip()[:100]
    show_drafts = management and request.GET.get("show_drafts") == "1"
    announcements = Announcement.objects.filter(
        school=membership.school,
        audience__in=allowed_audiences,
    )
    if not show_drafts:
        announcements = announcements.filter(is_published=True)
    if search_query:
        announcements = announcements.filter(
            Q(title__icontains=search_query) | Q(body__icontains=search_query)
        )
    announcements = announcements.select_related("created_by").order_by("-published_at", "-pk")
    page_obj = Paginator(announcements, 10).get_page(request.GET.get("page"))
    page_ids = [item.pk for item in page_obj.object_list]
    read_ids = set(
        AnnouncementRead.objects.filter(
            user=request.user, announcement_id__in=page_ids
        ).values_list("announcement_id", flat=True)
    )
    return render(request, "schools/community_feed.html", {
        "membership": membership,
        "role": role,
        "can_manage": management,
        "announcements": page_obj,
        "page_obj": page_obj,
        "read_ids": read_ids,
        "search_query": search_query,
        "show_drafts": show_drafts,
        "audience_choices": Announcement.Audience.choices,
    })
