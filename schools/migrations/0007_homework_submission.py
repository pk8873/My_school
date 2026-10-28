# Adds student homework submission and teacher feedback workflow.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0006_student_portal_user"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HomeworkSubmission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("submission_text", models.TextField()),
                ("submitted_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(choices=[("submitted", "Submitted"), ("reviewed", "Reviewed"), ("needs_work", "Needs improvement")], default="submitted", max_length=16)),
                ("teacher_feedback", models.TextField(blank=True)),
                ("graded_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("graded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="graded_homework_submissions", to=settings.AUTH_USER_MODEL)),
                ("homework", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="submissions", to="schools.homework")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="homework_submissions", to="schools.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="homework_submissions", to="schools.student")),
            ],
            options={"ordering": ["-submitted_at"]},
        ),
        migrations.AddConstraint(
            model_name="homeworksubmission",
            constraint=models.UniqueConstraint(fields=("homework", "student"), name="unique_homework_submission_per_student"),
        ),
        migrations.AddIndex(
            model_name="homeworksubmission",
            index=models.Index(fields=["school", "status"], name="hwsub_school_status_idx"),
        ),
    ]
