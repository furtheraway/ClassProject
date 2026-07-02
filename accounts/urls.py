from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm

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
    path("users/<int:pk>/", views.profile_detail, name="profile-detail"),
    path("profile/edit/", views.profile_edit, name="profile-edit"),
]
