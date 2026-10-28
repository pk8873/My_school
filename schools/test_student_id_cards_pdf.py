from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from schools.models import ClassRoom, Membership, School, Student


User = get_user_model()


class StudentIdCardsPdfTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="ID Card School", slug="id-card-school", phone="1234567890")
        self.other_school = School.objects.create(name="Private Other School", slug="private-other-school")
        self.admin = User.objects.create_user(username="idcard_admin", password="synthetic-test-pass-123")
        self.teacher = User.objects.create_user(username="idcard_teacher", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.teacher, school=self.school, role=Membership.Role.TEACHER)
        self.classroom = ClassRoom.objects.create(school=self.school, name="Class 7", section="A", academic_year="2026-2027")
        self.other_classroom = ClassRoom.objects.create(school=self.other_school, name="Class 7", section="A", academic_year="2026-2027")
        Student.objects.create(
            school=self.school, classroom=self.classroom, admission_number="ID-001",
            first_name="Aarav", last_name="Sharma", date_of_birth=date(2013, 5, 4),
        )
        Student.objects.create(
            school=self.other_school, classroom=self.other_classroom, admission_number="SECRET-999",
            first_name="Private", last_name="Student",
        )

    def test_admin_downloads_school_scoped_pdf(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/students/id-cards.pdf?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn('attachment; filename="student-id-cards.pdf"', response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertNotIn(b"SECRET-999", response.content)

    def test_class_filter_and_invalid_or_foreign_class(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/students/id-cards.pdf?school={self.school.pk}&classroom={self.classroom.pk}")
        invalid = self.client.get(f"/students/id-cards.pdf?school={self.school.pk}&classroom=abc")
        foreign = self.client.get(f"/students/id-cards.pdf?school={self.school.pk}&classroom={self.other_classroom.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(foreign.status_code, 404)

    def test_teacher_cannot_generate_id_cards(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/students/id-cards.pdf?school={self.school.pk}")
        self.assertEqual(response.status_code, 403)
