from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import AttendanceRecord, ClassRoom, Membership, ParentStudentLink, School, Student

User = get_user_model()


class ParentStudentAttendanceHistoryTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Attendance Portal School", slug="attendance-portal")
        self.other_school = School.objects.create(name="Other Attendance School", slug="other-attendance")
        self.parent = User.objects.create_user(username="attendance_parent", password="test-pass-12345")
        self.student_user = User.objects.create_user(username="attendance_student", password="test-pass-12345")
        self.admin = User.objects.create_user(username="attendance_admin", password="test-pass-12345")
        Membership.objects.create(user=self.parent, school=self.school, role=Membership.Role.PARENT)
        Membership.objects.create(user=self.student_user, school=self.school, role=Membership.Role.STUDENT)
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        classroom = ClassRoom.objects.create(school=self.school, name="Class 6", section="A", academic_year="2026-2027")
        other_class = ClassRoom.objects.create(school=self.other_school, name="Class 6", section="A", academic_year="2026-2027")
        self.child = Student.objects.create(school=self.school, classroom=classroom, admission_number="ATT-1", first_name="Asha", portal_user=self.student_user)
        self.unlinked = Student.objects.create(school=self.school, classroom=classroom, admission_number="ATT-2", first_name="Ravi")
        self.foreign = Student.objects.create(school=self.other_school, classroom=other_class, admission_number="ATT-X", first_name="Foreign")
        ParentStudentLink.objects.create(parent=self.parent, student=self.child, relationship="Parent")
        AttendanceRecord.objects.create(school=self.school, student=self.child, date="2026-10-01", status=AttendanceRecord.Status.PRESENT)
        AttendanceRecord.objects.create(school=self.school, student=self.child, date="2026-10-02", status=AttendanceRecord.Status.ABSENT)
        AttendanceRecord.objects.create(school=self.school, student=self.unlinked, date="2026-10-02", status=AttendanceRecord.Status.LATE)
        AttendanceRecord.objects.create(school=self.other_school, student=self.foreign, date="2026-10-02", status=AttendanceRecord.Status.PRESENT)

    def test_parent_sees_only_linked_children_and_can_filter(self):
        self.client.force_login(self.parent)
        response = self.client.get(reverse("my_attendance_history"), {"school": self.school.pk, "status": "absent"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["summary"]["total"], 1)
        self.assertEqual(list(response.context["records"])[0].student_id, self.child.pk)

    def test_parent_cannot_select_unlinked_student(self):
        self.client.force_login(self.parent)
        response = self.client.get(reverse("my_attendance_history"), {"school": self.school.pk, "student": self.unlinked.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["summary"]["total"], 0)

    def test_student_sees_only_own_attendance(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("my_attendance_history"), {"school": self.school.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["summary"]["total"], 2)
        self.assertEqual({row.student_id for row in response.context["records"]}, {self.child.pk})

    def test_staff_cannot_open_family_attendance_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("my_attendance_history"), {"school": self.school.pk})
        self.assertEqual(response.status_code, 403)
