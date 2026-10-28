from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase

from schools.models import AttendanceRecord, ClassRoom, Membership, School, Student


User = get_user_model()


class AttendanceCsvRangeExportTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Attendance CSV Synthetic", slug="attendance-csv-synthetic")
        self.other_school = School.objects.create(name="Attendance CSV Other", slug="attendance-csv-other")
        self.admin = User.objects.create_user(username="attendance_csv_admin", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        self.classroom = ClassRoom.objects.create(school=self.school, name="Class 4", section="A", academic_year="2026-2027")
        self.other_class = ClassRoom.objects.create(school=self.other_school, name="Class 4", section="A", academic_year="2026-2027")
        self.student = Student.objects.create(school=self.school, classroom=self.classroom, admission_number="ATT-001", first_name="Range", last_name="Student")
        other_student = Student.objects.create(school=self.other_school, classroom=self.other_class, admission_number="PRIVATE-999", first_name="Private", last_name="Student")
        self._record(self.student, date(2026, 10, 10), AttendanceRecord.Status.PRESENT, "normal")
        self._record(self.student, date(2026, 10, 15), AttendanceRecord.Status.ABSENT, "test note")
        self._record(other_student, date(2026, 10, 12), AttendanceRecord.Status.PRESENT, "other tenant")

    def _record(self, student, day, status, note):
        AttendanceRecord.objects.create(school=student.school, student=student, date=day, status=status, note=note)

    def test_date_range_export_only_includes_matching_school_and_dates(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/reports/attendance.csv?school={self.school.pk}&date_from=2026-10-11&date_to=2026-10-16")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8-sig")
        self.assertIn("ATT-001", body)
        self.assertIn("test note", body)
        self.assertNotIn("normal", body)
        self.assertNotIn("PRIVATE-999", body)

    def test_class_filter_and_single_day_filter_can_be_used(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/reports/attendance.csv?school={self.school.pk}&date=2026-10-10&classroom={self.classroom.pk}")
        body = response.content.decode("utf-8-sig")
        self.assertEqual(response.status_code, 200)
        self.assertIn("ATT-001", body)
        self.assertNotIn("PRIVATE-999", body)

    def test_invalid_or_reversed_date_range_returns_bad_request(self):
        self.client.force_login(self.admin)
        invalid = self.client.get(f"/reports/attendance.csv?school={self.school.pk}&date_from=bad")
        reversed_range = self.client.get(f"/reports/attendance.csv?school={self.school.pk}&date_from=2026-10-20&date_to=2026-10-01")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(reversed_range.status_code, 400)

    def test_non_academic_role_cannot_export_attendance(self):
        from schools.models import Membership
        accountant = User.objects.create_user(username="attendance_csv_accountant", password="synthetic-test-pass-123")
        Membership.objects.create(user=accountant, school=self.school, role=Membership.Role.ACCOUNTANT)
        self.client.force_login(accountant)
        response = self.client.get(f"/reports/attendance.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 403)
