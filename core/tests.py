from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()


class PasswordResetFlowTests(TestCase):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_request_sends_email_for_registered_account(self):
        User.objects.create_user(
            username="reset_test_user",
            email="reset-user@example.test",
            password="Synthetic-Only-Password-123!",
        )
        response = self.client.post(
            reverse("password_reset"),
            {"email": "reset-user@example.test"},
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("accounts/reset/", mail.outbox[0].body)
        self.assertIn("School Saathi", mail.outbox[0].subject)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_unknown_email_does_not_disclose_account_existence(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "not-registered@example.test"},
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_pages_are_reachable(self):
        response = self.client.get(reverse("password_reset"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registered email")
        done = self.client.get(reverse("password_reset_done"))
        self.assertEqual(done.status_code, 200)
