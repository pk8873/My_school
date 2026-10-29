from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from schools.models import Membership, School


User = get_user_model()


class PublicHomeTests(TestCase):
    def test_anonymous_visitors_see_public_homepage(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "public/home.html")
        self.assertContains(response, "Less paperwork.")
        self.assertContains(response, "Student & class records")
        self.assertContains(response, reverse("login"))

    def test_authenticated_user_is_redirected_to_dashboard(self):
        user = User.objects.create_user(username="public-home-user", password="synthetic-test-pass-123")
        school = School.objects.create(name="Private Synthetic School", slug="private-synthetic-school")
        Membership.objects.create(user=user, school=school, role=Membership.Role.SCHOOL_ADMIN)
        self.client.force_login(user)
        response = self.client.get(reverse("home"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_public_home_does_not_list_school_or_student_records(self):
        School.objects.create(name="Confidential Synthetic School", slug="confidential-synthetic-school")
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Confidential Synthetic School")
        self.assertNotContains(response, "admission_number")
