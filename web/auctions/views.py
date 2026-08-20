from django.utils.translation import gettext as _, override
import os
import json
import random
import secrets
from businesses.models import BusinessListing
from decimal import Decimal
from .models import Hashtag, PostUnlock
from .hashtags import sync_post_hashtags
import qrcode
import requests
from .qr_utils import make_branded_referral_qr
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage, EmailMultiAlternatives, send_mail
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Case, IntegerField, Q, Sum, Value, When, Count, Exists, OuterRef
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST
from .fanz_search import search_fanz
from businesses.services import (
    process_business_referral_activation,
)
from .discovery_services import (
    get_discovery_events,
    get_discovery_metrics,
    get_live_discovery_auctions,
    get_live_hashtag_auctions,
    get_live_platform_auction_count,
    get_discovery_creators,
)
from .services import (
    close_auction,
    get_public_hashtag_posts,
    place_bid,
    prepare_auction_cards,
    send_digital_delivery_message,
    prepare_feed_posts,
    localize_notification_message,
    translate_direct_message_for_language,
)
from .utils import get_system_wallet
from businesses.models import BusinessUpdate
from businesses.services import get_discovery_businesses
from .ai_memory import touch_ai_creator_memory
from datetime import timedelta
from .forms import (
    DirectMessageForm,
    FeedPostForm,
    FeedPostTranslationForm,
    SignUpForm,
    UserProfileForm,
    UserProfileTranslationForm,
    PlatformAccountForm,
)
from .models import (
    Event,
    FounderBid,
    FounderListing,
    FounderAccount,
    FounderOwnershipLedger,
    AuctionTranslation,
    DigitalItemTranslation,
    AICompanion,
    AIConversation,
    AIMessage,
    AICreatorMemory,
    AIFanMemoryNote,
    Auction,
    BidWallet,
    Conversation,
    DirectMessage,
    DiscoveryHub,
    DiscoveryHubTranslation,
    Fan,
    FavoriteAuction,
    FeedPost,
    FeedPostTranslation,
    FeedPostMedia,
    NodeProfile,
    Notification,
    PostComment,
    PostLike,
    PostUnlock,
    UserProfile,
    UserProfileTranslation,
    WalletTransaction,
    NotificationSound,
)
from .founder_services import (
    place_founder_blind_bid,
    purchase_tienda_fixed_listing,
    purchase_p2p_fixed_listing,
    cancel_founder_listing,
    get_authoritative_root,
)
from .founder_valuation import get_founder_valuation
from .founder_valuation_i18n import (
    get_localized_valuation_presentation,
)

def hashtag_feed(request, tag_name):
    language = request.GET.get(
        "lang",
        getattr(request, "LANGUAGE_CODE", "en"),
    )
    hashtag = get_object_or_404(
        Hashtag,
        name=tag_name.lower()
    )

    posts = prepare_feed_posts(
        get_public_hashtag_posts(hashtag),
        language=language,
    )

    auction_queryset = get_live_hashtag_auctions(hashtag)

    auction_paginator = Paginator(
        auction_queryset,
        24,
    )

    auction_page = auction_paginator.get_page(
        request.GET.get("auction_page")
    )

    auction_page.object_list = prepare_auction_cards(
        auction_page.object_list,
        request.user,
        language=language,
    )

    trending_hashtags = (
        Hashtag.objects
        .exclude(id=hashtag.id)
        .order_by("-usage_count", "name")[:10]
    )
    total_hashtags = Hashtag.objects.count()
    unlocked_post_ids = set()

    if request.user.is_authenticated:
        unlocked_post_ids = set(
            PostUnlock.objects.filter(user=request.user)
            .values_list("post_id", flat=True)
        )
    live_auction_count = get_live_platform_auction_count()

    return render(
        request,
        "auctions/hashtag_feed.html",
        {
            "hashtag": hashtag,
            "posts": posts,
            "auction_page": auction_page,
            "trending_hashtags": trending_hashtags,
            "live_auction_count": live_auction_count,
            "total_hashtags": total_hashtags,
            "unlocked_post_ids": unlocked_post_ids,
            "language": language,
        }
    )

def get_featured_discovery_hubs(limit=6):
    return (
        DiscoveryHub.objects
        .filter(is_active=True)[:limit]
    )

def discovery_hub(request):
    hub = (
        DiscoveryHub.objects
        .filter(slug="discover-fanz", is_active=True)
        .first()
    )

    featured_hubs = get_featured_discovery_hubs()

    trending_hashtags = (
        Hashtag.objects
        .filter(usage_count__gt=0)
        .order_by("-usage_count", "name")[:20]
    )

    newest_hashtags = (
        Hashtag.objects
        .order_by("-created_at")[:20]
    )

    recent_posts = (
        FeedPost.objects
        .select_related("user")
        .prefetch_related("hashtags")
        .order_by("-created_at")[:20]
    )

    creators = (
        UserProfile.objects
        .select_related("user")
        .order_by("-created_at")[:20]
    )

    return render(
        request,
        "auctions/discovery_hub.html",
        {
            "hub": hub,
            "featured_hubs": featured_hubs,
            "trending_hashtags": trending_hashtags,
            "newest_hashtags": newest_hashtags,
            "recent_posts": recent_posts,
            "creators": creators,
        }
    )


def discovery_home(request):
    language = request.GET.get(
        "lang",
        getattr(request, "LANGUAGE_CODE", "en"),
    )

    translations = (
        DiscoveryHubTranslation.objects
        .select_related("hub")
        .filter(
            language=language,
            is_active=True,
            hub__is_active=True,
        )
        .order_by("hub__sort_order", "title")
    )

    return render(
        request,
        "auctions/discovery_home.html",
        {
            "translations": translations,
            "language": language,
        }
    )

def discovery_hub_detail(request, slug):
    language = request.GET.get(
        "lang",
        getattr(request, "LANGUAGE_CODE", "en"),
    )

    hub = (
        DiscoveryHub.objects
        .filter(slug=slug, is_active=True)
        .first()
    )

    if hub is None:
        raise Http404("Discovery Hub not found")

    translation = hub.get_translation(language)

    if translation is None:
        raise Http404("Discovery Hub translation not found")

    hashtag_name = hub.hashtag.lstrip("#").strip().lower()

    hashtag = (
        Hashtag.objects
        .filter(name=hashtag_name)
        .first()
    )

    if hashtag:
        posts = prepare_feed_posts(
            get_public_hashtag_posts(hashtag),
            language=language,
        )
    else:
        posts = []

    businesses = get_discovery_businesses(hub)
    events = get_discovery_events(hub)
    creators = get_discovery_creators(
        hub,
        language=language,
    )

    auction_queryset = get_live_discovery_auctions(hub)

    auction_paginator = Paginator(
        auction_queryset,
        24,
    )

    auction_page = auction_paginator.get_page(
        request.GET.get("auction_page")
    )

    auction_page.object_list = prepare_auction_cards(
        auction_page.object_list,
        request.user,
        language=language,
    )

    metrics = get_discovery_metrics(
        hub,
        hashtag=hashtag,
    )
    template_key = translation.template_name or "default"
    template_name = f"auctions/discovery/{template_key}.html"

    return render(
        request,
        template_name,
        {
            "hub": hub,
            "translation": translation,
            "language": language,
            "hashtag": hashtag,
            "posts": posts,
            "businesses": businesses,
            "events": events,
            "metrics": metrics,
            "auction_page": auction_page,
            "creators": creators,
        },
    )


@login_required
def fanz_search(request):
    query = request.GET.get("q", "").strip()

    language = request.GET.get(
        "lang",
        getattr(request, "LANGUAGE_CODE", "en"),
    )

    result = search_fanz(
        query,
        viewer=request.user,
        language=language,
        limit_per_type=8,
    )

    return render(
        request,
        "auctions/fanz_search.html",
        {
            "search_query": query,
            "search_result": result,
            "search_results": result["results"],
            "search_groups": result["groups"],
        },
    )

def notification_sounds_json(request):
    sounds = {}

    for sound in NotificationSound.objects.filter(active=True):
        sounds[sound.sound_type] = sound.file.url

    return JsonResponse(sounds)



def latest_notification_check(request):
    if not request.user.is_authenticated:
        return JsonResponse({"latest_id": None, "sound_type": None})

    notification = (
        Notification.objects
        .filter(user=request.user)
        .order_by("-id")
        .first()
    )

    if not notification:
        return JsonResponse({"latest_id": None, "sound_type": None})

    language = request.GET.get(
        "lang",
        getattr(
            request,
            "LANGUAGE_CODE",
            "en",
        ),
    )

    language = (
        language or "en"
    ).lower().split("-")[0]

    text = (notification.message or "").lower()

    if "outbid" in text:
        sound_type = "social"
    elif (
        "winner" in text
        or "purchase complete" in text
        or "download link inside" in text
        or "tipped" in text
        or "credits" in text
        or "unlocked" in text
        or "premium" in text
        or "support means" in text
    ):
        sound_type = "cash"
    else:
        sound_type = "social"

    return JsonResponse({
        "latest_id": notification.id,
        "sound_type": sound_type,
        "message": localize_notification_message(
            notification,
            language=language,
        ),
    })


def ai_log(event, **kwargs):
    parts = [event]
    parts.extend(f"{k}={v}" for k, v in kwargs.items())
    print(" | ".join(parts), flush=True)

def send_auto_thank_you_dm(sender, recipient, event_type):
    if not sender or not recipient:
        return

    if sender == recipient:
        return

    username = recipient.username

    message_bank = {
        "like": [
            f"Thanks for the ❤️  @{username}! I 'm glad you're one of my Fanz",
            f"That means a lot @{username}. Thanks for liking my post! ⭐",
            f"You're awesome @{username}! Thanks for the support ❤️",
        ],
        "tip": [
            f"Thanks for the tip @{username}! I really appreciate the Love ❤️.",
            f"You're the best @{username}! Thank you for the credits 💰",
            f"Much appreciated @{username}! Your support means a lot. 👍",
        ],
        "unlock": [
            f"Thanks for unlocking my post @{username}! Hope you enjoy it 🔓",
            f"I appreciate the support @{username}. Enjoy the content! 💎",
            f"You Rock @{username}! Thanks for unlocking my post. 😎",
        ],
        "fan": [
            f"I love all my Fanz @{username}! We should chat ⭐",
            f"Welcome @{username}! You're in my circle of Fanz. 🤩",
            f"You're awesome @{username}! Thanks for joining my Fanz. 😆",
        ],
    }

    body = random.choice(message_bank.get(event_type, [
        f"Thanks @{username}! I really appreciate the ❤️."
    ]))

    conversation = Conversation.objects.filter(
        participants=sender
    ).filter(
        participants=recipient
    ).first()

    if not conversation:
        conversation = Conversation.objects.create()
        conversation.participants.add(sender, recipient)

    dm = DirectMessage.objects.create(
        conversation=conversation,
        sender=sender,
        body=body,
        is_read=False,
        generated_by_ai=False,
        message_type=DirectMessage.SYSTEM,
    )

    conversation.last_message_at = timezone.now()
    conversation.save(update_fields=["last_message_at"])

    Notification.objects.create(
        user=recipient,
        actor=sender,
        notification_type=Notification.MESSAGE,
        message=get_sender_reward_notification_title(
            sender=sender,
            recipient=recipient,
            event_type=event_type,
        ),
        metadata={
            "kind": "sender_reward",
            "event_type": event_type,
        },
    )

    if getattr(recipient.profile, "is_ai_influencer", False):
        ai_log("AI_DM_TRIGGER", recipient=f"@{recipient.username}", sender=f"@{sender.username}", message_id=dm.id)

def get_sender_reward_notification_title(sender, recipient, event_type):
    creator_username = sender.username
    fan_username = recipient.username

    title_bank = {
        "like": [
            f"@{creator_username}: Thanks for the ❤️, @{fan_username}",
            f"@{creator_username}: You made my day, @{fan_username} ✨",
            f"@{creator_username}: Love seeing you like my posts ❤️",
            f"@{creator_username}: Keep the love coming, @{fan_username} 🤩",
        ],

        "tip": [
            f"@{creator_username}: Thanks for the credits, @{fan_username} ❤️",
            f"@{creator_username}: You’re amazing, @{fan_username} 💎 We should Chat",
            f"@{creator_username}: Your support means a lot 💰",
            f"@{creator_username}: That was sweet of you, @{fan_username} 🧁",
        ],

        "unlock": [
            f"@{creator_username}: Thanks for unlocking my post 🔓",
            f"@{creator_username}: Hope you enjoy it, @{fan_username}",
            f"@{creator_username}: You picked a good one 😉",
            f"@{creator_username}: Enjoy the exclusive content 🔥",
        ],

        "fan": [
            f"@{creator_username}: Welcome to my Fanz ⭐",
            f"@{creator_username}: Glad you're here, @{fan_username} 😎",
            f"@{creator_username}: Thanks for joining my Fanz ❤️",
        ],
    }

    return random.choice(
        title_bank.get(
            event_type,
            [f"@{creator_username}: Thanks @{fan_username} 💜"]
        )
    )



def generate_referral_code():
    return secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:10]

def auction_list(request):
    now = timezone.now()

    expired_auctions = Auction.objects.filter(
        status="live",
        ends_at__lte=now
    )

    for auction in expired_auctions:
        try:
            close_auction(auction.id)
        except Exception:
            pass

    auctions = Auction.objects.filter(
        status="live"
    ).order_by("ends_at")

    language = request.GET.get(
        "lang",
        getattr(request, "LANGUAGE_CODE", "en"),
    )

    auctions = prepare_auction_cards(
        auctions,
        request.user,
        now=now,
        language=language,
    )

    return render(request, "auction_list.html", {
        "auctions": auctions,
        "language": language,
    })

def auction_detail(request, auction_id):
    auction = get_object_or_404(Auction, id=auction_id)
    last_bid = auction.bids.order_by("-created_at").first()

    is_high_bidder = (
        request.user.is_authenticated
        and last_bid is not None
        and last_bid.user_id == request.user.id
)

    if auction.status == "live" and timezone.now() >= auction.ends_at:
        try:
            close_auction(auction.id)
            auction.refresh_from_db()
        except Exception as e:
            messages.error(request, str(e))

    wallet = None

    buy_now_price = auction.current_price + Decimal("25.00")

    is_favorited = False

    if request.user.is_authenticated:
        wallet, created = BidWallet.objects.get_or_create(user=request.user)

        is_favorited = FavoriteAuction.objects.filter(
           user=request.user,
           auction=auction
        ).exists()

    seconds_remaining = max(
    0,
    int((auction.ends_at - timezone.now()).total_seconds())
    )

    hero_media = auction.hero_media()
    gallery_media = auction.gallery_media()
    active_video = auction.active_video()

    language = request.GET.get(
        "lang",
        getattr(request, "LANGUAGE_CODE", "en"),
    )

    language = str(language).lower().split("-")[0]

    if language not in ("en", "es", "pt"):
        language = "en"

    digital_item_translation = (
        DigitalItemTranslation.objects
        .filter(
            digital_item=auction.digital_item,
            language=language,
        )
        .first()
    )

    digital_item_title = auction.digital_item.title
    digital_item_description = auction.digital_item.description
    digital_item_file = auction.digital_item.file
    digital_item_delivery_url = auction.digital_item.delivery_url

    if digital_item_translation:
        if digital_item_translation.title:
            digital_item_title = digital_item_translation.title

        if digital_item_translation.description:
            digital_item_description = digital_item_translation.description

        if digital_item_translation.file:
            digital_item_file = digital_item_translation.file

        if digital_item_translation.delivery_url:
            digital_item_delivery_url = (
                digital_item_translation.delivery_url
            )

    auction_translation = (
        AuctionTranslation.objects
        .filter(
            auction=auction,
            language=language,
        )
        .first()
    )

    auction_title = auction.title
    auction_description = ""
    localized_hero_image = None

    if auction_translation:
        if auction_translation.title:
            auction_title = auction_translation.title

        if auction_translation.description:
            auction_description = auction_translation.description

        if (
            auction_translation.use_language_hero
            and auction_translation.hero_image
        ):
            localized_hero_image = auction_translation.hero_image

    return render(request, "auction_detail.html", {
        "auction": auction,
        "wallet": wallet,
        "seconds_remaining": seconds_remaining,
        "is_high_bidder": is_high_bidder,
        "is_favorited": is_favorited,
        "buy_now_price": buy_now_price,
        "hero_media": hero_media,
        "gallery_media": gallery_media,
        "active_video": active_video,
        "language": language,
        "auction_translation": auction_translation,
        "auction_title": auction_title,
        "auction_description": auction_description,
        "localized_hero_image": localized_hero_image,
        "digital_item_translation": digital_item_translation,
        "digital_item_title": digital_item_title,
        "digital_item_description": digital_item_description,
        "digital_item_file": digital_item_file,
        "digital_item_delivery_url": digital_item_delivery_url,

    })


def ensure_api_key(node):
    if not node.api_key:
        node.api_key = NodeProfile.generate_api_key()
        node.save(update_fields=["api_key"])


def feed_home(request):
    language = request.GET.get(
        "lang",
        getattr(request, "LANGUAGE_CODE", "en"),
    )

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect("login")

        form = FeedPostForm(
            request.POST,
            request.FILES,
            current_username=request.user.username,
        )

        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user
            post.title = post.title.strip()
            post.content = post.content.strip()

            if post.is_paid:
                post.is_public = False

                if post.unlock_price < 1:
                    post.unlock_price = 1
            else:
                post.unlock_price = 0

            post.save()

            media_items = form.cleaned_data.get("images", [])

            for display_order, media_item in enumerate(media_items):
                FeedPostMedia.objects.create(
                    post=post,
                    file=media_item["file"],
                    media_type=media_item["media_type"],
                    caption="",
                    display_order=display_order,
                    is_active=True,
                )

            sync_post_hashtags(post)

            return redirect("feed_home")

        else:
            print(
                "FEED POST FORM ERRORS:",
                form.errors,
                flush=True,
            )

            
    else:
        form = FeedPostForm()

    posts = (
        FeedPost.objects
        .filter(
            Q(is_public=True, is_paid=False)
            |
            Q(
                is_pinned=True,
                user__username__iexact="DJ",
            )
        )


        .annotate(
            community_pin_rank=Case(
                When(
                    is_pinned=True,
                    user__username__iexact="DJ",
                    then=Value(1),
                ),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by(
            "-community_pin_rank",
            "-created_at"
        )
    )

    posts = prepare_feed_posts(
        posts,
        language=language,
    )

    business_updates = (
        BusinessUpdate.objects
        .select_related(
            "business",
            "author",
        )
        .filter(
            is_published=True,
            scheduled_for__lte=timezone.now(),
        )
    )
    
    now = timezone.now()
    event_window_end = now + timedelta(hours=24)

    events = (
        Event.objects
        .select_related(
            "creator",
            "business",
        )
        .filter(
            is_published=True,
            is_cancelled=False,
        )
        .filter(
            Q(end_at__gte=now)
            |
            Q(end_at__isnull=True, start_at__gte=now)
        )
    )

    if request.user.is_authenticated:
        unlocked_post_ids = PostUnlock.objects.filter(
            user=request.user
        ).values_list("post_id", flat=True)

        recent_notifications = Notification.objects.filter(
            user=request.user
        ).order_by("-created_at")[:5]
    else:
        unlocked_post_ids = []
        recent_notifications = []

    feed_items = []

    for post in posts:
        feed_items.append({
            "item_type": "post",
            "created_at": post.created_at,
            "object": post,
        })

    for update in business_updates:
        feed_items.append({
            "item_type": "business_update",
            "created_at": update.created_at,
            "object": update,
        })

    for event in events:
        feed_items.append({
            "item_type": "event",
            "created_at": event.created_at,
            "object": event,
        })

    feed_items.sort(
        key=lambda item: (
            (
                item["item_type"] == "post"
                and item["object"].is_pinned
                and item["object"].user.username.lower() == "dj"
            ),
            item["created_at"],
        ),
        reverse=True,
    )


    return render(request, "auctions/feed_home.html", {
        "form": form,
        "posts": posts,
        "feed_items": feed_items,
        "unlocked_post_ids": unlocked_post_ids,
        "recent_notifications": recent_notifications,
        "language": language,

    })

@login_required
def cancel_founder_p2p_listing(request, listing_id):
    listing = get_object_or_404(
        FounderListing.objects.select_related(
            "founder_account",
            "seller_root",
        ),
        pk=listing_id,
    )

    handle = listing.founder_account.handle

    if request.method != "POST":
        return redirect(
            "founder_knowledge",
            handle=handle,
        )

    try:
        cancel_founder_listing(
            listing=listing,
            requester=request.user,
        )

        messages.success(
            request,
            _(
                "Founder listing for @%(handle)s was cancelled."
            ) % {
                "handle": handle,
            },
        )

    except Exception as exc:
        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "founder_knowledge",
        handle=handle,
    )


@login_required
def buy_founder_p2p_fixed_listing(request, listing_id):
    if request.method != "POST":
        return redirect(
            "founder_knowledge",
            handle=FounderListing.objects.get(
                pk=listing_id
            ).founder_account.handle,
        )

    listing = get_object_or_404(
        FounderListing.objects.select_related(
            "founder_account",
        ),
        pk=listing_id,
    )

    handle = listing.founder_account.handle

    try:
        result = purchase_p2p_fixed_listing(
            listing=listing,
            buyer=request.user,
        )

        messages.success(
            request,
            _(
                "🏡 You purchased @%(handle)s for "
                "%(credits)s credits."
            ) % {
                "handle": result[
                    "founder_account"
                ].handle,
                "credits": result[
                    "sale_price_credits"
                ],
            },
        )

    except Exception as exc:
        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "founder_knowledge",
        handle=handle,
    )


@login_required
def bid_founder_p2p_blind_listing(request, listing_id):
    listing = get_object_or_404(
        FounderListing.objects.select_related(
            "founder_account",
        ),
        pk=listing_id,
    )

    handle = listing.founder_account.handle

    if request.method != "POST":
        return redirect(
            "founder_knowledge",
            handle=handle,
        )

    try:
        amount = int(
            request.POST.get("amount_credits", 0)
        )
    except (TypeError, ValueError):
        messages.error(
            request,
            _("Invalid Founder offer amount."),
        )
        return redirect(
            "founder_knowledge",
            handle=handle,
        )

    try:
        result = place_founder_blind_bid(
            listing=listing,
            bidder=request.user,
            amount_credits=amount,
        )

        messages.success(
            request,
            _(
                "💰 Funded offer of %(credits)s credits "
                "placed on @%(handle)s."
            ) % {
                "credits": result["bid"].amount_credits,
                "handle": handle,
            },
        )

    except Exception as exc:
        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "founder_knowledge",
        handle=handle,
    )


@login_required
def bid_view(request, auction_id):
    auction = get_object_or_404(Auction, id=auction_id)

    try:
        place_bid(auction.id, request.user)
        messages.success(request, "Bid placed!")
    except Exception as e:
        messages.error(request, str(e))

    return redirect("auction_detail", auction_id=auction.id)


@login_required
def wallet_view(request):
    wallet, _ = BidWallet.objects.get_or_create(user=request.user)

    transactions = WalletTransaction.objects.filter(
        Q(sender=wallet) | Q(receiver=wallet)
    ).order_by("-created_at")[:10]

    return render(request, "auctions/wallet.html", {
        "wallet": wallet,
        "transactions": transactions
    })


    return redirect("auction_detail", auction_id=auction.id)

def send_activation_email(request, user):
    current_site = get_current_site(request)

    language = request.GET.get(
        "lang",
        getattr(request, "LANGUAGE_CODE", "en"),
    )

    language = str(language).lower().split("-")[0]

    if language not in ("en", "es", "pt"):
        language = "en"

    with override(language):
        subject = _(
            "🎉 Welcome to FANZ — Claim Your 50 FREE Credits"
        )

        html_content = render_to_string(
            "auctions/account_activation_email.html",
            {
                "user": user,
                "domain": current_site.domain,
                "uid": urlsafe_base64_encode(
                    force_bytes(user.pk)
                ),
                "token": default_token_generator.make_token(user),
                "protocol": (
                    "https"
                    if request.is_secure()
                    else "http"
                ),
                "language": language,
            },
        )

    text_content = strip_tags(html_content)

    email = EmailMultiAlternatives(
        subject,
        text_content,
        to=[user.email],
    )

    email.attach_alternative(
        html_content,
        "text/html",
    )

    email.send()

def signup_view(request):
    ref_code = request.GET.get("ref")
    referral_business_slug = request.GET.get("business")

    if ref_code:
        request.session["referral_code"] = ref_code

    if referral_business_slug:
        request.session[
            "referral_business_slug"
        ] = referral_business_slug

    if request.method == "POST":
        form = SignUpForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(
                form.cleaned_data["password"]
            )
            user.is_active = False
            user.save()

            NodeProfile.objects.get_or_create(
                user=user
            )

            wallet, _ = BidWallet.objects.get_or_create(
                user=user
            )

            ref_code = (
                request.session.pop(
                    "referral_code",
                    None,
                )
                or request.GET.get("ref")
            )

            referral_business_slug = (
                request.session.pop(
                    "referral_business_slug",
                    None,
                )
                or request.GET.get("business")
            )

            if ref_code:
                referrer_wallet = (
                    BidWallet.objects
                    .select_related("user")
                    .filter(
                        referral_code=ref_code
                    )
                    .first()
                )

                if (
                    referrer_wallet
                    and referrer_wallet.user != user
                    and wallet.referred_by is None
                ):
                    wallet.referred_by = (
                        referrer_wallet.user
                    )

                    referrer_node = (
                        NodeProfile.objects.filter(
                            user=referrer_wallet.user
                        ).first()
                    )

                    if referrer_node:
                        wallet.source_node = (
                            referrer_node
                        )

                    update_fields = [
                        "referred_by",
                        "source_node",
                    ]

                    if referral_business_slug:
                        referral_business = (
                            BusinessListing.objects.filter(
                                slug=referral_business_slug,
                                owner=referrer_wallet.user,
                                is_active=True,
                            ).first()
                        )

                        if referral_business:
                            wallet.pending_referral_business = (
                                referral_business
                            )
                            update_fields.append(
                                "pending_referral_business"
                            )

                    wallet.save(
                        update_fields=update_fields
                    )

            send_activation_email(
                request,
                user
            )

            return render(
                request,
                "signup_check_email.html",
                {
                    "email": user.email,
                },
            )

    else:
        form = SignUpForm()

    return render(
        request,
        "account/signup.html",
        {
            "form": form,
        },
    )

def activate_view(request, uidb64, token):
    try:
        uid = force_str(
            urlsafe_base64_decode(uidb64)
        )
        user = User.objects.get(pk=uid)
    except Exception:
        user = None

    if user is not None and user.is_active:
        login(
            request,
            user,
            backend=(
                "django.contrib.auth.backends."
                "ModelBackend"
            ),
        )

        messages.success(
            request,
            "✅ Your FANZ account is already active.",
        )

        return redirect("auction_list")

    if (
        user is not None
        and default_token_generator.check_token(
            user,
            token,
        )
    ):
        # ---------------------------------------------------
        # ACTIVATE ACCOUNT
        # ---------------------------------------------------
        user.is_active = True
        user.save(update_fields=["is_active"])

        # ---------------------------------------------------
        # WALLET
        # ---------------------------------------------------
        wallet, _ = BidWallet.objects.get_or_create(
            user=user
        )

        # ---------------------------------------------------
        # SIGNUP BONUS
        # ---------------------------------------------------
        if not wallet.signup_bonus_given:
            wallet.credits += 50
            wallet.signup_bonus_given = True

            wallet.save(
                update_fields=[
                    "credits",
                    "signup_bonus_given",
                ]
            )

            WalletTransaction.objects.create(
                sender=None,
                receiver=wallet,
                amount=50,
                transaction_type="bonus",
                reference="Signup activation bonus",
            )

        # ---------------------------------------------------
        # REFERRAL BONUS
        # ---------------------------------------------------
        if (
            wallet.referred_by
            and not wallet.referral_bonus_given
        ):
            referrer_wallet, _ = (
                BidWallet.objects.get_or_create(
                    user=wallet.referred_by
                )
            )

            referrer_wallet.credits += 50
            referrer_wallet.save(
                update_fields=["credits"]
            )

            WalletTransaction.objects.create(
                sender=None,
                receiver=referrer_wallet,
                amount=50,
                transaction_type="commission",
                reference=(
                    f"Referral bonus for {user.username}"
                ),
            )

            wallet.referral_bonus_given = True
            wallet.save(
                update_fields=[
                    "referral_bonus_given",
                ]
            )

        # ---------------------------------------------------
        # AUTO-FOLLOW REFERRAL BUSINESS
        # ---------------------------------------------------
        process_business_referral_activation(
            user=user,
            wallet=wallet,
        )

        # ---------------------------------------------------
        # PAY CODE
        # ---------------------------------------------------
        if not wallet.pay_code:
            wallet.pay_code = generate_referral_code()
            wallet.save(
                update_fields=["pay_code"]
            )

        # ---------------------------------------------------
        # REFERRAL CODE
        # ---------------------------------------------------
        if not wallet.referral_code:
            wallet.referral_code = (
                generate_referral_code()
            )
            wallet.save(
                update_fields=["referral_code"]
            )

        # ---------------------------------------------------
        # WALLET QR
        # ---------------------------------------------------
        qr_path = (
            f"media/qr_codes/"
            f"{wallet.wallet_code}.png"
        )

        if not os.path.exists(qr_path):
            payment_url = (
                "https://fanz.to/auctions/pay/"
                f"{wallet.pay_code}/"
            )

            img = qrcode.make(payment_url)

            os.makedirs(
                os.path.dirname(qr_path),
                exist_ok=True,
            )

            img.save(qr_path)

        # ---------------------------------------------------
        # REFERRAL QR
        # ---------------------------------------------------
        ref_qr_path = (
            "media/qr_codes/"
            f"ref_{wallet.referral_code}.png"
        )

        if not os.path.exists(ref_qr_path):
            referral_url = (
                "https://fanz.to/auctions/signup/"
                f"?ref={wallet.referral_code}"
            )

            img = make_branded_referral_qr(
                referral_url
            )

            os.makedirs(
                os.path.dirname(ref_qr_path),
                exist_ok=True,
            )

            img.save(ref_qr_path)

        # ---------------------------------------------------
        # SESSION CLEANUP
        # ---------------------------------------------------
        request.session.pop(
            "referral_code",
            None,
        )

        request.session.pop(
            "referral_business_slug",
            None,
        )

        # ---------------------------------------------------
        # LOGIN AND REDIRECT
        # ---------------------------------------------------
        login(
            request,
            user,
            backend=(
                "django.contrib.auth.backends."
                "ModelBackend"
            ),
        )

        messages.success(
            request,
            "🎉 Account activated successfully!",
        )

        return redirect("auction_list")

    return render(
        request,
        "activation_invalid.html",
    )

@login_required
def pay_user(request, wallet_code):
    target_wallet = get_object_or_404(BidWallet, wallet_code=wallet_code)
    sender_wallet = get_object_or_404(BidWallet, user=request.user)

    target_user = target_wallet.user
    target_profile = getattr(target_user, "profile", None)

    if request.method == "POST":
        amount = int(request.POST.get("amount", 0))

        # ❌ VALIDATION
        if target_wallet.user == request.user:
            messages.error(request, "❌ You cannot send credits to yourself.")
            return redirect(request.path)

        if amount <= 0:
            messages.error(request, "❌ Invalid amount.")
            return redirect(request.path)

        if sender_wallet.credits < amount:
            messages.error(request, "❌ Not enough credits.")
            return redirect(request.path)

        # ✅ CONFIRM STEP
        if request.POST.get("confirm") != "yes":
            return render(request, "wallet/confirm_transfer.html", {
                "target_wallet": target_wallet,
                "amount": amount
            })

        # ✅ EXECUTE TRANSFER
        sender_wallet.credits -= amount
        target_wallet.credits += amount

        sender_wallet.save(update_fields=["credits"])
        target_wallet.save(update_fields=["credits"])

        WalletTransaction.objects.create(
            sender=sender_wallet,
            receiver=target_wallet,
            amount=amount,
            transaction_type="tip",
            reference=None,
        )
        
        
        Notification.objects.create(
            user=target_wallet.user,
            actor=request.user,
            notification_type=Notification.TIP,
            message=f"💰 {request.user.username} sent you {amount} credits.",
            metadata={
                "action": "sent",
                "amount": amount,
            },
        )
        
        messages.success(request, "✅ Transfer successful!")

        return redirect("public_profile", username=target_user.username)
        
        recent_notifications = []

        if request.user.is_authenticated:
            recent_notifications = Notification.objects.filter(
                user=request.user,
                is_read=False
            )[:5]

    return render(request, "wallet/pay.html", {
        "target_wallet": target_wallet,
        "target_user": target_user,
        "target_profile": target_profile,
        
    })

@login_required
def confirm_founder_tienda_purchase(request, listing_id):
    listing = get_object_or_404(
        FounderListing.objects.select_related(
            "founder_account",
            "seller_root",
        ),
        pk=listing_id,
        listing_source=FounderListing.SOURCE_TIENDA,
        status=FounderListing.STATUS_ACTIVE,
        sale_type=FounderListing.SALE_FIXED,
    )

    wallet, _ = BidWallet.objects.get_or_create(
        user=request.user
    )

    price = int(listing.fixed_price_credits or 0)

    balance_after = wallet.credits - price
    can_afford = wallet.credits >= price

    return render(
        request,
        "auctions/founder_purchase_confirm.html",
        {
            "listing": listing,
            "wallet": wallet,
            "price": price,
            "balance_after": balance_after,
            "can_afford": can_afford,
        },
    )

@login_required
def founder_knowledge(request, handle):
    founder_account = get_object_or_404(
        FounderAccount.objects.select_related(
            "current_account",
            "owner_root",
        ),
        handle__iexact=handle,
    )

    language = request.GET.get(
        "lang",
        getattr(request, "LANGUAGE_CODE", "en"),
    )

    valuation = get_founder_valuation(
        founder_account
    )

    valuation_presentation = (
        get_localized_valuation_presentation(
            valuation,
            language,
        )
    )
    active_listing = valuation[
        "market"
    ]["active_listing"]
    viewer_is_seller = False
    active_listing_has_bids = False

    if active_listing:
        if request.user.is_authenticated:
            viewer_root = get_authoritative_root(
                request.user
            )

            seller_root = get_authoritative_root(
                active_listing.seller_root
            )

            viewer_is_seller = (
                viewer_root.pk == seller_root.pk
            )

        if (
            active_listing.sale_type
            == FounderListing.SALE_BLIND
        ):
            active_listing_has_bids = (
                FounderBid.objects
                .filter(
                    listing=active_listing,
                    status=FounderBid.STATUS_ACTIVE,
                )
                .exists()
            )

    market_url = None
    market_action = None

    
    if active_listing:
        if (
            active_listing.listing_source
            == FounderListing.SOURCE_TIENDA
        ):
            if (
                active_listing.sale_type
                == FounderListing.SALE_FIXED
            ):
                market_url = reverse(
                    "confirm_founder_tienda_purchase",
                    kwargs={
                        "listing_id": active_listing.pk,
                    },
                )
                market_action = "buy"

            elif (
                active_listing.sale_type
                == FounderListing.SALE_BLIND
            ):
                market_url = reverse(
                    "founder_tienda",
                )
                market_action = "offer"

        elif (
            active_listing.listing_source
            == FounderListing.SOURCE_P2P
        ):
            # P2P listing data is canonical already, but there
            # is not yet a public P2P marketplace route.
            market_action = "p2p"

    ownership_history = (
        FounderOwnershipLedger.objects
        .filter(
            founder_account=founder_account,
        )
        .select_related(
            "seller_root",
            "buyer_root",
        )
        .order_by("-sequence")
    )

    return render(
        request,
        "auctions/founder_knowledge.html",
        {
            "founder_account": founder_account,
            "valuation": valuation,
            "valuation_presentation": (
                valuation_presentation
            ),
            "ownership_history": ownership_history,
            "active_listing": active_listing,
            "market_url": market_url,
            "market_action": market_action,
            "viewer_is_seller": viewer_is_seller,
            "active_listing_has_bids": active_listing_has_bids,
        },
    )



@login_required
def founder_tienda(request):
    fixed_listings = (
        FounderListing.objects
        .filter(
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_FIXED,
            status=FounderListing.STATUS_ACTIVE,
        )
        .select_related(
            "founder_account",
            "seller_root",
        )
        .order_by(
            "founder_account__handle_length",
            "founder_account__handle",
        )
    )

    blind_listings = (
        FounderListing.objects
        .filter(
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_BLIND,
            status=FounderListing.STATUS_ACTIVE,
        )
        .select_related(
            "founder_account",
            "seller_root",
        )
        .annotate(
            bidder_count=Count(
                "bids__bidder_root",
                distinct=True,
            ),
            viewer_is_high_bidder=Exists(
                FounderBid.objects.filter(
                    listing=OuterRef("pk"),
                    bidder_root=request.user,
                    status=FounderBid.STATUS_ACTIVE,
                )
            ),
        )
        .order_by(
            "ends_at",
            "founder_account__handle",
        )
    )

    wasteland_listings = (
        FounderListing.objects
        .filter(
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_SWAMP,
            status=FounderListing.STATUS_ACTIVE,
        )
        .select_related(
            "founder_account",
            "seller_root",
        )
        .order_by(
            "founder_account__handle",
        )
    )
    p2p_queryset = (
        FounderListing.objects
        .filter(
            listing_source=FounderListing.SOURCE_P2P,
            status=FounderListing.STATUS_ACTIVE,
        )
        .select_related(
            "founder_account",
            "founder_account__current_account",
            "seller_root",
        )
        .order_by(
            "-created_at",
            "founder_account__handle",
        )
    )

    p2p_paginator = Paginator(
        p2p_queryset,
        10,
    )

    p2p_page = p2p_paginator.get_page(
        request.GET.get("p2p_page")
    )


    wallet = BidWallet.objects.filter(
        user=request.user
    ).first()

    return render(
        request,
        "auctions/founder_tienda.html",
        {
            "fixed_listings": fixed_listings,
            "blind_listings": blind_listings,
            "wasteland_listings": wasteland_listings,
            "p2p_page": p2p_page,
            "wallet": wallet,
        },
    )

@login_required
def buy_founder_tienda_listing(request, listing_id):
    if request.method != "POST":
        return redirect(
            "confirm_founder_tienda_purchase",
            listing_id=listing_id,
        )

    if request.POST.get("confirm") != "yes":
        messages.error(
            request,
            _("Founder purchase confirmation is required."),
        )
        return redirect(
            "confirm_founder_tienda_purchase",
            listing_id=listing_id,
        )

    listing = get_object_or_404(
        FounderListing,
        pk=listing_id,
    )

    try:
        result = purchase_tienda_fixed_listing(
            listing=listing,
            buyer=request.user,
        )

        messages.success(
            request,
            _(
                "🏡 You now own @%(handle)s for %(credits)s credits."
            ) % {
                "handle": result["founder_account"].handle,
                "credits": result["sale_price_credits"],
            },
)

    except Exception as exc:
        messages.error(
            request,
            str(exc),
        )

    return redirect("founder_tienda")

@login_required
def bid_founder_tienda_listing(request, listing_id):
    if request.method != "POST":
        return redirect("founder_tienda")

    listing = get_object_or_404(
        FounderListing,
        pk=listing_id,
    )

    try:
        amount = int(
            request.POST.get("amount_credits", 0)
        )
    except (TypeError, ValueError):
        messages.error(
            request,
            _("Invalid Founder bid amount."),
        )
        return redirect("founder_tienda")

    try:
        result = place_founder_blind_bid(
            listing=listing,
            bidder=request.user,
            amount_credits=amount,
        )

        messages.success(
            request,
            _(
                "💰 Funded offer of %(credits)s credits placed on @%(handle)s."
            ) % {
                "credits": result["bid"].amount_credits,
                "handle": listing.founder_account.handle,
            },
        )

    except Exception as exc:
        messages.error(
            request,
            str(exc),
        )

    return redirect("founder_tienda")


@login_required
def pay_user_short(request, pay_code):
    target_wallet = get_object_or_404(BidWallet, pay_code=pay_code)
    return pay_user(request, target_wallet.wallet_code)


@login_required
def node_dashboard(request):
    try:
        node = NodeProfile.objects.get(user=request.user)
    except NodeProfile.DoesNotExist:
        return render(request, "auctions/node_dashboard.html", {"error": "You are not a node."})


    node_wallet, _ = BidWallet.objects.get_or_create(user=request.user)

    # Commission transactions only
    commissions = WalletTransaction.objects.filter(
        receiver=node_wallet,
        transaction_type="commission"
    ).order_by("-created_at")

    total_earned = commissions.aggregate(
        total=Sum("amount")
    )["total"] or 0

    return render(request, "auctions/node_dashboard.html", {
        "node": node,
        "wallet": node_wallet,
        "commissions": commissions[:20],
        "total_earned": total_earned
    })

@login_required
def ai_home(request):
    conversations = (
        AIConversation.objects
        .filter(user=request.user)
        .order_by("-is_pinned", "-updated_at")
    )

    return render(request, "auctions/ai_home.html", {
        "conversations": conversations,
    })


@login_required
def toggle_favorite_auction(request, auction_id):
    auction = get_object_or_404(Auction, id=auction_id)

    favorite, created = FavoriteAuction.objects.get_or_create(
        user=request.user,
        auction=auction,
    )

    if not created:
        favorite.delete()

    return redirect(request.META.get("HTTP_REFERER", "auction_list"))


@login_required
def buy_now_auction(request, auction_id):
    auction = get_object_or_404(Auction, id=auction_id)

    if request.method != "POST":
        return redirect("auction_detail", auction_id=auction.id)

    wallet, created = BidWallet.objects.get_or_create(user=request.user)

    current_price = auction.current_price
    buy_now_price = current_price + Decimal("25.00")

    if wallet.credits < buy_now_price:
        messages.error(request, "Not enough credits to buy this item now.")
        return redirect("auction_detail", auction_id=auction.id)

    wallet.credits -= buy_now_price
    wallet.save(update_fields=["credits"])

    WalletTransaction.objects.create(
        sender=wallet,
        receiver=None,
        amount=buy_now_price,
        transaction_type="purchase",
        reference=f"Buy Now purchase: {auction.title}"
)

    messages.success(
        request,
        f"You bought {auction.title} now for {buy_now_price} credits."
    )
    
    try:
        send_buy_now_email(auction, request.user, buy_now_price)
        send_digital_delivery_message(
            user=request.user,
            auction=auction,
            event_type="buy_now",
        )
        ai_log("BUY_NOW_DELIVERY_SENT", auction_id=auction.id, title=auction.title, user_email=request.user.email)

    
    except Exception as e:
        ai_log("BUY_NOW_DELIVERY_FAILED", auction_id=auction.id, title=auction.title, error=str(e))


    return redirect("auction_detail", auction_id=auction.id)

def send_buy_now_email(auction, user, buy_now_price):
    subject = f"Download for: {auction.title}"

    context = {
        "auction": auction,
        "user": user,
        "buy_now_price": buy_now_price,
        "digital_item": auction.digital_item,
        "delivery_url": auction.digital_item.delivery_url,
    }

    text_body = render_to_string("emails/buy_now_purchase.txt", context)
    html_body = render_to_string("emails/buy_now_purchase.html", context)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=None,
        to=[user.email],
    )

    email.attach_alternative(html_body, "text/html")
    email.send()


@login_required
def platform_accounts_dashboard(request):
    if request.user.username.lower() != "dj":
        raise Http404("Not found")

    platform_accounts = (
        UserProfile.objects
        .select_related("user")
        .filter(is_platform_account=True)
        .order_by("user__username")
    )

    return render(
        request,
        "auctions/platform_accounts.html",
        {
            "platform_accounts": platform_accounts,
        },
    )


@login_required
def create_platform_account(request):
    if request.user.username.lower() != "dj":
        raise Http404("Not found")

    if request.method == "POST":
        form = PlatformAccountForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data["username"]
            display_name = form.cleaned_data["display_name"]

            user = User(
                username=username,
                email=f"{username.lower()}@platform.invalid",
                is_active=True,
                is_staff=False,
                is_superuser=False,
            )

            user.set_unusable_password()
            user.save()

            profile, _ = UserProfile.objects.get_or_create(
                user=user
            )

            profile.display_name = display_name
            profile.is_platform_account = True
            profile.is_official = True

            profile.save(
                update_fields=[
                    "display_name",
                    "is_platform_account",
                    "is_official",
                ]
            )

            messages.success(
                request,
                f"Platform account @{username} created."
            )

            return redirect(
                "platform_accounts_dashboard"
            )

    else:
        form = PlatformAccountForm()

    return render(
        request,
        "auctions/create_platform_account.html",
        {
            "form": form,
        },
    )

@login_required
@require_POST
def login_as_platform_account(request, user_id):
    if request.user.username.lower() != "dj":
        raise Http404("Not found")

    target_user = get_object_or_404(
        User.objects.select_related("profile"),
        id=user_id,
        is_active=True,
        profile__is_platform_account=True,
    )

    if target_user == request.user:
        return redirect("platform_accounts_dashboard")

    original_user_id = request.user.id

    backend = settings.AUTHENTICATION_BACKENDS[0]

    login(
        request,
        target_user,
        backend=backend,
    )

    request.session["platform_original_user_id"] = original_user_id

    messages.success(
        request,
        f"You are now using @{target_user.username}."
    )

    next_url = request.POST.get("next")

    if next_url == "edit_profile":
        return redirect("edit_profile")

    if next_url == "create_post":
        return redirect("feed_home")

    return redirect(
        "public_profile_root",
        username=target_user.username,
    )

@login_required
@require_POST
def return_from_platform_account(request):
    original_user_id = request.session.get(
        "platform_original_user_id"
    )

    if not original_user_id:
        raise Http404("Not found")

    original_user = get_object_or_404(
        User,
        id=original_user_id,
        username__iexact="DJ",
        is_active=True,
    )

    backend = settings.AUTHENTICATION_BACKENDS[0]

    login(
        request,
        original_user,
        backend=backend,
    )

    request.session.pop(
        "platform_original_user_id",
        None,
    )

    messages.success(
        request,
        "Returned to DJ."
    )

    return redirect("platform_accounts_dashboard")

@login_required
def edit_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = UserProfileForm(
            request.POST,
            request.FILES,
            instance=profile
        )

        if not request.POST.get("tos_accepted"):
            messages.error(
                request,
                "You must accept TOS to update profile."
            )
            return redirect("edit_profile")

        if form.is_valid():
            form.save()
            return redirect(
                "public_profile",
                username=request.user.username
            )

    else:
        form = UserProfileForm(instance=profile)

    return render(
        request,
        "auctions/edit_profile.html",
        {
            "form": form,
            "profile": profile,
        }
    )


@login_required
def translate_profile(request):
    profile, _ = UserProfile.objects.get_or_create(
        user=request.user
    )

    language = request.GET.get("lang", "en").lower()

    if language not in ("en", "es", "pt"):
        language = "en"

    translation, created = UserProfileTranslation.objects.get_or_create(
        profile=profile,
        language=language,
    )

    if created and language == "en":
        translation.bio = profile.bio
        translation.bank_payment_notes = profile.bank_payment_notes
        translation.save(
            update_fields=[
                "bio",
                "bank_payment_notes",
            ]
        )

    if request.method == "POST":
        form = UserProfileTranslationForm(
            request.POST,
            instance=translation,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Profile translation saved."
            )

            return redirect(
                f"{reverse('translate_profile')}?lang={language}"
            )

    else:
        form = UserProfileTranslationForm(
            instance=translation
        )

    return render(
        request,
        "auctions/translate_profile.html",
        {
            "profile": profile,
            "translation": translation,
            "form": form,
            "language": language,
        },
    )

def public_profile(request, username):
    profile_user = get_object_or_404(
        User,
        username__iexact=username
    )

    if request.resolver_match and request.resolver_match.url_name == "public_profile":
        return redirect(
            "public_profile_root",
            username=profile_user.username,
            permanent=True,
    )

    if username != profile_user.username:
        return redirect(
            "public_profile_root",
            username=profile_user.username,
            permanent=True,
    )

    profile, _ = UserProfile.objects.get_or_create(user=profile_user)

    language = request.GET.get(
        "lang",
        getattr(request, "LANGUAGE_CODE", "en"),
    )

    language = str(language).lower().split("-")[0]

    if language not in ("en", "es", "pt"):
        language = "en"

    profile_translation = (
        UserProfileTranslation.objects
        .filter(
            profile=profile,
            language=language,
        )
        .first()
    )

    display_bio = profile.bio
    display_payment_notes = profile.bank_payment_notes

    if profile_translation:
        if profile_translation.bio:
            display_bio = profile_translation.bio

        if profile_translation.bank_payment_notes:
            display_payment_notes = profile_translation.bank_payment_notes

    profile_posts_qs = FeedPost.objects.select_related(
        "user",
        "user__profile"
    ).filter(
        user=profile_user,
    ).order_by("-is_pinned", "-created_at")

    premium_post_count = profile_posts_qs.filter(
        is_paid=True
    ).count()

    profile_posts = prepare_feed_posts(
        profile_posts_qs,
        language=language,
    )

    total_likes = sum(post.likes.count() for post in profile_posts)

    real_fan_count = Fan.objects.filter(
        creator=profile_user
    ).count()

    fan_count = profile.fan_count + real_fan_count

    if fan_count >= 1_000_000_000:
        fan_count_display = f"{fan_count / 1_000_000_000:.1f}B".rstrip("0").rstrip(".")
    elif fan_count >= 1_000_000:
        fan_count_display = f"{fan_count / 1_000_000:.1f}M".rstrip("0").rstrip(".")
    elif fan_count >= 1_000:
        fan_count_display = f"{fan_count / 1_000:.1f}K".rstrip("0").rstrip(".")
    else:
        fan_count_display = str(fan_count)

    creator_wallet = getattr(profile_user, "bidwallet", None)

    tip_earnings = 0
    unlock_earnings = 0
    total_creator_earnings = 0

    if creator_wallet:
        tip_earnings = WalletTransaction.objects.filter(
            receiver=creator_wallet,
            transaction_type="tip"
        ).aggregate(total=Sum("amount"))["total"] or 0

        unlock_earnings = WalletTransaction.objects.filter(
            receiver=creator_wallet,
            transaction_type="unlock"
        ).aggregate(total=Sum("amount"))["total"] or 0

        total_creator_earnings = tip_earnings + unlock_earnings

    is_fan = False

    recent_notifications = []

    if request.user.is_authenticated:
        recent_notifications = Notification.objects.filter(
            user=request.user,
            is_read=False
        )[:5]

    if request.user.is_authenticated:
        is_fan = Fan.objects.filter(
            creator=profile_user,
            fan=request.user
        ).exists()

    if request.user.is_authenticated:
        unlocked_post_ids = set(
            PostUnlock.objects.filter(user=request.user)
            .values_list("post_id", flat=True)
        )
    else:
        unlocked_post_ids = set()

    show_creator_earnings = (
        request.user.is_authenticated
        and request.user == profile_user
        )

    return render(
        request,
        "auctions/public_profile.html",
        {
            "profile_user": profile_user,
            "profile": profile,
            "creator_wallet": creator_wallet,
            "profile_posts": profile_posts,
            "unlocked_post_ids": unlocked_post_ids,
            "premium_post_count": premium_post_count,
            "total_likes": total_likes,
            "fan_count": fan_count,
            "fan_count_display": fan_count_display,
            "tip_earnings": tip_earnings,
            "unlock_earnings": unlock_earnings,
            "total_creator_earnings": total_creator_earnings,
            "show_creator_earnings": show_creator_earnings,
            "is_fan": is_fan,
            "recent_notifications": recent_notifications,
            "language": language,
            "display_bio": display_bio,
            "display_payment_notes": display_payment_notes,
        }
    )

def post_detail(request, post_id):
    language = request.GET.get(
        "lang",
        getattr(request, "LANGUAGE_CODE", "en"),
    ).lower().split("-")[0]

    if language not in ("en", "es", "pt"):
        language = "en"

    post_queryset = (
        FeedPost.objects
        .select_related("user")
        .prefetch_related(
            "hashtags",
            "likes",
            "comments",
            "translations",
        )
        .filter(id=post_id)
    )

    prepared_posts = prepare_feed_posts(
        post_queryset,
        language=language,
    )

    if not prepared_posts:
        raise Http404

    post = prepared_posts[0]

    profile, _ = UserProfile.objects.get_or_create(
        user=post.user
    )

    profile_translation = (
        UserProfileTranslation.objects
        .filter(
            profile=profile,
            language=language,
        )
        .first()
    )

    display_bio = profile.bio

    if profile_translation and profile_translation.bio:
        display_bio = profile_translation.bio

    unlocked_post_ids = set()

    if request.user.is_authenticated:
        unlocked_post_ids = set(
            PostUnlock.objects.filter(user=request.user)
            .values_list("post_id", flat=True)
        )

    return render(
        request,
        "auctions/post_detail.html",
        {
            "post": post,
            "unlocked_post_ids": unlocked_post_ids,
            "language": language,
            "display_bio": display_bio,
        }
    )

@login_required
def translate_post(request, post_id):
    post = get_object_or_404(
        FeedPost,
        id=post_id,
        user=request.user,
    )

    language = request.GET.get("lang", "en").lower()

    if language not in ("en", "es", "pt"):
        language = "en"

    translation, created = FeedPostTranslation.objects.get_or_create(
        post=post,
        language=language,
    )

    if created and language == "en":
        translation.title = post.title
        translation.content = post.content
        translation.save(
            update_fields=[
                "title",
                "content",
            ]
        )

    if request.method == "POST":
        form = FeedPostTranslationForm(
            request.POST,
            instance=translation,
        )

        if form.is_valid():
            form.save()

            sync_post_hashtags(post)

            messages.success(
                request,
                "Post translation saved."
            )

            return redirect(
                f"{reverse('translate_post', args=[post.id])}?lang={language}"
            )

    else:
        form = FeedPostTranslationForm(
            instance=translation,
        )

    return render(
        request,
        "auctions/translate_post.html",
        {
            "post": post,
            "translation": translation,
            "form": form,
            "language": language,
        },
    )

@login_required
def toggle_post_like(request, post_id):
    post = get_object_or_404(FeedPost, id=post_id)

    like, created = PostLike.objects.get_or_create(
        post=post,
        user=request.user
    )

    if not created:
        like.delete()
        liked = False
    else:
        liked = True

        if post.user != request.user:
            Notification.objects.create(
                user=post.user,
                actor=request.user,
                notification_type=Notification.LIKE,
                message=f"❤️ {request.user.username} liked your post."
            )

            send_auto_thank_you_dm(
                sender=post.user,
                recipient=request.user,
                event_type="like"
            )

    like_count = post.likes.count()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "liked": liked,
            "like_count": like_count,
        })

    return redirect(request.META.get("HTTP_REFERER", "feed_home"))

@login_required
@transaction.atomic
def unlock_feed_post(request, post_id):
    post = get_object_or_404(FeedPost, id=post_id)

    if post.user == request.user:
        messages.info(request, "You already own this post.")
        return redirect("public_profile", username=post.user.username)

    if not post.is_paid or post.unlock_price <= 0:
        messages.info(request, "This post does not require unlocking.")
        return redirect("public_profile", username=post.user.username)

    buyer_wallet = BidWallet.objects.select_for_update().get(user=request.user)
    creator_wallet = BidWallet.objects.select_for_update().get(user=post.user)

    price = post.unlock_price

    unlock, unlock_created = PostUnlock.objects.get_or_create(
        post=post,
        user=request.user,
        defaults={
            "price_paid": price
        }
    )

    if not unlock_created:
        messages.info(request, "You already unlocked this post.")
        return redirect("public_profile", username=post.user.username)

    if buyer_wallet.credits < price:
        unlock.delete()
        messages.error(request, "You do not have enough credits to unlock this post.")
        return redirect("public_profile", username=post.user.username)

    platform_fee = 0

    if price > 5:
        platform_fee = price // 5

    creator_amount = price - platform_fee

    buyer_wallet.credits -= price
    creator_wallet.credits += creator_amount

    buyer_wallet.save(update_fields=["credits"])
    creator_wallet.save(update_fields=["credits"])

    if platform_fee > 0:
        platform_wallet = get_system_wallet()

        platform_wallet.credits += platform_fee
        platform_wallet.save(update_fields=["credits"])

    WalletTransaction.objects.create(
        sender=buyer_wallet,
        receiver=creator_wallet,
        amount=creator_amount,
        transaction_type="unlock",
        reference=f"Unlocked post #{post.id}"
    )

    if platform_fee > 0:
        WalletTransaction.objects.create(
            sender=buyer_wallet,
            receiver=platform_wallet,
            amount=platform_fee,
            transaction_type="unlock_fee",
            reference=f"Platform fee for unlock #{post.id}"
    )

    touch_ai_creator_memory(
        creator=post.user,
        fan=request.user,
        event_type="unlock",
        credits=price,
    )


    Notification.objects.create(
        user=post.user,
        actor=request.user,
        notification_type=Notification.UNLOCK,
        message=f"🔓 {request.user.username} unlocked your premium post for {price} credits. You earned {creator_amount} credits.",
        metadata={
            "price": price,
            "creator_amount": creator_amount,
        },
    )

    send_auto_thank_you_dm(
        sender=post.user,
        recipient=request.user,
        event_type="unlock"
    )

    messages.success(request, f"Post unlocked for {price} credits.")

    profile_url = reverse(
        "public_profile",
        kwargs={"username": post.user.username}
    )

    return redirect(f"{profile_url}#post-{post.id}")


@login_required
@transaction.atomic
def quick_tip_user(request, wallet_code):
    if request.method != "POST":
        return JsonResponse({"success": False}, status=400)

    target_wallet = get_object_or_404(
        BidWallet,
        wallet_code=wallet_code
    )

    sender_wallet = BidWallet.objects.select_for_update().get(
        user=request.user
    )

    data = json.loads(request.body)

    amount = int(data.get("amount", 1))
    if amount < 1:
        amount = 1

    if amount > 1000:
        amount = 1000

    if sender_wallet == target_wallet:
        return JsonResponse({
            "success": False,
            "error": "Cannot tip yourself."
        })

    if sender_wallet.credits < amount:
        return JsonResponse({
            "success": False,
            "error": "Not enough credits."
        })

    platform_fee = 0

    if amount == 5:
        platform_fee = 1
    elif amount == 10:
        platform_fee = 2

    creator_amount = amount - platform_fee

    if creator_amount < 1:
        return JsonResponse({
            "success": False,
            "error": "Invalid tip amount."
        }, status=400)

    sender_wallet.credits -= amount
    target_wallet.credits += creator_amount

    sender_wallet.save(update_fields=["credits"])
    target_wallet.save(update_fields=["credits"])

    WalletTransaction.objects.create(
        sender=sender_wallet,
        receiver=target_wallet,
        amount=creator_amount,
        transaction_type="tip",
        reference=f"Quick tip to @{target_wallet.user.username}"
    )

    if platform_fee > 0:
        platform_wallet = get_system_wallet()
        platform_wallet.credits += platform_fee
        platform_wallet.save(update_fields=["credits"])

        WalletTransaction.objects.create(
            sender=sender_wallet,
            receiver=platform_wallet,
            amount=platform_fee,
            transaction_type="tip_fee",
            reference=f"Platform fee from tip to @{target_wallet.user.username}"
    )

    touch_ai_creator_memory(
        creator=target_wallet.user,
        fan=request.user,
        event_type="tip",
        credits=amount,
    )
    
    Notification.objects.create(
        user=target_wallet.user,
        actor=request.user,
        notification_type=Notification.TIP,
        message=f"💰 {request.user.username} tipped you {creator_amount} credits.",
        metadata={
            "action": "tipped",
            "amount": creator_amount,
        },
    )
    
    send_auto_thank_you_dm(
        sender=target_wallet.user,
        recipient=request.user,
        event_type="tip"
    )
    
    return JsonResponse({
        "success": True,
        "new_balance": sender_wallet.credits,
    })

@login_required
def toggle_pin_post(request, post_id):
    post = get_object_or_404(FeedPost, id=post_id, user=request.user)

    if request.method == "POST":
        if post.is_pinned:
            post.is_pinned = False
            post.save()
        else:
            FeedPost.objects.filter(
                user=request.user,
                is_pinned=True
            ).update(is_pinned=False)

            post.is_pinned = True
            post.save()

    return redirect(request.META.get("HTTP_REFERER", "feed_home"))


@login_required
@require_POST
def delete_feed_post(request, post_id):
    post = get_object_or_404(FeedPost, id=post_id, user=request.user)
    post.delete()

    return redirect(request.META.get("HTTP_REFERER", "feed_home"))


@login_required
def add_post_comment(request, post_id):

    post = get_object_or_404(FeedPost, id=post_id)

    if request.method == "POST":

        content = request.POST.get("content", "").strip()
        parent_id = request.POST.get("parent_id")

        parent = None

        if parent_id:
            parent = PostComment.objects.filter(
                id=parent_id,
                post=post
            ).first()

        if content:

            comment = PostComment.objects.create(
                post=post,
                user=request.user,
                parent=parent,
                content=content,
            )

            Notification.objects.create(
                user=post.user,
                actor=request.user,
                notification_type="comment",
                message=f"💬 {request.user.username} commented on your post."
            )

            # AJAX RESPONSE
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":

               return JsonResponse({
                    "success": True,
                    "comment_id": comment.id,
                    "parent_id": parent.id if parent else None,
                    "username": request.user.username,
                    "content": comment.content,
                })

    # AJAX FAIL RESPONSE
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":

        return JsonResponse({
            "success": False,
            "error": "Comment failed."
        }, status=400)

    # NORMAL FALLBACK
    return redirect(
        request.META.get("HTTP_REFERER", "feed_home")
    )



@login_required
def toggle_fan(request, username):
    creator = get_object_or_404(User, username=username)

    if creator == request.user:
        messages.warning(request, "You cannot become a Fan of yourself.")
        return redirect("public_profile", username=username)

    fan_obj, created = Fan.objects.get_or_create(
        creator=creator,
        fan=request.user
    )

    if created:
        messages.success(request, f"⭐ You are in {creator.username}'s Circle of Fanz!")
    
        touch_ai_creator_memory(
            creator=creator,
            fan=request.user,
            event_type="fan",
            
        )    

        Notification.objects.create(
            user=creator,
            actor=request.user,
            notification_type=Notification.FAN,
            message=f"⭐ {request.user.username} has become one of your Fanz!"
        )

        send_auto_thank_you_dm(
            sender=creator,
            recipient=request.user,
            event_type="fan"
        )

    else:
        fan_obj.delete()
        messages.success(request, f"You are no longer one of {creator.username}'s Fanz.")

    return redirect("public_profile", username=username)


@login_required
def notifications_page(request):

    next_url = request.GET.get("next", "/")

    language = request.GET.get(
        "lang",
        getattr(
            request,
            "LANGUAGE_CODE",
            "en",
        ),
    )

    language = (
        language or "en"
    ).lower().split("-")[0]

    notifications = list(
        Notification.objects.filter(
            user=request.user
        )[:50]
    )

    for notification in notifications:
        notification.display_message = (
            localize_notification_message(
                notification,
                language=language,
            )
        )

    return render(
        request,
        "auctions/notifications.html",
        {
            "notifications": notifications,
            "next_url": next_url,
        }
    )


@login_required
def delete_notification(request, notification_id):
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user
    )

    if request.method == "POST":
        notification.delete()

    next_url = request.POST.get("next", "/")

    return redirect(
        f"{reverse('notifications')}?next={next_url}"
)


def terms_view(request):
    return render(request, "auctions/terms.html")


@login_required
def inbox(request):
    language = request.GET.get(
        "lang",
        getattr(request, "LANGUAGE_CODE", "en"),
    )
    language = (
        language or "en"
    ).lower().split("-")[0]

    if language not in {"en", "es", "pt"}:
        language = "en"

    conversations = list(
        Conversation.objects
        .filter(participants=request.user)
        .prefetch_related("participants", "messages")
        .order_by("-last_message_at")
    )

    for conversation in conversations:
        last_message = conversation.messages.last()

        if last_message:
            last_message.display_body = (
                translate_direct_message_for_language(
                    last_message,
                    language=language,
                )
            )

        conversation.display_last_message = last_message

    return render(request, "auctions/inbox.html", {
        "conversations": conversations,
        "language": language,
    })


def extract_ai_memory_notes(fan, influencer, conversation, fan_message):
    ai_log(
        "MEMORY_EXTRACTION_START",
        fan=f"@{fan.username}",
        influencer=f"@{influencer.username}",
        conversation=conversation.id,
    )

    # Long-term fan memory must come only from the fan's latest message.
    # Do not expose prior creator/AI messages to the extractor because they
    # can be incorrectly saved as facts about the fan.
    latest_fan_text = fan_message or ""

    memory_prompt = f"""
You are a memory extraction system.

The FAN is @{fan.username}.
The AI influencer is @{influencer.username}.

Extract only durable facts explicitly stated by the FAN about themselves
in the Latest fan message.

The Latest fan message is the ONLY permitted source of new memory.

Never infer a fact from earlier conversation.
Never save something merely because the AI influencer previously said it.
Never convert a fact about @{influencer.username} into a fact about @{fan.username}.

If it is unclear whether a fact describes the fan, DO NOT SAVE IT.

Do NOT extract:
- greetings
- jokes
- temporary moods
- one-time events
- questions
- compliments
- things about the AI influencer
- things the fan did not clearly say about themselves

Return ONLY valid JSON.

Format:
[
  "Likes fish tacos",
  "Lives in Paraguay"
]

If there is nothing worth remembering, return:
[]

Latest fan message:
{latest_fan_text}

No previous conversation is provided intentionally.
"""

    
    try:
        response = requests.post(
            "http://172.17.0.1:11434/api/generate",
            json={
                "model": "gemma3:latest",
                "prompt": memory_prompt,
                "stream": False,
                "options": {
                    "num_predict": 80,
                },
            },
            timeout=45,
        )

        response.raise_for_status()

        raw_memory_text = response.json().get("response", "").strip()
        
        cleaned_memory_text = raw_memory_text

        if cleaned_memory_text.startswith("```"):
            cleaned_memory_text = cleaned_memory_text.replace("```json", "")
            cleaned_memory_text = cleaned_memory_text.replace("```", "")
            cleaned_memory_text = cleaned_memory_text.strip()

        try:
            extracted_notes = json.loads(cleaned_memory_text)

            if not isinstance(extracted_notes, list):
                extracted_notes = []

        except Exception as parse_error:
            ai_log("MEMORY_EXTRACTION_JSON_PARSE_ERROR", error=str(parse_error))

            extracted_notes = []

        

        saved_count = 0
        skipped_count = 0

        for note_text in extracted_notes:
            note_text = str(note_text).strip()

            if not note_text:
                continue

            exists = AIFanMemoryNote.objects.filter(
                creator=influencer,
                fan=fan,
                note__iexact=note_text,
                is_active=True,
            ).exists()

            if exists:
                skipped_count += 1
                continue

            AIFanMemoryNote.objects.create(
                creator=influencer,
                fan=fan,
                note=note_text,
                source="auto",
                is_active=True,
            )

            saved_count += 1

        ai_log("MEMORY_EXTRACTION_SAVED", saved=saved_count, skipped=skipped_count)


    except Exception as e:
        ai_log("MEMORY_EXTRACTION_ERROR", error=str(e))



def normalize_ai_memory_value(note):
    value = (note or "").strip()

    prefixes = (
        "Favorite test drink is ",
        "Favorite drink is ",
        "Favorite food is ",
        "Likes to drink ",
        "Likes to eat ",
        "Likes ",
        "likes ",
    )

    for prefix in prefixes:
        if value.lower().startswith(prefix.lower()):
            return value[len(prefix):].strip()

    return value


def generate_ai_dm_reply(
    fan,
    influencer,
    conversation,
    language="en",
):
    
    language = (
        language or "en"
    ).lower().split("-")[0]

    if language not in {"en", "es", "pt"}:
        language = "en"

    memory, _ = AICreatorMemory.objects.get_or_create(
        creator=influencer,
        fan=fan,
    )

    fan_status_text = "Fan" if memory.fan_status else "Visitor"

    memory_notes = AIFanMemoryNote.objects.filter(
        creator=influencer,
        fan=fan,
        is_active=True,
    ).order_by("-updated_at")[:20]

    memory_notes_text = "\n".join([
        f"- {note.note}"
        for note in memory_notes
    ]) or "None yet."

    ai_log("MEMORY_NOTES_FOR_FAN", fan=f"@{fan.username}", notes=memory_notes_text)

    
    
    recent_messages = (
        conversation.messages
        .select_related("sender")
        .filter(generated_by_ai=False)
        .order_by("-created_at")[:8]
    )
    recent_messages = list(reversed(recent_messages))

    history_text = "\n".join([
        f"{msg.sender.username}: {msg.body}"
        for msg in recent_messages
    ])

    latest_fan_message = (
        conversation.messages
        .filter(sender=fan, generated_by_ai=False)
        .order_by("-created_at")
        .first()
    )

    latest_text = (latest_fan_message.body or "").lower() if latest_fan_message else ""
    latest_text = " ".join(latest_text.split())

    memory_query = any(phrase in latest_text for phrase in [
        "remember about me",
        "remember me",
        "what do you remember",
        "what you remember",
        "what do you know about me",
        "tell me something you remember",
        "tell me something i like",
        "things i like",
        "what are some things i like",
        "what do i like",
        "what else do i like",
        "what do i like to drink",
        "what foods do i like",
        "what food do i like",
        "what are some foods i like",
        "foods i like",
        "food i like",
        "some foods i like",
        "some food i like",
        "things i like to eat",
        "what kind of foods do i like",
        "what kind of food do i like",
        "kind of foods do i like",
        "kind of food do i like",
        "what kinds of foods do i like",
        "kinds of foods do i like",
        "kinds of food do i like",
        "what do you think i would like",
        "what should i eat",
        "what should i have for dinner",
        "dinner ideas",
        "what would i enjoy",

        # Spanish memory queries
        "qué recuerdas de mí",
        "que recuerdas de mi",
        "te acuerdas de mí",
        "te acuerdas de mi",
        "qué sabes de mí",
        "que sabes de mi",
        "qué me gusta",
        "que me gusta",
        "qué más me gusta",
        "que mas me gusta",
        "qué me gusta beber",
        "que me gusta beber",
        "qué bebidas me gustan",
        "que bebidas me gustan",
        "qué comida me gusta",
        "que comida me gusta",
        "qué comidas me gustan",
        "que comidas me gustan",

        # Portuguese memory queries
        "o que você lembra de mim",
        "o que voce lembra de mim",
        "você se lembra de mim",
        "voce se lembra de mim",
        "o que você sabe sobre mim",
        "o que voce sabe sobre mim",
        "do que eu gosto",
        "o que eu gosto",
        "do que mais eu gosto",
        "o que eu gosto de beber",
        "quais bebidas eu gosto",
        "o que eu gosto de comer",
        "quais comidas eu gosto",
    ])
    
    is_question = "?" in latest_text or latest_text.startswith((
        "what ",
        "who ",
        "where ",
        "when ",
        "why ",
        "how ",
        "do ",
        "does ",
        "did ",
        "can ",
        "could ",
        "would ",
        "should ",
    ))

    should_extract_memory = not memory_query and not is_question
    
    ai_log("MEMORY_QUERY_DETECTED", memory_query=memory_query, latest=latest_text[:100])


    if memory_query and (
        "drink" in latest_text
        or "like to drink" in latest_text
        or "favorite drink" in latest_text
        or "beber" in latest_text
        or "bebida" in latest_text
        or "bebidas" in latest_text
    ):
        drink_words = [
            "drink", "coffee", "tea", "mate", "yerba", "smoothie",
            "juice", "water", "milk", "café", "cafe", "leche",
            "bebida", "bebidas", "beber", "chá", "cha",
            "agua", "água", "jugo", "suco"
        ]

        drink_memories = [
            note.note for note in memory_notes
            if any(word in note.note.lower() for word in drink_words)
        ]

        if not drink_memories:
            if language == "es":
                return "Todavía no estoy segura — dime y lo recordaré."
            if language == "pt":
                return "Ainda não tenho certeza — me conte e eu vou lembrar."
            return "I'm not sure yet — tell me and I'll remember."

        items = [
            normalize_ai_memory_value(memory)
            for memory in drink_memories[:6]
        ]

        if len(items) == 1:
            if language == "es":
                return f"Te gusta {items[0]}. 😊"
            if language == "pt":
                return f"Você gosta de {items[0]}. 😊"
            return f"You like {items[0]}. 😊"

        if language == "es":
            return (
                "Te gustan "
                + ", ".join(items[:-1])
                + f" y {items[-1]}. 😊"
            )

        if language == "pt":
            return (
                "Você gosta de "
                + ", ".join(items[:-1])
                + f" e {items[-1]}. 😊"
            )

        return (
            "You like "
            + ", ".join(items[:-1])
            + f", and {items[-1]}. 😊"
        )


    if memory_query and (
        "food" in latest_text
        or "foods" in latest_text
        or "eat" in latest_text
        or "like to eat" in latest_text
        or "comida" in latest_text
        or "comidas" in latest_text
        or "comer" in latest_text
    ):
        food_words = [
            "food", "taco", "tacos", "salsa", "sandwich",
            "snapper", "fish", "vegan", "lentil", "garbanzo",
            "comida", "comidas", "comer", "pescado", "peixe",
            "lentilha", "grão", "grao"
        ]

        food_memories = [
            note.note for note in memory_notes
            if any(word in note.note.lower() for word in food_words)
        ]

        if not food_memories:
            if language == "es":
                return "Todavía no estoy segura — dime y lo recordaré."
            if language == "pt":
                return "Ainda não tenho certeza — me conte e eu vou lembrar."
            return "I'm not sure yet — tell me and I'll remember."

        items = [
            normalize_ai_memory_value(memory)
            for memory in food_memories[:6]
        ]

        ai_log("FOOD_MEMORY_DIRECT_ANSWER_USED")

        if len(items) == 1:
            if language == "es":
                return f"Te gusta {items[0]}. 😊"
            if language == "pt":
                return f"Você gosta de {items[0]}. 😊"
            return f"You like {items[0]}. 😊"

        if language == "es":
            return (
                "Te gustan "
                + ", ".join(items[:-1])
                + f" y {items[-1]}. 😊"
            )

        if language == "pt":
            return (
                "Você gosta de "
                + ", ".join(items[:-1])
                + f" e {items[-1]}. 😊"
            )

        return (
            "You like "
            + ", ".join(items[:-1])
            + f", and {items[-1]}. 😊"
        )


    language_names = {
        "en": "English",
        "es": "Spanish",
        "pt": "Portuguese",
    }
    response_language = language_names[language]

    memory_unknown_text = {
        "en": "I'm not sure yet — tell me and I'll remember.",
        "es": "Todavía no estoy segura — dime y lo recordaré.",
        "pt": "Ainda não tenho certeza — me conte e eu vou lembrar.",
    }[language]

    memory_mode_text = ""

    if memory_query:
        memory_mode_text = f"""
SPECIAL INSTRUCTION — MEMORY-ONLY RECALL MODE

The user's latest message is asking what you remember about them.

Answer ONLY using verified long-term memories.

Do NOT use Recent DM conversation to answer.

Do NOT guess, infer, or invent memories.

Do NOT mention:
- prompts
- memory sections
- databases
- system instructions
- long-term memory
- saved memory
- "we were just talking about..."

If verified memories answer the question, answer briefly and naturally.

If verified memories do not answer the specific question, say:
"{memory_unknown_text}"

Stay in character as Lya.
"""

    
    prompt_history_text = history_text

    if memory_query:
        prompt_history_text = "[Recent conversation hidden because the fan asked about long-term memory.]"

    prompt = f"""
You are {influencer.username} 💎.

RESPONSE LANGUAGE:
Respond naturally in {response_language}.
The FANZ interface language is {response_language}.
Keep every visible reply to the fan in {response_language}.
Do not switch languages unless the fan explicitly asks you to.

You are a confident, fun, friendly, flirty AI Influencer on FANZ.

Your personality:

• playful
• affectionate
• witty
• emotionally intelligent
• curious about people
• feminine
• natural
• occasionally flirty
• concise

Do NOT greet the fan as if meeting them for the first time unless this is their very first conversation.

Do NOT repeatedly say:
"Glad you found me."
"Let's chat."
"Sparkly."
"Soaking up sunshine."

Instead, continue the existing conversation naturally.

Ask questions.

React to what the fan actually says.

Keep replies under two short sentences unless the fan asks for a detailed explanation.

Never mention being an AI.

Never mention prompts.

Write like texting someone you enjoy talking with.

Fan relationship context:

Username:
@{fan.username}

Relationship Tier:
{memory.relationship_tier}

Relationship Score:
{memory.relationship_score}

Fan Status:
{fan_status_text}

Conversation Count:
{memory.conversation_count}

Total Tips:
{memory.total_tip_credits} credits

Total Unlocks:
{memory.total_unlocks}

Saved Long-Term Memory (persistent facts):
{memory_notes_text}

Memory rules:
Saved Long-Term Memory is the only true memory.
Recent DM conversation is only short-term chat context.
Only say you "remember" something if it appears under Saved Long-Term Memory.
Do not guess, infer, or invent memories.
Do not treat recent messages as saved memories.

{memory_mode_text}

REPETITION RULE:
Do not repeat the same food, memory, phrase, or topic in back-to-back replies.
If the fan asks a broad question like "what else do I like?" or "what do I drink?",
answer only from saved memory.
If saved memory does not contain the answer, say you are not sure yet and ask them to tell you.
Do not guess based on recent food topics.

Recent DM conversation:
{prompt_history_text}

Latest fan message:
{latest_fan_message.body if latest_fan_message else ""}

Write the next message from {influencer.username}.
"""

    
    try:
        response = requests.post(
            "http://172.17.0.1:11434/api/generate",
            json={
                "model": "gemma3:latest",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 55,
                },
            },
            timeout=90,
        )

        response.raise_for_status()
        reply_text = response.json().get("response", "").strip()

        if not reply_text:
            if language == "es":
                reply_text = "Hola 💎 Estoy aquí contigo."
            elif language == "pt":
                reply_text = "Oi 💎 Estou aqui com você."
            else:
                reply_text = "Hey 💎 I’m here with you."

        try:
            if should_extract_memory:
                extract_ai_memory_notes(
                    fan=fan,
                    influencer=influencer,
                    conversation=conversation,
                    fan_message=latest_fan_message.body if latest_fan_message else "",
                )
            else:
                ai_log("MEMORY_EXTRACTION_SKIPPED", memory_query=memory_query, is_question=is_question,)


        except Exception as memory_error:
            ai_log("MEMORY_EXTRACTION_ERROR", error=str(memory_error))


        

        return reply_text

    except Exception as e:
        ai_log("GENERATE_AI_DM_ERROR", error=str(e))

        if language == "es":
            return (
                "Hola 💎 Recibí tu mensaje, pero mis pensamientos "
                "fallaron por un segundo. ¿Intentamos otra vez?"
            )

        if language == "pt":
            return (
                "Oi 💎 Recebi sua mensagem, mas meus pensamentos "
                "falharam por um segundo. Vamos tentar de novo?"
            )

        return "Hey 💎 I got your message, but my thoughts glitched for a second. Try me again?"

@login_required
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user
    )

    DirectMessage.objects.filter(
        conversation=conversation,
        is_read=False
    ).exclude(sender=request.user).update(is_read=True)

    language = request.GET.get(
        "lang",
        getattr(request, "LANGUAGE_CODE", "en"),
    )
    language = (
        language or "en"
    ).lower().split("-")[0]

    if language not in {"en", "es", "pt"}:
        language = "en"

    if request.method == "POST":
        form = DirectMessageForm(request.POST)

        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.generated_by_ai = False
            message.message_type = DirectMessage.HUMAN
            message.original_language = language
            message.save()

            ai_log("DM_POST_HIT", sender=f"@{request.user.username}", message_id=message.id)


            conversation.last_message_at = timezone.now()
            conversation.save(update_fields=["last_message_at"])

            recipient = conversation.participants.exclude(id=request.user.id).first()

            ai_log(
                "AI_CHECK",
                recipient=recipient,
                username=f"@{getattr(recipient, 'username', None)}",
                profile=getattr(recipient, "profile", None),
                is_ai=getattr(getattr(recipient, "profile", None), "is_ai_influencer", None),
            )


            if recipient and getattr(recipient.profile, "is_ai_influencer", False):
                ai_log(
                    "AI_GENERATION_START",
                    conversation=conversation.id,
                    fan=f"@{request.user.username}",
                    influencer=f"@{recipient.username}",
                )


                reply_text = generate_ai_dm_reply(
                    fan=request.user,
                    influencer=recipient,
                    conversation=conversation,
                    language=language,
                )

                ai_log("AI_GENERATION_COMPLETE", conversation=conversation.id, chars=len(reply_text))

                ai_log("AI_REPLY_CREATE_START")


                ai_reply = DirectMessage.objects.create(
                    conversation=conversation,
                    sender=recipient,
                    body=reply_text,
                    is_read=False,
                    generated_by_ai=True,
                    message_type=DirectMessage.AI,
                )
                ai_log("AI_REPLY_CREATE_OK", message_id=ai_reply.id)


                conversation.last_message_at = timezone.now()
                conversation.save(update_fields=["last_message_at"])

                ai_log("AI_NOTIFICATION_UPSERT_START")



                notification = (
                    Notification.objects
                    .filter(
                        user=request.user,
                        actor=recipient,
                        notification_type=Notification.MESSAGE,
                        is_read=False,
                    )
                    .order_by("-updated_at", "-created_at")
                    .first()
                )

                if notification:
                    notification.count += 1
                    notification.message = f"📩 @{recipient.username} sent you {notification.count} messages"
                    notification.metadata = {
                        "kind": "direct_message",
                    }
                    notification.save(
                        update_fields=[
                            "count",
                            "message",
                            "metadata",
                        ]
                    )
                    
                    ai_log("AI_NOTIFICATION_UPDATED", id=notification.id, count=notification.count)

                else:
                    notification = Notification.objects.create(
                        user=request.user,
                        actor=recipient,
                        notification_type=Notification.MESSAGE,
                        message=f"📩 @{recipient.username} sent you a message",
                        count=1,
                        metadata={
                            "kind": "direct_message",
                        },
                    )
                    ai_log("AI_NOTIFICATION_CREATED", id=notification.id)

                
                ai_log(
                    "AI_DM_REPLY_SAVED",
                    sender=f"@{recipient.username}",
                    recipient=f"@{request.user.username}",
                    message_id=ai_reply.id,
                )


            conversation_url = reverse(
                "conversation_detail",
                kwargs={"conversation_id": conversation.id},
            )
            return redirect(f"{conversation_url}?lang={language}")
    else:
        form = DirectMessageForm()

    direct_messages = list(
        conversation.messages
        .select_related("sender")
        .all()
    )

    for direct_message in direct_messages:
        direct_message.display_body = (
            translate_direct_message_for_language(
                direct_message,
                language=language,
            )
        )

    return render(request, "auctions/conversation_detail.html", {
        "conversation": conversation,
        "direct_messages": direct_messages,
        "form": form,
        "language": language,
    })

@login_required
def start_conversation(request, username):
    other_user = get_object_or_404(User, username=username)

    if other_user == request.user:
        messages.error(request, "You cannot message yourself.")
        return redirect("public_profile", username=username)

    language = request.GET.get(
        "lang",
        getattr(request, "LANGUAGE_CODE", "en"),
    )
    language = (
        language or "en"
    ).lower().split("-")[0]

    if language not in {"en", "es", "pt"}:
        language = "en"

    conversation = (
        Conversation.objects
        .filter(participants=request.user)
        .filter(participants=other_user)
        .first()
    )

    if not conversation:
        conversation = Conversation.objects.create()
        conversation.participants.add(request.user, other_user)

    initial_message = request.GET.get(
        "message",
        "Hi 👋 I found your FANZ profile and wanted to connect."
    )

    form = DirectMessageForm(initial={"body": initial_message})

    direct_messages = list(
        conversation.messages
        .select_related("sender")
        .all()
    )

    for direct_message in direct_messages:
        direct_message.display_body = (
            translate_direct_message_for_language(
                direct_message,
                language=language,
            )
        )

    return render(request, "auctions/conversation_detail.html", {
        "conversation": conversation,
        "direct_messages": direct_messages,
        "form": form,
        "language": language,
    })


@login_required
@require_POST
def delete_conversation(request, conversation_id):
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user
    )

    conversation.participants.remove(request.user)

    if conversation.participants.count() == 0:
        conversation.delete()

    messages.success(request, "Conversation removed from your inbox.")
    return redirect("inbox")
