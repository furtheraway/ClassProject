from django.contrib import admin

from .models import Application, Membership, Project


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0


class ApplicationInline(admin.TabularInline):
    model = Application
    extra = 0
    readonly_fields = ["created_at", "decided_at"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "status", "group_size", "created_at"]
    list_filter = ["status"]
    search_fields = ["title", "keywords", "owner__full_name", "owner__email"]
    date_hierarchy = "created_at"
    inlines = [MembershipInline, ApplicationInline]


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["applicant", "project", "status", "created_at", "decided_at"]
    list_filter = ["status"]
    search_fields = ["applicant__full_name", "applicant__email", "project__title"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["member", "project", "joined_at"]
    search_fields = ["member__full_name", "member__email", "project__title"]
