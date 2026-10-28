# Generated for the transfer certificate issuance register.
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0012_student_class_history"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TransferCertificate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("certificate_number", models.CharField(max_length=40)),
                ("issue_date", models.DateField(default=django.utils.timezone.localdate)),
                ("leaving_date", models.DateField(blank=True, null=True)),
                ("reason", models.CharField(blank=True, max_length=250)),
                ("conduct", models.CharField(blank=True, max_length=100)),
                ("remarks", models.CharField(blank=True, max_length=500)),
                ("status", models.CharField(choices=[("issued", "Issued"), ("cancelled", "Cancelled")], default="issued", max_length=12)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("cancelled_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="transfer_certificates_cancelled", to=settings.AUTH_USER_MODEL)),
                ("issued_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="transfer_certificates_issued", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transfer_certificates", to="schools.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transfer_certificates", to="schools.student")),
            ],
            options={
                "ordering": ["-issue_date", "-created_at"],
                "indexes": [models.Index(fields=["school", "status", "issue_date"], name="tc_school_status_date_idx")],
                "constraints": [models.UniqueConstraint(fields=("school", "certificate_number"), name="unique_tc_number_per_school")],
            },
        ),
    ]
