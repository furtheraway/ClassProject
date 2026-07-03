from django.urls import path

from . import views

urlpatterns = [
    path("report/", views.my_report, name="my-report"),
]
