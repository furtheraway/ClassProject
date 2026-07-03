from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)

from .models import User

# Profile fields shared by registration and profile editing (SPEC §3.1)
PROFILE_FIELDS = [
    "full_name",
    "birth_year",
    "department",
    "major",
    "study_year",
    "gender",
    "height_cm",
    "languages",
    "interests",
    "skills",
]

_TEXTAREA = forms.Textarea(attrs={"rows": 3})


class BootstrapFormMixin:
    """Adds Bootstrap CSS classes to every widget so templates stay plain."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                css = "form-select"
            elif isinstance(widget, forms.CheckboxInput):
                css = "form-check-input"
            else:
                css = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()


class RegistrationForm(BootstrapFormMixin, UserCreationForm):
    """Sign-up form: email + password + all profile fields, all required."""

    class Meta:
        model = User
        fields = ["email", *PROFILE_FIELDS]
        widgets = {"interests": _TEXTAREA, "skills": _TEXTAREA}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in PROFILE_FIELDS:
            self.fields[name].required = True


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    """Profile editing — same fields as registration, minus email/password."""

    class Meta:
        model = User
        fields = PROFILE_FIELDS
        widgets = {"interests": _TEXTAREA, "skills": _TEXTAREA}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in PROFILE_FIELDS:
            self.fields[name].required = True


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    # AuthenticationForm rejects inactive users; here "inactive" always means
    # "hasn't clicked the verification link yet" (SPEC §3.1), so say that.
    error_messages = {
        **AuthenticationForm.error_messages,
        "inactive": (
            "This account hasn't been verified yet. Check your inbox for the "
            "verification link, or request a new one below."
        ),
    }


class ResendVerificationForm(BootstrapFormMixin, forms.Form):
    email = forms.EmailField(label="Email address")


# Password reset (SPEC §6) — Django's built-in forms, restyled for Bootstrap.


class PasswordResetRequestForm(BootstrapFormMixin, PasswordResetForm):
    pass


class SetNewPasswordForm(BootstrapFormMixin, SetPasswordForm):
    pass
