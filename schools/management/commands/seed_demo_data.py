from datetime import timedelta, time
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from schools.models import (
    Announcement, AttendanceRecord, ClassRoom, Exam, ExamResult, FeeRecord,
    Homework, HomeworkSubmission, Membership, ParentStudentLink, School,
    SchoolSubscription, Student, TimetableSlot,
)


class Command(BaseCommand):
    help = "Create repeatable, clearly synthetic demo data for local development only."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo data is disabled when DEBUG=False. Run only in a local development environment.")
        User = get_user_model()
        today = timezone.localdate()

        def demo_user(username, email, first_name, last_name, role):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email, "first_name": first_name, "last_name": last_name},
            )
            if created:
                user.set_password("DemoPass123!")
                user.save(update_fields=["password"])
            Membership.objects.update_or_create(
                user=user, school=school,
                defaults={"role": role, "is_active": True},
            )
            return user, created

        school, _ = School.objects.get_or_create(
            slug="school-saathi-demo",
            defaults={
                "name": "School Saathi Demo School (Synthetic Data)",
                "email": "demo-school@example.test",
                "phone": "0000000000",
                "address": "Fictional demo address — not a real school",
                "is_active": True,
            },
        )
        SchoolSubscription.objects.update_or_create(
            school=school,
            defaults={
                "plan": SchoolSubscription.Plan.STANDARD,
                "status": SchoolSubscription.Status.TRIAL,
                "student_limit": 100,
                "trial_ends_at": today + timedelta(days=14),
            },
        )

        admin, admin_new = demo_user("demo_admin", "demo-admin@example.test", "Demo", "Administrator", Membership.Role.SCHOOL_ADMIN)
        teacher, teacher_new = demo_user("demo_teacher", "demo-teacher@example.test", "Demo", "Teacher", Membership.Role.TEACHER)
        parent, parent_new = demo_user("demo_parent", "demo-parent@example.test", "Demo", "Parent", Membership.Role.PARENT)
        pupil, pupil_new = demo_user("demo_student", "demo-student@example.test", "Demo", "Student", Membership.Role.STUDENT)

        classroom, _ = ClassRoom.objects.get_or_create(
            school=school, name="Class 5", section="A", academic_year=f"{today.year}-{today.year + 1}",
            defaults={"class_teacher": teacher, "capacity": 35, "is_active": True},
        )
        if classroom.class_teacher_id != teacher.pk:
            classroom.class_teacher = teacher
            classroom.save(update_fields=["class_teacher"])

        student_specs = [
            ("DEMO-001", "Aarav", "Sharma", pupil),
            ("DEMO-002", "Anaya", "Verma", None),
            ("DEMO-003", "Vivaan", "Patel", None),
        ]
        students = []
        for admission, first, last, portal_user in student_specs:
            student, _ = Student.objects.get_or_create(
                school=school, admission_number=admission,
                defaults={
                    "classroom": classroom, "first_name": first, "last_name": last,
                    "date_of_birth": today - timedelta(days=365 * 10),
                    "admitted_at": today - timedelta(days=60), "is_active": True,
                    "portal_user": portal_user,
                },
            )
            changed = []
            if student.classroom_id != classroom.pk:
                student.classroom = classroom
                changed.append("classroom")
            if portal_user and student.portal_user_id != portal_user.pk:
                student.portal_user = portal_user
                changed.append("portal_user")
            if changed:
                student.save(update_fields=changed)
            students.append(student)

        for student in students[:2]:
            ParentStudentLink.objects.update_or_create(
                parent=parent, student=student,
                defaults={"relationship": "Parent", "can_view_fees": True, "can_view_results": True, "is_active": True},
            )

        for index, student in enumerate(students):
            AttendanceRecord.objects.update_or_create(
                student=student, date=today - timedelta(days=1),
                defaults={"school": school, "status": AttendanceRecord.Status.ABSENT if index == 2 else AttendanceRecord.Status.PRESENT, "note": "Synthetic demo attendance", "marked_by": teacher},
            )
            amount = Decimal("12000.00")
            paid = [Decimal("12000.00"), Decimal("6000.00"), Decimal("0.00")][index]
            fee_status = FeeRecord.Status.PAID if paid >= amount else (FeeRecord.Status.PARTIAL if paid > 0 else FeeRecord.Status.PENDING)
            FeeRecord.objects.update_or_create(
                school=school, student=student, title="Demo Term Fee",
                defaults={"amount": amount, "paid_amount": paid, "due_date": today + timedelta(days=14), "status": fee_status, "payment_reference": f"DEMO-NOT-A-REAL-PAYMENT-{index + 1}", "note": "Synthetic sample record; no payment processed", "recorded_by": admin},
            )

        exam, _ = Exam.objects.get_or_create(
            school=school, title="Demo Term Examination", classroom=classroom, exam_date=today + timedelta(days=7),
            defaults={"max_marks": Decimal("100.00"), "created_by": teacher},
        )
        for student, marks in zip(students, [Decimal("88.00"), Decimal("76.00"), Decimal("63.00")]):
            result, _ = ExamResult.objects.get_or_create(
                school=school, exam=exam, student=student,
                defaults={"marks_obtained": marks, "remarks": "Synthetic example result", "entered_by": teacher},
            )
            result.full_clean()

        homework, _ = Homework.objects.get_or_create(
            school=school, classroom=classroom, title="Demo Science Homework",
            defaults={"instructions": "Write five sentences about the water cycle. This is sample content.", "assigned_date": today, "due_date": today + timedelta(days=5), "assigned_by": teacher, "is_published": True},
        )
        HomeworkSubmission.objects.update_or_create(
            school=school, homework=homework, student=students[0],
            defaults={"submission_text": "Demo answer: evaporation, condensation, precipitation and collection describe the water cycle.", "status": HomeworkSubmission.Status.SUBMITTED, "teacher_feedback": ""},
        )
        Announcement.objects.get_or_create(
            school=school, title="Welcome to the demo school",
            defaults={"body": "This notice and all linked records are synthetic test data. Do not use them as real school information.", "audience": Announcement.Audience.EVERYONE, "is_published": True, "created_by": admin},
        )
        for subject, start, end, room in [
            ("Mathematics", time(9, 0), time(9, 45), "Room 5A"),
            ("English", time(10, 0), time(10, 45), "Room 5A"),
            ("Science", time(11, 0), time(11, 45), "Lab Demo"),
        ]:
            TimetableSlot.objects.get_or_create(
                school=school, classroom=classroom, weekday=TimetableSlot.Weekday.MONDAY, start_time=start,
                defaults={"subject": subject, "teacher": teacher, "end_time": end, "room": room, "is_active": True},
            )

        self.stdout.write(self.style.SUCCESS("Synthetic demo data is ready. Re-running this command is safe and will not delete records."))
        self.stdout.write(f"School: {school.name} (slug: {school.slug})")
        self.stdout.write("Demo login password for newly created demo users: DemoPass123!")
        self.stdout.write("Usernames: demo_admin, demo_teacher, demo_parent, demo_student")
        self.stdout.write("Existing usernames keep their existing passwords. Never use these demo accounts in production.")
