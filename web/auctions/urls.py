from . import views
from django.conf.urls.i18n import i18n_patterns
from django.urls import path, include
from .views import bid_view, auction_detail, auction_list, signup_view, activate_view
from .views import pay_user
from .views import wallet_view
from . import views_ai
from . import views_events


urlpatterns = [
    path(
        "webhooks/btcpay/",
        views.btcpay_webhook,
        name="btcpay_webhook",
    ),



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
    path(
        "search/",
        views.fanz_search,
        name="fanz_search",
    ),
    path(
        "founder/tienda/",
        views.founder_tienda,
        name="founder_tienda",
    ),
    path(
        "founder/tienda/sui/verify/",
        views.verify_founder_sui_payment,
        name="verify_founder_sui_payment",
    ),
    path(
        "founder/tienda/vending/quote/",
        views.quote_founder_vending,
        name="quote_founder_vending",
    ),
    path(
        "founder/tienda/vending/<int:item_id>/buy/",
        views.buy_founder_vending,
        name="buy_founder_vending",
    ),
    path(
        "founder/tienda/vending/<int:item_id>/cancel/",
        views.cancel_founder_vending,
        name="cancel_founder_vending",
    ),
    path(
        "founder/tienda/<int:listing_id>/buy/",
        views.buy_founder_tienda_listing,
        name="buy_founder_tienda_listing",
    ),

    path(
        "founder/tienda/<int:listing_id>/bid/",
        views.bid_founder_tienda_listing,
        name="bid_founder_tienda_listing",
    ),

    path(
        "founder/tienda/<int:listing_id>/confirm/",
        views.confirm_founder_tienda_purchase,
        name="confirm_founder_tienda_purchase",
    ),
    
    path(
        "founder/<int:founder_id>/p2p/list/",
        views.list_founder_p2p_fixed,
        name="list_founder_p2p_fixed",
    ),

    path(
        "founder/p2p/<int:listing_id>/buy/",
        views.buy_founder_p2p_fixed_listing,
        name="buy_founder_p2p_fixed_listing",
    ),

    path(
        "founder/p2p/<int:listing_id>/offer/",
        views.bid_founder_p2p_blind_listing,
        name="bid_founder_p2p_blind_listing",
    ),

    path(
        "founder/p2p/<int:listing_id>/cancel/",
        views.cancel_founder_p2p_listing,
        name="cancel_founder_p2p_listing",
    ),

    path(
        "founder/<str:handle>/",
        views.founder_knowledge,
        name="founder_knowledge",
    ),

    path(
        "platform/accounts/<int:user_id>/login-as/",
        views.login_as_platform_account,
        name="login_as_platform_account",
    ),

    path(
        "platform/accounts/return/",
        views.return_from_platform_account,
        name="return_from_platform_account",
    ),
    path(
        "platform/accounts/create/",
        views.create_platform_account,
        name="create_platform_account",
    ),
    path(
        "profile/translate/",
        views.translate_profile,
        name="translate_profile",
    ),
    path(
        "platform/accounts/",
        views.platform_accounts_dashboard,
        name="platform_accounts_dashboard",
    ),

    path(
        "events/",
        views_events.event_list,
        name="event_list",
    ),

    path(
        "events/<int:event_id>/",
        views_events.event_detail,
        name="event_detail",
    ),

    path(
        "events/<int:event_id>/edit/",
        views_events.edit_event,
        name="edit_event",
    ),

    path(
        "events/<int:event_id>/delete/",
        views_events.delete_event,
        name="delete_event",
    ),

    path(
        "events/create/",
        views_events.create_event,
        name="create_event",
    ),

    path("<str:username>/fan/", views.toggle_fan, name="toggle_fan"),
    path("notifications/", views.notifications_page, name="notifications"),
    path("inbox/", views.inbox, name="inbox"),
    path("messages/<int:conversation_id>/", views.conversation_detail, name="conversation_detail"),
    path("messages/<int:conversation_id>/delete/", views.delete_conversation, name="delete_dm_conversation"),
    path("u/<str:username>/message/", views.start_conversation, name="start_conversation"),
    path("notification-sounds.json", views.notification_sounds_json, name="notification_sounds_json"),
    path("notifications/check/", views.latest_notification_check, name="latest_notification_check"),

    path("terms/", views.terms_view, name="terms"),

    path(
    "notifications/<int:notification_id>/delete/",
    views.delete_notification,
    name="delete_notification"
    ),
    path("u/<str:username>/", views.public_profile, name="public_profile"),
    path("feed/", views.feed_home, name="feed_home"),
    path("feed/post/<int:post_id>/", views.post_detail, name="post_detail"),
    path(
        "feed/post/<int:post_id>/translate/",
        views.translate_post,
        name="translate_post",
    ),
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

path(
    "discover/",
    views.discovery_home,
    name="discovery_home",
),

path(
    "discover/<slug:slug>/",
    views.discovery_hub_detail,
    name="discovery_hub_detail",
),




path(
    "tags/",
    views.discovery_hub,
    name="discovery_hub",
),


path(
    "tag/<str:tag_name>/",
    views.hashtag_feed,
    name="hashtag_feed",
),


]
