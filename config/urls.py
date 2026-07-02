"""Root URL configuration — routes live in each app's urls.py (SPEC §5)."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("projects.urls")),
]
