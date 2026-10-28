import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from schools.models import Membership, School, SchoolSubscription


class Command(BaseCommand):
    help = "Create the first School Saathi school-admin account from Render environment variables."

    def handle(self, *args, **options):
        username = os.environ.get("SCHOOL_BOOTSTRAP_ADMIN_USERNAME", "").strip()
        if not username:
            self.stdout.write("School admin bootstrap skipped: no bootstrap username configured.")
            return

        school_name = os.environ.get("SCHOOL_BOOTSTRAP_SCHOOL_NAME", "").strip()
        school_slug = os.environ.get("SCHOOL_BOOTSTRAP_SCHOOL_SLUG", "").strip().lower()
        email = os.environ.get("SCHOOL_BOOTSTRAP_ADMIN_EMAIL", "").strip()
        password = os.environ.get("SCHOOL_BOOTSTRAP_ADMIN_PASSWORD", "")
        if not school_name or not school_slug or not email:
            raise CommandError(
                "Set SCHOOL_BOOTSTRAP_SCHOOL_NAME, SCHOOL_BOOTSTRAP_SCHOOL_SLUG, "
                "and SCHOOL_BOOTSTRAP_ADMIN_EMAIL. Do not put secrets in source code."
            )

        User = get_user_model()
        with transaction.atomic():
            school = School.objects.filter(slug=school_slug).first()
            user = User.objects.filter(username=username).first()

            if user:
                if school and Membership.objects.filter(
                    user=user, school=school, role=Membership.Role.SCHOOL_ADMIN, is_active=True
                ).exists():
                    self.stdout.write(self.style.SUCCESS(
                        f"Bootstrap already completed for username '{username}'. Password was not changed."
                    ))
                    return
                raise CommandError(
                    f"Username '{username}' already exists but is not the school admin for slug "
                    f"'{school_slug}'. No changes were made. Choose a new username or review records securely."
                )

            if not password or len(password) < 12:
                raise CommandError(
                    "SCHOOL_BOOTSTRAP_ADMIN_PASSWORD must be at least 12 characters. "
                    "Set a unique strong password in Render Environment."
                )

            if school is None:
                school = School.objects.create(
                    name=school_name,
                    slug=school_slug,
                    email=email,
                    is_active=True,
                )
            elif school.name != school_name:
                self.stdout.write(self.style.WARNING(
                    f"School slug '{school_slug}' already exists; keeping its existing name."
                ))

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                is_staff=False,
                is_superuser=False,
            )
            Membership.objects.create(
                user=user,
                school=school,
                role=Membership.Role.SCHOOL_ADMIN,
                is_active=True,
            )
            SchoolSubscription.objects.get_or_create(
                school=school,
                defaults={
                    "plan": SchoolSubscription.Plan.STARTER,
                    "status": SchoolSubscription.Status.TRIAL,
                    "student_limit": 100,
                    "trial_ends_at": timezone.localdate() + timedelta(days=14),
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"Created school admin '{username}' for school '{school.name}'. "
            "After confirming login, remove SCHOOL_BOOTSTRAP_ADMIN_PASSWORD from Render Environment."
        ))
