from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from auctions.models import UserProfile


PLATFORM_ACCOUNTS = [
    ("Fanz", "FANZ"),
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

            if user:
                existing_count += 1

                profile, _ = UserProfile.objects.get_or_create(
                    user=user
                )

                self.stdout.write(
                    self.style.WARNING(
                        f"EXISTS: @{user.username}"
                    )
                )

                continue

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

            created_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"CREATED: @{username}"
                )
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
