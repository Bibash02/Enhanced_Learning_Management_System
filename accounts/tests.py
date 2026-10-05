from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class AuthenticationFlowTests(TestCase):
    def test_instructor_role_is_preserved_and_redirects_to_instructor_dashboard(self):
        signup_response = self.client.post(
            reverse("signup"),
            {
                "fullname": "Instructor User",
                "email": "instructor@example.com",
                "password": "secure-password",
                "confirm_password": "secure-password",
                "role": "instructor",
            },
        )

        self.assertRedirects(signup_response, reverse("signin"))
        user = User.objects.get(username="instructor@example.com")
        self.assertEqual(user.profile.role, "instructor")

        signin_response = self.client.post(
            reverse("signin"),
            {
                "email": "instructor@example.com",
                "password": "secure-password",
            },
        )

        self.assertRedirects(signin_response, reverse("instructor_dashboard"))
