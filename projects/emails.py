"""Notification emails for project-board events (SPEC §3.3, §6).

Every function here uses fail_silently=True: a SendGrid outage must never turn
a successful action (apply, confirm, cancel…) into a 500 for the student. The
verification email in accounts/emails.py stays strict because sign-up can't
proceed without it.

Admin notifications go through Django's mail_admins(), which sends to the
ADMINS list in settings (driven by the ADMIN_EMAIL env var) and is a no-op
when that list is empty.
"""

from django.conf import settings
from django.core.mail import mail_admins, send_mail
from django.template.loader import render_to_string
from django.urls import reverse

SUBJECT_TAG = "[SUM 26001 Class Project]"


def project_url(project):
    """Absolute link to the project page, built from settings.SITE_URL.

    Emails sent from the service layer have no HttpRequest to call
    build_absolute_uri() on, so the base URL comes from configuration.
    """
    return settings.SITE_URL.rstrip("/") + reverse("project-detail", args=[project.pk])


def _send(subject, template, context, recipients):
    if not recipients:
        return
    body = render_to_string(template, context)
    # from_email=None uses DEFAULT_FROM_EMAIL from settings.
    send_mail(f"{SUBJECT_TAG} {subject}", body, None, recipients, fail_silently=True)


# ---------------------------------------------------------------------------
# Admin notifications (instructor)

def notify_admin_project_created(project):
    mail_admins(
        f"New project posted: {project.title}",
        f"{project.owner.full_name} <{project.owner.email}> posted a new project:\n\n"
        f"  {project.title} (group size {project.group_size})\n\n"
        f"{project_url(project)}\n",
        fail_silently=True,
    )


def notify_admin_project_fulfilled(project):
    mail_admins(
        f"Project fulfilled: {project.title}",
        f"“{project.title}” (owner {project.owner.full_name}) reached its group "
        f"size of {project.group_size} and is now fulfilled.\n\n"
        f"{project_url(project)}\n",
        fail_silently=True,
    )


# ---------------------------------------------------------------------------
# Student notifications

def notify_owner_new_application(application):
    project = application.project
    _send(
        f"New application to “{project.title}”",
        "projects/emails/application_received.txt",
        {"application": application, "project": project, "project_url": project_url(project)},
        [project.owner.email],
    )


def notify_application_confirmed(application):
    project = application.project
    _send(
        f"You joined “{project.title}”",
        "projects/emails/application_confirmed.txt",
        {"application": application, "project": project, "project_url": project_url(project)},
        [application.applicant.email],
    )


def notify_applications_declined(project, applicants, reason):
    """One email per declined applicant; `reason` is a full sentence."""
    board_url = settings.SITE_URL.rstrip("/") + reverse("home")
    for applicant in applicants:
        _send(
            f"About your application to “{project.title}”",
            "projects/emails/application_declined.txt",
            {
                "applicant": applicant,
                "project": project,
                "reason": reason,
                "board_url": board_url,
            },
            [applicant.email],
        )


def notify_team_fulfilled(project, member_emails):
    _send(
        f"Your team for “{project.title}” is complete",
        "projects/emails/project_fulfilled.txt",
        {"project": project, "project_url": project_url(project)},
        member_emails,
    )


def notify_team_cancelled(project, member_emails):
    _send(
        f"“{project.title}” was cancelled",
        "projects/emails/project_cancelled.txt",
        {"project": project, "project_url": project_url(project)},
        member_emails,
    )
