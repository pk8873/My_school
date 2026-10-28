from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from schools.models import AttendanceRecord, ClassRoom, Membership, School, Student


User = get_user_model()


class AttendanceReportPdfTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Attendance PDF School", slug="attendance-pdf-school")
        self.other_school = School.objects.create(name="Attendance PDF Other", slug="attendance-pdf-other")
        self.admin = User.objects.create_user(username="attendance_pdf_admin", password="synthetic-test-pass-123")
        self.accountant = User.objects.create_user(username="attendance_pdf_accountant", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.accountant, school=self.school, role=Membership.Role.ACCOUNTANT)
        self.classroom = ClassRoom.objects.create(school=self.school, name="Class 5", section="B", academic_year="2026-2027")
        other_class = ClassRoom.objects.create(school=self.other_school, name="Class 5", section="B", academic_year="2026-2027")
        student = Student.objects.create(school=self.school, classroom=self.classroom, admission_number="PDF-001", first_name="Asha")
        other_student = Student.objects.create(school=self.other_school, classroom=other_class, admission_number="PRIVATE-PDF", first_name="Private")
        AttendanceRecord.objects.create(school=self.school, student=student, date=date(2026, 10, 10), status=AttendanceRecord.Status.PRESENT)
        AttendanceRecord.objects.create(school=self.other_school, student=other_student, date=date(2026, 10, 10), status=AttendanceRecord.Status.PRESENT)

    def test_academic_staff_can_download_school_scoped_pdf(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            f"/attendance/report.pdf?school={self.school.pk}&date_from=2026-10-01&date_to=2026-10-31&classroom={self.classroom.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn('attachment; filename="attendance-report.pdf"', response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_invalid_filter_is_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/attendance/report.pdf?school={self.school.pk}&date_from=not-a-date")
        self.assertEqual(response.status_code, 400)

    def test_accountant_cannot_download_attendance_pdf(self):
        self.client.force_login(self.accountant)
        response = self.client.get(f"/attendance/report.pdf?school={self.school.pk}")
        self.assertEqual(response.status_code, 403)
