from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "status", "group_size", "created_at"]
    list_filter = ["status"]
    search_fields = ["title", "keywords", "owner__full_name", "owner__email"]
    date_hierarchy = "created_at"
