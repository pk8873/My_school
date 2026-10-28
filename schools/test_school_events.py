from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from schools.models import Membership, School, SchoolEvent


User = get_user_model()


class SchoolEventsTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Calendar School", slug="calendar-school")
        self.other_school = School.objects.create(name="Other Calendar School", slug="other-calendar-school")
        self.admin = User.objects.create_user(username="calendar_admin", password="synthetic-test-pass-123")
        self.parent = User.objects.create_user(username="calendar_parent", password="synthetic-test-pass-123")
        self.student = User.objects.create_user(username="calendar_student", password="synthetic-test-pass-123")
        self.teacher = User.objects.create_user(username="calendar_teacher", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.parent, school=self.school, role=Membership.Role.PARENT)
        Membership.objects.create(user=self.student, school=self.school, role=Membership.Role.STUDENT)
        Membership.objects.create(user=self.teacher, school=self.school, role=Membership.Role.TEACHER)
        starts = timezone.now() + timedelta(days=3)
        self.parent_event = SchoolEvent.objects.create(
            school=self.school, title="Parent meeting", starts_at=starts,
            audience=SchoolEvent.Audience.PARENTS,
        )
        self.student_event = SchoolEvent.objects.create(
            school=self.school, title="Student sports day", starts_at=starts,
            audience=SchoolEvent.Audience.STUDENTS,
        )
        self.staff_event = SchoolEvent.objects.create(
            school=self.school, title="Staff training", starts_at=starts,
            audience=SchoolEvent.Audience.STAFF,
        )
        self.everyone_event = SchoolEvent.objects.create(
            school=self.school, title="Annual day", starts_at=starts,
            audience=SchoolEvent.Audience.EVERYONE,
        )
        SchoolEvent.objects.create(
            school=self.other_school, title="Other school's private event", starts_at=starts,
            audience=SchoolEvent.Audience.EVERYONE,
        )
        SchoolEvent.objects.create(
            school=self.school, title="Unpublished draft", starts_at=starts,
            audience=SchoolEvent.Audience.EVERYONE, is_published=False,
        )

    def test_parent_sees_only_parent_and_everyone_events_from_own_school(self):
        self.client.force_login(self.parent)
        response = self.client.get(f"/events/?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Parent meeting")
        self.assertContains(response, "Annual day")
        self.assertNotContains(response, "Student sports day")
        self.assertNotContains(response, "Staff training")
        self.assertNotContains(response, "Other school's private event")
        self.assertNotContains(response, "Unpublished draft")

    def test_student_and_staff_see_their_audience(self):
        self.client.force_login(self.student)
        response = self.client.get(f"/events/?school={self.school.pk}")
        self.assertContains(response, "Student sports day")
        self.assertNotContains(response, "Parent meeting")
        self.client.force_login(self.teacher)
        response = self.client.get(f"/events/?school={self.school.pk}")
        self.assertContains(response, "Staff training")
        self.assertNotContains(response, "Student sports day")

    def test_only_management_can_create_event(self):
        self.client.force_login(self.parent)
        response = self.client.post("/events/", {
            "school": self.school.pk, "title": "Parent created event",
            "starts_at": (timezone.now() + timedelta(days=4)).strftime("%Y-%m-%dT%H:%M"),
            "audience": "everyone",
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(SchoolEvent.objects.filter(title="Parent created event").exists())

    def test_admin_can_publish_event_and_invalid_time_order_is_rejected(self):
        self.client.force_login(self.admin)
        start = timezone.now() + timedelta(days=4)
        response = self.client.post("/events/", {
            "school": self.school.pk, "title": "Science exhibition",
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (start - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "audience": "students", "location": "Science lab",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SchoolEvent.objects.filter(title="Science exhibition").exists())
        response = self.client.post("/events/", {
            "school": self.school.pk, "title": "Science exhibition",
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "audience": "students", "location": "Science lab",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SchoolEvent.objects.filter(
            school=self.school, title="Science exhibition", audience="students"
        ).exists())


    def test_event_search_matches_title_description_and_location(self):
        self.parent_event.description = "Bring the student progress file"
        self.parent_event.location = "Main library"
        self.parent_event.save(update_fields=["description", "location"])
        self.client.force_login(self.parent)
        response = self.client.get(f"/events/?school={self.school.pk}&q=library")
        self.assertContains(response, "Parent meeting")
        self.assertNotContains(response, "Annual day")
        response = self.client.get(f"/events/?school={self.school.pk}&q=progress")
        self.assertContains(response, "Parent meeting")

    def test_event_date_filters_show_upcoming_past_and_all(self):
        past_event = SchoolEvent.objects.create(
            school=self.school, title="Past parent conference",
            starts_at=timezone.now() - timedelta(days=4),
            audience=SchoolEvent.Audience.PARENTS,
        )
        self.client.force_login(self.parent)
        upcoming = self.client.get(f"/events/?school={self.school.pk}&when=upcoming")
        self.assertContains(upcoming, "Parent meeting")
        self.assertNotContains(upcoming, "Past parent conference")
        past = self.client.get(f"/events/?school={self.school.pk}&when=past")
        self.assertContains(past, "Past parent conference")
        self.assertNotContains(past, "Parent meeting")
        all_events = self.client.get(f"/events/?school={self.school.pk}&when=all")
        self.assertContains(all_events, "Past parent conference")
        self.assertContains(all_events, "Parent meeting")

    def test_event_search_keeps_school_and_audience_boundaries(self):
        self.client.force_login(self.parent)
        response = self.client.get(f"/events/?school={self.school.pk}&q=event")
        self.assertNotContains(response, "Other school's private event")
        self.assertNotContains(response, "Staff training")
