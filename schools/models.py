from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

class School(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80, unique=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["name"]
    def __str__(self): return self.name

class Membership(models.Model):
    class Role(models.TextChoices):
        SCHOOL_ADMIN = "school_admin", "School Admin"
        PRINCIPAL = "principal", "Principal"
        TEACHER = "teacher", "Teacher"
        ACCOUNTANT = "accountant", "Accountant"
        PARENT = "parent", "Parent"
        STUDENT = "student", "Student"
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="school_memberships")
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "school"], name="unique_user_school_membership")]
        indexes = [models.Index(fields=["school", "role", "is_active"], name="schools_me_school__e89f75_idx")]

class ClassRoom(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="classrooms")
    name = models.CharField(max_length=80)
    section = models.CharField(max_length=30, blank=True)
    academic_year = models.CharField(max_length=9, help_text="Example: 2026-2027")
    class_teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="class_teacher_assignments")
    capacity = models.PositiveIntegerField(default=40)
    is_active = models.BooleanField(default=True)
    class Meta:
        ordering = ["academic_year", "name", "section"]
        constraints = [models.UniqueConstraint(fields=["school", "name", "section", "academic_year"], name="unique_class_section_year_per_school")]
        indexes = [models.Index(fields=["school", "academic_year"], name="schools_cl_school__d8c6f1_idx")]
    def __str__(self): return f"{self.name} {self.section}".strip()

class Student(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="students")
    classroom = models.ForeignKey(ClassRoom, on_delete=models.PROTECT, related_name="students")
    admission_number = models.CharField(max_length=40)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    admitted_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["first_name", "last_name"]
        constraints = [models.UniqueConstraint(fields=["school", "admission_number"], name="unique_admission_number_per_school")]
        indexes = [models.Index(fields=["school", "classroom", "is_active"], name="schools_st_school__a7bc6a_idx")]
    def clean(self):
        if self.classroom_id and self.school_id and self.classroom.school_id != self.school_id:
            raise ValidationError({"classroom": "Classroom must belong to the same school."})
    def __str__(self): return f"{self.first_name} {self.last_name}".strip()

class ParentStudentLink(models.Model):
    parent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="linked_children")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="parent_links")
    relationship = models.CharField(max_length=30, blank=True)
    can_view_fees = models.BooleanField(default=True)
    can_view_results = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["parent", "student"], name="unique_parent_student_link")]
        indexes = [models.Index(fields=["parent", "is_active"], name="schools_pa_parent__f19f65_idx")]


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        LATE = "late", "Late"
        LEAVE = "leave", "On leave"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="attendance_records")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    note = models.CharField(max_length=250, blank=True)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "student__first_name"]
        constraints = [models.UniqueConstraint(fields=["student", "date"], name="unique_student_attendance_date")]
        indexes = [models.Index(fields=["school", "date"], name="schools_at_school__date_idx")]

    def clean(self):
        if self.student_id and self.school_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "Student must belong to the same school."})

    def __str__(self):
        return f"{self.student} · {self.date} · {self.get_status_display()}"


class FeeRecord(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PARTIAL = "partial", "Partially paid"
        PAID = "paid", "Paid"
        WAIVED = "waived", "Waived"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="fee_records")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="fee_records")
    title = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    payment_reference = models.CharField(max_length=100, blank=True)
    note = models.CharField(max_length=250, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["status", "due_date", "student__first_name"]
        indexes = [models.Index(fields=["school", "status"], name="schools_fe_school__status_idx")]

    def clean(self):
        errors = {}
        if self.student_id and self.school_id and self.student.school_id != self.school_id:
            errors["student"] = "Student must belong to the same school."
        if self.amount is not None and self.amount < 0:
            errors["amount"] = "Amount cannot be negative."
        if self.paid_amount is not None and self.amount is not None and self.paid_amount > self.amount:
            errors["paid_amount"] = "Paid amount cannot exceed total amount."
        if errors:
            raise ValidationError(errors)

    @property
    def balance(self):
        return max(self.amount - self.paid_amount, 0)

    def __str__(self):
        return f"{self.student} · {self.title}"



class Exam(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="exams")
    title = models.CharField(max_length=160)
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, null=True, blank=True, related_name="exams")
    exam_date = models.DateField()
    max_marks = models.DecimalField(max_digits=7, decimal_places=2, default=100)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-exam_date", "title"]
        constraints = [models.UniqueConstraint(fields=["school", "title", "classroom", "exam_date"], name="unique_exam_class_date")]

    def clean(self):
        errors = {}
        if self.classroom_id and self.school_id and self.classroom.school_id != self.school_id:
            errors["classroom"] = "Classroom must belong to the same school."
        if self.max_marks is not None and self.max_marks <= 0:
            errors["max_marks"] = "Maximum marks must be greater than zero."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title


class ExamResult(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="exam_results")
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="results")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="exam_results")
    marks_obtained = models.DecimalField(max_digits=7, decimal_places=2)
    remarks = models.CharField(max_length=250, blank=True)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["student__first_name", "student__last_name"]
        constraints = [models.UniqueConstraint(fields=["exam", "student"], name="unique_result_per_exam_student")]

    def clean(self):
        errors = {}
        if self.exam_id and self.school_id and self.exam.school_id != self.school_id:
            errors["exam"] = "Exam must belong to the same school."
        if self.student_id and self.school_id and self.student.school_id != self.school_id:
            errors["student"] = "Student must belong to the same school."
        if self.exam_id and self.student_id and self.exam.classroom_id and self.student.classroom_id != self.exam.classroom_id:
            errors["student"] = "Student must belong to the exam classroom."
        if self.marks_obtained is not None and self.exam_id and self.marks_obtained > self.exam.max_marks:
            errors["marks_obtained"] = "Marks cannot exceed the exam maximum."
        if self.marks_obtained is not None and self.marks_obtained < 0:
            errors["marks_obtained"] = "Marks cannot be negative."
        if errors:
            raise ValidationError(errors)

    @property
    def percentage(self):
        return round(float(self.marks_obtained / self.exam.max_marks * 100), 2) if self.exam.max_marks else 0

    def __str__(self):
        return f"{self.student} · {self.exam}"


class Homework(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="homework_items")
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, null=True, blank=True, related_name="homework_items")
    title = models.CharField(max_length=160)
    instructions = models.TextField()
    assigned_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assigned_date", "title"]

    def clean(self):
        if self.classroom_id and self.school_id and self.classroom.school_id != self.school_id:
            raise ValidationError({"classroom": "Classroom must belong to the same school."})

    def __str__(self):
        return self.title


class Announcement(models.Model):
    class Audience(models.TextChoices):
        EVERYONE = "everyone", "Everyone"
        PARENTS = "parents", "Parents"
        STUDENTS = "students", "Students"
        STAFF = "staff", "Staff"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="announcements")
    title = models.CharField(max_length=160)
    body = models.TextField()
    audience = models.CharField(max_length=12, choices=Audience.choices, default=Audience.EVERYONE)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self):
        return self.title


class TimetableSlot(models.Model):
    class Weekday(models.TextChoices):
        MONDAY = "mon", "Monday"
        TUESDAY = "tue", "Tuesday"
        WEDNESDAY = "wed", "Wednesday"
        THURSDAY = "thu", "Thursday"
        FRIDAY = "fri", "Friday"
        SATURDAY = "sat", "Saturday"
        SUNDAY = "sun", "Sunday"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="timetable_slots")
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name="timetable_slots")
    subject = models.CharField(max_length=100)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="timetable_slots")
    weekday = models.CharField(max_length=3, choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=40, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["weekday", "start_time", "classroom__name"]
        constraints = [models.UniqueConstraint(fields=["school", "classroom", "weekday", "start_time"], name="unique_timetable_start_per_class")]

    def clean(self):
        errors = {}
        if self.classroom_id and self.school_id and self.classroom.school_id != self.school_id:
            errors["classroom"] = "Classroom must belong to the same school."
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            errors["end_time"] = "End time must be later than start time."
        if self.teacher_id and self.school_id and not self.teacher.school_memberships.filter(school_id=self.school_id, is_active=True, role=Membership.Role.TEACHER).exists():
            errors["teacher"] = "Teacher must have an active teacher membership in this school."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.classroom} · {self.subject} · {self.get_weekday_display()}"
