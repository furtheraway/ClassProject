from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Instructor's view of students — includes the private profile fields."""

    ordering = ["email"]
    list_display = ["email", "full_name", "department", "major", "is_active", "is_staff"]
    list_filter = ["is_active", "is_staff", "department", "study_year"]
    search_fields = ["email", "full_name", "department", "major"]
    readonly_fields = ["last_login", "date_joined"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Profile",
            {
                "fields": (
                    "full_name",
                    "department",
                    "major",
                    "languages",
                    "interests",
                    "skills",
                )
            },
        ),
        (
            "Private fields (instructor only)",
            {"fields": ("birth_year", "study_year", "gender", "height_cm")},
        ),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "password1", "password2"),
            },
        ),
    )
