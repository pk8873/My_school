from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from schools.models import ClassRoom, FeeRecord, Membership, School, Student


User = get_user_model()


class OverdueFeeCsvTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Overdue Fee School", slug="overdue-fee-school")
        self.other_school = School.objects.create(name="Other Overdue Fee School", slug="other-overdue-fee-school")
        self.admin = User.objects.create_user(username="overdue_fee_admin", password="synthetic-test-pass-123")
        self.accountant = User.objects.create_user(username="overdue_fee_accountant", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.accountant, school=self.school, role=Membership.Role.ACCOUNTANT)
        self.classroom = ClassRoom.objects.create(school=self.school, name="Class 8", section="A", academic_year="2026-2027")
        other_classroom = ClassRoom.objects.create(school=self.other_school, name="Class 8", section="A", academic_year="2026-2027")
        self.student = Student.objects.create(school=self.school, classroom=self.classroom, admission_number="DUE-001", first_name="Asha", last_name="Singh")
        other_student = Student.objects.create(school=self.other_school, classroom=other_classroom, admission_number="PRIVATE-DUE", first_name="Private", last_name="Student")
        yesterday = timezone.localdate() - timedelta(days=1)
        tomorrow = timezone.localdate() + timedelta(days=1)
        self.overdue = FeeRecord.objects.create(
            school=self.school, student=self.student, title="Tuition fee", amount="1000.00",
            paid_amount="250.00", due_date=yesterday, status=FeeRecord.Status.PARTIAL,
        )
        FeeRecord.objects.create(
            school=self.school, student=self.student, title="Future fee", amount="500.00",
            paid_amount="0.00", due_date=tomorrow, status=FeeRecord.Status.PENDING,
        )
        FeeRecord.objects.create(
            school=self.school, student=self.student, title="Paid old fee", amount="200.00",
            paid_amount="200.00", due_date=yesterday, status=FeeRecord.Status.PAID,
        )
        FeeRecord.objects.create(
            school=self.other_school, student=other_student, title="Private overdue", amount="900.00",
            paid_amount="0.00", due_date=yesterday, status=FeeRecord.Status.PENDING,
        )

    def test_export_contains_only_past_due_unpaid_balance_for_current_school(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/reports/overdue-fees.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment; filename="overdue-fees.csv"', response["Content-Disposition"])
        body = response.content.decode("utf-8-sig")
        self.assertIn("DUE-001", body)
        self.assertIn("Tuition fee", body)
        self.assertIn("750.00", body)
        self.assertNotIn("Future fee", body)
        self.assertNotIn("Paid old fee", body)
        self.assertNotIn("PRIVATE-DUE", body)

    def test_class_filter_and_invalid_filter(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/reports/overdue-fees.csv?school={self.school.pk}&classroom={self.classroom.pk}")
        invalid = self.client.get(f"/reports/overdue-fees.csv?school={self.school.pk}&classroom=invalid")
        self.assertEqual(response.status_code, 200)
        self.assertIn("DUE-001", response.content.decode("utf-8-sig"))
        self.assertEqual(invalid.status_code, 400)

    def test_accountant_can_export_fee_report_but_teacher_cannot(self):
        self.client.force_login(self.accountant)
        allowed = self.client.get(f"/reports/overdue-fees.csv?school={self.school.pk}")
        self.assertEqual(allowed.status_code, 200)
        teacher = User.objects.create_user(username="overdue_fee_teacher", password="synthetic-test-pass-123")
        Membership.objects.create(user=teacher, school=self.school, role=Membership.Role.TEACHER)
        self.client.force_login(teacher)
        denied = self.client.get(f"/reports/overdue-fees.csv?school={self.school.pk}")
        self.assertEqual(denied.status_code, 403)
