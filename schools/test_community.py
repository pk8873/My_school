from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Announcement, AnnouncementRead, Membership, School


User = get_user_model()


class CommunityFeedTests(TestCase):
    def setUp(self):
        self.alpha = School.objects.create(name="Alpha Synthetic School", slug="community-alpha")
        self.beta = School.objects.create(name="Beta Synthetic School", slug="community-beta")
        self.admin = User.objects.create_user(username="community_admin", password="Synthetic-test-123")
        self.other_admin = User.objects.create_user(username="other_community_admin", password="Synthetic-test-123")
        Membership.objects.create(user=self.admin, school=self.alpha, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.other_admin, school=self.beta, role=Membership.Role.SCHOOL_ADMIN)

    def test_feed_is_school_scoped(self):
        Announcement.objects.create(school=self.alpha, title="Alpha notice", body="Only Alpha", audience="everyone")
        Announcement.objects.create(school=self.beta, title="Beta secret", body="Only Beta", audience="everyone")
        self.client.force_login(self.admin)
        response = self.client.get("/community/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha notice")
        self.assertNotContains(response, "Beta secret")

    def test_parent_sees_only_permitted_audiences(self):
        parent = User.objects.create_user(username="community_parent", password="Synthetic-test-123")
        Membership.objects.create(user=parent, school=self.alpha, role=Membership.Role.PARENT)
        Announcement.objects.create(school=self.alpha, title="For parents", body="Parent message", audience="parents")
        Announcement.objects.create(school=self.alpha, title="For students", body="Student message", audience="students")
        self.client.force_login(parent)
        response = self.client.get("/community/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "For parents")
        self.assertNotContains(response, "For students")

    def test_management_can_save_draft_and_draft_is_not_public_to_parent(self):
        self.client.force_login(self.admin)
        response = self.client.post("/community/", {
            "school": str(self.alpha.pk), "action": "create_announcement", "title": "Internal draft",
            "body": "Draft text", "audience": "parents", "status": "draft",
        })
        self.assertEqual(response.status_code, 302)
        draft = Announcement.objects.get(school=self.alpha, title="Internal draft")
        self.assertFalse(draft.is_published)
        self.assertEqual(draft.created_by, self.admin)
        self.assertContains(self.client.get(f"/community/?school={self.alpha.pk}&show_drafts=1"), "Internal draft")
        parent = User.objects.create_user(username="draft_parent", password="Synthetic-test-123")
        Membership.objects.create(user=parent, school=self.alpha, role=Membership.Role.PARENT)
        self.client.force_login(parent)
        self.assertNotContains(self.client.get("/community/"), "Internal draft")

    def test_teacher_cannot_create_notice(self):
        teacher = User.objects.create_user(username="community_teacher", password="Synthetic-test-123")
        Membership.objects.create(user=teacher, school=self.alpha, role=Membership.Role.TEACHER)
        self.client.force_login(teacher)
        response = self.client.post("/community/", {
            "school": str(self.alpha.pk), "action": "create_announcement", "title": "Unauthorized",
            "body": "Should not be created", "audience": "everyone", "status": "published",
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Announcement.objects.filter(title="Unauthorized").exists())

    def test_feed_search_and_pagination(self):
        for number in range(12):
            Announcement.objects.create(school=self.alpha, title=f"Notice {number:02d}", body="Searchable update", audience="everyone")
        self.client.force_login(self.admin)
        response = self.client.get("/community/?q=Searchable")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["announcements"]), 10)
        self.assertTrue(response.context["page_obj"].has_next())

    def test_cannot_mark_foreign_school_notice_read(self):
        foreign = Announcement.objects.create(school=self.beta, title="Foreign", body="Private", audience="everyone")
        self.client.force_login(self.admin)
        response = self.client.post("/community/", {"action": "mark_read", "announcement_id": str(foreign.pk)})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(AnnouncementRead.objects.filter(announcement=foreign, user=self.admin).exists())
