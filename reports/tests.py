from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from projects.models import Membership, Project

from .models import PeerReview, Report

User = get_user_model()

PROJECT_DATA = {
    "title": "Campus food-sharing app",
    "description": "An app to reduce food waste in the canteen.",
    "keywords": "web, sustainability",
    "group_size": 3,
    "talents_needed": "One backend dev, one designer",
    "contact_info": "wechat: alice123",
}

REPORT_DATA = {
    "work_url": "https://github.com/team/food-sharing",
    "contribution": "Built the backend API.",
    "did_well": "Kept the scope realistic.",
    "to_improve": "Start integration testing earlier.",
}


def make_user(email, name="Some Student"):
    return User.objects.create_user(email=email, password="correct-horse-9!", full_name=name)


class ReportAccessTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com", "Olive Owner")
        self.dave = make_user("dave@example.com", "Dave Deng")
        self.loner = make_user("loner@example.com", "Lone Wolf")
        self.project = Project.objects.create(owner=self.owner, **PROJECT_DATA)
        Membership.objects.create(project=self.project, member=self.dave)

    def test_report_requires_login(self):
        response = self.client.get(reverse("my-report"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_student_without_group_sees_no_group_page(self):
        self.client.force_login(self.loner)
        response = self.client.get(reverse("my-report"))
        self.assertContains(response, "not in a group")

    def test_nav_link_only_when_in_group(self):
        self.client.force_login(self.dave)
        self.assertContains(self.client.get(reverse("home")), "My report")
        self.client.force_login(self.loner)
        self.assertNotContains(self.client.get(reverse("home")), "My report")

    def test_form_lists_teammates_and_privacy_notice(self):
        self.client.force_login(self.dave)
        response = self.client.get(reverse("my-report"))
        self.assertContains(response, "Olive Owner")  # owner is reviewed too
        self.assertNotContains(response, "Dave Deng</legend>")  # never reviews self
        self.assertContains(response, "only to the instructor")

    def test_cancelled_project_gives_no_report_access(self):
        self.project.status = Project.Status.CANCELLED
        self.project.save()
        self.project.memberships.all().delete()
        self.client.force_login(self.owner)
        response = self.client.get(reverse("my-report"))
        self.assertContains(response, "not in a group")


class ReportSubmitTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com", "Olive Owner")
        self.dave = make_user("dave@example.com", "Dave Deng")
        self.erin = make_user("erin@example.com", "Erin Xu")
        self.project = Project.objects.create(owner=self.owner, **PROJECT_DATA)
        Membership.objects.create(project=self.project, member=self.dave)
        Membership.objects.create(project=self.project, member=self.erin)
        self.client.force_login(self.dave)

    def _payload(self, **overrides):
        data = dict(REPORT_DATA)
        # dave reviews owner + erin
        data[f"score_{self.owner.pk}"] = 9
        data[f"comments_{self.owner.pk}"] = "Great leadership."
        data[f"score_{self.erin.pk}"] = 7
        data[f"comments_{self.erin.pk}"] = ""
        data.update(overrides)
        return data

    def test_submit_creates_report_and_reviews(self):
        response = self.client.post(reverse("my-report"), self._payload())
        self.assertRedirects(response, reverse("my-report"))
        report = Report.objects.get()
        self.assertEqual(report.author, self.dave)
        self.assertEqual(report.project, self.project)
        self.assertEqual(report.peer_reviews.count(), 2)
        self.assertEqual(report.peer_reviews.get(reviewee=self.owner).score, 9)

    def test_work_url_required_and_validated(self):
        response = self.client.post(reverse("my-report"), self._payload(work_url=""))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse("my-report"), self._payload(work_url="not a url"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Report.objects.exists())

    def test_score_bounds_enforced(self):
        payload = self._payload(**{f"score_{self.owner.pk}": 11})
        response = self.client.post(reverse("my-report"), payload)
        self.assertEqual(response.status_code, 200)
        payload = self._payload(**{f"score_{self.owner.pk}": ""})
        response = self.client.post(reverse("my-report"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Report.objects.exists())

    def test_resubmit_updates_single_report(self):
        self.client.post(reverse("my-report"), self._payload())
        self.client.post(
            reverse("my-report"),
            self._payload(contribution="Rewrote the backend twice.",
                          **{f"score_{self.erin.pk}": 10}),
        )
        self.assertEqual(Report.objects.count(), 1)
        report = Report.objects.get()
        self.assertEqual(report.contribution, "Rewrote the backend twice.")
        self.assertEqual(report.peer_reviews.get(reviewee=self.erin).score, 10)
        self.assertEqual(report.peer_reviews.count(), 2)

    def test_resubmit_after_team_change_drops_stale_review(self):
        self.client.post(reverse("my-report"), self._payload())
        Membership.objects.filter(member=self.erin).delete()
        payload = dict(REPORT_DATA)
        payload[f"score_{self.owner.pk}"] = 8
        payload[f"comments_{self.owner.pk}"] = ""
        self.client.post(reverse("my-report"), payload)
        report = Report.objects.get()
        self.assertEqual(
            [r.reviewee for r in report.peer_reviews.all()], [self.owner]
        )

    def test_edit_form_prefills_existing_values(self):
        self.client.post(reverse("my-report"), self._payload())
        response = self.client.get(reverse("my-report"))
        self.assertContains(response, "https://github.com/team/food-sharing")
        self.assertContains(response, "Great leadership.")
        self.assertContains(response, "Update report")


class InstructorOnlyTests(TestCase):
    """SPEC §3.5 — reviews visible only in the admin; CSV export works."""

    def setUp(self):
        self.owner = make_user("owner@example.com", "Olive Owner")
        self.dave = make_user("dave@example.com", "Dave Deng")
        self.project = Project.objects.create(owner=self.owner, **PROJECT_DATA)
        Membership.objects.create(project=self.project, member=self.dave)
        self.report = Report.objects.create(
            author=self.dave, project=self.project, **REPORT_DATA
        )
        PeerReview.objects.create(
            report=self.report, reviewee=self.owner, score=9, comments="Great leadership."
        )

    def test_student_cannot_open_reports_admin(self):
        self.client.force_login(self.owner)
        response = self.client.get("/admin/reports/peerreview/")
        self.assertEqual(response.status_code, 302)  # bounced to admin login

    def test_teammate_report_page_never_shows_others_reviews(self):
        # Olive opens her own report form — Dave's score about her must not leak.
        self.client.force_login(self.owner)
        response = self.client.get(reverse("my-report"))
        self.assertNotContains(response, "Great leadership.")

    def test_csv_export(self):
        instructor = User.objects.create_superuser(
            email="prof@example.com", password="correct-horse-9!", full_name="The Instructor"
        )
        self.client.force_login(instructor)
        response = self.client.post(
            "/admin/reports/peerreview/",
            {
                "action": "export_as_csv",
                "_selected_action": [str(PeerReview.objects.get().pk)],
            },
        )
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        body = response.content.decode()
        self.assertIn("reviewer,reviewer_email,reviewee", body)
        self.assertIn("Dave Deng", body)
        self.assertIn("Great leadership.", body)
        self.assertIn("9", body)
