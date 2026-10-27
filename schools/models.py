from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

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
        indexes = [models.Index(fields=["school", "role", "is_active"])]

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
        indexes = [models.Index(fields=["school", "academic_year"])]
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
        indexes = [models.Index(fields=["school", "classroom", "is_active"])]
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
        indexes = [models.Index(fields=["parent", "is_active"])]
