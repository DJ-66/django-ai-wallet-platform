from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files import File
from django.core.management.base import BaseCommand

from auctions.models import UserProfile


PLATFORM_ACCOUNTS = [
    ("Fanz", "FANZ"),
    ("BuyCredits", "Buy FANZ Credits"),
    ("News", "FANZ News"),
    ("AI", "FANZ AI"),
    ("Yoga", "FANZ Yoga"),

    ("Auctions", "FANZ Auctions"),
    ("Discover", "FANZ Discover"),
    ("Events", "FANZ Events"),
    ("Live", "FANZ Live"),
    ("Shop", "FANZ Shop"),
    ("Deals", "FANZ Deals"),
    ("Advertise", "FANZ Advertise"),

    ("Sports", "FANZ Sports"),
    ("Music", "FANZ Music"),
    ("Audio", "FANZ Audio"),
    ("Movies", "FANZ Movies"),
    ("Books", "FANZ Books"),
    ("Ebook", "FANZ eBooks"),
    ("Author", "FANZ Authors"),
    ("Art", "FANZ Art"),
    ("Fashion", "FANZ Fashion"),
    ("Games", "FANZ Games"),
    ("Horror", "FANZ Horror"),

    ("Travel", "FANZ Travel"),
    ("Beach", "FANZ Beach"),
    ("BeachYoga", "FANZ Beach Yoga"),
    ("DigitalNomad", "FANZ Digital Nomads"),
    ("Dating", "FANZ Dating"),

    ("Food", "FANZ Food"),
    ("Coffee", "FANZ Coffee"),
    ("Pizza", "FANZ Pizza"),

    ("Tech", "FANZ Tech"),
    ("Python", "FANZ Python"),
    ("Blockchain", "FANZ Blockchain"),
    ("Bitcoin", "FANZ Bitcoin"),
    ("Dogecoin", "FANZ Dogecoin"),
    ("Monero", "FANZ Monero"),
    ("Memecoin", "FANZ Memecoins"),
    ("Crypto", "FANZ Crypto"),

    ("Fitness", "FANZ Fitness"),
    ("Meditation", "FANZ Meditation"),

    ("Jobs", "FANZ Jobs"),
    ("Freelance", "FANZ Freelance"),
    ("Influencer", "FANZ Influencers"),

    ("Local", "FANZ Local"),
    ("Encarnacion", "FANZ Encarnacion"),

    ("WatchParty", "FANZ Watch Parties"),
]


class Command(BaseCommand):
    help = "Create or verify FANZ platform accounts."

    def handle(self, *args, **options):
        created_count = 0
        existing_count = 0

        for username, display_name in PLATFORM_ACCOUNTS:
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

                self.stdout.write(
                    self.style.SUCCESS(
                        f"CREATED: @{username}"
                    )
                )
            else:
                existing_count += 1

                self.stdout.write(
                    self.style.WARNING(
                        f"EXISTS: @{user.username}"
                    )
                )

            profile, _ = (
                UserProfile.objects.get_or_create(
                    user=user
                )
            )

            profile.display_name = display_name
            profile.is_platform_account = True
            profile.is_official = True
            profile.is_verified = True

            update_fields = [
                "display_name",
                "is_platform_account",
                "is_official",
                "is_verified",
            ]

            if username.lower() == "buycredits":
                profile.bio = (
                    "Official FANZ Credits storefront. "
                    "Buy FANZ Credit packages using "
                    "BTC, SUI, or DOGE. "
                    "Current packages and promotions "
                    "are published here."
                )

                update_fields.append("bio")

                avatar_source = (
                    Path(settings.BASE_DIR)
                    / "static"
                    / "img"
                    / "platform"
                    / "buycredits-avatar.png"
                )

                avatar_name = (
                    "avatars/"
                    "buycredits-avatar.png"
                )

                if not avatar_source.exists():
                    raise RuntimeError(
                        "Canonical BuyCredits avatar "
                        f"not found: {avatar_source}"
                    )

                storage = profile.avatar.storage

                if not storage.exists(
                    avatar_name
                ):
                    with avatar_source.open("rb") as fh:
                        storage.save(
                            avatar_name,
                            File(fh),
                        )

                profile.avatar.name = avatar_name
                update_fields.append("avatar")

            profile.save(
                update_fields=update_fields
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Created: {created_count}"
            )
        )
        self.stdout.write(
            f"Already existed: {existing_count}"
        )
