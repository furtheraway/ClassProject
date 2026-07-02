from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Project(models.Model):
    """A project posting looking for teammates (SPEC §3.2)."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        FULFILLED = "fulfilled", "Fulfilled"
        CANCELLED = "cancelled", "Cancelled"

    # Statuses that count as "active": they block the owner from posting
    # another project and count toward the stats card (SPEC §3.3, §3.4).
    ACTIVE_STATUSES = (Status.OPEN, Status.FULFILLED)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_projects"
    )
    title = models.CharField(max_length=220)
    description = models.TextField()
    keywords = models.CharField(
        max_length=200,
        blank=True,
        help_text="Comma-separated, e.g. “web, AI, finance”.",
    )
    group_size = models.PositiveSmallIntegerField(
        "group size",
        validators=[MinValueValidator(2), MaxValueValidator(5)],
        help_text="Total team size including you — between 2 and 5.",
    )
    talents_needed = models.TextField("talents needed", blank=True)
    contact_info = models.CharField(
        "contact info",
        max_length=200,
        help_text="How teammates reach you to discuss — email, phone, WeChat…",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def keyword_list(self):
        return [k.strip() for k in self.keywords.split(",") if k.strip()]

    @property
    def members_joined(self):
        """The owner counts toward group size; confirmed members add to this in Milestone 3."""
        return 1

    @property
    def is_cancelled(self):
        return self.status == self.Status.CANCELLED

    @property
    def is_open(self):
        return self.status == self.Status.OPEN
