import os
import secrets
import qrcode
import json
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
from .models import AICompanion, AIConversation, AIMessage, Auction, BidWallet, FavoriteAuction, NodeProfile, UserProfile, WalletTransaction
from .forms import SignUpForm, UserProfileForm
from .services import close_auction, place_bid
from .forms import FeedPostForm
from .models import FeedPost, PostComment
from .models import PostLike
from django.db.models import Q
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.db import transaction
from .models import FeedPost, PostUnlock, BidWallet, WalletTransaction
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from .models import Fan, Notification
from .models import Notification

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

    unlocked_post_ids = set(
        PostUnlock.objects.filter(user=request.user)
        .values_list("post_id", flat=True)
    )

    posts = FeedPost.objects.select_related(
        "user",
        "user__profile"
    ).prefetch_related(
        "unlocks"
    ).filter(
        Q(is_public=True) |
        Q(user=request.user) |
        Q(unlocks__user=request.user)
    ).distinct().order_by("-created_at")

    return render(request, "auctions/feed_home.html", {
        "form": form,
        "posts": posts,
        "unlocked_post_ids": unlocked_post_ids,
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

    return render(request, "activation_invalid.html")


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
            transaction_type="transfer",
            reference=None,
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
        return render(request, "auctions/node_dashboard.html", {
            "error": "You are not a node."
        })

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

        if form.is_valid():
            form.save()
            return redirect("public_profile", username=request.user.username)

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
    profile_user = get_object_or_404(User, username=username)
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
    fan_count = Fan.objects.filter(
    creator=profile_user
    ).count()

    if fan_count >= 1_000_000_000:
        fan_count_display = f"{fan_count / 1_000_000_000:.1f}B".rstrip("0").rstrip(".")
    elif fan_count >= 1_000_000:
        fan_count_display = f"{fan_count / 1_000_000:.1f}M".rstrip("0").rstrip(".")
    elif fan_count >= 1_000:
        fan_count_display = f"{fan_count / 1_000:.1f}K".rstrip("0").rstrip(".")
    else:
        fan_count_display = str(fan_count)

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

    return render(
        request,
        "auctions/public_profile.html",
        {
            "profile_user": profile_user,
            "profile": profile,
            "profile_posts": profile_posts,
            "unlocked_post_ids": unlocked_post_ids,
            "premium_post_count": premium_post_count,
            "total_likes": total_likes,
            "fan_count": fan_count,
            "fan_count_display": fan_count_display,
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

    existing_unlock = PostUnlock.objects.filter(
        post=post,
        user=request.user
    ).first()

    if existing_unlock:
        messages.info(request, "You already unlocked this post.")
        return redirect("public_profile_root", username=post.user.username)

    buyer_wallet = BidWallet.objects.select_for_update().get(user=request.user)
    creator_wallet = BidWallet.objects.select_for_update().get(user=post.user)

    price = post.unlock_price

    if buyer_wallet.credits < price:
        messages.error(request, "You do not have enough credits to unlock this post.")
        return redirect("public_profile_root", username=post.user.username)

    buyer_wallet.credits -= price
    creator_wallet.credits += price

    buyer_wallet.save()
    creator_wallet.save()

    PostUnlock.objects.create(
        post=post,
        user=request.user,
        price_paid=price
    )

    WalletTransaction.objects.create(
        sender=buyer_wallet,
        receiver=creator_wallet,
        amount=price,
        transaction_type="purchase",
        reference=f"Unlocked post #{post.id}"
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

    sender_wallet.credits -= amount
    target_wallet.credits += amount

    sender_wallet.save(update_fields=["credits"])
    target_wallet.save(update_fields=["credits"])

    WalletTransaction.objects.create(
        sender=sender_wallet,
        receiver=target_wallet,
        amount=amount,
        transaction_type="transfer",
        reference=f"Quick tip to @{target_wallet.user.username}"
    )

    return JsonResponse({
        "success": True,
        "new_balance": sender_wallet.credits,
    })

@login_required
@require_POST
def toggle_pin_post(request, post_id):
    post = get_object_or_404(FeedPost, id=post_id, user=request.user)

    post.is_pinned = not post.is_pinned
    post.save(update_fields=["is_pinned"])

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
        messages.warning(request, "You cannot become a fan of yourself.")
        return redirect("public_profile", username=username)

    fan_obj, created = Fan.objects.get_or_create(
        creator=creator,
        fan=request.user
    )

    if created:
        messages.success(request, f"⭐ You are now a fan of {creator.username}!")
     
        Notification.objects.create(
            user=creator,
            actor=request.user,
            notification_type=Notification.FAN,
            message=f"⭐ {request.user.username} became a fan of you."
    )
    else:
        fan_obj.delete()
        messages.success(request, f"You are no longer a fan of {creator.username}.")

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


