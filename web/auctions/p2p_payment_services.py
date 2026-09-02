from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .founder_ledger import (
    append_founder_ownership_ledger,
)
from .founder_services import (
    get_authoritative_root,
)
from .models import (
    FounderAccount,
    FounderListing,
    FounderOwnershipLedger,
    PaymentIntent,
)
from .payment_policy import (
    CONTEXT_FOUNDER_P2P,
    payment_method_allowed,
    seller_is_platform,
)
from .sui_adapter import (
    SuiAdapterError,
    quote_sui_payment,
    verify_sui_payment,
)


CREDITS_PER_USD = Decimal("20")

EXTERNAL_P2P_METHODS = frozenset({
    "btc",
    "doge",
    "sui",
})


class P2PPaymentError(RuntimeError):
    pass


def _credits_to_usd(credits):
    credits = int(credits)

    if credits < 200:
        raise P2PPaymentError(
            "Founder P2P purchases require "
            "at least 200 credits."
        )

    return (
        Decimal(credits)
        / CREDITS_PER_USD
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def _validate_external_listing(
    *,
    listing,
    buyer,
    payment_method,
):
    method = str(
        payment_method or ""
    ).strip().lower()

    if method not in EXTERNAL_P2P_METHODS:
        raise P2PPaymentError(
            "Unsupported external P2P payment method."
        )

    if (
        listing.status
        != FounderListing.STATUS_ACTIVE
    ):
        raise P2PPaymentError(
            "Founder P2P listing is no longer active."
        )

    if (
        listing.listing_source
        != FounderListing.SOURCE_P2P
    ):
        raise P2PPaymentError(
            "This listing is not P2P inventory."
        )

    if (
        listing.sale_type
        != FounderListing.SALE_FIXED
    ):
        raise P2PPaymentError(
            "External checkout currently supports "
            "fixed-price P2P listings only."
        )

    if (
        listing.starts_at
        and listing.starts_at > timezone.now()
    ):
        raise P2PPaymentError(
            "Founder P2P listing has not started yet."
        )

    seller_root = get_authoritative_root(
        listing.seller_root
    )

    buyer_root = get_authoritative_root(
        buyer
    )

    if buyer_root.pk == seller_root.pk:
        raise P2PPaymentError(
            "Seller cannot purchase their own "
            "Founder property."
        )

    if not seller_is_platform(
        seller_root
    ):
        raise P2PPaymentError(
            "External payment rails are available "
            "only for authorized FANZ sellers."
        )

    if not payment_method_allowed(
        context=CONTEXT_FOUNDER_P2P,
        payment_method=method,
        seller_is_platform=True,
    ):
        raise P2PPaymentError(
            "Payment method is not allowed "
            "for this Founder listing."
        )

    founder = listing.founder_account

    if founder.owner_root_id != seller_root.pk:
        raise P2PPaymentError(
            "Founder listing seller no longer owns "
            "this property."
        )

    if (
        founder.status
        != FounderAccount.STATUS_LISTED
    ):
        raise P2PPaymentError(
            "Founder property is not currently listed."
        )

    return (
        buyer_root,
        seller_root,
        method,
    )


@transaction.atomic
def create_p2p_external_payment_intent(
    *,
    listing,
    buyer,
    payment_method,
    sui_recipient_address="",
):
    locked_listing = (
        FounderListing.objects
        .select_for_update()
        .select_related(
            "founder_account",
            "seller_root",
        )
        .get(pk=listing.pk)
    )

    (
        buyer_root,
        seller_root,
        method,
    ) = _validate_external_listing(
        listing=locked_listing,
        buyer=buyer,
        payment_method=payment_method,
    )

    price_credits = int(
        locked_listing.fixed_price_credits
        or 0
    )

    amount_usd = _credits_to_usd(
        price_credits
    )

    if method in {"btc", "doge"}:
        settlement_source = (
            PaymentIntent.SETTLEMENT_BTCPAY
        )
    else:
        settlement_source = (
            PaymentIntent.SETTLEMENT_SUI
        )

    existing = (
        PaymentIntent.objects
        .filter(
            user=buyer_root,
            purpose="founder_purchase",
            settlement_source=settlement_source,
            metadata__purchase_channel="p2p",
            metadata__founder_listing_id=(
                locked_listing.pk
            ),
            metadata__payment_method=method,
            status__in=[
                "created",
                "invoice_created",
                "processing",
            ],
        )
        .order_by("-id")
        .first()
    )

    if existing is not None:
        return existing, False

    intent = PaymentIntent.objects.create(
        user=buyer_root,
        purpose="founder_purchase",
        status="created",
        amount=amount_usd,
        currency="USD",
        settlement_source=settlement_source,
        metadata={
            "purchase_channel": "p2p",
            "founder_listing_id":
                locked_listing.pk,
            "founder_account_id":
                locked_listing.founder_account_id,
            "wanted_handle":
                locked_listing.founder_account.handle,
            "seller_root_id":
                seller_root.pk,
            "seller_username":
                seller_root.username,
            "list_price_credits":
                price_credits,
            "payment_method":
                method,
            "sui_recipient_address":
                str(
                    sui_recipient_address or ""
                ).strip().lower(),
        },
    )

    return intent, True


@transaction.atomic
def freeze_p2p_sui_quote(
    *,
    payment_intent_id,
):
    intent = (
        PaymentIntent.objects
        .select_for_update()
        .get(pk=payment_intent_id)
    )

    metadata = dict(
        intent.metadata or {}
    )

    if (
        intent.purpose
        != "founder_purchase"
        or metadata.get(
            "purchase_channel"
        ) != "p2p"
        or metadata.get(
            "payment_method"
        ) != "sui"
        or intent.settlement_source
        != PaymentIntent.SETTLEMENT_SUI
    ):
        raise P2PPaymentError(
            "PaymentIntent is not a P2P "
            "SUI Founder purchase."
        )

    if (
        metadata.get("sui_required_mist")
        and metadata.get(
            "sui_payment_address"
        )
        and metadata.get(
            "sui_quote_expires_at"
        )
    ):
        return intent, False

    try:
        response = quote_sui_payment(
            amount_usd=intent.amount,
        )
    except SuiAdapterError as exc:
        raise P2PPaymentError(
            "Unable to obtain SUI payment quote."
        ) from exc

    quote = response.get("quote")

    if not isinstance(quote, dict):
        raise P2PPaymentError(
            "Sui service returned no quote."
        )

    if quote.get("network") != "mainnet":
        raise P2PPaymentError(
            "SUI quote is not for mainnet."
        )

    recipient = str(
        quote.get(
            "recipient_address",
            "",
        )
    ).strip().lower()

    try:
        required_mist = int(
            quote.get(
                "amount_mist",
                "0",
            )
        )
    except (TypeError, ValueError) as exc:
        raise P2PPaymentError(
            "SUI quote returned invalid MIST."
        ) from exc

    if (
        not recipient
        or required_mist <= 0
    ):
        raise P2PPaymentError(
            "SUI quote is incomplete."
        )

    metadata.update({
        "sui_network":
            "mainnet",

        # Payment destination:
        "sui_payment_address":
            recipient,

        "sui_required_mist":
            str(required_mist),

        "sui_amount":
            str(
                quote.get(
                    "amount_sui",
                    "",
                )
            ),

        "sui_usd_price":
            str(
                quote.get(
                    "sui_usd_price",
                    "",
                )
            ),

        "sui_quoted_at":
            str(
                quote.get(
                    "quoted_at",
                    "",
                )
            ),

        "sui_quote_expires_at":
            str(
                quote.get(
                    "quote_expires_at",
                    "",
                )
            ),
    })

    intent.metadata = metadata

    intent.save(
        update_fields=[
            "metadata",
            "updated_at",
        ]
    )

    return intent, True


@transaction.atomic
def settle_p2p_sui_payment(
    *,
    payment_intent_id,
    tx_digest,
):
    intent = (
        PaymentIntent.objects
        .select_for_update()
        .get(pk=payment_intent_id)
    )

    metadata = intent.metadata or {}

    if (
        metadata.get(
            "purchase_channel"
        ) != "p2p"
        or metadata.get(
            "payment_method"
        ) != "sui"
    ):
        raise P2PPaymentError(
            "PaymentIntent is not a P2P "
            "SUI purchase."
        )

    digest = str(
        tx_digest or ""
    ).strip()

    if not digest:
        raise P2PPaymentError(
            "SUI transaction digest is required."
        )

    if intent.status in {
        "settled",
        "fulfilled",
    }:
        if (
            intent.settlement_reference
            != digest
        ):
            raise P2PPaymentError(
                "PaymentIntent is already settled "
                "with another transaction."
            )

        return intent, False

    recipient = str(
        metadata.get(
            "sui_payment_address",
            "",
        )
    ).strip().lower()

    try:
        required_mist = int(
            metadata.get(
                "sui_required_mist",
                "0",
            )
        )
    except (TypeError, ValueError) as exc:
        raise P2PPaymentError(
            "Frozen SUI quote is invalid."
        ) from exc

    if (
        not recipient
        or required_mist <= 0
    ):
        raise P2PPaymentError(
            "Frozen SUI quote is missing."
        )

    try:
        response = verify_sui_payment(
            tx_digest=digest,
            recipient_address=recipient,
            minimum_amount_mist=required_mist,
        )
    except SuiAdapterError as exc:
        raise P2PPaymentError(
            "Unable to verify SUI payment."
        ) from exc

    verification = response.get(
        "verification"
    )

    if not isinstance(
        verification,
        dict,
    ):
        raise P2PPaymentError(
            "Sui verifier returned no verification."
        )

    if (
        verification.get("network")
        != "mainnet"
        or verification.get("success")
        is not True
        or verification.get("sufficient")
        is not True
    ):
        raise P2PPaymentError(
            "SUI payment verification failed."
        )

    if (
        str(
            verification.get(
                "tx_digest",
                "",
            )
        )
        != digest
    ):
        raise P2PPaymentError(
            "SUI transaction digest mismatch."
        )

    if (
        str(
            verification.get(
                "recipient_address",
                "",
            )
        ).strip().lower()
        != recipient
    ):
        raise P2PPaymentError(
            "SUI payment recipient mismatch."
        )

    try:
        received_mist = int(
            verification.get(
                "received_mist",
                "0",
            )
        )
    except (TypeError, ValueError) as exc:
        raise P2PPaymentError(
            "SUI verifier returned invalid amount."
        ) from exc

    if received_mist < required_mist:
        raise P2PPaymentError(
            "SUI payment amount is insufficient."
        )

    intent.status = "settled"
    intent.settlement_reference = digest

    if intent.paid_at is None:
        intent.paid_at = timezone.now()

    intent.save(
        update_fields=[
            "status",
            "settlement_reference",
            "paid_at",
            "updated_at",
        ]
    )

    return intent, True


def _post_commit_p2p_starter_grant(
    payment_intent_id,
):
    from .sui_grant_services import (
        grant_starter_sui_for_payment_intent,
    )

    intent = PaymentIntent.objects.get(
        pk=payment_intent_id
    )

    metadata = intent.metadata or {}

    grant_starter_sui_for_payment_intent(
        payment_intent=intent,
        payment_method=metadata.get(
            "payment_method",
            "",
        ),
        sui_address=metadata.get(
            "sui_recipient_address",
            "",
        ),
    )


@transaction.atomic
def fulfill_p2p_external_founder_purchase(
    *,
    payment_intent,
):
    """
    Transfer a settled P2P Founder listing after
    BTC/DOGE/SUI settlement.

    No FANZ Credits are debited, minted, or transferred.
    """

    if (
        payment_intent.status
        != "settled"
    ):
        raise P2PPaymentError(
            "P2P external payment must be settled "
            "before fulfillment."
        )

    metadata = payment_intent.metadata or {}

    if (
        metadata.get(
            "purchase_channel"
        ) != "p2p"
    ):
        raise P2PPaymentError(
            "PaymentIntent is not a P2P purchase."
        )

    try:
        listing_id = int(
            metadata[
                "founder_listing_id"
            ]
        )
        expected_seller_id = int(
            metadata[
                "seller_root_id"
            ]
        )
        expected_price = int(
            metadata[
                "list_price_credits"
            ]
        )
    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise P2PPaymentError(
            "P2P PaymentIntent metadata is invalid."
        ) from exc

    locked_listing = (
        FounderListing.objects
        .select_for_update()
        .select_related(
            "founder_account",
            "seller_root",
        )
        .get(pk=listing_id)
    )

    if (
        locked_listing.status
        != FounderListing.STATUS_ACTIVE
    ):
        raise P2PPaymentError(
            "Founder P2P listing is no longer active."
        )

    if (
        locked_listing.listing_source
        != FounderListing.SOURCE_P2P
        or locked_listing.sale_type
        != FounderListing.SALE_FIXED
    ):
        raise P2PPaymentError(
            "PaymentIntent does not reference "
            "an active fixed P2P listing."
        )

    seller_root = get_authoritative_root(
        locked_listing.seller_root
    )

    buyer_root = get_authoritative_root(
        payment_intent.user
    )

    if seller_root.pk != expected_seller_id:
        raise P2PPaymentError(
            "P2P listing seller changed."
        )

    if not seller_is_platform(
        seller_root
    ):
        raise P2PPaymentError(
            "P2P seller is not an authorized "
            "FANZ seller."
        )

    sale_price = int(
        locked_listing.fixed_price_credits
        or 0
    )

    if sale_price != expected_price:
        raise P2PPaymentError(
            "P2P listing price changed."
        )

    founder = (
        FounderAccount.objects
        .select_for_update()
        .get(
            pk=locked_listing.founder_account_id
        )
    )

    if (
        founder.owner_root_id
        != seller_root.pk
    ):
        raise P2PPaymentError(
            "P2P seller no longer owns "
            "the Founder property."
        )

    if (
        founder.status
        != FounderAccount.STATUS_LISTED
    ):
        raise P2PPaymentError(
            "Founder property is not currently listed."
        )

    if buyer_root.pk == seller_root.pk:
        raise P2PPaymentError(
            "Seller cannot purchase their own "
            "Founder property."
        )

    founder.owner_root = buyer_root
    founder.status = (
        FounderAccount.STATUS_OWNED
    )

    founder.save(
        update_fields=[
            "owner_root",
            "status",
            "updated_at",
        ]
    )

    # These are Credits-equivalent ledger values.
    # No actual FANZ Credit wallet transaction exists
    # for an externally-settled purchase.
    ledger_record = (
        append_founder_ownership_ledger(
            founder_account=founder,
            seller_root=seller_root,
            buyer_root=buyer_root,
            transfer_type=(
                FounderOwnershipLedger
                .TRANSFER_P2P_FIXED
            ),
            sale_price_credits=sale_price,
            platform_fee_credits=0,
            seller_proceeds_credits=sale_price,
            wallet_transaction_ids=[],
            metadata_snapshot={
                "external_payment": True,
                "payment_intent_id":
                    payment_intent.pk,
                "settlement_source":
                    payment_intent.settlement_source,
                "settlement_reference":
                    payment_intent.settlement_reference,
                "payment_method":
                    metadata.get(
                        "payment_method"
                    ),
                "seller_username":
                    seller_root.username,
                "buyer_username":
                    buyer_root.username,
                "handle":
                    founder.handle,
                "listing_id":
                    locked_listing.pk,
            },
        )
    )

    locked_listing.status = (
        FounderListing.STATUS_SOLD
    )

    locked_listing.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    if metadata.get(
        "sui_recipient_address"
    ):
        transaction.on_commit(
            lambda intent_id=payment_intent.pk: (
                _post_commit_p2p_starter_grant(
                    intent_id
                )
            )
        )

    return {
        "purchased": True,
        "founder_account": founder,
        "listing": locked_listing,
        "buyer_root": buyer_root,
        "seller_root": seller_root,
        "sale_price_credits": sale_price,
        "ledger_record": ledger_record,
    }
