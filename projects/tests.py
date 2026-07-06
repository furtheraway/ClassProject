from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Application, Membership, Project
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


APPLICATION_DATA = {"message": "We talked after class on Tuesday.", "discussed_with_owner": "on"}


def apply(client, project, data=APPLICATION_DATA):
    return client.post(reverse("project-apply", args=[project.pk]), data)


class ApplyTests(TestCase):
    """SPEC §3.3 — applying to a project."""

    def setUp(self):
        self.owner = make_user("owner@example.com", "Olive Owner")
        self.dave = make_user("dave@example.com", "Dave Deng")
        self.project = Project.objects.create(owner=self.owner, **PROJECT_DATA)
        self.client.force_login(self.dave)

    def test_apply_happy_path(self):
        response = apply(self.client, self.project)
        self.assertRedirects(response, reverse("project-detail", args=[self.project.pk]))
        app = Application.objects.get()
        self.assertEqual(app.applicant, self.dave)
        self.assertEqual(app.status, Application.Status.PENDING)

    def test_apply_requires_discussed_checkbox(self):
        response = apply(self.client, self.project, {"message": "hi"})
        self.assertEqual(response.status_code, 200)  # re-rendered with errors
        self.assertFalse(Application.objects.exists())

    def test_cannot_apply_to_own_project(self):
        self.client.force_login(self.owner)
        response = apply(self.client, self.project)
        self.assertRedirects(response, reverse("project-detail", args=[self.project.pk]))
        self.assertFalse(Application.objects.exists())

    def test_active_project_owner_must_cancel_first(self):
        Project.objects.create(owner=self.dave, **dict(PROJECT_DATA, title="Dave's own"))
        apply(self.client, self.project)
        self.assertFalse(Application.objects.exists())

    def test_cancelled_owner_can_apply(self):
        Project.objects.create(
            owner=self.dave,
            status=Project.Status.CANCELLED,
            **dict(PROJECT_DATA, title="Dave's old"),
        )
        apply(self.client, self.project)
        self.assertTrue(Application.objects.exists())

    def test_member_cannot_apply(self):
        other = Project.objects.create(
            owner=make_user("erin@example.com"), **dict(PROJECT_DATA, title="Other")
        )
        Membership.objects.create(project=other, member=self.dave)
        apply(self.client, self.project)
        self.assertFalse(Application.objects.exists())

    def test_only_one_pending_application_app_wide(self):
        other = Project.objects.create(
            owner=make_user("erin@example.com"), **dict(PROJECT_DATA, title="Other")
        )
        apply(self.client, self.project)
        apply(self.client, other)
        self.assertEqual(Application.objects.count(), 1)

    def test_cannot_apply_to_fulfilled_project(self):
        self.project.status = Project.Status.FULFILLED
        self.project.save()
        apply(self.client, self.project)
        self.assertFalse(Application.objects.exists())

    def test_withdraw_then_reapply(self):
        apply(self.client, self.project)
        self.client.post(reverse("application-withdraw", args=[self.project.pk]))
        self.assertEqual(
            Application.objects.get().status, Application.Status.WITHDRAWN
        )
        apply(self.client, self.project)
        self.assertEqual(
            Application.objects.filter(status=Application.Status.PENDING).count(), 1
        )


class ConfirmDeclineTests(TestCase):
    """SPEC §3.3 — owner decisions, auto-fulfill, auto-decline."""

    def setUp(self):
        self.owner = make_user("owner@example.com", "Olive Owner")
        self.dave = make_user("dave@example.com", "Dave Deng")
        self.erin = make_user("erin@example.com", "Erin Xu")
        self.frank = make_user("frank@example.com", "Frank Ma")
        self.project = Project.objects.create(owner=self.owner, **PROJECT_DATA)  # size 3

    def _pending_app(self, user):
        return Application.objects.create(
            project=self.project, applicant=user, discussed_with_owner=True
        )

    def _confirm(self, app):
        return self.client.post(
            reverse("application-confirm", args=[self.project.pk, app.pk])
        )

    def test_confirm_creates_membership(self):
        app = self._pending_app(self.dave)
        self.client.force_login(self.owner)
        self._confirm(app)
        app.refresh_from_db()
        self.assertEqual(app.status, Application.Status.CONFIRMED)
        self.assertTrue(Membership.objects.filter(member=self.dave, project=self.project).exists())
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.OPEN)  # 2/3, not full yet

    def test_autofulfill_declines_remaining_pending(self):
        Membership.objects.create(project=self.project, member=self.frank)  # 2/3
        app_dave = self._pending_app(self.dave)
        app_erin = self._pending_app(self.erin)
        self.client.force_login(self.owner)
        self._confirm(app_dave)  # 3/3 → fulfilled
        self.project.refresh_from_db()
        app_erin.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.FULFILLED)
        self.assertEqual(app_erin.status, Application.Status.DECLINED)

    def test_stale_confirm_blocked_when_applicant_joined_elsewhere(self):
        app = self._pending_app(self.dave)
        other = Project.objects.create(owner=self.erin, **dict(PROJECT_DATA, title="Other"))
        Membership.objects.create(project=other, member=self.dave)
        self.client.force_login(self.owner)
        self._confirm(app)
        app.refresh_from_db()
        self.assertEqual(app.status, Application.Status.PENDING)
        self.assertFalse(Membership.objects.filter(project=self.project).exists())

    def test_decline(self):
        app = self._pending_app(self.dave)
        self.client.force_login(self.owner)
        self.client.post(reverse("application-decline", args=[self.project.pk, app.pk]))
        app.refresh_from_db()
        self.assertEqual(app.status, Application.Status.DECLINED)
        self.assertIsNotNone(app.decided_at)

    def test_non_owner_cannot_confirm_or_decline(self):
        app = self._pending_app(self.dave)
        self.client.force_login(self.erin)
        for name in ("application-confirm", "application-decline"):
            response = self.client.post(reverse(name, args=[self.project.pk, app.pk]))
            self.assertEqual(response.status_code, 403, name)

    def test_member_cannot_create_project(self):
        Membership.objects.create(project=self.project, member=self.dave)
        self.client.force_login(self.dave)
        response = self.client.post(
            reverse("project-new"), dict(PROJECT_DATA, title="Sneaky side project")
        )
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(Project.objects.count(), 1)


class MemberRemoveTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com", "Olive Owner")
        self.dave = make_user("dave@example.com", "Dave Deng")
        self.project = Project.objects.create(
            owner=self.owner, **dict(PROJECT_DATA, group_size=2)
        )
        Membership.objects.create(project=self.project, member=self.dave)
        self.project.status = Project.Status.FULFILLED
        self.project.save()
        self.client.force_login(self.owner)

    def test_remove_member_reopens_fulfilled_project(self):
        self.client.post(
            reverse("member-remove", args=[self.project.pk, self.dave.pk])
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.OPEN)
        self.assertFalse(Membership.objects.exists())

    def test_non_owner_cannot_remove(self):
        self.client.force_login(self.dave)
        response = self.client.post(
            reverse("member-remove", args=[self.project.pk, self.dave.pk])
        )
        self.assertEqual(response.status_code, 403)


class CancelReleasesTeamTests(TestCase):
    """SPEC §3.2 — cancel releases members + declines pending; un-cancel guards."""

    def setUp(self):
        self.owner = make_user("owner@example.com", "Olive Owner")
        self.dave = make_user("dave@example.com", "Dave Deng")
        self.erin = make_user("erin@example.com", "Erin Xu")
        self.project = Project.objects.create(owner=self.owner, **PROJECT_DATA)
        self.client.force_login(self.owner)

    def test_cancel_releases_members_and_declines_pending(self):
        Membership.objects.create(project=self.project, member=self.dave)
        app = Application.objects.create(
            project=self.project, applicant=self.erin, discussed_with_owner=True
        )
        self.client.post(reverse("project-cancel", args=[self.project.pk]))
        self.project.refresh_from_db()
        app.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.CANCELLED)
        self.assertFalse(Membership.objects.exists())
        self.assertEqual(app.status, Application.Status.DECLINED)

    def test_uncancel_blocked_when_owner_joined_another_group(self):
        self.client.post(reverse("project-cancel", args=[self.project.pk]))
        other = Project.objects.create(owner=self.erin, **dict(PROJECT_DATA, title="Other"))
        Membership.objects.create(project=other, member=self.owner)
        self.client.post(reverse("project-uncancel", args=[self.project.pk]))
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.CANCELLED)

    def test_uncancel_blocked_by_own_pending_application(self):
        self.client.post(reverse("project-cancel", args=[self.project.pk]))
        other = Project.objects.create(owner=self.erin, **dict(PROJECT_DATA, title="Other"))
        Application.objects.create(
            project=other, applicant=self.owner, discussed_with_owner=True
        )
        self.client.post(reverse("project-uncancel", args=[self.project.pk]))
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.CANCELLED)

    def test_uncancel_does_not_restore_members(self):
        Membership.objects.create(project=self.project, member=self.dave)
        self.client.post(reverse("project-cancel", args=[self.project.pk]))
        self.client.post(reverse("project-uncancel", args=[self.project.pk]))
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.OPEN)
        self.assertFalse(Membership.objects.exists())


class GroupSizeEditTests(TestCase):
    """SPEC §3.2/§3.3 — group-size edits interact with fulfillment."""

    def setUp(self):
        self.owner = make_user("owner@example.com", "Olive Owner")
        self.dave = make_user("dave@example.com", "Dave Deng")
        self.project = Project.objects.create(owner=self.owner, **PROJECT_DATA)  # size 3
        Membership.objects.create(project=self.project, member=self.dave)  # team = 2
        self.client.force_login(self.owner)

    def _edit(self, group_size):
        return self.client.post(
            reverse("project-edit", args=[self.project.pk]),
            dict(PROJECT_DATA, group_size=group_size),
        )

    def test_cannot_shrink_below_current_team(self):
        # Team is 2 (owner + dave); group_size 2 is allowed, but a value
        # below members_joined is rejected by the form. Add a member to test.
        erin = make_user("erin@example.com", "Erin Xu")
        Membership.objects.create(project=self.project, member=erin)  # team = 3
        response = self._edit(2)
        self.assertEqual(response.status_code, 200)  # form error, not saved
        self.project.refresh_from_db()
        self.assertEqual(self.project.group_size, 3)

    def test_shrink_to_team_size_autofulfills(self):
        self._edit(2)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.FULFILLED)

    def test_enlarging_fulfilled_project_reopens(self):
        self._edit(2)  # fulfilled at 2/2
        self._edit(4)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.OPEN)


@override_settings(ADMINS=[("Instructor", "instructor@example.com")])
class NotificationEmailTests(TestCase):
    """Notification emails for board events (SPEC §3.3, §6).

    on_commit callbacks never fire inside TestCase's wrapping transaction, so
    the flows that defer email until commit (confirm / fulfill / cancel) run
    inside captureOnCommitCallbacks(execute=True).
    """

    def setUp(self):
        self.owner = make_user("owner@example.com", "Olive Owner")
        self.dave = make_user("dave@example.com", "Dave Deng")
        self.erin = make_user("erin@example.com", "Erin Xu")
        self.frank = make_user("frank@example.com", "Frank Ma")

    def _project(self, **overrides):
        return Project.objects.create(owner=self.owner, **dict(PROJECT_DATA, **overrides))

    def _pending_app(self, project, user):
        return Application.objects.create(
            project=project, applicant=user, discussed_with_owner=True
        )

    def _outbox_for(self, address):
        return [m for m in mail.outbox if address in m.to]

    def test_project_create_notifies_admin(self):
        self.client.force_login(self.owner)
        self.client.post(reverse("project-new"), PROJECT_DATA)
        (message,) = self._outbox_for("instructor@example.com")
        self.assertIn("New project posted", message.subject)
        self.assertIn(PROJECT_DATA["title"], message.body)

    def test_apply_notifies_project_owner(self):
        project = self._project()
        self.client.force_login(self.dave)
        apply(self.client, project)
        (message,) = self._outbox_for(self.owner.email)
        self.assertIn("New application", message.subject)
        self.assertIn(self.dave.full_name, message.body)

    def test_confirm_notifies_applicant(self):
        project = self._project()
        app = self._pending_app(project, self.dave)
        self.client.force_login(self.owner)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("application-confirm", args=[project.pk, app.pk]))
        (message,) = self._outbox_for(self.dave.email)
        self.assertIn("You joined", message.subject)

    def test_decline_notifies_applicant(self):
        project = self._project()
        app = self._pending_app(project, self.dave)
        self.client.force_login(self.owner)
        self.client.post(reverse("application-decline", args=[project.pk, app.pk]))
        (message,) = self._outbox_for(self.dave.email)
        self.assertIn("not accepted", message.body)
        self.assertIn("owner declined", message.body)

    def test_fulfillment_notifies_team_admin_and_declined_applicants(self):
        project = self._project()  # group size 3
        Membership.objects.create(project=project, member=self.frank)  # 2/3
        app_dave = self._pending_app(project, self.dave)
        self._pending_app(project, self.erin)
        self.client.force_login(self.owner)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("application-confirm", args=[project.pk, app_dave.pk]))
        # Dave: joined + team-complete; Frank: team-complete only.
        subjects = [m.subject for m in self._outbox_for(self.dave.email)]
        self.assertEqual(len(subjects), 2, subjects)
        self.assertTrue(any("is complete" in s for s in subjects), subjects)
        (frank_msg,) = self._outbox_for(self.frank.email)
        self.assertIn("is complete", frank_msg.subject)
        # Erin's pending application was auto-declined by the fulfillment.
        (erin_msg,) = self._outbox_for(self.erin.email)
        self.assertIn("filled up", erin_msg.body)
        # The instructor hears the project is fulfilled.
        (admin_msg,) = self._outbox_for("instructor@example.com")
        self.assertIn("fulfilled", admin_msg.subject)

    def test_cancel_notifies_members_and_pending_applicants(self):
        project = self._project()
        Membership.objects.create(project=project, member=self.frank)
        self._pending_app(project, self.erin)
        self.client.force_login(self.owner)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("project-cancel", args=[project.pk]))
        (frank_msg,) = self._outbox_for(self.frank.email)
        self.assertIn("cancelled", frank_msg.subject)
        (erin_msg,) = self._outbox_for(self.erin.email)
        self.assertIn("cancelled", erin_msg.body)

    @override_settings(ADMINS=[])
    def test_no_admin_configured_sends_nothing_to_admin(self):
        self.client.force_login(self.owner)
        self.client.post(reverse("project-new"), PROJECT_DATA)
        self.assertEqual(mail.outbox, [])
