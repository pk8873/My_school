from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="family-user",
            email="family@example.com",
            password="Initial-Strong-Pass-123!",
        )

    def test_login_page_links_to_password_reset(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("password_reset"))

    def test_reset_form_does_not_disclose_unknown_email(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "unknown@example.com"},
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)
        done = self.client.get(reverse("password_reset_done"))
        self.assertEqual(done.status_code, 200)
        self.assertContains(done, "does not reveal whether an account exists")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_known_email_receives_reset_link(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": self.user.email},
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Reset your School Saathi password", mail.outbox[0].subject)
        self.assertIn("/accounts/reset/", mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reset_link_changes_password(self):
        self.client.post(reverse("password_reset"), {"email": self.user.email})
        body = mail.outbox[0].body
        link = next(line.strip() for line in body.splitlines() if "/accounts/reset/" in line)
        path = "/" + link.split("/", 3)[3]
        response = self.client.get(path, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a new password")
        confirm_path = response.request["PATH_INFO"]
        response = self.client.post(
            confirm_path,
            {
                "new_password1": "A-Different-Strong-Password-456!",
                "new_password2": "A-Different-Strong-Password-456!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Password updated")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("A-Different-Strong-Password-456!"))
