# Generated for School Saathi academic, homework and notice modules.
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0002_attendance_fee_records"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Exam",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=160)),
                ("exam_date", models.DateField()),
                ("max_marks", models.DecimalField(decimal_places=2, default=100, max_digits=7)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("classroom", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="exams", to="schools.classroom")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exams", to="schools.school")),
            ],
            options={"ordering": ["-exam_date", "title"]},
        ),
        migrations.CreateModel(
            name="Homework",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=160)),
                ("instructions", models.TextField()),
                ("assigned_date", models.DateField(default=django.utils.timezone.localdate)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("is_published", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assigned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("classroom", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="homework_items", to="schools.classroom")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="homework_items", to="schools.school")),
            ],
            options={"ordering": ["-assigned_date", "title"]},
        ),
        migrations.CreateModel(
            name="Announcement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=160)),
                ("body", models.TextField()),
                ("audience", models.CharField(choices=[("everyone", "Everyone"), ("parents", "Parents"), ("students", "Students"), ("staff", "Staff")], default="everyone", max_length=12)),
                ("is_published", models.BooleanField(default=True)),
                ("published_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="announcements", to="schools.school")),
            ],
            options={"ordering": ["-published_at"]},
        ),
        migrations.CreateModel(
            name="ExamResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("marks_obtained", models.DecimalField(decimal_places=2, max_digits=7)),
                ("remarks", models.CharField(blank=True, max_length=250)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("entered_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("exam", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="results", to="schools.exam")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exam_results", to="schools.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exam_results", to="schools.student")),
            ],
            options={"ordering": ["student__first_name", "student__last_name"]},
        ),
        migrations.AddConstraint(
            model_name="exam",
            constraint=models.UniqueConstraint(fields=("school", "title", "classroom", "exam_date"), name="unique_exam_class_date"),
        ),
        migrations.AddConstraint(
            model_name="examresult",
            constraint=models.UniqueConstraint(fields=("exam", "student"), name="unique_result_per_exam_student"),
        ),
    ]
