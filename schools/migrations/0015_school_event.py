import django.conf
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0014_announcement_read"),
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SchoolEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("location", models.CharField(blank=True, max_length=180)),
                ("audience", models.CharField(choices=[("everyone", "Everyone"), ("parents", "Parents"), ("students", "Students"), ("staff", "Staff")], default="everyone", max_length=12)),
                ("is_published", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="school_events_created", to=django.conf.settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="schools.school")),
            ],
            options={
                "ordering": ["starts_at", "pk"],
                "indexes": [models.Index(fields=["school", "is_published", "starts_at"], name="school_event_date_idx")],
            },
        ),
    ]
