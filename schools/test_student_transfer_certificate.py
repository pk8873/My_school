from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from schools.models import ClassRoom, Membership, School, Student


User = get_user_model()


class StudentTransferCertificateDraftTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="TC Draft School", slug="tc-draft-school",
            phone="1234567890", address="Main Road, Test Town",
        )
        self.other_school = School.objects.create(name="Other TC School", slug="other-tc-school")
        self.admin = User.objects.create_user(username="tc_admin", password="synthetic-test-pass-123")
        self.teacher = User.objects.create_user(username="tc_teacher", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.teacher, school=self.school, role=Membership.Role.TEACHER)
        self.classroom = ClassRoom.objects.create(school=self.school, name="Class 8", section="B", academic_year="2026-2027")
        self.other_classroom = ClassRoom.objects.create(school=self.other_school, name="Class 8", section="B", academic_year="2026-2027")
        self.student = Student.objects.create(
            school=self.school, classroom=self.classroom, admission_number="TC-001",
            first_name="Nisha", last_name="Kumar", date_of_birth=date(2012, 8, 14),
            admitted_at=date(2020, 4, 1),
        )
        self.other_student = Student.objects.create(
            school=self.other_school, classroom=self.other_classroom, admission_number="PRIVATE-TC-001",
            first_name="Private", last_name="Student",
        )

    def test_management_can_generate_school_scoped_draft_pdf(self):
        self.client.force_login(self.admin)
        form = self.client.get(f"/students/transfer-certificate/?school={self.school.pk}")
        self.assertEqual(form.status_code, 200)
        self.assertContains(form, "marked DRAFT")
        response = self.client.post("/students/transfer-certificate/", {
            "school": self.school.pk,
            "student": self.student.pk,
            "leaving_date": "2026-10-28",
            "reason": "Family relocation",
            "conduct": "Good",
            "remarks": "Verify all records before issue",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertIn('attachment; filename="transfer-certificate-draft.pdf"', response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_rejects_student_from_another_school_and_invalid_date(self):
        self.client.force_login(self.admin)
        foreign = self.client.post("/students/transfer-certificate/", {
            "school": self.school.pk, "student": self.other_student.pk,
        })
        invalid = self.client.post("/students/transfer-certificate/", {
            "school": self.school.pk, "student": self.student.pk, "leaving_date": "not-a-date",
        })
        self.assertEqual(foreign.status_code, 200)
        self.assertContains(foreign, "does not belong to this school")
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, "valid leaving date")

    def test_teacher_cannot_generate_transfer_certificate(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/students/transfer-certificate/?school={self.school.pk}")
        self.assertEqual(response.status_code, 403)
