import schools.models
import schools.uploads
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0016_school_event_rsvp"),
    ]

    operations = [
        migrations.AddField(
            model_name="homework",
            name="attachment",
            field=models.FileField(
                blank=True,
                upload_to=schools.uploads.homework_attachment_path,
                validators=[schools.uploads.validate_school_attachment],
            ),
        ),
        migrations.AddField(
            model_name="homeworksubmission",
            name="attachment",
            field=models.FileField(
                blank=True,
                upload_to=schools.uploads.homework_submission_attachment_path,
                validators=[schools.uploads.validate_school_attachment],
            ),
        ),
    ]
