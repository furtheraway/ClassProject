"""End-of-project reports and instructor-only peer reviews (SPEC §3.5)."""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from projects.models import Project


class Report(models.Model):
    """One student's report about the project they belong to.

    Editable indefinitely (SPEC §9.1) — resubmitting updates this row,
    `updated_at` records the last change.
    """

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports"
    )
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="reports")
    work_url = models.URLField(
        "Link to the project work",
        max_length=500,
        help_text="e.g. a GitHub repository, a project website, "
        "or a shared Google Drive / Baidu Pan link.",
    )
    contribution = models.TextField("My contribution to the project")
    did_well = models.TextField("What I did well")
    to_improve = models.TextField("What can be improved")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["author", "project"], name="one_report_per_student_per_project"
            )
        ]

    def __str__(self):
        return f"Report by {self.author} on {self.project}"


class PeerReview(models.Model):
    """A score + comments about one teammate, part of a report.

    Visible ONLY to the instructor via the admin — never rendered on any
    student-facing page (SPEC §3.5, non-regression rule in CLAUDE.md).
    """

    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="peer_reviews")
    reviewee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="peer_reviews_received"
    )
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    comments = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["report", "reviewee"], name="one_review_per_teammate_per_report"
            )
        ]

    def __str__(self):
        return f"{self.report.author} → {self.reviewee}: {self.score}/10"
