from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from schools.models import AttendanceRecord, ClassRoom, Membership, School, Student


User = get_user_model()


class AttendanceSummaryCsvTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Attendance Summary School", slug="attendance-summary-school")
        self.other_school = School.objects.create(name="Other Attendance Summary", slug="other-attendance-summary")
        self.admin = User.objects.create_user(username="attendance_summary_admin", password="synthetic-test-pass-123")
        self.accountant = User.objects.create_user(username="attendance_summary_accountant", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.accountant, school=self.school, role=Membership.Role.ACCOUNTANT)
        self.classroom = ClassRoom.objects.create(school=self.school, name="Class 6", section="A", academic_year="2026-2027")
        other_classroom = ClassRoom.objects.create(school=self.other_school, name="Class 6", section="A", academic_year="2026-2027")
        self.student = Student.objects.create(school=self.school, classroom=self.classroom, admission_number="SUM-001", first_name="Neha", last_name="Sharma")
        other_student = Student.objects.create(school=self.other_school, classroom=other_classroom, admission_number="PRIVATE-SUM", first_name="Private", last_name="Student")
        self._record(self.student, date(2026, 10, 1), AttendanceRecord.Status.PRESENT)
        self._record(self.student, date(2026, 10, 2), AttendanceRecord.Status.LATE)
        self._record(self.student, date(2026, 10, 3), AttendanceRecord.Status.ABSENT)
        self._record(self.student, date(2026, 10, 4), AttendanceRecord.Status.LEAVE)
        self._record(other_student, date(2026, 10, 1), AttendanceRecord.Status.PRESENT)

    def _record(self, student, day, status):
        AttendanceRecord.objects.create(school=student.school, student=student, date=day, status=status)

    def test_summary_contains_status_counts_and_attendance_percentage(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/reports/attendance-summary.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment; filename="attendance-summary.csv"', response["Content-Disposition"])
        body = response.content.decode("utf-8-sig")
        self.assertIn("SUM-001", body)
        self.assertIn("4,1,1,1,1,50.00", body)
        self.assertNotIn("PRIVATE-SUM", body)

    def test_date_range_and_class_filter(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            f"/reports/attendance-summary.csv?school={self.school.pk}&classroom={self.classroom.pk}"
            "&date_from=2026-10-01&date_to=2026-10-02"
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8-sig")
        self.assertIn("2,1,0,1,0,100.00", body)

    def test_invalid_class_or_reversed_date_range_is_rejected(self):
        self.client.force_login(self.admin)
        invalid = self.client.get(f"/reports/attendance-summary.csv?school={self.school.pk}&classroom=abc")
        reversed_range = self.client.get(
            f"/reports/attendance-summary.csv?school={self.school.pk}&date_from=2026-10-10&date_to=2026-10-01"
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(reversed_range.status_code, 400)

    def test_accountant_cannot_export_attendance_summary(self):
        self.client.force_login(self.accountant)
        response = self.client.get(f"/reports/attendance-summary.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 403)
