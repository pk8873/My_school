from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0015_school_event"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SchoolEventRSVP",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("response", models.CharField(choices=[("attending", "Attending"), ("not_attending", "Not attending")], max_length=16)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rsvps", to="schools.schoolevent")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="school_event_rsvps", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("event", "user"), name="unique_school_event_rsvp")],
                "indexes": [models.Index(fields=["event", "response"], name="school_event_rsvp_idx")],
            },
        ),
    ]
