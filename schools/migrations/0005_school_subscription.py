# Add school subscription metadata for platform-level SaaS administration.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("schools", "0004_timetable_slot")]

    operations = [
        migrations.CreateModel(
            name="SchoolSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("plan", models.CharField(choices=[("starter", "Starter"), ("standard", "Standard"), ("premium", "Premium")], default="starter", max_length=16)),
                ("status", models.CharField(choices=[("trial", "Trial"), ("active", "Active"), ("past_due", "Past due"), ("suspended", "Suspended"), ("cancelled", "Cancelled")], default="trial", max_length=16)),
                ("student_limit", models.PositiveIntegerField(default=100)),
                ("trial_ends_at", models.DateField(blank=True, null=True)),
                ("period_ends_at", models.DateField(blank=True, null=True)),
                ("provider", models.CharField(blank=True, max_length=30)),
                ("provider_subscription_id", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="subscription", to="schools.school")),
            ],
            options={"ordering": ["school__name"]},
        ),
    ]
