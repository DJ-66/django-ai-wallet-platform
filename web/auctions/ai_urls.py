from django.urls import path
from . import views_ai

urlpatterns = [
    path("", views_ai.companion_list, name="ai_home"),

    path(
        "chat/<int:conversation_id>/",
        views_ai.ai_conversation,
        name="ai_chat"
    ),

    path(
        "chat/<int:conversation_id>/stream/",
        views_ai.stream_ai_message,
        name="ai_stream"
    ),

    path(
        "chat/<int:conversation_id>/delete/",
        views_ai.delete_conversation,
        name="delete_conversation"
    ),

    path(
        "chat/<int:conversation_id>/pin/",
        views_ai.toggle_pin_conversation,
        name="toggle_pin_conversation"
    ),

    path(
        "start/<slug:slug>/",
        views_ai.start_companion_chat,
        name="start_companion_chat"
    ),
]
