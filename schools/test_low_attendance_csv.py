from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from schools.models import AttendanceRecord, ClassRoom, Membership, School, Student


User = get_user_model()


class LowAttendanceCsvTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Low Attendance School", slug="low-attendance-school")
        self.other_school = School.objects.create(name="Other Low Attendance", slug="other-low-attendance")
        self.admin = User.objects.create_user(username="low_attendance_admin", password="synthetic-test-pass-123")
        self.accountant = User.objects.create_user(username="low_attendance_accountant", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.accountant, school=self.school, role=Membership.Role.ACCOUNTANT)
        self.classroom = ClassRoom.objects.create(school=self.school, name="Class 7", section="A", academic_year="2026-2027")
        other_classroom = ClassRoom.objects.create(school=self.other_school, name="Class 7", section="A", academic_year="2026-2027")
        self.student = Student.objects.create(school=self.school, classroom=self.classroom, admission_number="LOW-001", first_name="Ravi", last_name="Kumar")
        other_student = Student.objects.create(school=self.other_school, classroom=other_classroom, admission_number="PRIVATE-LOW", first_name="Private", last_name="Student")
        start = date(2026, 10, 1)
        for offset, status in enumerate((
            AttendanceRecord.Status.PRESENT,
            AttendanceRecord.Status.ABSENT,
            AttendanceRecord.Status.LATE,
            AttendanceRecord.Status.ABSENT,
        )):
            AttendanceRecord.objects.create(
                school=self.school, student=self.student, date=start + timedelta(days=offset), status=status,
            )
        AttendanceRecord.objects.create(
            school=self.other_school, student=other_student, date=start, status=AttendanceRecord.Status.ABSENT,
        )

    def test_report_includes_only_students_below_threshold_with_enough_marked_days(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            f"/reports/low-attendance.csv?school={self.school.pk}&threshold=75&min_days=4"
            "&date_from=2026-10-01&date_to=2026-10-04&classroom="
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment; filename="low-attendance.csv"', response["Content-Disposition"])
        body = response.content.decode("utf-8-sig")
        self.assertIn("LOW-001", body)
        self.assertIn("50.00,75", body)
        self.assertNotIn("PRIVATE-LOW", body)

    def test_threshold_and_minimum_days_are_validated(self):
        self.client.force_login(self.admin)
        bad_threshold = self.client.get(f"/reports/low-attendance.csv?school={self.school.pk}&threshold=101")
        bad_days = self.client.get(f"/reports/low-attendance.csv?school={self.school.pk}&min_days=0")
        self.assertEqual(bad_threshold.status_code, 400)
        self.assertEqual(bad_days.status_code, 400)

    def test_accountant_cannot_export_low_attendance_report(self):
        self.client.force_login(self.accountant)
        response = self.client.get(f"/reports/low-attendance.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 403)
