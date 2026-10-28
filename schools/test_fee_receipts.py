from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from schools.models import FeePayment, FeeRecord, Membership, School, Student, ClassRoom


User = get_user_model()


class IndividualFeeReceiptTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Receipt Synthetic School", slug="receipt-synthetic")
        self.other_school = School.objects.create(name="Other Synthetic School", slug="other-synthetic")
        self.admin = User.objects.create_user(username="receipt_admin", password="synthetic-test-pass-123")
        self.other_admin = User.objects.create_user(username="other_receipt_admin", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.other_admin, school=self.other_school, role=Membership.Role.SCHOOL_ADMIN)
        self.classroom = ClassRoom.objects.create(
            school=self.school, name="Class 5", section="A", academic_year="2026-2027",
        )
        self.student = Student.objects.create(
            school=self.school, classroom=self.classroom, admission_number="R-001",
            first_name="Synthetic", last_name="Learner",
        )
        self.fee = FeeRecord.objects.create(
            school=self.school, student=self.student, title="Synthetic term fee",
            amount="1000.00", paid_amount="250.00", status=FeeRecord.Status.PARTIAL,
        )
        self.payment = FeePayment.objects.create(
            school=self.school, fee_record=self.fee, amount="250.00",
            payment_date="2026-10-28", method=FeePayment.Method.CASH,
            reference="SYNTHETIC-RECEIPT-01", recorded_by=self.admin,
        )

    def test_fee_payment_receipt_returns_pdf_for_own_school(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/fees/payments/{self.payment.pk}/receipt.pdf?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(b"%PDF", response.content[:10])
        self.assertIn("fee-payment-", response["Content-Disposition"])

    def test_fee_payment_receipt_cannot_cross_school_boundary(self):
        self.client.force_login(self.other_admin)
        response = self.client.get(f"/fees/payments/{self.payment.pk}/receipt.pdf?school={self.other_school.pk}")
        self.assertEqual(response.status_code, 404)

    def test_non_fee_role_cannot_download_individual_receipt(self):
        teacher = User.objects.create_user(username="receipt_teacher", password="synthetic-test-pass-123")
        Membership.objects.create(user=teacher, school=self.school, role=Membership.Role.TEACHER)
        self.client.force_login(teacher)
        response = self.client.get(f"/fees/payments/{self.payment.pk}/receipt.pdf?school={self.school.pk}")
        self.assertEqual(response.status_code, 403)

    def test_demo_seed_creates_repeatable_synthetic_payment_rows(self):
        with override_settings(DEBUG=True):
            call_command("seed_demo_data", verbosity=0)
            demo_school = School.objects.get(slug="school-saathi-demo")
            first_count = FeePayment.objects.filter(school=demo_school).count()
            first_total = sum(FeePayment.objects.filter(school=demo_school).values_list("amount", flat=True))
            call_command("seed_demo_data", verbosity=0)
            second_count = FeePayment.objects.filter(school=demo_school).count()
        self.assertEqual(first_count, 4)
        self.assertEqual(first_total, 18000)
        self.assertEqual(second_count, first_count)
