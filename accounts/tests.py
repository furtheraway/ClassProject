import time
from unittest import mock

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .emails import make_verification_token
from .models import User

REGISTRATION_DATA = {
    "email": "alice@example.com",
    "password1": "correct-horse-9!",
    "password2": "correct-horse-9!",
    "full_name": "Alice Zhang",
    "birth_year": 2004,
    "department": "Computer Science",
    "major": "Software Engineering",
    "study_year": 3,
    "gender": "F",
    "height_cm": 213,
    "languages": "Chinese, English",
    "interests": "Robotics",
    "skills": "Python, SQL",
}


class RegistrationTests(TestCase):
    def test_register_creates_inactive_user_and_sends_verification(self):
        response = self.client.post(reverse("register"), REGISTRATION_DATA)
        self.assertContains(response, "Check your email")
        user = User.objects.get(email="alice@example.com")
        self.assertEqual(user.full_name, "Alice Zhang")
        self.assertEqual(user.height_cm, 213)
        # Inactive until the emailed link is clicked (SPEC §3.1)
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["alice@example.com"])
        self.assertIn("/accounts/verify/", mail.outbox[0].body)
        # And not signed in — home still bounces to the login page
        response = self.client.get(reverse("home"))
        self.assertIn(reverse("login"), response.url)

    def test_profile_fields_are_required(self):
        data = dict(REGISTRATION_DATA, department="")
        response = self.client.post(reverse("register"), data)
        self.assertEqual(response.status_code, 200)  # re-rendered with errors
        self.assertFormError(response.context["form"], "department", "This field is required.")
        self.assertFalse(User.objects.filter(email="alice@example.com").exists())

    def test_duplicate_email_rejected(self):
        User.objects.create_user(
            email="alice@example.com", password="x-9!pqrs", full_name="First Alice"
        )
        response = self.client.post(reverse("register"), REGISTRATION_DATA)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(email="alice@example.com").count(), 1)


class EmailVerificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com",
            password="correct-horse-9!",
            full_name="Alice Zhang",
            is_active=False,
        )

    def test_valid_token_activates_account(self):
        token = make_verification_token(self.user)
        response = self.client.get(reverse("verify-email", args=[token]))
        self.assertRedirects(response, reverse("login"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_tampered_token_rejected(self):
        token = make_verification_token(self.user) + "x"
        response = self.client.get(reverse("verify-email", args=[token]))
        self.assertRedirects(response, reverse("resend-verification"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_expired_token_rejected(self):
        # Sign with a timestamp 4 days in the past (max age is 3 days)
        four_days_ago = time.time() - 60 * 60 * 24 * 4
        with mock.patch("django.core.signing.time.time", return_value=four_days_ago):
            token = make_verification_token(self.user)
        self.client.get(reverse("verify-email", args=[token]))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_unverified_user_cannot_sign_in(self):
        response = self.client.post(
            reverse("login"),
            {"username": "alice@example.com", "password": "correct-horse-9!"},
        )
        self.assertEqual(response.status_code, 200)  # form re-rendered
        # (apostrophe in "hasn't" is HTML-escaped, so match around it)
        self.assertContains(response, "been verified yet")

    def test_resend_sends_new_link_for_unverified_account(self):
        response = self.client.post(
            reverse("resend-verification"), {"email": "alice@example.com"}
        )
        self.assertRedirects(response, reverse("login"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/verify/", mail.outbox[0].body)

    def test_resend_is_silent_for_unknown_or_verified_accounts(self):
        self.user.is_active = True
        self.user.save()
        for email in ("alice@example.com", "nobody@example.com"):
            response = self.client.post(reverse("resend-verification"), {"email": email})
            self.assertRedirects(response, reverse("login"))
        self.assertEqual(len(mail.outbox), 0)


class PasswordResetTests(TestCase):
    def test_reset_email_link_allows_setting_new_password(self):
        User.objects.create_user(
            email="bob@example.com", password="old-pass-9!", full_name="Bob Li"
        )
        response = self.client.post(
            reverse("password_reset"), {"email": "bob@example.com"}
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        # Pull the confirm URL out of the email body
        reset_url = next(
            line for line in mail.outbox[0].body.splitlines() if "/password-reset/" in line
        ).strip()
        # Django redirects the tokened URL to a session-backed one first
        response = self.client.get(reset_url, follow=True)
        self.assertContains(response, "Choose a new password")
        form_url = response.redirect_chain[-1][0]
        response = self.client.post(
            form_url,
            {"new_password1": "brand-new-pass-9!", "new_password2": "brand-new-pass-9!"},
            follow=True,
        )
        self.assertContains(response, "Password changed")
        # The new password works
        response = self.client.post(
            reverse("login"),
            {"username": "bob@example.com", "password": "brand-new-pass-9!"},
        )
        self.assertRedirects(response, reverse("home"))


class LoginTests(TestCase):
    def test_login_with_email(self):
        User.objects.create_user(
            email="bob@example.com", password="correct-horse-9!", full_name="Bob Li"
        )
        response = self.client.post(
            reverse("login"),
            {"username": "bob@example.com", "password": "correct-horse-9!"},
        )
        self.assertRedirects(response, reverse("home"))


class ProfileTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@example.com",
            password="correct-horse-9!",
            full_name="Alice Zhang",
            department="Computer Science",
            major="Software Engineering",
            languages="Chinese, English",
            interests="Robotics",
            skills="Python, SQL",
            birth_year=1993,
            study_year=3,
            gender="F",
            height_cm=213,
        )
        self.bob = User.objects.create_user(
            email="bob@example.com", password="correct-horse-9!", full_name="Bob Li"
        )

    def test_profile_requires_login(self):
        response = self.client.get(reverse("profile-detail", args=[self.alice.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_classmate_sees_public_fields_only(self):
        self.client.force_login(self.bob)
        response = self.client.get(reverse("profile-detail", args=[self.alice.pk]))
        self.assertContains(response, "Alice Zhang")
        self.assertContains(response, "Computer Science")
        self.assertContains(response, "Robotics")
        # Private fields (SPEC §3.1) never appear — not even to the owner here
        self.assertNotContains(response, "213")   # height
        self.assertNotContains(response, "1993")  # birth year

    def test_own_profile_shows_edit_button_and_privacy_note(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("profile-detail", args=[self.alice.pk]))
        self.assertContains(response, "Edit profile")
        self.assertContains(response, "private")
        self.assertNotContains(response, "213")

    def test_edit_profile_updates_fields(self):
        self.client.force_login(self.alice)
        data = {
            "full_name": "Alice Zhang",
            "birth_year": 1993,
            "department": "Computer Science",
            "major": "Software Engineering",
            "study_year": 3,
            "gender": "F",
            "height_cm": 213,
            "languages": "Chinese, English",
            "interests": "Robotics",
            "skills": "Python, SQL, Django",
        }
        response = self.client.post(reverse("profile-edit"), data)
        self.assertRedirects(response, reverse("profile-detail", args=[self.alice.pk]))
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.skills, "Python, SQL, Django")

    def test_edit_profile_cannot_change_email(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("profile-edit"))
        self.assertNotContains(response, 'name="email"')
