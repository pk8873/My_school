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

    def test_service_worker_is_available_at_root_scope(self):
        response = self.client.get("/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertContains(response, "Never cache authenticated HTML")

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
            "capacity": "35", "onboard-is_active": "on",
        })
        self.assertRedirects(response, f"/classes/?school={self.a.pk}")
        self.assertTrue(ClassRoom.objects.filter(school=self.a, name="Class 6").exists())
        self.assertFalse(ClassRoom.objects.filter(school=self.b, name="Class 6").exists())

    def test_school_admin_can_create_student_only_in_own_class(self):
        self.client.force_login(self.user_a)
        response = self.client.post("/students/", {
            "classroom": self.ca.pk, "admission_number": "A-002",
            "first_name": "New", "last_name": "Synthetic", "is_active": "on",
        })
        self.assertRedirects(response, f"/students/?school={self.a.pk}")
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
        self.assertRedirects(response, f"/attendance/?school={self.a.pk}")
        self.assertTrue(AttendanceRecord.objects.filter(school=self.a, student=self.sa).exists())
        self.assertFalse(AttendanceRecord.objects.filter(school=self.b, student=self.sb).exists())

    def test_fee_entry_is_manual_and_school_scoped(self):
        self.client.force_login(self.user_a)
        response = self.client.post("/fees/", {
            "student": self.sa.pk, "title": "Term 1", "amount": "1000.00",
            "paid_amount": "250.00", "due_date": "2026-11-15", "status": "pending",
            "payment_reference": "MANUAL-TEST", "note": "",
        })
        self.assertRedirects(response, f"/fees/?school={self.a.pk}")
        fee = FeeRecord.objects.get(school=self.a, student=self.sa)
        self.assertEqual(fee.paid_amount, 250)
        self.assertEqual(fee.balance, 750)
        self.assertEqual(fee.status, FeeRecord.Status.PARTIAL)
        self.assertFalse(FeeRecord.objects.filter(school=self.b).exists())


    def test_teacher_can_create_exam_only_for_own_school(self):
        teacher = User.objects.create_user(username="synthetic_teacher_exam", password="synthetic-test-pass-123")
        Membership.objects.create(user=teacher, school=self.a, role=Membership.Role.TEACHER)
        self.client.force_login(teacher)
        response = self.client.post("/academics/", {
            "action": "exam", "exam-title": "Synthetic Midterm",
            "exam-classroom": str(self.ca.pk), "exam-exam_date": "2026-11-10",
            "exam-max_marks": "50",
        })
        self.assertRedirects(response, f"/academics/?school={self.a.pk}")
        from .models import Exam
        self.assertTrue(Exam.objects.filter(school=self.a, title="Synthetic Midterm").exists())
        self.assertFalse(Exam.objects.filter(school=self.b, title="Synthetic Midterm").exists())

    def test_academics_page_is_available_to_school_member(self):
        self.client.force_login(self.user_a)
        response = self.client.get("/academics/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create exam")
        self.assertContains(response, "Assign homework")

    def test_parent_cannot_see_another_school_child_results(self):
        from .models import Exam, ExamResult
        parent = User.objects.create_user(username="synthetic_parent_results", password="synthetic-test-pass-123")
        Membership.objects.create(user=parent, school=self.a, role=Membership.Role.PARENT)
        ParentStudentLink.objects.create(parent=parent, student=self.sa, can_view_results=True)
        exam_a = Exam.objects.create(school=self.a, title="Alpha exam", classroom=self.ca, exam_date="2026-10-01", max_marks=100)
        ExamResult.objects.create(school=self.a, exam=exam_a, student=self.sa, marks_obtained=85)
        exam_b = Exam.objects.create(school=self.b, title="Beta exam", classroom=self.cb, exam_date="2026-10-01", max_marks=100)
        ExamResult.objects.create(school=self.b, exam=exam_b, student=self.sb, marks_obtained=99)
        self.client.force_login(parent)
        response = self.client.get("/academics/")
        self.assertContains(response, "Alpha exam")
        self.assertNotContains(response, "Beta exam")


    def test_school_admin_can_create_timetable_slot(self):
        teacher = User.objects.create_user(username="synthetic_timetable_teacher", password="synthetic-test-pass-123")
        Membership.objects.create(user=teacher, school=self.a, role=Membership.Role.TEACHER)
        self.client.force_login(self.user_a)
        response = self.client.post("/timetable/", {
            "classroom": str(self.ca.pk), "subject": "Mathematics", "teacher": str(teacher.pk),
            "weekday": "mon", "start_time": "09:00", "end_time": "09:45",
            "room": "Room 5", "is_active": "on",
        })
        self.assertRedirects(response, f"/timetable/?school={self.a.pk}")
        from .models import TimetableSlot
        self.assertTrue(TimetableSlot.objects.filter(school=self.a, classroom=self.ca, subject="Mathematics").exists())
        self.assertFalse(TimetableSlot.objects.filter(school=self.b).exists())

    def test_timetable_rejects_end_time_before_start_time(self):
        from .models import TimetableSlot
        slot = TimetableSlot(
            school=self.a, classroom=self.ca, subject="Science", weekday="mon",
            start_time="10:00", end_time="09:00",
        )
        with self.assertRaises(ValidationError):
            slot.full_clean()


    def test_student_csv_export_is_tenant_scoped(self):
        self.client.force_login(self.user_a)
        response = self.client.get(f"/reports/students.csv?school={self.a.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        content = response.content.decode("utf-8-sig")
        self.assertIn("Synthetic Alpha", content)
        self.assertNotIn("Synthetic Beta", content)

    def test_parent_cannot_export_school_student_register(self):
        parent = User.objects.create_user(username="synthetic_parent_export", password="synthetic-test-pass-123")
        Membership.objects.create(user=parent, school=self.a, role=Membership.Role.PARENT)
        self.client.force_login(parent)
        response = self.client.get(f"/reports/students.csv?school={self.a.pk}")
        self.assertEqual(response.status_code, 403)


    def test_only_superuser_can_open_platform_onboarding(self):
        self.client.force_login(self.user_a)
        response = self.client.get("/platform/")
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_onboard_school_and_admin_atomically(self):
        platform_user = User.objects.create_superuser(username="platform_root", email="root@example.test", password="synthetic-test-pass-123")
        self.client.force_login(platform_user)
        response = self.client.post("/platform/", {
            "action": "onboard", "onboard-name": "Synthetic New School", "onboard-slug": "synthetic-new-school",
            "onboard-email": "school@example.test", "onboard-phone": "", "onboard-address": "",
            "onboard-is_active": "on", "onboard-admin_username": "synthetic_new_admin",
            "onboard-admin_email": "admin@example.test", "onboard-admin_password": "synthetic-admin-pass-123",
            "onboard-plan": "starter", "onboard-student_limit": "25", "onboard-trial_days": "14",
        })
        self.assertRedirects(response, "/platform/")
        school = School.objects.get(slug="synthetic-new-school")
        admin_user = User.objects.get(username="synthetic_new_admin")
        self.assertTrue(Membership.objects.filter(user=admin_user, school=school, role=Membership.Role.SCHOOL_ADMIN).exists())
        from .models import SchoolSubscription
        self.assertEqual(school.subscription.student_limit, 25)
        self.assertEqual(school.subscription.status, SchoolSubscription.Status.TRIAL)

    def test_management_can_create_school_scoped_staff_account(self):
        self.client.force_login(self.user_a)
        response = self.client.post(f"/staff/?school={self.a.pk}", {
            "action": "create_staff", "school": str(self.a.pk),
            "username": "synthetic_new_teacher", "email": "teacher@example.test",
            "first_name": "Synthetic", "last_name": "Teacher",
            "password": "synthetic-teacher-pass-123", "role": "teacher",
        })
        self.assertRedirects(response, f"/staff/?school={self.a.pk}")
        teacher = User.objects.get(username="synthetic_new_teacher")
        self.assertTrue(Membership.objects.filter(user=teacher, school=self.a, role=Membership.Role.TEACHER).exists())
        self.assertFalse(Membership.objects.filter(user=teacher, school=self.b).exists())

    def test_management_can_link_parent_only_within_school(self):
        parent = User.objects.create_user(username="synthetic_link_parent", password="synthetic-test-pass-123")
        Membership.objects.create(user=parent, school=self.a, role=Membership.Role.PARENT)
        self.client.force_login(self.user_a)
        response = self.client.post(f"/staff/?school={self.a.pk}", {
            "action": "link_parent", "school": str(self.a.pk),
            "link-parent_username": parent.username, "link-student": str(self.sa.pk),
            "link-relationship": "Mother", "link-can_view_fees": "on",
            "link-can_view_results": "on", "link-is_active": "on",
        })
        self.assertRedirects(response, f"/staff/?school={self.a.pk}")
        self.assertTrue(ParentStudentLink.objects.filter(parent=parent, student=self.sa, is_active=True).exists())

    def test_management_can_link_student_account_and_student_sees_only_own_profile(self):
        student_user = User.objects.create_user(username="synthetic_student_portal", password="synthetic-test-pass-123")
        Membership.objects.create(user=student_user, school=self.a, role=Membership.Role.STUDENT)
        self.client.force_login(self.user_a)
        response = self.client.post(f"/staff/?school={self.a.pk}", {
            "action": "link_student", "school": str(self.a.pk),
            "student_link-student": str(self.sa.pk),
            "student_link-student_username": student_user.username,
        })
        self.assertRedirects(response, f"/staff/?school={self.a.pk}")
        self.client.force_login(student_user)
        response = self.client.get(f"/dashboard/?school={self.a.pk}")
        self.assertContains(response, "Synthetic Alpha")
        self.assertNotContains(response, "Synthetic Beta")

    def test_student_limit_blocks_new_admission(self):
        from .models import SchoolSubscription
        SchoolSubscription.objects.create(school=self.a, plan="starter", status="trial", student_limit=1)
        self.client.force_login(self.user_a)
        response = self.client.post(f"/students/?school={self.a.pk}", {
            "school": str(self.a.pk), "classroom": str(self.ca.pk), "admission_number": "A-002",
            "first_name": "Second", "last_name": "Synthetic", "date_of_birth": "",
            "admitted_at": "", "is_active": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "plan limit")
        self.assertFalse(Student.objects.filter(school=self.a, admission_number="A-002").exists())



    def test_staff_can_download_school_scoped_student_report_card_pdf(self):
        from .models import Exam, ExamResult
        exam = Exam.objects.create(school=self.a, title="Synthetic Term Exam", classroom=self.ca, exam_date="2026-10-01", max_marks=100)
        ExamResult.objects.create(school=self.a, exam=exam, student=self.sa, marks_obtained=87)
        self.client.force_login(self.user_a)
        response = self.client.get(f"/students/{self.sa.pk}/report-card.pdf?school={self.a.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(b"%PDF", response.content[:10])
        self.assertNotIn(b"Synthetic Beta", response.content)

    def test_parent_cannot_download_report_card_without_permission(self):
        parent = User.objects.create_user(username="synthetic_no_report_parent", password="synthetic-test-pass-123")
        Membership.objects.create(user=parent, school=self.a, role=Membership.Role.PARENT)
        ParentStudentLink.objects.create(parent=parent, student=self.sa, can_view_results=False)
        self.client.force_login(parent)
        response = self.client.get(f"/students/{self.sa.pk}/report-card.pdf?school={self.a.pk}")
        self.assertEqual(response.status_code, 403)

    def test_parent_can_download_fee_statement_only_for_linked_child_with_permission(self):
        parent = User.objects.create_user(username="synthetic_fee_parent", password="synthetic-test-pass-123")
        Membership.objects.create(user=parent, school=self.a, role=Membership.Role.PARENT)
        ParentStudentLink.objects.create(parent=parent, student=self.sa, can_view_fees=True)
        FeeRecord.objects.create(school=self.a, student=self.sa, title="Synthetic Term Fee", amount="1000.00", paid_amount="300.00")
        self.client.force_login(parent)
        response = self.client.get(f"/students/{self.sa.pk}/fee-statement.pdf?school={self.a.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(b"%PDF", response.content[:10])

    def test_fee_statement_pdf_cannot_cross_school_boundary(self):
        self.client.force_login(self.user_a)
        response = self.client.get(f"/students/{self.sb.pk}/fee-statement.pdf?school={self.a.pk}")
        self.assertEqual(response.status_code, 404)


    def test_platform_admin_can_update_subscription_plan_metadata(self):
        from .models import SchoolSubscription
        SchoolSubscription.objects.create(school=self.a, plan="starter", status="trial", student_limit=20)
        platform_user = User.objects.create_superuser(username="platform_plan_admin", email="plan@example.test", password="synthetic-test-pass-123")
        self.client.force_login(platform_user)
        response = self.client.post("/platform/", {
            "action": "update_subscription", "school_id": str(self.a.pk),
            f"sub-{self.a.pk}-plan": "standard",
            f"sub-{self.a.pk}-status": "active",
            f"sub-{self.a.pk}-student_limit": "250",
            f"sub-{self.a.pk}-trial_ends_at": "",
            f"sub-{self.a.pk}-period_ends_at": "2027-10-01",
        })
        self.assertRedirects(response, "/platform/")
        subscription = SchoolSubscription.objects.get(school=self.a)
        self.assertEqual(subscription.plan, "standard")
        self.assertEqual(subscription.student_limit, 250)
        self.assertEqual(subscription.status, "active")
