from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from schools.models import Membership, School, StaffLeaveRequest


User = get_user_model()


class StaffLeaveTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Leave School", slug="leave-school")
        self.other_school = School.objects.create(name="Other Leave School", slug="other-leave-school")
        self.admin = User.objects.create_user(username="leave_admin", password="synthetic-test-pass-123")
        self.teacher = User.objects.create_user(username="leave_teacher", password="synthetic-test-pass-123")
        self.other_admin = User.objects.create_user(username="other_leave_admin", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.teacher, school=self.school, role=Membership.Role.TEACHER)
        Membership.objects.create(user=self.other_admin, school=self.other_school, role=Membership.Role.SCHOOL_ADMIN)

    def test_staff_can_submit_request_and_only_see_own_requests(self):
        self.client.force_login(self.teacher)
        start = (timezone.localdate() + timedelta(days=3)).isoformat()
        end = (timezone.localdate() + timedelta(days=4)).isoformat()
        response = self.client.post(f"/staff/leave/?school={self.school.pk}", {
            "school": self.school.pk, "action": "request_leave",
            "start_date": start, "end_date": end, "reason": "Family commitment",
        })
        self.assertEqual(response.status_code, 302)
        leave = StaffLeaveRequest.objects.get(school=self.school, requester=self.teacher)
        self.assertEqual(leave.status, StaffLeaveRequest.Status.PENDING)
        page = self.client.get(f"/staff/leave/?school={self.school.pk}")
        self.assertContains(page, "Family commitment")
        self.assertNotContains(page, "leave_admin")

    def test_management_can_approve_but_other_school_cannot_access_request(self):
        leave = StaffLeaveRequest.objects.create(
            school=self.school, requester=self.teacher,
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=1), reason="Appointment",
        )
        self.client.force_login(self.admin)
        response = self.client.post(f"/staff/leave/?school={self.school.pk}", {
            "school": self.school.pk, "action": "review_leave",
            "request_id": leave.pk, "decision": "approved", "review_note": "Approved",
        })
        self.assertEqual(response.status_code, 302)
        leave.refresh_from_db()
        self.assertEqual(leave.status, StaffLeaveRequest.Status.APPROVED)
        self.assertEqual(leave.reviewed_by, self.admin)
        self.client.force_login(self.other_admin)
        denied = self.client.post(f"/staff/leave/?school={self.other_school.pk}", {
            "school": self.other_school.pk, "action": "review_leave",
            "request_id": leave.pk, "decision": "rejected",
        })
        self.assertEqual(denied.status_code, 404)

    def test_invalid_date_range_is_rejected(self):
        leave = StaffLeaveRequest(
            school=self.school, requester=self.teacher,
            start_date=date.today() + timedelta(days=2),
            end_date=date.today() + timedelta(days=1), reason="Invalid range",
        )
        with self.assertRaises(ValidationError):
            leave.full_clean()

    def test_teacher_cannot_review_leave(self):
        leave = StaffLeaveRequest.objects.create(
            school=self.school, requester=self.teacher,
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=1), reason="Appointment",
        )
        self.client.force_login(self.teacher)
        response = self.client.post(f"/staff/leave/?school={self.school.pk}", {
            "school": self.school.pk, "action": "review_leave",
            "request_id": leave.pk, "decision": "approved",
        })
        self.assertEqual(response.status_code, 403)
