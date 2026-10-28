from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from schools.models import ClassRoom, Membership, School, Student, SchoolSubscription


User = get_user_model()


class StudentCsvImportTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="CSV Import School", slug="csv-import-school")
        self.other_school = School.objects.create(name="CSV Other School", slug="csv-other-school")
        self.admin = User.objects.create_user(username="csv_import_admin", password="synthetic-test-pass-123")
        Membership.objects.create(user=self.admin, school=self.school, role=Membership.Role.SCHOOL_ADMIN)
        self.classroom = ClassRoom.objects.create(school=self.school, name="Class 4", section="A", academic_year="2026-2027")
        self.other_class = ClassRoom.objects.create(school=self.other_school, name="Class 4", section="A", academic_year="2026-2027")
        self.client.force_login(self.admin)

    def upload(self, csv_text, school=None):
        file = SimpleUploadedFile("students.csv", csv_text.encode("utf-8"), content_type="text/csv")
        return self.client.post("/students/import/", {"school": (school or self.school).pk, "csv_file": file})

    def test_valid_csv_imports_students(self):
        response = self.upload("admission_number,first_name,last_name,class_name,section,academic_year,date_of_birth,admitted_at,is_active\nCSV-001,Asha,Devi,Class 4,A,2026-2027,2016-08-12,2026-04-01,true\n")
        self.assertEqual(response.status_code, 302)
        student = Student.objects.get(school=self.school, admission_number="CSV-001")
        self.assertEqual(student.classroom, self.classroom)
        self.assertTrue(student.is_active)

    def test_invalid_row_means_no_partial_import(self):
        response = self.upload("admission_number,first_name,last_name,class_name,section,academic_year,date_of_birth,admitted_at,is_active\nCSV-002,Asha,Devi,Class 4,A,2026-2027,,,true\nCSV-003,Ravi,Kumar,Unknown,B,2026-2027,,,true\n")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Student.objects.filter(school=self.school).count(), 0)
        self.assertContains(response, "No rows were imported") if "duplicate" in response.content.decode().lower() else self.assertContains(response, "class/section/year")

    def test_duplicate_existing_admission_number_rejected(self):
        Student.objects.create(school=self.school, classroom=self.classroom, admission_number="EXISTS-1", first_name="Existing")
        response = self.upload("admission_number,first_name,last_name,class_name,section,academic_year,date_of_birth,admitted_at,is_active\nEXISTS-1,Another,Student,Class 4,A,2026-2027,,,true\n")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Student.objects.filter(school=self.school).count(), 1)
        self.assertContains(response, "duplicate admission number")

    def test_class_from_another_school_cannot_be_used(self):
        response = self.upload("admission_number,first_name,last_name,class_name,section,academic_year,date_of_birth,admitted_at,is_active\nCSV-004,Asha,Devi,Other Class,B,2026-2027,,,true\n")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Student.objects.filter(school=self.school).count(), 0)

    def test_teacher_cannot_import_students(self):
        teacher = User.objects.create_user(username="csv_import_teacher", password="synthetic-test-pass-123")
        Membership.objects.create(user=teacher, school=self.school, role=Membership.Role.TEACHER)
        self.client.force_login(teacher)
        response = self.client.get(f"/students/import/?school={self.school.pk}")
        self.assertEqual(response.status_code, 403)

    def test_student_limit_is_enforced(self):
        SchoolSubscription.objects.create(school=self.school, plan=SchoolSubscription.Plan.STARTER, status=SchoolSubscription.Status.ACTIVE, student_limit=1)
        response = self.upload("admission_number,first_name,last_name,class_name,section,academic_year,date_of_birth,admitted_at,is_active\nCSV-005,Asha,Devi,Class 4,A,2026-2027,,,true\nCSV-006,Ravi,Kumar,Class 4,A,2026-2027,,,true\n")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Student.objects.filter(school=self.school).count(), 0)
        self.assertContains(response, "plan limit of 1 students")
