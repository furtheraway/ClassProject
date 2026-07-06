"""Notification emails for project-board events (SPEC §3.3, §6).

Every function here uses fail_silently=True: a SendGrid outage must never turn
a successful action (apply, confirm, cancel…) into a 500 for the student. The
verification email in accounts/emails.py stays strict because sign-up can't
proceed without it.

Admin notifications go to every active staff account (the instructor) via
accounts.emails.notify_staff() — recipients live in the database, so there is
no admin-address setting to configure or forget.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from accounts.emails import SUBJECT_TAG, notify_staff


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
    notify_staff(
        f"New project posted: {project.title}",
        f"{project.owner.full_name} <{project.owner.email}> posted a new project:\n\n"
        f"  {project.title} (group size {project.group_size})\n\n"
        f"{project_url(project)}\n",
    )


def notify_admin_project_fulfilled(project):
    notify_staff(
        f"Project fulfilled: {project.title}",
        f"“{project.title}” (owner {project.owner.full_name}) reached its group "
        f"size of {project.group_size} and is now fulfilled.\n\n"
        f"{project_url(project)}\n",
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
