from django.urls import path

from . import views


app_name = "businesses"

urlpatterns = [
    path(
        "create/",
        views.business_create,
        name="create",
    ),
    path(
        "<slug:slug>/fan/",
        views.toggle_business_fan,
        name="toggle_fan",
    ),
    path(
        "<slug:slug>/",
        views.business_detail,
        name="detail",
    ),
]
