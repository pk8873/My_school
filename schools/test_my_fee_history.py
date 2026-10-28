from django.contrib.auth import get_user_model
from django.test import TestCase

from schools.models import (
    ClassRoom, FeePayment, FeeRecord, Membership, ParentStudentLink,
    School, Student,
)


User = get_user_model()


class FamilyFeeHistoryTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Family Fee School", slug="family-fee-school")
        self.other_school = School.objects.create(name="Other Family Fee School", slug="other-family-fee-school")
        self.parent = User.objects.create_user(username="family_parent", password="synthetic-test-pass-123")
        self.student_user = User.objects.create_user(username="family_student", password="synthetic-test-pass-123")
        self.teacher = User.objects.create_user(username="family_teacher", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.parent, school=self.school, role=Membership.Role.PARENT)
        Membership.objects.create(user=self.student_user, school=self.school, role=Membership.Role.STUDENT)
        Membership.objects.create(user=self.teacher, school=self.school, role=Membership.Role.TEACHER)
        self.classroom = ClassRoom.objects.create(
            school=self.school, name="Class 6", section="A", academic_year="2026-2027",
        )
        self.child = Student.objects.create(
            school=self.school, classroom=self.classroom, admission_number="F-001",
            first_name="Linked", last_name="Child",
        )
        self.child.portal_user = self.student_user
        self.child.save(update_fields=["portal_user"])
        self.unlinked_child = Student.objects.create(
            school=self.school, classroom=self.classroom, admission_number="F-002",
            first_name="Unlinked", last_name="Child",
        )
        self.other_classroom = ClassRoom.objects.create(
            school=self.other_school, name="Class 6", section="A", academic_year="2026-2027",
        )
        self.other_child = Student.objects.create(
            school=self.other_school, classroom=self.other_classroom, admission_number="F-003",
            first_name="Other", last_name="School",
        )
        ParentStudentLink.objects.create(
            parent=self.parent, student=self.child, relationship="Parent", can_view_fees=True,
        )
        self.fee = FeeRecord.objects.create(
            school=self.school, student=self.child, title="Term fee",
            amount="1200.00", paid_amount="300.00", status=FeeRecord.Status.PARTIAL,
        )
        self.hidden_fee = FeeRecord.objects.create(
            school=self.school, student=self.unlinked_child, title="Private sibling fee",
            amount="900.00", paid_amount="0.00",
        )
        self.payment = FeePayment.objects.create(
            school=self.school, fee_record=self.fee, amount="300.00",
            payment_date="2026-10-28", method=FeePayment.Method.UPI,
            reference="FAMILY-TEST-REF",
        )

    def test_parent_sees_only_linked_child_fees_and_payments(self):
        self.client.force_login(self.parent)
        response = self.client.get(f"/my-fees/?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Term fee")
        self.assertContains(response, "FAMILY-TEST-REF")
        self.assertNotContains(response, "Private sibling fee")
        self.assertNotContains(response, "Other School")

    def test_parent_without_fee_permission_cannot_see_child_fee(self):
        ParentStudentLink.objects.filter(parent=self.parent, student=self.child).update(can_view_fees=False)
        self.client.force_login(self.parent)
        response = self.client.get(f"/my-fees/?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Term fee")
        self.assertNotContains(response, "FAMILY-TEST-REF")

    def test_student_sees_only_their_own_fee_history(self):
        self.client.force_login(self.student_user)
        response = self.client.get(f"/my-fees/?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Term fee")
        self.assertNotContains(response, "Private sibling fee")

    def test_teacher_cannot_use_family_fee_history(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/my-fees/?school={self.school.pk}")
        self.assertEqual(response.status_code, 403)

    def test_parent_cannot_view_history_for_another_school(self):
        self.client.force_login(self.parent)
        response = self.client.get(f"/my-fees/?school={self.other_school.pk}")
        self.assertNotEqual(response.status_code, 200)
