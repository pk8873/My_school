from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from schools.models import Membership, School, StaffAttendance


User = get_user_model()


class StaffAttendanceTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Staff Attendance School", slug="staff-attendance-school")
        self.other_school = School.objects.create(name="Other Staff Attendance School", slug="other-staff-attendance-school")
        self.admin = User.objects.create_user(username="staff_attendance_admin", password="synthetic-test-pass-123")
        self.teacher = User.objects.create_user(username="staff_attendance_teacher", password="synthetic-test-pass-123")
        self.other_teacher = User.objects.create_user(username="other_staff_attendance_teacher", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.teacher, school=self.school, role=Membership.Role.TEACHER)
        Membership.objects.create(user=self.other_teacher, school=self.other_school, role=Membership.Role.TEACHER)
        self.day = timezone.localdate()

    def test_admin_can_mark_staff_and_monthly_summary_updates(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            f"/staff/attendance/?school={self.school.pk}",
            {
                "school": self.school.pk,
                "action": "save_attendance",
                "date": self.day.isoformat(),
                f"status_{self.teacher.pk}": StaffAttendance.Status.PRESENT,
                f"note_{self.teacher.pk}": "Checked in",
            },
        )
        self.assertEqual(response.status_code, 302)
        record = StaffAttendance.objects.get(school=self.school, staff=self.teacher, date=self.day)
        self.assertEqual(record.status, StaffAttendance.Status.PRESENT)
        self.assertEqual(record.note, "Checked in")
        self.assertEqual(record.marked_by, self.admin)
        page = self.client.get(f"/staff/attendance/?school={self.school.pk}&date={self.day.isoformat()}")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Monthly summary")
        self.assertContains(page, "Checked in")

    def test_staff_can_only_view_own_attendance_and_cannot_mark(self):
        StaffAttendance.objects.create(
            school=self.school, staff=self.teacher, date=self.day,
            status=StaffAttendance.Status.LATE, marked_by=self.admin,
        )
        self.client.force_login(self.teacher)
        page = self.client.get(f"/staff/attendance/?school={self.school.pk}&date={self.day.isoformat()}")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Late")
        self.assertNotContains(page, "Other Teacher")
        denied = self.client.post(
            f"/staff/attendance/?school={self.school.pk}",
            {"school": self.school.pk, "action": "save_attendance", "date": self.day.isoformat()},
        )
        self.assertEqual(denied.status_code, 403)

    def test_school_scope_and_invalid_date(self):
        self.client.force_login(self.admin)
        invalid = self.client.post(
            f"/staff/attendance/?school={self.school.pk}",
            {"school": self.school.pk, "action": "save_attendance", "date": "not-a-date"},
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(StaffAttendance.objects.filter(school=self.other_school).exists())
        self.assertEqual(
            StaffAttendance.objects.filter(school=self.school, staff=self.other_teacher).count(), 0
        )
