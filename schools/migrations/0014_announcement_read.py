import django.conf
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0013_transfer_certificate"),
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AnnouncementRead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("read_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("announcement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="read_receipts", to="schools.announcement")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="announcement_reads", to=django.conf.settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("announcement", "user"), name="unique_announcement_read_user")],
                "indexes": [models.Index(fields=["user", "read_at"], name="announce_read_user_date_idx")],
            },
        ),
    ]
