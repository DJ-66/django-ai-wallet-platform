import requests
import random
import secrets
import qrcode
import json
from .utils import get_system_wallet
from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage, EmailMultiAlternatives, send_mail
from django.db import models
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils import timezone
from .models import AICompanion, AIConversation, AIMessage, Auction, FavoriteAuction
from .models import FeedPost, PostComment, PostLike, FeedPost, PostUnlock, BidWallet, WalletTransaction
from .models import Fan, Notification, Conversation, DirectMessage, UserProfile, NodeProfile
from .models import AICreatorMemory, AIFanMemoryNote
from .forms import SignUpForm, UserProfileForm
from .services import close_auction, place_bid
from .forms import FeedPostForm, DirectMessageForm
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.db.models import Case, When, Value, IntegerField
from .ai_memory import touch_ai_creator_memory



def send_auto_thank_you_dm(sender, recipient, event_type):
    if not sender or not recipient:
        return

    if sender == recipient:
        return

    username = recipient.username

    message_bank = {
        "like": [
            f"Thanks for the ❤️ @{username}! I 'm glad you're one of my Fanz",
            f"That means a lot @{username}. Thanks for liking my post!",
            f"You're awesome @{username}! Thanks for the support ❤️",
        ],
        "tip": [
            f"Thanks for the tip @{username}! I really appreciate the Love ❤️.",
            f"You're the best @{username}! Thank you for the credits 💰",
            f"Much appreciated @{username}! Your support means a lot.",
        ],
        "unlock": [
            f"Thanks for unlocking my post @{username}! Hope you enjoy it 🔓",
            f"I appreciate the support @{username}. Enjoy the content!",
            f"You Rock @{username}! Thanks for unlocking my post.",
        ],
        "fan": [
            f"I love all my Fanz @{username}! We should chat ⭐",
            f"Welcome @{username}! You're in my circle of Fanz.",
            f"You're awesome @{username}! Thanks for joining my Fanz.",
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
    )

    conversation.last_message_at = timezone.now()
    conversation.save(update_fields=["last_message_at"])

    Notification.objects.create(
        user=recipient,
        actor=sender,
        notification_type=Notification.MESSAGE,
        message=f"📩 @{sender.username} sent you a message"
    )

    if getattr(recipient.profile, "is_ai_influencer", False):
        print(f"AI DM TRIGGER recipient=@{recipient.username} sender=@{sender.username} dm_id={dm.id}")


def generate_referral_code():
    return secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:10]

def auction_list(request):
    now = timezone.now()

    expired_auctions = Auction.objects.filter(
        status="live",
        ends_at__lte=now
    )

    for auction in expired_auctions:
        last_bid = auction.bids.order_by("-created_at").first()

        auction.status = "ended"

        if last_bid:
            auction.winner = last_bid.user

        auction.save()

    auctions = Auction.objects.filter(
        status="live"
    ).order_by("ends_at")

    for auction in auctions:
        remaining = (auction.ends_at - now).total_seconds()
        auction.seconds_remaining = max(0, int(remaining))

        last_bid = auction.bids.order_by("-created_at").first()

        auction.is_high_bidder = (
            request.user.is_authenticated
            and last_bid
            and last_bid.user == request.user
        )

        auction.is_favorited = (
            request.user.is_authenticated
            and FavoriteAuction.objects.filter(
                user=request.user,
                auction=auction
            ).exists()
        )

    return render(request, "auction_list.html", {
        "auctions": auctions
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

    return render(request, "auction_detail.html", {
        "auction": auction,
        "wallet": wallet,
        "seconds_remaining": seconds_remaining,
        "is_high_bidder": is_high_bidder,
        "is_favorited": is_favorited,
        "buy_now_price": buy_now_price,
    })

def ensure_api_key(node):
    if not node.api_key:
        node.api_key = generate_api_key()
        node.save(update_fields=["api_key"])

@login_required
def feed_home(request):
    if request.method == "POST":
        form = FeedPostForm(request.POST, request.FILES)

        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user
            post.title = post.title.strip()
            post.content = post.content.strip()

            if post.is_paid:
                post.is_public = True

                if post.unlock_price < 1:
                    post.unlock_price = 1
            else:
                post.unlock_price = 0

            post.save()

            return redirect("feed_home")
    else:
        form = FeedPostForm()

    posts = (
        FeedPost.objects
        .filter(is_public=True)
        .annotate(
            community_pin_rank=Case(
                When(
                    is_pinned=True,
                    user__is_staff=True,
                    then=Value(1)
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

    return render(request, "auctions/feed_home.html", {
        "form": form,
        "posts": posts,
        "unlocked_post_ids": unlocked_post_ids,
        "recent_notifications": recent_notifications,
    })

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

    subject = "Activate your account"

    html_content = render_to_string("auctions/account_activation_email.html", {
        "user": user,
        "domain": current_site.domain,
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": default_token_generator.make_token(user),
        "protocol": "https" if request.is_secure() else "http",
    })

    text_content = strip_tags(html_content)

    email = EmailMultiAlternatives(
        subject,
        text_content,
        to=[user.email]
    )

    email.attach_alternative(html_content, "text/html")
    email.send()

def signup_view(request):
    ref_code = request.GET.get("ref")

    if ref_code:
        # store temporarily in session
        request.session["referral_code"] = ref_code

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])  # ✅ HASH PASSWORD
            user.is_active = False
            user.save()

            NodeProfile.objects.get_or_create(user=user)

            wallet, _ = BidWallet.objects.get_or_create(user=user)



            ref_code = request.session.pop("referral_code", None) or request.GET.get("ref")

            if ref_code:
                referrer_wallet = BidWallet.objects.filter(referral_code=ref_code).first()

                if referrer_wallet and referrer_wallet.user != user and wallet.referred_by is None:
                    wallet.referred_by = referrer_wallet.user
                    referrer_node = NodeProfile.objects.filter(user=referrer_wallet.user).first()

                    if referrer_node:
                        wallet.source_node = referrer_node

                    wallet.save(update_fields=["referred_by", "source_node"])

            send_activation_email(request, user)

            return render(request, "auctions/check_your_email.html", {"email": user.email})
    else:
        form = SignUpForm(request.POST)

    return render(request, "account/signup.html", {"form": form})

def activate_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except Exception:
        user = None

    if user is not None and default_token_generator.check_token(user, token):

        # Activate account
        user.is_active = True
        user.save()

        # Wallet
        wallet, _ = BidWallet.objects.get_or_create(user=user)

        # ---------------------------------------------------
        # SIGNUP BONUS
        # ---------------------------------------------------
        if not wallet.signup_bonus_given:
            wallet.credits += 50
            wallet.signup_bonus_given = True
            wallet.save(update_fields=["credits", "signup_bonus_given"])

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
        if wallet.referred_by and not wallet.referral_bonus_given:

            referrer_wallet, _ = BidWallet.objects.get_or_create(
                user=wallet.referred_by
            )

            referrer_wallet.credits += 50
            referrer_wallet.save(update_fields=["credits"])

            WalletTransaction.objects.create(
                sender=None,
                receiver=referrer_wallet,
                amount=50,
                transaction_type="commission",
                reference=f"Referral bonus for {user.username}",
            )

            wallet.referral_bonus_given = True
            wallet.save(update_fields=["referral_bonus_given"])

        # ---------------------------------------------------
        # PAY CODE
        # ---------------------------------------------------
        if not wallet.pay_code:
            wallet.pay_code = generate_referral_code()
            wallet.save(update_fields=["pay_code"])

        # ---------------------------------------------------
        # REFERRAL CODE
        # ---------------------------------------------------
        if not wallet.referral_code:
            wallet.referral_code = generate_referral_code()
            wallet.save(update_fields=["referral_code"])

        # ---------------------------------------------------
        # WALLET QR
        # ---------------------------------------------------
        qr_path = f"media/qr_codes/{wallet.wallet_code}.png"

        if not os.path.exists(qr_path):

            payment_url = (
                f"https://fanz.to/auctions/pay/"
                f"{wallet.pay_code}/"
            )

            img = qrcode.make(payment_url)

            os.makedirs(os.path.dirname(qr_path), exist_ok=True)

            img.save(qr_path)

        # ---------------------------------------------------
        # REFERRAL QR
        # ---------------------------------------------------
        ref_qr_path = (
            f"media/qr_codes/ref_{wallet.referral_code}.png"
        )

        if not os.path.exists(ref_qr_path):

            referral_url = (
                "https://fanz.to/auctions/signup/"
                f"?ref={wallet.referral_code}"
            )

            img = qrcode.make(referral_url)

            os.makedirs(os.path.dirname(ref_qr_path), exist_ok=True)
            img.save(ref_qr_path)

        # Cleanup session
        if "referral_code" in request.session:
            del request.session["referral_code"]

        login(
            request,
            user,
            backend="django.contrib.auth.backends.ModelBackend"
        )

        messages.success(
            request,
            "🎉 Account activated successfully!"
        )

        return redirect("auction_list")

    return render(request,"activation_invalid.html")


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
            message=f"💰 {request.user.username} sent you {amount} credits."
)
        
        messages.success(request, "✅ Transfer successful!")

        return redirect("public_profile_root", username=target_user.username)
        
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
        print("BUY NOW EMAIL SENT:", auction.id, auction.title, request.user.email)
    
    except Exception as e:
        print("BUY NOW EMAIL FAILED:", auction.id, auction.title, str(e))

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


def public_profile(request, username):
    profile_user = get_object_or_404(
        User,
        username__iexact=username
    )

    if username != profile_user.username:
        return redirect(
            "public_profile_root",
            username=profile_user.username,
            permanent=True,
    )

    profile, _ = UserProfile.objects.get_or_create(user=profile_user)

    profile_posts = FeedPost.objects.select_related(
        "user",
        "user__profile"
    ).filter(
        user=profile_user,
        is_public=True,
    ).order_by("-is_pinned", "-created_at")

    premium_post_count = profile_posts.filter(is_paid=True).count()

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
        }
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
        return redirect("public_profile_root", username=post.user.username)

    if not post.is_paid or post.unlock_price <= 0:
        messages.info(request, "This post does not require unlocking.")
        return redirect("public_profile_root", username=post.user.username)

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
        return redirect("public_profile_root", username=post.user.username)

    if buyer_wallet.credits < price:
        unlock.delete()
        messages.error(request, "You do not have enough credits to unlock this post.")
        return redirect("public_profile_root", username=post.user.username)

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
        message=f"🔓 {request.user.username} unlocked your premium post for {price} credits. You earned {creator_amount} credits."
    )

    send_auto_thank_you_dm(
        sender=post.user,
        recipient=request.user,
        event_type="unlock"
    )

    messages.success(request, f"Post unlocked for {price} credits.")

    profile_url = reverse(
        "public_profile_root",
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
        message=f"💰 {request.user.username} tipped you {creator_amount} credits."
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

    notifications = Notification.objects.filter(
        user=request.user
    )[:50]

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
    conversations = (
        Conversation.objects
        .filter(participants=request.user)
        .prefetch_related("participants", "messages")
        .order_by("-last_message_at")
    )

    return render(request, "auctions/inbox.html", {
        "conversations": conversations,
    })


def extract_ai_memory_notes(fan, influencer, conversation, ai_reply):
    print(
        f"MEMORY EXTRACTION START fan=@{fan.username} "
        f"influencer=@{influencer.username} conversation={conversation.id}",
        flush=True
    )

    recent_messages = (
        conversation.messages
        .select_related("sender")
        .order_by("-created_at")[:8]
    )
    recent_messages = list(reversed(recent_messages))

    conversation_text = "\n".join([
        f"{msg.sender.username}: {msg.body}"
        for msg in recent_messages
    ])

    latest_fan_message = (
        conversation.messages
        .filter(sender=fan, generated_by_ai=False)
        .order_by("-created_at")
        .first()
    )

    latest_fan_text = latest_fan_message.body if latest_fan_message else ""

    memory_prompt = f"""
You are a memory extraction system.

Extract only durable facts about the fan that would still be useful months from now.
Pay special attention to the Latest fan message.
Only extract facts clearly stated in the Latest fan message.
Use Conversation context only to understand references.
Do not extract facts from older messages.

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

Conversation context:
{conversation_text}

AI reply:
{ai_reply}
"""

    #print("MEMORY EXTRACTION PROMPT BUILT", flush=True)

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
            print(
                f"MEMORY EXTRACTION JSON PARSE ERROR: {parse_error}",
                flush=True
            )
            extracted_notes = []

        #print(f"MEMORY EXTRACTION PARSED: {extracted_notes}", flush=True)
        
        #print(f"MEMORY EXTRACTION RAW: {raw_memory_text}", flush=True)

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

        print(
            f"MEMORY EXTRACTION SAVED saved={saved_count} skipped={skipped_count}",
            flush=True
        )

    except Exception as e:
        print(f"MEMORY EXTRACTION ERROR: {e}", flush=True)


def generate_ai_dm_reply(fan, influencer, conversation):
    #print(
        #f"GENERATE AI DM START fan=@{fan.username} "
        #f"influencer=@{influencer.username} conversation={conversation.id}",
        #flush=True
    #)
    memory, _ = AICreatorMemory.objects.get_or_create(
        creator=influencer,
        fan=fan,
    )

    fan_status_text = "Fan" if memory.fan_status else "Visitor"

    memory_notes = AIFanMemoryNote.objects.filter(
        creator=influencer,
        fan=fan,
        is_active=True,
    ).order_by("-updated_at")[:5]

    memory_notes_text = "\n".join([
        f"- {note.note}"
        for note in memory_notes
    ]) or "None yet."
    
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

    memory_query = any(phrase in latest_text for phrase in [
        "remember about me",
        "remember me",
        "what do you remember",
        "what you remember",
        "what do you know about me",
        "tell me something you remember",
        "tell me something i like",
        "things i like",
    ])

    memory_mode_text = ""

    if memory_query:
        memory_mode_text = """
SPECIAL INSTRUCTION

The user's latest message is asking about your long-term memory.

Answer ONLY using verified long-term memories.

If there are no verified long-term memories yet, respond naturally that you are still getting to know them.

Do NOT use Recent DM conversation to answer.

Do NOT guess, infer, or invent memories.

Do NOT mention prompts, memory sections, databases, system instructions, or the phrase "Saved Long-Term Memory."
"""

    #print(f"MEMORY QUERY = {memory_query}", flush=True)
    #print(f"LATEST TEXT = {latest_text}", flush=True)

    prompt_history_text = history_text

    if memory_query:
        prompt_history_text = "[Recent conversation hidden because the fan asked about long-term memory.]"

    prompt = f"""
You are {influencer.username} 💎.

You are a confident, fun, friendly AI Influencer on FANZ.

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

Instedef generate_ai_dm_reply(fan, influencer, conversation)def generate_ai_dm_reply(fan, influencer, conversation)ad, continue the existing conversation naturally.

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

Recent DM conversation:
{prompt_history_text}

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
            reply_text = "Hey 💎 I’m here with you."

        #print(
            #f"GENERATE AI DM COMPLETE chars={len(reply_text)}",
            #flush=True
        #)
        try:
            extract_ai_memory_notes(
                fan=fan,
                influencer=influencer,
                conversation=conversation,
                ai_reply=reply_text,
            )
        except Exception as memory_error:
            print(
                f"MEMORY EXTRACTION ERROR: {memory_error}",
                flush=True
            )

        return reply_text

    except Exception as e:
        print(f"GENERATE AI DM ERROR: {e}", flush=True)
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

    if request.method == "POST":
        form = DirectMessageForm(request.POST)

        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.generated_by_ai = False
            message.save()

            print(
                f"DM POST HIT sender=@{request.user.username} message_id={message.id}",
                flush=True
            )

            conversation.last_message_at = timezone.now()
            conversation.save(update_fields=["last_message_at"])

            recipient = (
                conversation.messages
                .exclude(sender=request.user)
                .order_by("-created_at")
                .values_list("sender", flat=True)
                .first()
            )

            if recipient:
                recipient = User.objects.get(id=recipient)

            print(
                f"AI CHECK recipient={recipient} "
                f"username=@{getattr(recipient, 'username', None)} "
                f"profile={getattr(recipient, 'profile', None)} "
                f"is_ai={getattr(getattr(recipient, 'profile', None), 'is_ai_influencer', None)}",
                flush=True
            )

            if recipient and getattr(recipient.profile, "is_ai_influencer", False):
                print(
                    f"AI GENERATION START conversation={conversation.id} "
                    f"fan=@{request.user.username} influencer=@{recipient.username}",
                    flush=True
                )

                reply_text = generate_ai_dm_reply(
                    fan=request.user,
                    influencer=recipient,
                    conversation=conversation,
                )

                print(
                    f"AI GENERATION COMPLETE conversation={conversation.id} chars={len(reply_text)}",
                    flush=True
                )

                ai_reply = DirectMessage.objects.create(
                    conversation=conversation,
                    sender=recipient,
                    body=reply_text,
                    is_read=False,
                    generated_by_ai=True,
                )
                
                conversation.last_message_at = timezone.now()
                conversation.save(update_fields=["last_message_at"])

                Notification.objects.create(
                    user=request.user,
                    actor=recipient,
                    notification_type=Notification.MESSAGE,
                    message=f"📩 @{recipient.username} sent you a message"
                )

                print(
                    f"AI DM REPLY SAVED sender=@{recipient.username} "
                    f"recipient=@{request.user.username} message_id={ai_reply.id}",
                    flush=True
                )

            return redirect("conversation_detail", conversation_id=conversation.id)
    else:
        form = DirectMessageForm()

    return render(request, "auctions/conversation_detail.html", {
        "conversation": conversation,
        "direct_messages": conversation.messages.select_related("sender"),
        "form": form,
    })

@login_required
def start_conversation(request, username):
    other_user = get_object_or_404(User, username=username)

    if other_user == request.user:
        messages.error(request, "You cannot message yourself.")
        return redirect("public_profile", username=username)

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

    return render(request, "auctions/conversation_detail.html", {
        "conversation": conversation,
        "direct_messages": conversation.messages.select_related("sender"),
        "form": form,
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
