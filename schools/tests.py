from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from .models import AttendanceRecord, ClassRoom, FeeRecord, Membership, ParentStudentLink, School, Student
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
        with self.assertRaises(PermissionDenied):
            require_membership(self.user_a, self.b.pk)

    def test_student_query_is_scoped(self):
        visible = Student.objects.filter(school=self.a)
        self.assertEqual(list(visible), [self.sa])
        self.assertNotIn(self.sb, visible)

    def test_classroom_must_belong_to_same_school(self):
        bad = Student(school=self.a, classroom=self.cb, admission_number="BAD-1", first_name="Synthetic")
        with self.assertRaises(ValidationError):
            bad.clean()

    def test_parent_link_unique_constraint(self):
        parent = User.objects.create_user(username="synthetic_parent", password="synthetic-test-pass-123")
        ParentStudentLink.objects.create(parent=parent, student=self.sa)
        with self.assertRaises(Exception):
            ParentStudentLink.objects.create(parent=parent, student=self.sa)

    def test_dashboard_hides_other_tenant_students(self):
        self.client.force_login(self.user_a)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Synthetic Alpha")
        self.assertNotContains(response, "Synthetic Beta")

    def test_school_admin_can_create_class_for_own_school(self):
        self.client.force_login(self.user_a)
        response = self.client.post("/classes/", {
            "name": "Class 6", "section": "B", "academic_year": "2026-2027",
            "capacity": "35", "is_active": "on",
        })
        self.assertRedirects(response, "/classes/")
        self.assertTrue(ClassRoom.objects.filter(school=self.a, name="Class 6").exists())
        self.assertFalse(ClassRoom.objects.filter(school=self.b, name="Class 6").exists())

    def test_school_admin_can_create_student_only_in_own_class(self):
        self.client.force_login(self.user_a)
        response = self.client.post("/students/", {
            "classroom": self.ca.pk, "admission_number": "A-002",
            "first_name": "New", "last_name": "Synthetic", "is_active": "on",
        })
        self.assertRedirects(response, "/students/")
        self.assertTrue(Student.objects.filter(school=self.a, admission_number="A-002").exists())

    def test_other_tenant_class_is_not_selectable_in_student_form(self):
        self.client.force_login(self.user_a)
        response = self.client.get("/students/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'value="{self.cb.pk}"')

    def test_teacher_cannot_open_class_management(self):
        teacher = User.objects.create_user(username="synthetic_teacher", password="synthetic-test-pass-123")
        Membership.objects.create(user=teacher, school=self.a, role=Membership.Role.TEACHER)
        self.client.force_login(teacher)
        response = self.client.get("/classes/")
        self.assertEqual(response.status_code, 403)

    def test_attendance_is_school_scoped_and_saved(self):
        self.client.force_login(self.user_a)
        response = self.client.post("/attendance/", {
            "student": self.sa.pk, "date": "2026-10-27", "status": "present", "note": "",
        })
        self.assertRedirects(response, "/attendance/")
        self.assertTrue(AttendanceRecord.objects.filter(school=self.a, student=self.sa).exists())
        self.assertFalse(AttendanceRecord.objects.filter(school=self.b, student=self.sb).exists())

    def test_fee_entry_is_manual_and_school_scoped(self):
        self.client.force_login(self.user_a)
        response = self.client.post("/fees/", {
            "student": self.sa.pk, "title": "Term 1", "amount": "1000.00",
            "paid_amount": "250.00", "due_date": "2026-11-15", "status": "pending",
            "payment_reference": "MANUAL-TEST", "note": "",
        })
        self.assertRedirects(response, "/fees/")
        fee = FeeRecord.objects.get(school=self.a, student=self.sa)
        self.assertEqual(fee.paid_amount, 250)
        self.assertEqual(fee.balance, 750)
        self.assertEqual(fee.status, FeeRecord.Status.PARTIAL)
        self.assertFalse(FeeRecord.objects.filter(school=self.b).exists())
