from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from schools.models import ClassRoom, Homework, HomeworkSubmission, Membership, School, Student


User = get_user_model()


class HomeworkSubmissionCsvExportTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Homework Export School", slug="homework-export-school")
        self.other_school = School.objects.create(name="Other Homework School", slug="other-homework-school")
        self.admin = User.objects.create_user(username="homework_export_admin", password="synthetic-test-pass-123")
        self.parent = User.objects.create_user(username="homework_export_parent", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.parent, school=self.school, role=Membership.Role.PARENT)
        self.classroom = ClassRoom.objects.create(school=self.school, name="Class 7", section="B", academic_year="2026-2027")
        other_classroom = ClassRoom.objects.create(school=self.other_school, name="Class 7", section="B", academic_year="2026-2027")
        self.student = Student.objects.create(school=self.school, classroom=self.classroom, admission_number="HW-001", first_name="Riya", last_name="Singh")
        other_student = Student.objects.create(school=self.other_school, classroom=other_classroom, admission_number="PRIVATE-HW", first_name="Private", last_name="Student")
        self.homework = Homework.objects.create(school=self.school, classroom=self.classroom, title="Science worksheet", instructions="Answer questions", assigned_date=date(2026, 10, 1), due_date=date(2026, 10, 15))
        other_homework = Homework.objects.create(school=self.other_school, classroom=other_classroom, title="Private worksheet", instructions="Private", assigned_date=date(2026, 10, 1))
        self.submission = HomeworkSubmission.objects.create(school=self.school, homework=self.homework, student=self.student, submission_text="Answers are attached", status=HomeworkSubmission.Status.REVIEWED, teacher_feedback="Well done")
        HomeworkSubmission.objects.create(school=self.other_school, homework=other_homework, student=other_student, submission_text="Secret text")

    def test_csv_export_is_school_scoped_and_downloadable(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/reports/homework-submissions.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn('attachment; filename="homework-submissions.csv"', response["Content-Disposition"])
        body = response.content.decode("utf-8-sig")
        self.assertIn("HW-001", body)
        self.assertIn("Well done", body)
        self.assertNotIn("PRIVATE-HW", body)
        self.assertNotIn("Secret text", body)

    def test_homework_class_status_and_date_filters(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            f"/reports/homework-submissions.csv?school={self.school.pk}&homework={self.homework.pk}"
            f"&classroom={self.classroom.pk}&status=reviewed&date_from=2026-10-01&date_to=2026-10-31"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Science worksheet", response.content.decode("utf-8-sig"))

    def test_invalid_filter_and_reversed_dates_are_rejected(self):
        self.client.force_login(self.admin)
        invalid = self.client.get(f"/reports/homework-submissions.csv?school={self.school.pk}&status=unknown")
        reversed_dates = self.client.get(f"/reports/homework-submissions.csv?school={self.school.pk}&date_from=2026-11-01&date_to=2026-10-01")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(reversed_dates.status_code, 400)

    def test_parent_cannot_export_all_homework_submissions(self):
        self.client.force_login(self.parent)
        response = self.client.get(f"/reports/homework-submissions.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 403)
