from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from schools.models import ClassRoom, Membership, School, Student


User = get_user_model()


class UpcomingStudentBirthdaysCsvTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Birthday Report School", slug="birthday-report-school")
        self.other_school = School.objects.create(name="Other Birthday School", slug="other-birthday-school")
        self.admin = User.objects.create_user(username="birthday_admin", password="synthetic-test-pass-123")
        self.teacher = User.objects.create_user(username="birthday_teacher", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.teacher, school=self.school, role=Membership.Role.TEACHER)
        self.classroom = ClassRoom.objects.create(school=self.school, name="Class 4", section="B", academic_year="2026-2027")
        other_class = ClassRoom.objects.create(school=self.other_school, name="Class 4", section="B", academic_year="2026-2027")
        today = timezone.localdate()
        self.soon = Student.objects.create(
            school=self.school, classroom=self.classroom, admission_number="BDAY-001",
            first_name="Aarav", last_name="Shah", date_of_birth=date(today.year - 10, (today + timedelta(days=5)).month, (today + timedelta(days=5)).day),
        )
        self.far = Student.objects.create(
            school=self.school, classroom=self.classroom, admission_number="BDAY-002",
            first_name="Far", last_name="Away", date_of_birth=date(today.year - 10, 12, 31),
        )
        Student.objects.create(
            school=self.other_school, classroom=other_class, admission_number="PRIVATE-BDAY",
            first_name="Private", last_name="Student", date_of_birth=today,
        )

    def test_report_is_school_scoped_and_contains_upcoming_birthday(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/reports/upcoming-birthdays.csv?school={self.school.pk}&days=30")
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment; filename="upcoming-student-birthdays.csv"', response["Content-Disposition"])
        body = response.content.decode("utf-8-sig")
        self.assertIn("BDAY-001", body)
        self.assertNotIn("PRIVATE-BDAY", body)
        self.assertNotIn("BDAY-002", body)

    def test_invalid_days_and_teacher_permission(self):
        self.client.force_login(self.admin)
        invalid = self.client.get(f"/reports/upcoming-birthdays.csv?school={self.school.pk}&days=0")
        self.assertEqual(invalid.status_code, 400)
        self.client.force_login(self.teacher)
        denied = self.client.get(f"/reports/upcoming-birthdays.csv?school={self.school.pk}&days=30")
        self.assertEqual(denied.status_code, 403)
