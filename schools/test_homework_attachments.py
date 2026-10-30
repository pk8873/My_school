from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import ClassRoom, Homework, Membership, School, Student
from .uploads import validate_school_attachment

User = get_user_model()


class HomeworkAttachmentTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Attachment School", slug="attachment-school")
        self.other_school = School.objects.create(name="Other Attachment School", slug="other-attachment-school")
        self.classroom = ClassRoom.objects.create(
            school=self.school, name="Class 7", section="A", academic_year="2026-2027"
        )
        self.other_classroom = ClassRoom.objects.create(
            school=self.other_school, name="Class 7", section="A", academic_year="2026-2027"
        )
        self.teacher = User.objects.create_user(
            username="attachment_teacher", password="synthetic-test-pass-123"
        )
        Membership.objects.create(
            user=self.teacher, school=self.school, role=Membership.Role.TEACHER
        )
        self.student_user = User.objects.create_user(
            username="attachment_student", password="synthetic-test-pass-123"
        )
        Membership.objects.create(
            user=self.student_user, school=self.school, role=Membership.Role.STUDENT
        )
        self.student = Student.objects.create(
            school=self.school, classroom=self.classroom, portal_user=self.student_user,
            admission_number="ATT-001", first_name="Synthetic Student",
        )
        self.homework = Homework.objects.create(
            school=self.school, classroom=self.classroom, title="Read chapter",
            instructions="Read the attached worksheet.", assigned_by=self.teacher,
            is_published=True,
            attachment=SimpleUploadedFile(
                "worksheet.pdf", b"%PDF-1.4\nsynthetic pdf content", content_type="application/pdf"
            ),
        )

    def test_allowed_pdf_signature_is_accepted(self):
        upload = SimpleUploadedFile("worksheet.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        validate_school_attachment(upload)

    def test_disallowed_extension_is_rejected(self):
        upload = SimpleUploadedFile("script.exe", b"MZ fake executable")
        with self.assertRaises(ValidationError):
            validate_school_attachment(upload)

    def test_mismatched_file_signature_is_rejected(self):
        upload = SimpleUploadedFile("fake.pdf", b"not a pdf")
        with self.assertRaises(ValidationError):
            validate_school_attachment(upload)

    def test_student_can_download_published_homework_for_own_class(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("homework_attachment_download", args=[self.homework.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertIn("attachment;", response["Content-Disposition"])

    def test_other_school_member_cannot_download_homework_attachment(self):
        outsider = User.objects.create_user(
            username="other_school_admin", password="synthetic-test-pass-123"
        )
        Membership.objects.create(
            user=outsider, school=self.other_school, role=Membership.Role.SCHOOL_ADMIN
        )
        self.client.force_login(outsider)
        response = self.client.get(reverse("homework_attachment_download", args=[self.homework.pk]))
        self.assertEqual(response.status_code, 404)

    def test_unpublished_homework_is_not_visible_to_student_download(self):
        self.homework.is_published = False
        self.homework.save()
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("homework_attachment_download", args=[self.homework.pk]))
        self.assertEqual(response.status_code, 404)
