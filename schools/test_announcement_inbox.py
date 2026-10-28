from django.contrib.auth import get_user_model
from django.test import TestCase

from schools.models import Announcement, AnnouncementRead, Membership, School


User = get_user_model()


class AnnouncementInboxTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Inbox School", slug="inbox-school")
        self.other_school = School.objects.create(name="Other Inbox School", slug="other-inbox-school")
        self.parent = User.objects.create_user(username="inbox_parent", password="synthetic-test-pass-123")
        self.teacher = User.objects.create_user(username="inbox_teacher", password="synthetic-test-pass-123")
        self.admin = User.objects.create_user(username="inbox_admin", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.parent, school=self.school, role=Membership.Role.PARENT)
        Membership.objects.create(user=self.teacher, school=self.school, role=Membership.Role.TEACHER)
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        self.parents_announcement = Announcement.objects.create(
            school=self.school, title="Parent meeting", body="Meeting at 10 AM.",
            audience=Announcement.Audience.PARENTS, is_published=True,
        )
        self.staff_announcement = Announcement.objects.create(
            school=self.school, title="Staff meeting", body="Staff only.",
            audience=Announcement.Audience.STAFF, is_published=True,
        )
        self.student_announcement = Announcement.objects.create(
            school=self.school, title="Student event", body="Students only.",
            audience=Announcement.Audience.STUDENTS, is_published=True,
        )
        self.unpublished = Announcement.objects.create(
            school=self.school, title="Draft announcement", body="Not public.",
            audience=Announcement.Audience.EVERYONE, is_published=False,
        )
        self.foreign_announcement = Announcement.objects.create(
            school=self.other_school, title="Foreign school", body="Private school message.",
            audience=Announcement.Audience.EVERYONE, is_published=True,
        )

    def test_parent_only_sees_parent_and_everyone_published_announcements(self):
        self.client.force_login(self.parent)
        response = self.client.get(f"/announcements/inbox/?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Parent meeting")
        self.assertNotContains(response, "Staff meeting")
        self.assertNotContains(response, "Student event")
        self.assertNotContains(response, "Draft announcement")
        self.assertNotContains(response, "Foreign school")

    def test_staff_sees_staff_audience_and_mark_read_is_saved(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/announcements/inbox/?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Staff meeting")
        self.client.post("/announcements/inbox/", {
            "school": self.school.pk, "announcement_id": self.staff_announcement.pk,
        })
        self.assertTrue(AnnouncementRead.objects.filter(
            user=self.teacher, announcement=self.staff_announcement
        ).exists())

    def test_parent_cannot_mark_staff_only_announcement_read(self):
        self.client.force_login(self.parent)
        response = self.client.post("/announcements/inbox/", {
            "school": self.school.pk, "announcement_id": self.staff_announcement.pk,
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(AnnouncementRead.objects.filter(
            user=self.parent, announcement=self.staff_announcement
        ).exists())

    def test_read_receipt_is_unique_per_user_and_announcement(self):
        self.client.force_login(self.parent)
        self.client.post("/announcements/inbox/", {
            "school": self.school.pk, "announcement_id": self.parents_announcement.pk,
        })
        self.client.post("/announcements/inbox/", {
            "school": self.school.pk, "announcement_id": self.parents_announcement.pk,
        })
        self.assertEqual(AnnouncementRead.objects.filter(
            user=self.parent, announcement=self.parents_announcement
        ).count(), 1)
