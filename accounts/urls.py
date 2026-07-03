from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm, PasswordResetRequestForm, SetNewPasswordForm

urlpatterns = [
    path("accounts/register/", views.register, name="register"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            authentication_form=LoginForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Email verification (SPEC §3.1)
    path("accounts/verify/<str:token>/", views.verify_email, name="verify-email"),
    path("accounts/resend-verification/", views.resend_verification, name="resend-verification"),
    # Password reset (SPEC §6) — Django's built-in four-step flow. The view
    # names below are what Django's own machinery reverses (e.g. the email
    # links to "password_reset_confirm"), so they keep the stock snake_case.
    path(
        "accounts/password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/emails/password_reset_email.txt",
            subject_template_name="accounts/emails/password_reset_subject.txt",
            form_class=PasswordResetRequestForm,
        ),
        name="password_reset",
    ),
    path(
        "accounts/password-reset/sent/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "accounts/password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            form_class=SetNewPasswordForm,
        ),
        name="password_reset_confirm",
    ),
    path(
        "accounts/password-reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("users/<int:pk>/", views.profile_detail, name="profile-detail"),
    path("profile/edit/", views.profile_edit, name="profile-edit"),
]
