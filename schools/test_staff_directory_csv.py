from django.contrib.auth import get_user_model
from django.test import TestCase

from schools.models import Membership, School


User = get_user_model()


class StaffDirectoryCsvTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Directory School", slug="directory-school")
        self.other_school = School.objects.create(name="Private Directory School", slug="private-directory-school")
        self.admin = User.objects.create_user(username="directory_admin", password="synthetic-test-pass-123")
        self.teacher = User.objects.create_user(
            username="directory_teacher", password="synthetic-test-pass-123",
            first_name="Asha", last_name="Sharma", email="asha@example.test",
        )
        self.private_user = User.objects.create_user(username="private_directory_user", password="synthetic-test-pass-123")
        self.inactive_teacher = User.objects.create_user(username="directory_inactive_teacher", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.teacher, school=self.school, role=Membership.Role.TEACHER)
        Membership.objects.create(user=self.inactive_teacher, school=self.school, role=Membership.Role.TEACHER, is_active=False)
        Membership.objects.create(user=self.private_user, school=self.other_school, role=Membership.Role.PARENT)

    def test_management_can_export_only_current_school_accounts(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/reports/staff-directory.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment; filename="school-account-directory.csv"', response["Content-Disposition"])
        body = response.content.decode("utf-8-sig")
        self.assertIn("directory_teacher", body)
        self.assertIn("asha@example.test", body)
        self.assertIn("Inactive", body)
        self.assertNotIn("private_directory_user", body)

    def test_role_and_status_filters_and_invalid_filter(self):
        self.client.force_login(self.admin)
        filtered = self.client.get(
            f"/reports/staff-directory.csv?school={self.school.pk}&role=teacher&status=inactive"
        )
        invalid = self.client.get(f"/reports/staff-directory.csv?school={self.school.pk}&status=maybe")
        body = filtered.content.decode("utf-8-sig")
        self.assertEqual(filtered.status_code, 200)
        self.assertIn("directory_inactive_teacher", body)
        self.assertNotIn("directory_teacher", body)
        self.assertNotIn("directory_admin", body)
        self.assertEqual(invalid.status_code, 400)

    def test_teacher_cannot_export_account_directory(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/reports/staff-directory.csv?school={self.school.pk}")
        self.assertEqual(response.status_code, 403)
