from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from schools.models import ClassRoom, FeePayment, FeeRecord, Membership, School, Student


User = get_user_model()


class FeePaymentCsvExportTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="CSV Export Synthetic School", slug="csv-export-synthetic")
        self.other_school = School.objects.create(name="CSV Export Other School", slug="csv-export-other")
        self.admin = User.objects.create_user(username="csv_fee_admin", password="synthetic-test-pass-123")
        self.other_admin = User.objects.create_user(username="csv_other_admin", password="synthetic-test-pass-123")
        self.teacher = User.objects.create_user(username="csv_teacher", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.ACCOUNTANT)
        Membership.objects.create(user=self.other_admin, school=self.other_school, role=Membership.Role.ACCOUNTANT)
        Membership.objects.create(user=self.teacher, school=self.school, role=Membership.Role.TEACHER)
        self.classroom = ClassRoom.objects.create(school=self.school, name="Class 6", section="A", academic_year="2026-2027")
        self.student = Student.objects.create(school=self.school, classroom=self.classroom, admission_number="CSV-001", first_name="Sample", last_name="Student")
        self.other_class = ClassRoom.objects.create(school=self.other_school, name="Class 6", section="A", academic_year="2026-2027")
        other_student = Student.objects.create(school=self.other_school, classroom=self.other_class, admission_number="SECRET-999", first_name="Other", last_name="School")
        fee = FeeRecord.objects.create(school=self.school, student=self.student, title="Term tuition", amount=Decimal("1000.00"), paid_amount=Decimal("300.00"), status=FeeRecord.Status.PARTIAL)
        other_fee = FeeRecord.objects.create(school=self.other_school, student=other_student, title="Private tuition", amount=Decimal("2000.00"), paid_amount=Decimal("400.00"), status=FeeRecord.Status.PARTIAL)
        self.payment = FeePayment.objects.create(school=self.school, fee_record=fee, amount=Decimal("200.00"), payment_date=date(2026, 10, 20), method=FeePayment.Method.CASH, reference="CSV-REF-001", note="Synthetic test row", recorded_by=self.admin)
        FeePayment.objects.create(school=self.school, fee_record=fee, amount=Decimal("100.00"), payment_date=date(2026, 10, 25), method=FeePayment.Method.UPI, reference="CSV-REF-002", recorded_by=self.admin)
        FeePayment.objects.create(school=self.other_school, fee_record=other_fee, amount=Decimal("400.00"), payment_date=date(2026, 10, 20), method=FeePayment.Method.CASH, reference="OTHER-SECRET", recorded_by=self.other_admin)

    def test_fee_payment_csv_is_school_scoped_and_downloadable(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/reports/fee-payments.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn('attachment; filename="fee-payments.csv"', response["Content-Disposition"])
        body = response.content.decode("utf-8-sig")
        self.assertIn("CSV-001", body)
        self.assertIn("CSV-REF-001", body)
        self.assertNotIn("SECRET-999", body)
        self.assertNotIn("OTHER-SECRET", body)

    def test_fee_payment_csv_supports_fee_method_date_and_search_filters(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/reports/fee-payments.csv?school={self.school.pk}&fee_id={self.payment.fee_record_id}&method=cash&date_from=2026-10-19&date_to=2026-10-21&q=CSV-REF-001")
        body = response.content.decode("utf-8-sig")
        self.assertEqual(response.status_code, 200)
        self.assertIn("CSV-REF-001", body)
        self.assertNotIn("CSV-REF-002", body)

    def test_fee_payment_csv_rejects_invalid_or_reversed_date_range(self):
        self.client.force_login(self.admin)
        bad_date = self.client.get(f"/reports/fee-payments.csv?school={self.school.pk}&date_from=not-a-date")
        reversed_range = self.client.get(f"/reports/fee-payments.csv?school={self.school.pk}&date_from=2026-10-30&date_to=2026-10-01")
        self.assertEqual(bad_date.status_code, 400)
        self.assertEqual(reversed_range.status_code, 400)

    def test_non_fee_role_cannot_export_payment_history(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/reports/fee-payments.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 403)
