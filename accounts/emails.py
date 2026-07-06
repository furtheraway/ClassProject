"""Email-verification helpers (SPEC §3.1, §6).

Django's `signing` module is the analogue of ASP.NET Core's Data Protection
(`ITimeLimitedDataProtector`): it HMAC-signs a payload with SECRET_KEY and a
timestamp, so the token needs no database table and expires on its own.
"""

from django.core import signing
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

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
