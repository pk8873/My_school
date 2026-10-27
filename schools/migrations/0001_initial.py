# Generated for School Saathi initial tenant schema.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="School",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("address", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="ClassRoom",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("section", models.CharField(blank=True, max_length=30)),
                ("academic_year", models.CharField(help_text="Example: 2026-2027", max_length=9)),
                ("capacity", models.PositiveIntegerField(default=40)),
                ("is_active", models.BooleanField(default=True)),
                ("class_teacher", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="class_teacher_assignments", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="classrooms", to="schools.school")),
            ],
            options={"ordering": ["academic_year", "name", "section"]},
        ),
        migrations.CreateModel(
            name="Membership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("school_admin", "School Admin"), ("principal", "Principal"), ("teacher", "Teacher"), ("accountant", "Accountant"), ("parent", "Parent"), ("student", "Student")], max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="schools.school")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="school_memberships", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Student",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("admission_number", models.CharField(max_length=40)),
                ("first_name", models.CharField(max_length=100)),
                ("last_name", models.CharField(blank=True, max_length=100)),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("admitted_at", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("classroom", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="students", to="schools.classroom")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="students", to="schools.school")),
            ],
            options={"ordering": ["first_name", "last_name"]},
        ),
        migrations.CreateModel(
            name="ParentStudentLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("relationship", models.CharField(blank=True, max_length=30)),
                ("can_view_fees", models.BooleanField(default=True)),
                ("can_view_results", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("parent", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="linked_children", to=settings.AUTH_USER_MODEL)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="parent_links", to="schools.student")),
            ],
        ),
        migrations.AddConstraint(model_name="classroom", constraint=models.UniqueConstraint(fields=("school", "name", "section", "academic_year"), name="unique_class_section_year_per_school")),
        migrations.AddIndex(model_name="classroom", index=models.Index(fields=["school", "academic_year"], name="schools_cl_school__d8c6f1_idx")),
        migrations.AddConstraint(model_name="membership", constraint=models.UniqueConstraint(fields=("user", "school"), name="unique_user_school_membership")),
        migrations.AddIndex(model_name="membership", index=models.Index(fields=["school", "role", "is_active"], name="schools_me_school__e89f75_idx")),
        migrations.AddConstraint(model_name="student", constraint=models.UniqueConstraint(fields=("school", "admission_number"), name="unique_admission_number_per_school")),
        migrations.AddIndex(model_name="student", index=models.Index(fields=["school", "classroom", "is_active"], name="schools_st_school__a7bc6a_idx")),
        migrations.AddConstraint(model_name="parentstudentlink", constraint=models.UniqueConstraint(fields=("parent", "student"), name="unique_parent_student_link")),
        migrations.AddIndex(model_name="parentstudentlink", index=models.Index(fields=["parent", "is_active"], name="schools_pa_parent__f19f65_idx")),
    ]
