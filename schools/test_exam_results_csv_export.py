from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from schools.models import ClassRoom, Exam, ExamResult, Membership, School, Student


User = get_user_model()


class ExamResultsCsvExportTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Exam Export School", slug="exam-export-school")
        self.other_school = School.objects.create(name="Other Exam Export School", slug="other-exam-export-school")
        self.admin = User.objects.create_user(username="exam_export_admin", password="synthetic-test-pass-123")
        self.parent = User.objects.create_user(username="exam_export_parent", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.parent, school=self.school, role=Membership.Role.PARENT)
        self.classroom = ClassRoom.objects.create(school=self.school, name="Class 5", section="A", academic_year="2026-2027")
        other_classroom = ClassRoom.objects.create(school=self.other_school, name="Class 5", section="A", academic_year="2026-2027")
        self.student = Student.objects.create(school=self.school, classroom=self.classroom, admission_number="EX-001", first_name="Asha", last_name="Kumar")
        other_student = Student.objects.create(school=self.other_school, classroom=other_classroom, admission_number="PRIVATE-999", first_name="Private", last_name="Student")
        self.exam = Exam.objects.create(school=self.school, title="Mid Term", classroom=self.classroom, exam_date=date(2026, 10, 10), max_marks=Decimal("100"))
        final_exam = Exam.objects.create(school=self.school, title="Final", classroom=self.classroom, exam_date=date(2026, 12, 10), max_marks=Decimal("100"))
        other_exam = Exam.objects.create(school=self.other_school, title="Private Exam", classroom=other_classroom, exam_date=date(2026, 10, 10), max_marks=Decimal("100"))
        ExamResult.objects.create(school=self.school, exam=self.exam, student=self.student, marks_obtained=Decimal("82"), remarks="Good work")
        ExamResult.objects.create(school=self.school, exam=final_exam, student=self.student, marks_obtained=Decimal("91"))
        ExamResult.objects.create(school=self.other_school, exam=other_exam, student=other_student, marks_obtained=Decimal("99"), remarks="Private")

    def test_export_is_downloadable_and_school_scoped(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/reports/exam-results.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn('attachment; filename="exam-results.csv"', response["Content-Disposition"])
        body = response.content.decode("utf-8-sig")
        self.assertIn("EX-001", body)
        self.assertIn("Good work", body)
        self.assertNotIn("PRIVATE-999", body)
        self.assertNotIn("Private Exam", body)

    def test_exam_class_and_date_filters(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            f"/reports/exam-results.csv?school={self.school.pk}&exam={self.exam.pk}"
            f"&classroom={self.classroom.pk}&date_from=2026-10-01&date_to=2026-10-31"
        )
        body = response.content.decode("utf-8-sig")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Mid Term", body)
        self.assertNotIn("Final", body)

    def test_invalid_filters_return_bad_request(self):
        self.client.force_login(self.admin)
        invalid = self.client.get(f"/reports/exam-results.csv?school={self.school.pk}&exam=nope")
        reversed_range = self.client.get(f"/reports/exam-results.csv?school={self.school.pk}&date_from=2026-12-01&date_to=2026-10-01")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(reversed_range.status_code, 400)

    def test_parent_cannot_export_all_school_results(self):
        self.client.force_login(self.parent)
        response = self.client.get(f"/reports/exam-results.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 403)
