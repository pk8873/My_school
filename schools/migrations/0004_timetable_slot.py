# Generated for the school-scoped weekly timetable.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0003_academic_homework_announcements"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TimetableSlot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject", models.CharField(max_length=100)),
                ("weekday", models.CharField(choices=[("mon", "Monday"), ("tue", "Tuesday"), ("wed", "Wednesday"), ("thu", "Thursday"), ("fri", "Friday"), ("sat", "Saturday"), ("sun", "Sunday")], max_length=3)),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("room", models.CharField(blank=True, max_length=40)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("classroom", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="timetable_slots", to="schools.classroom")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="timetable_slots", to="schools.school")),
                ("teacher", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="timetable_slots", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["weekday", "start_time", "classroom__name"]},
        ),
        migrations.AddConstraint(
            model_name="timetableslot",
            constraint=models.UniqueConstraint(fields=("school", "classroom", "weekday", "start_time"), name="unique_timetable_start_per_class"),
        ),
    ]
