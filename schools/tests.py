from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from .models import ClassRoom, Membership, ParentStudentLink, School, Student
from .tenant import require_membership
User = get_user_model()

class TenantBoundaryTests(TestCase):
    def setUp(self):
        self.a = School.objects.create(name="Alpha Synthetic School", slug="alpha")
        self.b = School.objects.create(name="Beta Synthetic School", slug="beta")
        self.user_a = User.objects.create_user(username="alpha_admin", password="synthetic-test-pass-123")
        self.user_b = User.objects.create_user(username="beta_admin", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.user_a, school=self.a, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.user_b, school=self.b, role=Membership.Role.SCHOOL_ADMIN)
        self.ca = ClassRoom.objects.create(school=self.a, name="Class 5", section="A", academic_year="2026-2027")
        self.cb = ClassRoom.objects.create(school=self.b, name="Class 5", section="A", academic_year="2026-2027")
        self.sa = Student.objects.create(school=self.a, classroom=self.ca, admission_number="A-001", first_name="Synthetic Alpha")
        self.sb = Student.objects.create(school=self.b, classroom=self.cb, admission_number="B-001", first_name="Synthetic Beta")

    def test_membership_cannot_cross_school(self):
        with self.assertRaises(PermissionDenied): require_membership(self.user_a, self.b.pk)

    def test_student_query_is_scoped(self):
        visible = Student.objects.filter(school=self.a)
        self.assertEqual(list(visible), [self.sa])
        self.assertNotIn(self.sb, visible)

    def test_classroom_must_belong_to_same_school(self):
        bad = Student(school=self.a, classroom=self.cb, admission_number="BAD-1", first_name="Synthetic")
        with self.assertRaises(ValidationError): bad.clean()

    def test_parent_link_unique_constraint(self):
        parent = User.objects.create_user(username="synthetic_parent", password="synthetic-test-pass-123")
        ParentStudentLink.objects.create(parent=parent, student=self.sa)
        with self.assertRaises(Exception): ParentStudentLink.objects.create(parent=parent, student=self.sa)

    def test_dashboard_hides_other_tenant_students(self):
        self.client.force_login(self.user_a)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Synthetic Alpha")
        self.assertNotContains(response, "Synthetic Beta")
