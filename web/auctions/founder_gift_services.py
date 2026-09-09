import hashlib
import secrets

from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .founder_coin_services import create_founder_coin_draft
from .founder_ledger import append_founder_ownership_ledger
from .founder_services import normalize_owner_root
from .models import (
    FounderAccount,
    FounderGiftClaim,
    FounderOwnershipLedger,
)


class FounderGiftError(RuntimeError):
    pass


def gift_token_hash(raw_token):
    return hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()


@transaction.atomic
def reissue_founder_gift_claim_token(
    *,
    claim_id,
):
    claim = (
        FounderGiftClaim.objects
        .select_for_update()
        .get(pk=claim_id)
    )

    if claim.status != FounderGiftClaim.STATUS_PENDING:
        raise FounderGiftError(
            "Only pending Founder gifts can be reissued."
        )

    raw_token = secrets.token_urlsafe(32)

    claim.token_hash = gift_token_hash(
        raw_token
    )

    claim.expires_at = (
        timezone.now()
        + timezone.timedelta(days=30)
    )

    claim.save(
        update_fields=[
            "token_hash",
            "expires_at",
            "updated_at",
        ]
    )

    return claim, raw_token


def send_founder_gift_claim_email(
    *,
    claim_id,
    raw_token,
):
    claim = (
        FounderGiftClaim.objects
        .select_related(
            "founder_account",
            "purchaser",
        )
        .get(pk=claim_id)
    )

    if claim.status != FounderGiftClaim.STATUS_PENDING:
        return False

    claim_url = (
        "https://fanz.to"
        "/auctions/founder/gift/"
        f"{raw_token}/"
    )

    context = {
        "claim": claim,
        "claim_url": claim_url,
        "founder": claim.founder_account,
        "purchaser": claim.purchaser,
    }

    text_body = render_to_string(
        "emails/founder_gift_claim.txt",
        context,
    )

    html_body = render_to_string(
        "emails/founder_gift_claim.html",
        context,
    )

    email = EmailMultiAlternatives(
        subject=(
            "🎁 You received "
            f"@{claim.founder_account.handle} on FANZ"
        ),
        body=text_body,
        from_email=None,
        to=[claim.recipient_email],
    )

    email.attach_alternative(
        html_body,
        "text/html",
    )

    email.send(
        fail_silently=False
    )

    return True


def get_founder_gift_claim(
    *,
    raw_token,
):
    token_hash = gift_token_hash(
        raw_token
    )

    claim = (
        FounderGiftClaim.objects
        .select_related(
            "founder_account",
            "purchaser",
            "claimed_by",
        )
        .filter(
            token_hash=token_hash
        )
        .first()
    )

    if claim is None:
        raise FounderGiftError(
            "Gift claim link is invalid."
        )

    if claim.status != FounderGiftClaim.STATUS_PENDING:
        raise FounderGiftError(
            "This Founder gift is no longer claimable."
        )

    if claim.expires_at <= timezone.now():
        raise FounderGiftError(
            "This Founder gift claim link has expired."
        )

    return claim


@transaction.atomic
def claim_founder_gift(
    *,
    raw_token,
    recipient_user,
    sui_recipient_address="",
):
    token_hash = gift_token_hash(
        raw_token
    )

    claim = (
        FounderGiftClaim.objects
        .select_for_update()
        .select_related(
            "founder_account",
            "purchaser",
        )
        .filter(
            token_hash=token_hash
        )
        .first()
    )

    if claim is None:
        raise FounderGiftError(
            "Gift claim link is invalid."
        )

    if claim.status != FounderGiftClaim.STATUS_PENDING:
        raise FounderGiftError(
            "This Founder gift is no longer claimable."
        )

    if claim.expires_at <= timezone.now():
        raise FounderGiftError(
            "This Founder gift claim link has expired."
        )

    recipient_email = (
        getattr(
            recipient_user,
            "email",
            "",
        )
        or ""
    ).strip().lower()

    if not recipient_email:
        raise FounderGiftError(
            "Your FANZ account needs an email "
            "before claiming this gift."
        )

    if recipient_email != claim.recipient_email.lower():
        raise FounderGiftError(
            "This Founder gift was sent to "
            "a different email address."
        )

    recipient_root = normalize_owner_root(
        recipient_user
    )

    founder = (
        FounderAccount.objects
        .select_for_update()
        .get(
            pk=claim.founder_account_id
        )
    )

    if (
        founder.status
        != FounderAccount.STATUS_OWNED
    ):
        raise FounderGiftError(
            "Gifted Founder property is not "
            "in an owned state."
        )

    if (
        founder.owner_root_id
        != claim.purchaser_id
    ):
        raise FounderGiftError(
            "Gifted Founder property is no longer "
            "owned by the original purchaser."
        )

    if recipient_root.pk == claim.purchaser_id:
        raise FounderGiftError(
            "This Founder gift is already owned "
            "by this account."
        )

    founder.owner_root = recipient_root
    founder.save(
        update_fields=[
            "owner_root",
            "updated_at",
        ]
    )

    ledger_record = (
        append_founder_ownership_ledger(
            founder_account=founder,
            seller_root=claim.purchaser,
            buyer_root=recipient_root,
            transfer_type=(
                FounderOwnershipLedger
                .TRANSFER_GIFT_CLAIM
            ),
            sale_price_credits=0,
            platform_fee_credits=0,
            seller_proceeds_credits=0,
            wallet_transaction_ids=[],
            metadata_snapshot={
                "gift_claim_id": claim.pk,
                "cart_item_id":
                    claim.cart_item_id,
                "recipient_email":
                    claim.recipient_email,
                "claimed_by_username":
                    recipient_user.username,
                "owner_root_username":
                    recipient_root.username,
            },
        )
    )

    claim.status = (
        FounderGiftClaim.STATUS_CLAIMED
    )
    claim.claimed_by = recipient_user
    claim.claimed_at = timezone.now()

    claim.save(
        update_fields=[
            "status",
            "claimed_by",
            "claimed_at",
            "updated_at",
        ]
    )

    sui_address = (
        sui_recipient_address or ""
    ).strip()

    if sui_address:
        transaction.on_commit(
            lambda founder_id=founder.pk,
            address=sui_address: (
                create_founder_coin_draft(
                    founder_account_id=founder_id,
                    recipient_address=address,
                    issuance_source=(
                        "founder_ownership"
                    ),
                    publication_network="mainnet",
                )
            )
        )

    return {
        "claim": claim,
        "founder_account": founder,
        "recipient_root": recipient_root,
        "ledger_record": ledger_record,
        "sui_recipient_address":
            sui_address,
    }
