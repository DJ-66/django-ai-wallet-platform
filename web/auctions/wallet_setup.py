import os
import qrcode
import secrets
import string
from django.conf import settings

from .models import BidWallet, WalletTransaction

SIGNUP_BONUS = 50
REFERRAL_BONUS = 50

def generate_referral_code(length=10):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

def provision_user_wallet(user, referral_code=None):

    wallet, _ = BidWallet.objects.get_or_create(user=user)

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

            referrer_wallet.credits += REFERRAL_BONUS
            referrer_wallet.save(update_fields=["credits"])

            WalletTransaction.objects.create(
                receiver=referrer_wallet,
                amount=REFERRAL_BONUS,
                transaction_type="commission",
                reference=f"Referral signup: {user.username}",
            )

    wallet.save()

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

    return wallet



