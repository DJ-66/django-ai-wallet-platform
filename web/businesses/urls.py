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
        "my/businesses/",
        views.my_businesses,
        name="my_businesses",
    ),
    path(
        "<slug:slug>/edit/",
        views.business_edit,
        name="edit",
    ),
    path(
        "<slug:slug>/fan/",
        views.toggle_business_fan,
        name="toggle_fan",
    ),
    path(
        "<slug:slug>/update/new/",
        views.publish_business_update,
        name="publish_update",
    ),
    path(
        "<slug:slug>/gallery/upload/",
        views.upload_business_media,
        name="upload_media",
    ),

    path(
        "<slug:slug>/gallery/delete/",
        views.delete_business_media,
        name="delete_media",
    ),

    path(
        "<slug:slug>/",
        views.business_detail,
        name="detail",
    ),
]
