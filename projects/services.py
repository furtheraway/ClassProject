"""Business rules for the project board and group formation (SPEC §3.2–§3.4)."""

import math

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import emails
from .models import Application, Membership, Project


def current_bonus_score(project_count):
    """Bonus score shown on the stats card (SPEC §3.4).

    Logistic S-curve: stays near the maximum while the class still needs
    projects, drops fastest around the midpoint, floors at the minimum.
    Constants live in settings.BONUS_SCORE so the curve can be tuned
    without code changes.
    """
    cfg = settings.BONUS_SCORE
    span = cfg["max"] - cfg["min"]
    exponent = (project_count - cfg["midpoint"]) / cfg["steepness"]
    return round(cfg["min"] + span / (1 + math.exp(exponent)))


def owned_active_project(user, exclude_pk=None):
    qs = user.owned_projects.filter(status__in=Project.ACTIVE_STATUSES)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.first()


def user_current_project(user):
    """The active project the user belongs to (as owner or member), or None.

    Used by the report page and the "My report" nav link (SPEC §3.5).
    """
    owned = owned_active_project(user)
    if owned:
        return owned
    membership = Membership.objects.select_related("project").filter(member=user).first()
    # Memberships are deleted when a project is cancelled, so an existing
    # membership always points at an open/fulfilled project.
    return membership.project if membership else None


def application_block_reason(user, project):
    """Why `user` can't apply to `project` right now — None if they can (SPEC §3.3)."""
    if project.owner_id == user.pk:
        return "You can't apply to your own project."
    if not project.is_open:
        return "This project isn't open for applications."
    if owned_active_project(user):
        return "You own an active project — cancel it before applying to another one."
    if Membership.objects.filter(member=user).exists():
        return "You're already in a group — one group per student."
    if Application.objects.filter(applicant=user, status=Application.Status.PENDING).exists():
        return "You already have a pending application — withdraw it before applying elsewhere."
    return None


def sync_fulfillment(project):
    """Keep status in step with team size after confirms, removals or group-size edits.

    Returns "fulfilled", "reopened" or None.
    """
    if project.status == Project.Status.OPEN and project.members_joined >= project.group_size:
        project.status = Project.Status.FULFILLED
        project.save()
        # Snapshot recipients before mutating: the declined applicants and the
        # team (minus the owner, who triggered this by confirming or editing).
        declined_applicants = [
            a.applicant
            for a in project.applications.filter(
                status=Application.Status.PENDING
            ).select_related("applicant")
        ]
        member_emails = list(project.memberships.values_list("member__email", flat=True))
        # Team complete: remaining pending applications are auto-declined (SPEC §3.3).
        project.applications.filter(status=Application.Status.PENDING).update(
            status=Application.Status.DECLINED, decided_at=timezone.now()
        )

        # on_commit defers the emails until the surrounding transaction commits
        # (like queueing work after a successful SaveChanges) — if the confirm
        # rolls back, nobody gets a wrong email. Outside a transaction it runs
        # immediately.
        def send_fulfillment_emails():
            emails.notify_team_fulfilled(project, member_emails)
            emails.notify_admin_project_fulfilled(project)
            emails.notify_applications_declined(
                project, declined_applicants, "the team filled up before your turn came."
            )

        transaction.on_commit(send_fulfillment_emails)
        return "fulfilled"
    if project.status == Project.Status.FULFILLED and project.members_joined < project.group_size:
        project.status = Project.Status.OPEN
        project.save()
        return "reopened"
    return None


def confirm_application(application):
    """Owner confirms an applicant. Returns an error message, or None on success.

    Eligibility is re-checked because it can change while an application
    waits (SPEC §3.3).
    """
    project = application.project
    applicant = application.applicant
    if not project.is_open:
        return "This project isn't open, so members can't be confirmed."
    if owned_active_project(applicant):
        return f"{applicant.full_name} now owns an active project and can't join yours."
    if Membership.objects.filter(member=applicant).exists():
        return f"{applicant.full_name} already joined another group."
    try:
        with transaction.atomic():
            Membership.objects.create(project=project, member=applicant)
            application.status = Application.Status.CONFIRMED
            application.decided_at = timezone.now()
            application.save()
            transaction.on_commit(lambda: emails.notify_application_confirmed(application))
            sync_fulfillment(project)
    except IntegrityError:
        return f"{applicant.full_name} just joined another group."
    return None


def remove_member(membership):
    """Owner removes a member; a full project reopens (SPEC §3.3).

    Returns "reopened" or None.
    """
    project = membership.project
    with transaction.atomic():
        membership.delete()
        return sync_fulfillment(project)


def cancel_project(project):
    """Cancel: release all members, decline pending applications (SPEC §3.2)."""
    with transaction.atomic():
        # Snapshot recipients before the deletes below wipe them out.
        member_emails = list(project.memberships.values_list("member__email", flat=True))
        pending_applicants = [
            a.applicant
            for a in project.applications.filter(
                status=Application.Status.PENDING
            ).select_related("applicant")
        ]
        project.status = Project.Status.CANCELLED
        project.save()
        project.memberships.all().delete()
        project.applications.filter(status=Application.Status.PENDING).update(
            status=Application.Status.DECLINED, decided_at=timezone.now()
        )

        def send_cancellation_emails():
            emails.notify_team_cancelled(project, member_emails)
            emails.notify_applications_declined(
                project, pending_applicants, "the project was cancelled by its owner."
            )

        transaction.on_commit(send_cancellation_emails)


def uncancel_block_reason(project):
    """Why a cancelled project can't be reactivated — None if it can (SPEC §3.2)."""
    owner = project.owner
    if owned_active_project(owner, exclude_pk=project.pk):
        return "You already have another active project, so this one can't be reactivated."
    if Membership.objects.filter(member=owner).exists():
        return "You've joined another group, so this project can't be reactivated."
    if Application.objects.filter(applicant=owner, status=Application.Status.PENDING).exists():
        return "Withdraw your pending application before reactivating your project."
    return None
