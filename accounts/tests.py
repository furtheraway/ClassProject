from django.test import TestCase
from django.urls import reverse

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
    def test_register_creates_user_and_signs_in(self):
        response = self.client.post(reverse("register"), REGISTRATION_DATA)
        self.assertRedirects(response, reverse("home"))
        user = User.objects.get(email="alice@example.com")
        self.assertEqual(user.full_name, "Alice Zhang")
        self.assertEqual(user.height_cm, 213)
        # The new user is signed in
        response = self.client.get(reverse("home"))
        self.assertTrue(response.context["user"].is_authenticated)

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
