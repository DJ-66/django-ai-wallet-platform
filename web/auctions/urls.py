from . import views
from django.urls import path
from .views import bid_view, auction_detail, auction_list, signup_view, activate_view
from .views import pay_user
from .views import wallet_view
from . import views_ai

urlpatterns = [
    path("", auction_list, name="auction_list"),
    path("<int:auction_id>/", auction_detail, name="auction_detail"),
    path("<int:auction_id>/bid/", bid_view, name="place_bid"),
    path("signup/", signup_view, name="signup"),
    path("activate/<uidb64>/<token>/", views.activate_view, name="activate"),
    path("wallet/pay/<uuid:wallet_code>/", pay_user, name="pay_user"),
    path("wallet/", wallet_view, name="wallet"),
    path("pay/<str:pay_code>/", views.pay_user_short, name="pay_user_short"),
    path("node/", views.node_dashboard, name="node_dashboard"),
    path("ai/", views_ai.companion_list, name="companion_list"),
    path("ai/start/<slug:slug>/", views_ai.start_companion_chat, name="start_companion_chat"),
    path("ai/chat/<int:conversation_id>/", views_ai.ai_conversation, name="ai_conversation"),
    path(
    "ai/chat/<int:conversation_id>/delete/",
    views_ai.delete_conversation,
    name="delete_conversation",
),

    path(
    "ai/chat/<int:conversation_id>/pin/",
    views_ai.toggle_pin_conversation,
    name="toggle_pin_conversation",
),
    path(
    "ai/chat/<int:conversation_id>/stream/",
    views_ai.stream_ai_message,
    name="stream_ai_message",
),

    path(
    "auctions/<int:auction_id>/favorite/",
    views.toggle_favorite_auction,
    name="toggle_favorite_auction",
),

]
