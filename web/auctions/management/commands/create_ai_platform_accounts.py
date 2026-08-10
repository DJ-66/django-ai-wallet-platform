from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from auctions.models import UserProfile


AI_PLATFORM_ACCOUNTS = [
    "Suzy",
    "Mary",
    "Clara",
    "Coquette",
    "Bikini",
    "Alana",
    "Claire",
    "Jaana",
    "Emilia",
    "Fay",
    "Mika",
    "Hazel",
    "Jemma",
    "Evelyn",
    "Kat",
    "Kayla",
    "Kendal",
    "Kira",
    "Livia",
    "Lizzy",
    "Mandi",
    "Maya",
    "Mia",
    "Molly",
    "Natalia",
    "Lola",
    "Nyra",
    "Peg",
    "Jenny",
    "Ruby",
    "Scarlett",
    "Skye",
    "Vale",
    "Vespa",
    "Yara",
    "Yuna",
    "Sophie",
    "Luxe",
    "Kim",
    "Rosa",
    "Tamaia",
    "Sika",
    "Nyla",
    "Elara",
    "Giorgina",
    "Jessica",
    "Lan",
    "Reina",
    "Manon",
]


class Command(BaseCommand):
    help = "Create or verify FANZ AI platform creator accounts."

    def handle(self, *args, **options):
        created_count = 0
        existing_count = 0

        for username in AI_PLATFORM_ACCOUNTS:
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
                        f"EXISTS: @{user.username} "
                        f"platform={profile.is_platform_account} "
                        f"ai={profile.is_ai_influencer}"
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

            profile.display_name = username
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
