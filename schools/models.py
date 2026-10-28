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
    portal_user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="student_portal_profile")
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


class AttendanceChangeLog(models.Model):
    """Immutable snapshot of attendance creation or correction."""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="attendance_change_logs")
    attendance = models.ForeignKey(AttendanceRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name="change_logs")
    student_name = models.CharField(max_length=220)
    admission_number = models.CharField(max_length=40)
    attendance_date = models.DateField()
    old_status = models.CharField(max_length=10, blank=True, choices=AttendanceRecord.Status.choices)
    new_status = models.CharField(max_length=10, choices=AttendanceRecord.Status.choices)
    old_note = models.CharField(max_length=250, blank=True)
    new_note = models.CharField(max_length=250, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_changes")
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        indexes = [models.Index(fields=["school", "attendance_date"], name="attlog_school_date_idx")]

    def __str__(self):
        return f"{self.student_name} · {self.attendance_date} · {self.old_status or 'new'} → {self.new_status}"


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



class FeePayment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        UPI = "upi", "UPI (manually verified)"
        BANK = "bank", "Bank transfer (manually verified)"
        CHEQUE = "cheque", "Cheque"
        OTHER = "other", "Other"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="fee_payments")
    fee_record = models.ForeignKey(FeeRecord, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(default=timezone.localdate)
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.CASH)
    reference = models.CharField(max_length=100, blank=True)
    note = models.CharField(max_length=250, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]
        indexes = [models.Index(fields=["school", "payment_date"], name="feepay_school_date_idx")]

    def clean(self):
        errors = {}
        if self.fee_record_id and self.school_id and self.fee_record.school_id != self.school_id:
            errors["fee_record"] = "Fee entry must belong to the same school."
        if self.amount is not None and self.amount <= 0:
            errors["amount"] = "Payment amount must be greater than zero."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.fee_record} · {self.amount} · {self.payment_date}"



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


class HomeworkSubmission(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        REVIEWED = "reviewed", "Reviewed"
        NEEDS_WORK = "needs_work", "Needs improvement"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="homework_submissions")
    homework = models.ForeignKey(Homework, on_delete=models.CASCADE, related_name="submissions")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="homework_submissions")
    submission_text = models.TextField()
    submitted_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUBMITTED)
    teacher_feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="graded_homework_submissions")
    graded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(fields=["homework", "student"], name="unique_homework_submission_per_student"),
        ]
        indexes = [
            models.Index(fields=["school", "status"], name="hwsub_school_status_idx"),
        ]

    def clean(self):
        errors = {}
        if self.homework_id and self.school_id and self.homework.school_id != self.school_id:
            errors["homework"] = "Homework must belong to the same school."
        if self.student_id and self.school_id and self.student.school_id != self.school_id:
            errors["student"] = "Student must belong to the same school."
        if self.homework_id and self.student_id and self.homework.classroom_id and self.student.classroom_id != self.homework.classroom_id:
            errors["student"] = "Student must belong to the homework classroom."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.homework.title} · {self.student}"


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


class SchoolSubscription(models.Model):
    class Plan(models.TextChoices):
        STARTER = "starter", "Starter"
        STANDARD = "standard", "Standard"
        PREMIUM = "premium", "Premium"

    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        SUSPENDED = "suspended", "Suspended"
        CANCELLED = "cancelled", "Cancelled"

    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name="subscription")
    plan = models.CharField(max_length=16, choices=Plan.choices, default=Plan.STARTER)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TRIAL)
    student_limit = models.PositiveIntegerField(default=100)
    trial_ends_at = models.DateField(null=True, blank=True)
    period_ends_at = models.DateField(null=True, blank=True)
    provider = models.CharField(max_length=30, blank=True)
    provider_subscription_id = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["school__name"]

    def __str__(self):
        return f"{self.school.name} · {self.get_plan_display()} · {self.get_status_display()}"


class StaffAttendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        LATE = "late", "Late"
        LEAVE = "leave", "On leave"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="staff_attendance_records")
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_attendance_records")
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    note = models.CharField(max_length=250, blank=True)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="marked_staff_attendance")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "staff__username"]
        constraints = [
            models.UniqueConstraint(fields=["school", "staff", "date"], name="unique_staff_attendance_day"),
        ]
        indexes = [
            models.Index(fields=["school", "date"], name="staffatt_school_date_idx"),
            models.Index(fields=["staff", "date"], name="staffatt_user_date_idx"),
        ]

    def clean(self):
        errors = {}
        if self.staff_id and self.school_id and not self.staff.school_memberships.filter(
            school_id=self.school_id, is_active=True,
            role__in=[Membership.Role.SCHOOL_ADMIN, Membership.Role.PRINCIPAL, Membership.Role.TEACHER, Membership.Role.ACCOUNTANT],
        ).exists():
            errors["staff"] = "Staff member must have an active staff membership in this school."
        if self.marked_by_id and self.school_id and not self.marked_by.school_memberships.filter(
            school_id=self.school_id, is_active=True,
            role__in=[Membership.Role.SCHOOL_ADMIN, Membership.Role.PRINCIPAL],
        ).exists():
            errors["marked_by"] = "Attendance must be marked by an active school admin or principal."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.staff} · {self.date} · {self.get_status_display()}"


class StaffLeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="staff_leave_requests")
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_leave_requests")
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(max_length=2000)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    review_note = models.CharField(max_length=500, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_staff_leave_requests")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["school", "status", "start_date"], name="staffleave_school_status_idx"),
            models.Index(fields=["requester", "status"], name="staffleave_user_status_idx"),
        ]

    def clean(self):
        errors = {}
        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors["end_date"] = "End date must be on or after the start date."
        if self.requester_id and self.school_id and not self.requester.school_memberships.filter(
            school_id=self.school_id, is_active=True
        ).exists():
            errors["requester"] = "Requester must have an active membership in this school."
        if self.reviewed_by_id and self.school_id and not self.reviewed_by.school_memberships.filter(
            school_id=self.school_id, is_active=True, role__in=[Membership.Role.SCHOOL_ADMIN, Membership.Role.PRINCIPAL]
        ).exists():
            errors["reviewed_by"] = "Reviewer must be an active school admin or principal."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.requester} · {self.start_date} to {self.end_date} · {self.get_status_display()}"


class StudentClassHistory(models.Model):
    """Auditable record of a student's class change or promotion."""

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="student_class_history")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="class_history")
    from_classroom = models.ForeignKey(ClassRoom, on_delete=models.PROTECT, related_name="student_promotions_from")
    to_classroom = models.ForeignKey(ClassRoom, on_delete=models.PROTECT, related_name="student_promotions_to")
    effective_date = models.DateField(default=timezone.localdate)
    promoted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="student_promotions_recorded")
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_date", "-created_at"]
        indexes = [
            models.Index(fields=["school", "effective_date"], name="studclass_school_date_idx"),
            models.Index(fields=["student", "effective_date"], name="studclass_student_date_idx"),
        ]

    def clean(self):
        errors = {}
        if self.student_id and self.school_id and self.student.school_id != self.school_id:
            errors["student"] = "Student must belong to the selected school."
        if self.from_classroom_id and self.school_id and self.from_classroom.school_id != self.school_id:
            errors["from_classroom"] = "Previous class must belong to the selected school."
        if self.to_classroom_id and self.school_id and self.to_classroom.school_id != self.school_id:
            errors["to_classroom"] = "New class must belong to the selected school."
        if self.from_classroom_id and self.to_classroom_id and self.from_classroom_id == self.to_classroom_id:
            errors["to_classroom"] = "Student must move to a different class."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.student} · {self.from_classroom} → {self.to_classroom} · {self.effective_date}"

class TransferCertificate(models.Model):
    class Status(models.TextChoices):
        ISSUED = "issued", "Issued"
        CANCELLED = "cancelled", "Cancelled"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="transfer_certificates")
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="transfer_certificates")
    certificate_number = models.CharField(max_length=40)
    issue_date = models.DateField(default=timezone.localdate)
    leaving_date = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=250, blank=True)
    conduct = models.CharField(max_length=100, blank=True)
    remarks = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ISSUED)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="transfer_certificates_issued")
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="transfer_certificates_cancelled")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issue_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["school", "certificate_number"], name="unique_tc_number_per_school"),
        ]
        indexes = [
            models.Index(fields=["school", "status", "issue_date"], name="tc_school_status_date_idx"),
        ]

    def clean(self):
        errors = {}
        if self.student_id and self.school_id and self.student.school_id != self.school_id:
            errors["student"] = "Student must belong to the selected school."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.certificate_number} · {self.student}"

class AnnouncementRead(models.Model):
    """Per-user read receipt for a published school announcement."""
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="read_receipts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="announcement_reads")
    read_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["announcement", "user"], name="unique_announcement_read_user"),
        ]
        indexes = [
            models.Index(fields=["user", "read_at"], name="announce_read_user_date_idx"),
        ]

    def __str__(self):
        return f"{self.user} read {self.announcement}"

class SchoolEvent(models.Model):
    class Audience(models.TextChoices):
        EVERYONE = "everyone", "Everyone"
        PARENTS = "parents", "Parents"
        STUDENTS = "students", "Students"
        STAFF = "staff", "Staff"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="events")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=180, blank=True)
    audience = models.CharField(max_length=12, choices=Audience.choices, default=Audience.EVERYONE)
    is_published = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="school_events_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at", "pk"]
        indexes = [
            models.Index(fields=["school", "is_published", "starts_at"], name="school_event_date_idx"),
        ]

    def clean(self):
        errors = {}
        if self.starts_at and self.ends_at and self.ends_at < self.starts_at:
            errors["ends_at"] = "Event end must be after its start."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title

class SchoolEventRSVP(models.Model):
    class Response(models.TextChoices):
        ATTENDING = "attending", "Attending"
        NOT_ATTENDING = "not_attending", "Not attending"

    event = models.ForeignKey(SchoolEvent, on_delete=models.CASCADE, related_name="rsvps")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="school_event_rsvps")
    response = models.CharField(max_length=16, choices=Response.choices)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["event", "user"], name="unique_school_event_rsvp"),
        ]
        indexes = [
            models.Index(fields=["event", "response"], name="school_event_rsvp_idx"),
        ]

    def __str__(self):
        return f"{self.user}: {self.event} ({self.response})"

