from django.urls import path

from . import views


app_name = "businesses"

urlpatterns = [
    path("<slug:slug>/", views.business_detail, name="detail"),
]
