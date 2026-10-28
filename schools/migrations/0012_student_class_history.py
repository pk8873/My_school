# Generated for student promotion and class-change history.
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("schools", "0011_staff_attendance"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentClassHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("effective_date", models.DateField(default=django.utils.timezone.localdate)),
                ("note", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("from_classroom", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="student_promotions_from", to="schools.classroom")),
                ("to_classroom", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="student_promotions_to", to="schools.classroom")),
                ("promoted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="student_promotions_recorded", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="student_class_history", to="schools.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="class_history", to="schools.student")),
            ],
            options={
                "ordering": ["-effective_date", "-created_at"],
                "indexes": [
                    models.Index(fields=["school", "effective_date"], name="studclass_school_date_idx"),
                    models.Index(fields=["student", "effective_date"], name="studclass_student_date_idx"),
                ],
            },
        ),
    ]
