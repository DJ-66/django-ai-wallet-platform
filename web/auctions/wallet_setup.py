import os
import logging
import qrcode
import secrets
import string
from django.conf import settings
from django.db import transaction
from django.db.models import F
from .qr_utils import make_branded_referral_qr
from .models import BidWallet, WalletTransaction
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.translation import gettext as _, override


logger = logging.getLogger(__name__)

SIGNUP_BONUS = 50
REFERRAL_BONUS = 50

def generate_referral_code(length=10):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

def send_welcome_email(user, language="en"):
    if not user.email:
        return

    language = str(language).lower().split("-")[0]

    if language not in ("en", "es", "pt"):
        language = "en"

    with override(language):
        subject = _(
            "🎉 Welcome to FANZ — Your 50 FREE Credits Are Ready"
        )

        html_content = render_to_string(
            "auctions/welcome_email.html",
            {
                "user": user,
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

    email.send(fail_silently=True)

@transaction.atomic
def provision_user_wallet(
    user,
    referral_code=None,
    language="en",
):

    # Ensure the wallet exists before locking it.
    wallet, _ = BidWallet.objects.get_or_create(user=user)

    wallet = (
        BidWallet.objects
        .select_for_update()
        .get(pk=wallet.pk)
    )

    # ---------------------------------------------------
    # WALLET CODE
    # ---------------------------------------------------
    if not wallet.wallet_code:
        wallet.wallet_code = generate_referral_code()

    # ---------------------------------------------------
    # PAY CODE
    # ---------------------------------------------------
    if not wallet.pay_code:
        wallet.pay_code = generate_referral_code()

    # ---------------------------------------------------
    # REFERRAL CODE
    # ---------------------------------------------------
    if not wallet.referral_code:
        wallet.referral_code = generate_referral_code()

    # ---------------------------------------------------
    # SIGNUP BONUS
    # ---------------------------------------------------
    if not wallet.signup_bonus_given:

        wallet.credits += SIGNUP_BONUS
        wallet.signup_bonus_given = True

        WalletTransaction.objects.create(
            receiver=wallet,
            amount=SIGNUP_BONUS,
            transaction_type="bonus",
            reference="Signup bonus",
        )

        def send_welcome_after_commit():
            try:
                send_welcome_email(user, language=language)
            except Exception:
                logger.exception(
                    "FANZ welcome email failed for user_id=%s",
                    user.pk,
                )

        transaction.on_commit(send_welcome_after_commit)

    # ---------------------------------------------------
    # REFERRAL BONUS
    # ---------------------------------------------------
    if referral_code and not wallet.referred_by:

        referrer_wallet = (
            BidWallet.objects
            .filter(referral_code=referral_code)
            .first()
        )

        if referrer_wallet and referrer_wallet.user != user:

            wallet.referred_by = referrer_wallet.user
            wallet.referral_bonus_given = True

            BidWallet.objects.filter(
                pk=referrer_wallet.pk,
            ).update(
                credits=F("credits") + REFERRAL_BONUS,
            )

            WalletTransaction.objects.create(
                receiver=referrer_wallet,
                amount=REFERRAL_BONUS,
                transaction_type="commission",
                reference=f"Referral signup: {user.username}",
            )

    wallet.save()

    wallet_code = str(wallet.wallet_code)
    pay_code = wallet.pay_code
    generated_referral_code = wallet.referral_code

    def generate_qr_after_commit():
        try:
            _generate_wallet_qr_codes(
                wallet_code,
                pay_code,
                generated_referral_code,
            )
        except Exception:
            logger.exception(
                "FANZ wallet QR generation failed for user_id=%s",
                user.pk,
            )

    transaction.on_commit(generate_qr_after_commit)

    return wallet





def _generate_wallet_qr_codes(wallet_code, pay_code, referral_code):
    # ---------------------------------------------------
    # WALLET QR
    # ---------------------------------------------------
    qr_path = os.path.join(settings.MEDIA_ROOT, "qr_codes", f"{wallet_code}.png")

    if not os.path.exists(qr_path):

        payment_url = (
            f"https://fanz.to/auctions/pay/"
            f"{pay_code}/"
        )

        img = qrcode.make(payment_url)

        os.makedirs(os.path.dirname(qr_path), exist_ok=True)

        img.save(qr_path)

    # ---------------------------------------------------
    # REFERRAL QR
    # ---------------------------------------------------
    ref_qr_path = os.path.join(settings.MEDIA_ROOT, "qr_codes", f"ref_{referral_code}.png")

    if not os.path.exists(ref_qr_path):

        referral_url = (
            "https://fanz.to/auctions/signup/"
            f"?ref={referral_code}"
        )

        img = make_branded_referral_qr(referral_url)

        os.makedirs(os.path.dirname(ref_qr_path), exist_ok=True)

        img.save(ref_qr_path)

