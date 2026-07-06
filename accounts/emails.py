"""Email-verification helpers and instructor notifications (SPEC §3.1, §6).

Django's `signing` module is the analogue of ASP.NET Core's Data Protection
(`ITimeLimitedDataProtector`): it HMAC-signs a payload with SECRET_KEY and a
timestamp, so the token needs no database table and expires on its own.
"""

from django.core import signing
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from .models import User

SUBJECT_TAG = "[SUM 26001 Class Project]"

VERIFICATION_SALT = "accounts.email-verification"
VERIFICATION_MAX_AGE = 60 * 60 * 24 * 3  # 3 days (SPEC §3.1)


def make_verification_token(user):
    return signing.dumps(user.pk, salt=VERIFICATION_SALT)


def read_verification_token(token):
    """Return the user pk inside the token, or None if invalid/expired."""
    try:
        return signing.loads(token, salt=VERIFICATION_SALT, max_age=VERIFICATION_MAX_AGE)
    except signing.BadSignature:  # covers tampering *and* expiry
        return None


def send_verification_email(request, user):
    verify_url = request.build_absolute_uri(
        reverse("verify-email", args=[make_verification_token(user)])
    )
    body = render_to_string(
        "accounts/emails/verify_email.txt",
        {"user": user, "verify_url": verify_url},
    )
    # from_email=None uses DEFAULT_FROM_EMAIL from settings.
    send_mail("Verify your SUM 26001 Class Project account", body, None, [user.email])


def notify_staff(subject, body):
    """Email the instructor: every active staff account (SPEC §6).

    Recipients come from the database instead of an ADMIN_EMAIL setting —
    seeding the instructor with `createsuperuser` is all the setup there is,
    and no staff accounts (a fresh database) simply means no email.
    fail_silently: an email hiccup must never break the student action that
    triggered the notification.
    """
    recipients = list(
        User.objects.filter(is_staff=True, is_active=True).values_list("email", flat=True)
    )
    if not recipients:
        return
    send_mail(f"{SUBJECT_TAG} {subject}", body, None, recipients, fail_silently=True)


def notify_admin_new_user(user):
    """Tell the instructor a student registered (SPEC §6)."""
    notify_staff(
        f"New user registered: {user.full_name}",
        f"{user.full_name} <{user.email}> just registered "
        "(account inactive until they verify their email).\n",
    )
