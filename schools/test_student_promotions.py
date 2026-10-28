from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from schools.models import ClassRoom, Membership, School, Student, StudentClassHistory


User = get_user_model()


class StudentPromotionTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Promotion School", slug="promotion-school")
        self.other_school = School.objects.create(name="Other Promotion School", slug="other-promotion-school")
        self.admin = User.objects.create_user(username="promotion_admin", password="test-pass-12345")
        self.teacher = User.objects.create_user(username="promotion_teacher", password="test-pass-12345")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        Membership.objects.create(user=self.teacher, school=self.school, role=Membership.Role.TEACHER)
        self.source = ClassRoom.objects.create(school=self.school, name="Class 5", section="A", academic_year="2025-2026")
        self.target = ClassRoom.objects.create(school=self.school, name="Class 6", section="A", academic_year="2026-2027")
        self.foreign = ClassRoom.objects.create(school=self.other_school, name="Class 6", section="A", academic_year="2026-2027")
        Student.objects.create(school=self.school, classroom=self.source, admission_number="PROM-001", first_name="Asha")
        Student.objects.create(school=self.school, classroom=self.source, admission_number="PROM-002", first_name="Dev")
        Student.objects.create(school=self.other_school, classroom=self.foreign, admission_number="PRIVATE-001", first_name="Private")

    def test_admin_promotes_class_and_records_each_student(self):
        self.client.force_login(self.admin)
        response = self.client.post("/students/promotions/", {
            "school": self.school.pk,
            "from_classroom": self.source.pk,
            "to_classroom": self.target.pk,
            "effective_date": "2026-04-01",
            "note": "Promoted for next academic year",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Student.objects.filter(school=self.school, classroom=self.target, is_active=True).count(), 2)
        self.assertEqual(StudentClassHistory.objects.filter(school=self.school).count(), 2)
        history = StudentClassHistory.objects.filter(school=self.school).first()
        self.assertEqual(history.from_classroom, self.source)
        self.assertEqual(history.to_classroom, self.target)
        self.assertEqual(history.effective_date, date(2026, 4, 1))
        self.assertEqual(history.promoted_by, self.admin)
        self.assertEqual(Student.objects.get(admission_number="PRIVATE-001").classroom, self.foreign)

    def test_rejects_same_class_and_foreign_school_class(self):
        self.client.force_login(self.admin)
        same = self.client.post("/students/promotions/", {
            "school": self.school.pk, "from_classroom": self.source.pk,
            "to_classroom": self.source.pk, "effective_date": "2026-04-01",
        })
        foreign = self.client.post("/students/promotions/", {
            "school": self.school.pk, "from_classroom": self.source.pk,
            "to_classroom": self.foreign.pk, "effective_date": "2026-04-01",
        })
        self.assertEqual(same.status_code, 200)
        self.assertContains(same, "Choose a different destination class.")
        self.assertEqual(foreign.status_code, 200)
        self.assertContains(foreign, "does not belong to this school")
        self.assertEqual(StudentClassHistory.objects.count(), 0)
        self.assertEqual(Student.objects.filter(school=self.school, classroom=self.source).count(), 2)

    def test_only_management_roles_can_promote_students(self):
        self.client.force_login(self.teacher)
        response = self.client.post("/students/promotions/", {
            "school": self.school.pk, "from_classroom": self.source.pk,
            "to_classroom": self.target.pk, "effective_date": "2026-04-01",
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(StudentClassHistory.objects.count(), 0)
