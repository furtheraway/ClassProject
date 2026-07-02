from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("projects/new/", views.project_create, name="project-new"),
    path("projects/<int:pk>/", views.project_detail, name="project-detail"),
    path("projects/<int:pk>/edit/", views.project_edit, name="project-edit"),
    path("projects/<int:pk>/cancel/", views.project_cancel, name="project-cancel"),
    path("projects/<int:pk>/uncancel/", views.project_uncancel, name="project-uncancel"),
    path("projects/<int:pk>/delete/", views.project_delete, name="project-delete"),
    path("projects/<int:pk>/apply/", views.project_apply, name="project-apply"),
    path("projects/<int:pk>/withdraw/", views.application_withdraw, name="application-withdraw"),
    path(
        "projects/<int:pk>/applications/<int:app_pk>/confirm/",
        views.application_confirm,
        name="application-confirm",
    ),
    path(
        "projects/<int:pk>/applications/<int:app_pk>/decline/",
        views.application_decline,
        name="application-decline",
    ),
    path(
        "projects/<int:pk>/members/<int:member_pk>/remove/",
        views.member_remove,
        name="member-remove",
    ),
]
