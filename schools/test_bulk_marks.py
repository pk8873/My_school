from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import ClassRoom, Exam, ExamResult, Membership, School, Student

User = get_user_model()


class BulkExamMarksTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Bulk Marks School", slug="bulk-marks")
        self.other_school = School.objects.create(name="Other Marks School", slug="other-marks")
        self.admin = User.objects.create_user(
            username="bulk_marks_admin", password="synthetic-test-pass-123"
        )
        Membership.objects.create(
            user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN
        )
        self.classroom = ClassRoom.objects.create(
            school=self.school, name="Class 8", section="A", academic_year="2026-2027"
        )
        self.other_class = ClassRoom.objects.create(
            school=self.other_school, name="Class 8", section="A", academic_year="2026-2027"
        )
        self.student_one = Student.objects.create(
            school=self.school, classroom=self.classroom,
            admission_number="BM-001", first_name="Asha",
        )
        self.student_two = Student.objects.create(
            school=self.school, classroom=self.classroom,
            admission_number="BM-002", first_name="Bharat",
        )
        Student.objects.create(
            school=self.other_school, classroom=self.other_class,
            admission_number="OTHER-001", first_name="Private Other",
        )
        self.exam = Exam.objects.create(
            school=self.school, classroom=self.classroom,
            title="Unit Test", exam_date="2026-10-30", max_marks=100,
        )
        self.client.force_login(self.admin)
        self.url = reverse("bulk_exam_results")

    def post_marks(self, first="75", second="80"):
        return self.client.post(self.url, {
            "school": str(self.school.pk),
            "exam": str(self.exam.pk),
            "classroom": str(self.classroom.pk),
            f"marks_{self.student_one.pk}": first,
            f"marks_{self.student_two.pk}": second,
        })

    def test_bulk_marks_page_is_school_scoped(self):
        response = self.client.get(self.url, {
            "school": self.school.pk, "exam": self.exam.pk, "classroom": self.classroom.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Asha")
        self.assertContains(response, "Bharat")
        self.assertNotContains(response, "Private Other")

    def test_bulk_marks_save_results_for_all_entered_students(self):
        response = self.post_marks()
        self.assertRedirects(
            response,
            f"{self.url}?school={self.school.pk}&exam={self.exam.pk}&classroom={self.classroom.pk}",
        )
        self.assertEqual(
            ExamResult.objects.get(exam=self.exam, student=self.student_one).marks_obtained, 75
        )
        self.assertEqual(
            ExamResult.objects.get(exam=self.exam, student=self.student_two).marks_obtained, 80
        )

    def test_bulk_marks_update_existing_results(self):
        ExamResult.objects.create(
            school=self.school, exam=self.exam, student=self.student_one, marks_obtained=40
        )
        self.post_marks(first="90", second="")
        result = ExamResult.objects.get(exam=self.exam, student=self.student_one)
        self.assertEqual(result.marks_obtained, 90)
        self.assertEqual(ExamResult.objects.filter(exam=self.exam).count(), 1)

    def test_invalid_mark_prevents_partial_save(self):
        response = self.post_marks(first="70", second="101")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ExamResult.objects.filter(exam=self.exam).exists())
        self.assertContains(response, "Marks cannot exceed the exam maximum")

    def test_cannot_load_another_schools_exam(self):
        other_exam = Exam.objects.create(
            school=self.other_school, classroom=self.other_class,
            title="Private Exam", exam_date="2026-10-30", max_marks=100,
        )
        response = self.client.get(self.url, {
            "school": self.school.pk, "exam": other_exam.pk, "classroom": self.other_class.pk,
        })
        self.assertEqual(response.status_code, 404)

    def test_parent_role_cannot_enter_marks(self):
        parent = User.objects.create_user(
            username="bulk_marks_parent", password="synthetic-test-pass-123"
        )
        Membership.objects.create(
            user=parent, school=self.school, role=Membership.Role.PARENT
        )
        self.client.force_login(parent)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
