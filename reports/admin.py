"""Instructor-only views of reports and peer reviews (SPEC §3.5).

The admin is the ONLY place peer-review data is ever shown.
"""

import csv

from django.contrib import admin
from django.http import HttpResponse

from .models import PeerReview, Report


class PeerReviewInline(admin.TabularInline):
    model = PeerReview
    extra = 0


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["author", "project", "work_url", "updated_at"]
    list_filter = ["project"]
    search_fields = ["author__full_name", "author__email", "project__title"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [PeerReviewInline]


@admin.register(PeerReview)
class PeerReviewAdmin(admin.ModelAdmin):
    list_display = ["reviewer", "reviewee", "project", "score", "comments"]
    list_filter = ["report__project"]
    search_fields = [
        "report__author__full_name",
        "reviewee__full_name",
        "report__project__title",
    ]
    actions = ["export_as_csv"]

    @admin.display(description="Reviewer", ordering="report__author__full_name")
    def reviewer(self, obj):
        return obj.report.author

    @admin.display(description="Project", ordering="report__project__title")
    def project(self, obj):
        return obj.report.project

    @admin.action(description="Export selected peer reviews to CSV")
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = "attachment; filename=peer_reviews.csv"
        writer = csv.writer(response)
        writer.writerow(["reviewer", "reviewer_email", "reviewee", "reviewee_email",
                         "project", "score", "comments"])
        for review in queryset.select_related("report__author", "report__project", "reviewee"):
            writer.writerow([
                review.report.author.full_name,
                review.report.author.email,
                review.reviewee.full_name,
                review.reviewee.email,
                review.report.project.title,
                review.score,
                review.comments,
            ])
        return response
