from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from schools.models import ClassRoom, Membership, School, Student, TransferCertificate


User = get_user_model()


class TransferCertificateRegisterTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Register School", slug="register-school", phone="1234567890")
        self.other_school = School.objects.create(name="Other Register School", slug="other-register-school")
        self.admin = User.objects.create_user(username="tc_register_admin", password="synthetic-test-pass-123")
        self.teacher = User.objects.create_user(username="tc_register_teacher", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.teacher, school=self.school, role=Membership.Role.TEACHER)
        self.classroom = ClassRoom.objects.create(school=self.school, name="Class 9", section="A", academic_year="2026-2027")
        self.other_classroom = ClassRoom.objects.create(school=self.other_school, name="Class 9", section="A", academic_year="2026-2027")
        self.student = Student.objects.create(
            school=self.school, classroom=self.classroom, admission_number="REG-TC-001",
            first_name="Riya", last_name="Singh", date_of_birth=date(2011, 3, 9),
        )
        self.foreign_student = Student.objects.create(
            school=self.other_school, classroom=self.other_classroom, admission_number="PRIVATE-REG-001",
            first_name="Private", last_name="Student",
        )

    def test_issue_creates_register_entry_and_pdf(self):
        self.client.force_login(self.admin)
        response = self.client.post("/students/transfer-certificates/", {
            "school": self.school.pk, "action": "issue", "student": self.student.pk,
            "issue_date": "2026-10-28", "leaving_date": "2026-10-20",
            "reason": "Family relocation", "conduct": "Good", "remarks": "Verified by office",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        record = TransferCertificate.objects.get(school=self.school, student=self.student)
        self.assertTrue(record.certificate_number.startswith("TC-2026-"))
        self.assertEqual(record.status, TransferCertificate.Status.ISSUED)
        self.assertEqual(record.issued_by, self.admin)

    def test_rejects_student_from_another_school(self):
        self.client.force_login(self.admin)
        response = self.client.post("/students/transfer-certificates/", {
            "school": self.school.pk, "action": "issue", "student": self.foreign_student.pk,
            "issue_date": "2026-10-28",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "select a student from this school")
        self.assertFalse(TransferCertificate.objects.filter(student=self.foreign_student).exists())

    def test_cancel_keeps_record_and_records_actor(self):
        record = TransferCertificate.objects.create(
            school=self.school, student=self.student, certificate_number="TC-TEST-0001",
            issue_date=date(2026, 10, 1), issued_by=self.admin,
        )
        self.client.force_login(self.admin)
        response = self.client.post("/students/transfer-certificates/", {
            "school": self.school.pk, "action": "cancel", "certificate_id": record.pk,
        })
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.status, TransferCertificate.Status.CANCELLED)
        self.assertEqual(record.cancelled_by, self.admin)
        self.assertIsNotNone(record.cancelled_at)

    def test_teacher_cannot_access_register(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/students/transfer-certificates/?school={self.school.pk}")
        self.assertEqual(response.status_code, 403)


class TransferCertificateRegisterCsvTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="CSV Register School", slug="csv-register-school")
        self.other_school = School.objects.create(name="Private CSV School", slug="private-csv-school")
        self.admin = User.objects.create_user(username="tc_csv_admin", password="synthetic-test-pass-123")
        self.teacher = User.objects.create_user(username="tc_csv_teacher", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.teacher, school=self.school, role=Membership.Role.TEACHER)
        self.classroom = ClassRoom.objects.create(school=self.school, name="Class 5", section="A", academic_year="2026-2027")
        self.other_classroom = ClassRoom.objects.create(school=self.other_school, name="Class 5", section="A", academic_year="2026-2027")
        self.student = Student.objects.create(
            school=self.school, classroom=self.classroom, admission_number="CSV-TC-001",
            first_name="Asha", last_name="Verma",
        )
        self.foreign_student = Student.objects.create(
            school=self.other_school, classroom=self.other_classroom, admission_number="PRIVATE-CSV-001",
            first_name="Private", last_name="Person",
        )
        TransferCertificate.objects.create(
            school=self.school, student=self.student, certificate_number="TC-2026-CSV001",
            issue_date=date(2026, 10, 1), reason="=HYPERLINK(\"https://bad.example\")",
        )
        TransferCertificate.objects.create(
            school=self.other_school, student=self.foreign_student, certificate_number="TC-PRIVATE-001",
            issue_date=date(2026, 10, 2),
        )
        self.cancelled = TransferCertificate.objects.create(
            school=self.school, student=self.student, certificate_number="TC-2026-CANCELLED",
            issue_date=date(2026, 10, 3), status=TransferCertificate.Status.CANCELLED,
        )

    def test_csv_is_school_scoped_and_formula_safe(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/students/transfer-certificates.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("private, no-store", response["Cache-Control"])
        self.assertIn("TC-2026-CSV001", response.content.decode("utf-8-sig"))
        self.assertNotIn("PRIVATE-CSV-001", response.content.decode("utf-8-sig"))
        self.assertIn("'=HYPERLINK", response.content.decode("utf-8-sig"))

    def test_status_filter_and_invalid_filter(self):
        self.client.force_login(self.admin)
        issued = self.client.get(f"/students/transfer-certificates.csv?school={self.school.pk}&status=issued")
        cancelled = self.client.get(f"/students/transfer-certificates.csv?school={self.school.pk}&status=cancelled")
        invalid = self.client.get(f"/students/transfer-certificates.csv?school={self.school.pk}&status=unknown")
        self.assertIn("TC-2026-CSV001", issued.content.decode("utf-8-sig"))
        self.assertNotIn("TC-2026-CANCELLED", issued.content.decode("utf-8-sig"))
        self.assertIn("TC-2026-CANCELLED", cancelled.content.decode("utf-8-sig"))
        self.assertEqual(invalid.status_code, 400)

    def test_teacher_cannot_export_register(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/students/transfer-certificates.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 403)
