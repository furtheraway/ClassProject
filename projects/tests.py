from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Project
from .services import current_bonus_score

User = get_user_model()

PROJECT_DATA = {
    "title": "Campus food-sharing app",
    "description": "An app to reduce food waste in the canteen.",
    "keywords": "web, sustainability",
    "group_size": 3,
    "talents_needed": "One backend dev, one designer",
    "contact_info": "wechat: alice123",
}


def make_user(email, name="Some Student"):
    return User.objects.create_user(email=email, password="correct-horse-9!", full_name=name)


class BonusScoreTests(TestCase):
    def test_curve_matches_spec_table(self):
        # SPEC §3.4 reference values
        expected = {0: 20, 4: 19, 8: 17, 10: 15, 12: 12, 14: 8, 16: 6, 18: 4, 22: 3}
        for n, score in expected.items():
            self.assertEqual(current_bonus_score(n), score, f"N={n}")

    def test_never_below_min_or_above_max(self):
        self.assertEqual(current_bonus_score(1000), 3)
        self.assertEqual(current_bonus_score(0), 20)


class ProjectCreateTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice@example.com", "Alice Zhang")
        self.client.force_login(self.alice)

    def test_create_project(self):
        response = self.client.post(reverse("project-new"), PROJECT_DATA)
        project = Project.objects.get()
        self.assertRedirects(response, reverse("project-detail", args=[project.pk]))
        self.assertEqual(project.owner, self.alice)
        self.assertEqual(project.status, Project.Status.OPEN)

    def test_group_size_bounds_enforced(self):
        for bad_size in (1, 6):
            response = self.client.post(reverse("project-new"), dict(PROJECT_DATA, group_size=bad_size))
            self.assertEqual(response.status_code, 200, f"group_size={bad_size} accepted")
        self.assertEqual(Project.objects.count(), 0)

    def test_owner_with_active_project_cannot_create_another(self):
        first = Project.objects.create(owner=self.alice, **PROJECT_DATA)
        response = self.client.post(reverse("project-new"), dict(PROJECT_DATA, title="Second try"))
        self.assertRedirects(response, reverse("project-detail", args=[first.pk]))
        self.assertEqual(Project.objects.count(), 1)

    def test_owner_with_cancelled_project_can_create_new(self):
        Project.objects.create(owner=self.alice, status=Project.Status.CANCELLED, **PROJECT_DATA)
        response = self.client.post(reverse("project-new"), dict(PROJECT_DATA, title="New idea"))
        self.assertEqual(Project.objects.count(), 2)


class OwnerGuardTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice@example.com", "Alice Zhang")
        self.bob = make_user("bob@example.com", "Bob Li")
        self.project = Project.objects.create(owner=self.alice, **PROJECT_DATA)
        self.client.force_login(self.bob)

    def test_non_owner_cannot_edit(self):
        response = self.client.get(reverse("project-edit", args=[self.project.pk]))
        self.assertEqual(response.status_code, 403)

    def test_non_owner_cannot_cancel(self):
        response = self.client.post(reverse("project-cancel", args=[self.project.pk]))
        self.assertEqual(response.status_code, 403)

    def test_non_owner_cannot_delete(self):
        response = self.client.post(reverse("project-delete", args=[self.project.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())

    def test_cancel_requires_post(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("project-cancel", args=[self.project.pk]))
        self.assertEqual(response.status_code, 405)


class CancelUncancelTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice@example.com", "Alice Zhang")
        self.project = Project.objects.create(owner=self.alice, **PROJECT_DATA)
        self.client.force_login(self.alice)

    def test_cancel_then_uncancel(self):
        self.client.post(reverse("project-cancel", args=[self.project.pk]))
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.CANCELLED)

        self.client.post(reverse("project-uncancel", args=[self.project.pk]))
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.OPEN)

    def test_uncancel_blocked_when_owner_has_another_active_project(self):
        self.client.post(reverse("project-cancel", args=[self.project.pk]))
        Project.objects.create(owner=self.alice, title="Newer project", **{
            k: v for k, v in PROJECT_DATA.items() if k != "title"
        })
        self.client.post(reverse("project-uncancel", args=[self.project.pk]))
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.CANCELLED)

    def test_delete_removes_project(self):
        response = self.client.post(reverse("project-delete", args=[self.project.pk]))
        self.assertRedirects(response, reverse("home"))
        self.assertFalse(Project.objects.exists())


class HomeListTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice@example.com", "Alice Zhang")
        self.bob = make_user("bob@example.com", "Bob Li")
        self.carol = make_user("carol@example.com", "Carol Wu")
        self.client.force_login(self.carol)

    def test_home_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_cancelled_projects_sort_last_and_are_greyed(self):
        old_open = Project.objects.create(owner=self.alice, **dict(PROJECT_DATA, title="Older open"))
        newer_cancelled = Project.objects.create(
            owner=self.bob,
            status=Project.Status.CANCELLED,
            **dict(PROJECT_DATA, title="Newer cancelled"),
        )
        response = self.client.get(reverse("home"))
        content = response.content.decode()
        self.assertLess(
            content.index("Older open"),
            content.index("Newer cancelled"),
            "cancelled project should sort below open ones despite being newer",
        )
        self.assertContains(response, "opacity-50")
        self.assertContains(response, "Cancelled")

    def test_stats_card_counts_exclude_cancelled(self):
        Project.objects.create(owner=self.alice, **PROJECT_DATA)
        Project.objects.create(
            owner=self.bob, status=Project.Status.CANCELLED, **dict(PROJECT_DATA, title="Ghost")
        )
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["project_count"], 1)
        self.assertEqual(response.context["bonus_score"], current_bonus_score(1))

    def test_search_filters_by_keyword(self):
        Project.objects.create(owner=self.alice, **PROJECT_DATA)
        Project.objects.create(
            owner=self.bob, **dict(PROJECT_DATA, title="Robot arm", keywords="hardware, robotics")
        )
        response = self.client.get(reverse("home"), {"q": "robotics"})
        self.assertContains(response, "Robot arm")
        self.assertNotContains(response, "Campus food-sharing app")

    def test_detail_shows_contact_and_meet_first_notice(self):
        project = Project.objects.create(owner=self.alice, **PROJECT_DATA)
        response = self.client.get(reverse("project-detail", args=[project.pk]))
        self.assertContains(response, "wechat: alice123")
        self.assertContains(response, "Discuss with the owner")
