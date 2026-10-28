from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("schools", "0010_staff_leave_request"),
    ]

    operations = [
        migrations.CreateModel(
            name="StaffAttendance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("status", models.CharField(choices=[("present", "Present"), ("absent", "Absent"), ("late", "Late"), ("leave", "On leave")], default="present", max_length=10)),
                ("note", models.CharField(blank=True, max_length=250)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="staff_attendance_records", to="schools.school")),
                ("staff", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="staff_attendance_records", to=settings.AUTH_USER_MODEL)),
                ("marked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="marked_staff_attendance", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-date", "staff__username"]},
        ),
        migrations.AddConstraint(
            model_name="staffattendance",
            constraint=models.UniqueConstraint(fields=("school", "staff", "date"), name="unique_staff_attendance_day"),
        ),
        migrations.AddIndex(
            model_name="staffattendance",
            index=models.Index(fields=["school", "date"], name="staffatt_school_date_idx"),
        ),
        migrations.AddIndex(
            model_name="staffattendance",
            index=models.Index(fields=["staff", "date"], name="staffatt_user_date_idx"),
        ),
    ]
