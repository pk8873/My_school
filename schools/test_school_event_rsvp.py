from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from schools.models import Membership, School, SchoolEvent, SchoolEventRSVP


User = get_user_model()


class SchoolEventRSVPTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="RSVP School", slug="rsvp-school")
        self.other_school = School.objects.create(name="Other RSVP School", slug="other-rsvp-school")
        self.parent = User.objects.create_user(username="rsvp_parent", password="synthetic-test-pass-123")
        self.admin = User.objects.create_user(username="rsvp_admin", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.parent, school=self.school, role=Membership.Role.PARENT)
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        self.event = SchoolEvent.objects.create(
            school=self.school, title="Parent orientation",
            starts_at=timezone.now() + timedelta(days=2),
            audience=SchoolEvent.Audience.PARENTS,
        )
        self.staff_event = SchoolEvent.objects.create(
            school=self.school, title="Staff planning",
            starts_at=timezone.now() + timedelta(days=2),
            audience=SchoolEvent.Audience.STAFF,
        )
        self.foreign_event = SchoolEvent.objects.create(
            school=self.other_school, title="Foreign event",
            starts_at=timezone.now() + timedelta(days=2),
            audience=SchoolEvent.Audience.EVERYONE,
        )

    def test_parent_can_rsvp_to_visible_event_and_change_response(self):
        self.client.force_login(self.parent)
        response = self.client.post("/events/", {
            "school": self.school.pk, "action": "rsvp",
            "event_id": self.event.pk, "response": "attending",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SchoolEventRSVP.objects.get(event=self.event, user=self.parent).response, "attending")
        self.client.post("/events/", {
            "school": self.school.pk, "action": "rsvp",
            "event_id": self.event.pk, "response": "not_attending",
        })
        self.assertEqual(SchoolEventRSVP.objects.filter(event=self.event, user=self.parent).count(), 1)
        self.assertEqual(SchoolEventRSVP.objects.get(event=self.event, user=self.parent).response, "not_attending")

    def test_parent_cannot_rsvp_to_staff_or_other_school_event(self):
        self.client.force_login(self.parent)
        for event in [self.staff_event, self.foreign_event]:
            response = self.client.post("/events/", {
                "school": self.school.pk, "action": "rsvp",
                "event_id": event.pk, "response": "attending",
            })
            self.assertEqual(response.status_code, 403)
        self.assertEqual(SchoolEventRSVP.objects.filter(user=self.parent).count(), 0)

    def test_management_sees_response_counts(self):
        SchoolEventRSVP.objects.create(event=self.event, user=self.parent, response="attending")
        self.client.force_login(self.admin)
        response = self.client.get(f"/events/?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 attending")


    def test_management_can_download_event_rsvp_csv(self):
        SchoolEventRSVP.objects.create(event=self.event, user=self.parent, response="attending")
        self.client.force_login(self.admin)
        response = self.client.get(f"/events/{self.event.pk}/rsvps.csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn(b"Parent orientation", response.content)
        self.assertIn(b"rsvp_parent", response.content)
        self.assertIn(b"Attending", response.content)

    def test_parent_cannot_download_rsvp_csv(self):
        self.client.force_login(self.parent)
        response = self.client.get(f"/events/{self.event.pk}/rsvps.csv")
        self.assertEqual(response.status_code, 403)

    def test_management_cannot_download_other_school_event_rsvp_csv(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/events/{self.foreign_event.pk}/rsvps.csv")
        self.assertEqual(response.status_code, 404)
