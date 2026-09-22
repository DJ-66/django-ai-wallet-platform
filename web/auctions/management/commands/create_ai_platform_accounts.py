import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from auctions.models import BidWallet, UserProfile


User = get_user_model()

MANIFEST_PATH = (
    Path(settings.BASE_DIR)
    / "auctions"
    / "data"
    / "ai_creator_media_manifest.json"
)


class Command(BaseCommand):
    help = (
        "Create or verify FANZ AI creator accounts from the "
        "canonical AI creator media manifest."
    )

    def handle(self, *args, **options):
        manifest = json.loads(
            MANIFEST_PATH.read_text()
        )

        creators = manifest["creators"]

        created_count = 0
        existing_count = 0
        wallet_created_count = 0

        with transaction.atomic():

            for creator in creators:
                username = creator["account"]
                display_name = creator["display_name"]

                user = (
                    User.objects
                    .filter(username__iexact=username)
                    .first()
                )

                if user is None:
                    user = User(
                        username=username,
                        email=(
                            f"{username.lower()}"
                            "@platform.invalid"
                        ),
                        is_active=True,
                        is_staff=False,
                        is_superuser=False,
                    )

                    user.set_unusable_password()
                    user.save()

                    created_count += 1
                    user_state = "CREATED"
                else:
                    existing_count += 1
                    user_state = "EXISTS"

                profile, _ = (
                    UserProfile.objects.get_or_create(
                        user=user
                    )
                )

                profile.display_name = display_name
                profile.is_platform_account = True
                profile.is_official = True
                profile.is_ai_influencer = True
                profile.is_ai_creator = True

                profile.save(
                    update_fields=[
                        "display_name",
                        "is_platform_account",
                        "is_official",
                        "is_ai_influencer",
                        "is_ai_creator",
                    ]
                )

                wallet, wallet_created = (
                    BidWallet.objects.get_or_create(
                        user=user
                    )
                )

                if wallet_created:
                    wallet_created_count += 1

                self.stdout.write(
                    f"{user_state:<8} "
                    f"@{user.username:<20} "
                    f"| display={profile.display_name!r} "
                    f"| wallet={wallet.pk} "
                    f"| wallet_created={wallet_created}"
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Manifest creators: {len(creators)}"
            )
        )
        self.stdout.write(
            f"Created users: {created_count}"
        )
        self.stdout.write(
            f"Existing users: {existing_count}"
        )
        self.stdout.write(
            f"Created wallets: {wallet_created_count}"
        )
