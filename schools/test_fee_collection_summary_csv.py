from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from schools.models import ClassRoom, FeePayment, FeeRecord, Membership, School, Student


User = get_user_model()


class FeeCollectionSummaryCsvTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Collection Summary School", slug="collection-summary-school")
        self.other_school = School.objects.create(name="Other Collection School", slug="other-collection-school")
        self.admin = User.objects.create_user(username="collection_admin", password="synthetic-test-pass-123")
        self.teacher = User.objects.create_user(username="collection_teacher", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.teacher, school=self.school, role=Membership.Role.TEACHER)
        classroom = ClassRoom.objects.create(school=self.school, name="Class 5", section="A", academic_year="2026-2027")
        other_classroom = ClassRoom.objects.create(school=self.other_school, name="Class 5", section="A", academic_year="2026-2027")
        student = Student.objects.create(school=self.school, classroom=classroom, admission_number="COL-001", first_name="Ravi", last_name="Kumar")
        other_student = Student.objects.create(school=self.other_school, classroom=other_classroom, admission_number="OTHER-COL", first_name="Other", last_name="Student")
        self.fee = FeeRecord.objects.create(school=self.school, student=student, title="Tuition", amount="5000.00")
        other_fee = FeeRecord.objects.create(school=self.other_school, student=other_student, title="Tuition", amount="5000.00")
        self.day = timezone.localdate() - timedelta(days=1)
        FeePayment.objects.create(school=self.school, fee_record=self.fee, amount="500.00", payment_date=self.day, method=FeePayment.Method.CASH)
        FeePayment.objects.create(school=self.school, fee_record=self.fee, amount="250.00", payment_date=self.day, method=FeePayment.Method.CASH)
        FeePayment.objects.create(school=self.school, fee_record=self.fee, amount="1000.00", payment_date=self.day, method=FeePayment.Method.UPI)
        FeePayment.objects.create(school=self.school, fee_record=self.fee, amount="200.00", payment_date=self.day - timedelta(days=2), method=FeePayment.Method.CASH)
        FeePayment.objects.create(school=self.other_school, fee_record=other_fee, amount="999.00", payment_date=self.day, method=FeePayment.Method.CASH)

    def test_summary_groups_payments_by_date_and_method_and_is_school_scoped(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/reports/fee-collection-summary.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment; filename="fee-collection-summary.csv"', response["Content-Disposition"])
        body = response.content.decode("utf-8-sig")
        self.assertIn("Cash,2,750.00", body)
        self.assertIn("UPI,1,1000.00", body)
        self.assertNotIn("999.00", body)
        self.assertNotIn("OTHER-COL", body)

    def test_date_filters_and_invalid_date(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            f"/reports/fee-collection-summary.csv?school={self.school.pk}&date_from={self.day.isoformat()}&date_to={self.day.isoformat()}"
        )
        invalid = self.client.get(f"/reports/fee-collection-summary.csv?school={self.school.pk}&date_from=not-a-date")
        reversed_range = self.client.get(
            f"/reports/fee-collection-summary.csv?school={self.school.pk}&date_from={self.day.isoformat()}&date_to={(self.day - timedelta(days=1)).isoformat()}"
        )
        body = response.content.decode("utf-8-sig")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Cash,2,750.00", body)
        self.assertNotIn("200.00", body)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(reversed_range.status_code, 400)

    def test_teacher_cannot_export_financial_summary(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/reports/fee-collection-summary.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 403)
