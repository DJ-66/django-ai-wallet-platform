from . import views
from django.conf.urls.i18n import i18n_patterns
from django.urls import path, include
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
    path("i18n/", include("django.conf.urls.i18n")),
    path("profile/edit/", views.edit_profile, name="edit_profile"),
    path("u/<str:username>/", views.public_profile, name="public_profile"),
    path("feed/", views.feed_home, name="feed_home"),
    path("feed/post/<int:post_id>/pin/", views.toggle_pin_post, name="toggle_pin_post"),
    path("feed/post/<int:post_id>/delete/", views.delete_feed_post, name="delete_feed_post"),
    path("feed/post/<int:post_id>/comment/", views.add_post_comment, name="add_post_comment"),
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

    path(
    "auction/<int:auction_id>/buy-now/",
    views.buy_now_auction,
    name="buy_now_auction"
),

path(
    "feed/like/<int:post_id>/",
    views.toggle_post_like,
    name="toggle_post_like"
),

path(
    "feed/unlock/<int:post_id>/",
    views.unlock_feed_post,
    name="unlock_feed_post"
),

path(
    "feed/quick-tip/<str:wallet_code>/",
    views.quick_tip_user,
    name="quick_tip_user",
),

]
