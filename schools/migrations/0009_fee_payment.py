from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("schools", "0008_attendance_change_log"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeePayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("payment_date", models.DateField(default=django.utils.timezone.localdate)),
                ("method", models.CharField(choices=[("cash", "Cash"), ("upi", "UPI (manually verified)"), ("bank", "Bank transfer (manually verified)"), ("cheque", "Cheque"), ("other", "Other")], default="cash", max_length=10)),
                ("reference", models.CharField(blank=True, max_length=100)),
                ("note", models.CharField(blank=True, max_length=250)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("fee_record", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="schools.feerecord")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fee_payments", to="schools.school")),
            ],
            options={
                "ordering": ["-payment_date", "-created_at"],
                "indexes": [models.Index(fields=["school", "payment_date"], name="feepay_school_date_idx")],
            },
        ),
    ]
