# Adds a school-scoped audit trail for attendance creation and corrections.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0007_homework_submission"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AttendanceChangeLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("student_name", models.CharField(max_length=220)),
                ("admission_number", models.CharField(max_length=40)),
                ("attendance_date", models.DateField()),
                ("old_status", models.CharField(blank=True, choices=[("present", "Present"), ("absent", "Absent"), ("late", "Late"), ("leave", "On leave")], max_length=10)),
                ("new_status", models.CharField(choices=[("present", "Present"), ("absent", "Absent"), ("late", "Late"), ("leave", "On leave")], max_length=10)),
                ("old_note", models.CharField(blank=True, max_length=250)),
                ("new_note", models.CharField(blank=True, max_length=250)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                ("attendance", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="change_logs", to="schools.attendancerecord")),
                ("changed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="attendance_changes", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance_change_logs", to="schools.school")),
            ],
            options={"ordering": ["-changed_at"]},
        ),
        migrations.AddIndex(
            model_name="attendancechangelog",
            index=models.Index(fields=["school", "attendance_date"], name="attlog_school_date_idx"),
        ),
    ]
