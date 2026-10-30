"""Database-backed localization of prepared FANZ AI publications."""

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from auctions.models import FeedPost, ScheduledPublication
from auctions.post_localization import localize_feed_post
from auctions.ai_services.legacy_publication_preparation import (
    plan_publication_ending,
)
from auctions.ai_services.legacy_cta_localization import (
    append_approved_localized_cta,
)


class PreparedAILocalizationTests(TestCase):

    def test_founder_cta_localizes_and_preserves_translations(self):
        user = get_user_model().objects.create_user(
            username="LocalizedFounderTest",
            password="test-only-password",
        )

        plan = plan_publication_ending(
            username=user.username,
            publication_key="ai:localizedfounder:fourth",
            sequence=4,
        )

        english = append_approved_localized_cta(
            content="A little adventure today.\n\n#Fashion #FANZ",
            plan=plan,
            language="en",
        )

        post = FeedPost.objects.create(
            user=user,
            title="A little adventure",
            content=english,
            is_public=True,
        )

        for number in (1, 2, 3):
            ScheduledPublication.objects.create(
                publication_key=f"ai:localizedfounder:history-{number}",
                creator=user,
                source_path=f"history/{number}.jpg",
                scheduled_for=timezone.now(),
                status=ScheduledPublication.STATUS_QUEUED,
            )

        ScheduledPublication.objects.create(
            publication_key="ai:localizedfounder:fourth",
            creator=user,
            source_path="creator/fourth.jpg",
            campaign_key="ai_founder",
            content=english,
            scheduled_for=timezone.now(),
            status=ScheduledPublication.STATUS_PUBLISHED,
            feed_post=post,
            published_at=timezone.now(),
        )

        def translate(post, *, target_language, **kwargs):
            content = (
                "Una pequeña aventura.\n\n#Fashion #FANZ"
                if target_language == "es"
                else "Uma pequena aventura.\n\n#Fashion #FANZ"
            )
            return {
                "title": "Localized adventure",
                "content": content,
            }

        with (
            patch(
                "auctions.post_localization._resolve_source_language",
                return_value="en",
            ),
            patch(
                "auctions.ai_services.legacy_multilingual_translation."
                "_translate_target",
                side_effect=translate,
            ),
            patch.dict(
                "os.environ",
                {"FANZ_LEGACY_AI_SUFFIX_ENABLED": "true"},
            ),
        ):
            result = localize_feed_post(
                post,
                provider=SimpleNamespace(),
            )

        self.assertEqual(result["status"], "localized")

        translations = {
            row.language: row
            for row in post.translations.all()
        }

        self.assertEqual(set(translations), {"en", "es", "pt"})

        for language in ("es", "pt"):
            content = translations[language].content

            self.assertIn(
                plan.suffix.translations[language],
                content,
            )
            self.assertEqual(
                content.count(plan.destination.url),
                1,
            )
            self.assertTrue(
                content.endswith("#Fashion #FANZ")
            )

        original_spanish = translations["es"].content

        with patch(
            "auctions.post_localization._resolve_source_language",
            return_value="en",
        ):
            second = localize_feed_post(
                post,
                provider=SimpleNamespace(),
            )

        self.assertEqual(second["status"], "complete")

        translations["es"].refresh_from_db()
        self.assertEqual(
            translations["es"].content,
            original_spanish,
        )

    def test_founder_localizes_with_feature_disabled(self):
        user = get_user_model().objects.create_user(
            username="LocalizedFounderTest",
            password="test-only-password",
        )

        plan = plan_publication_ending(
            username=user.username,
            publication_key="ai:localizedfounder:fourth",
            sequence=4,
        )

        english = append_approved_localized_cta(
            content="A little adventure today.\n\n#Fashion #FANZ",
            plan=plan,
            language="en",
        )

        post = FeedPost.objects.create(
            user=user,
            title="A little adventure",
            content=english,
            is_public=True,
        )

        for number in (1, 2, 3):
            ScheduledPublication.objects.create(
                publication_key=f"ai:localizedfounder:history-{number}",
                creator=user,
                source_path=f"history/{number}.jpg",
                scheduled_for=timezone.now(),
                status=ScheduledPublication.STATUS_QUEUED,
            )

        ScheduledPublication.objects.create(
            publication_key="ai:localizedfounder:fourth",
            creator=user,
            source_path="creator/fourth.jpg",
            campaign_key="ai_founder",
            content=english,
            scheduled_for=timezone.now(),
            status=ScheduledPublication.STATUS_PUBLISHED,
            feed_post=post,
            published_at=timezone.now(),
        )

        def translate(post, *, target_language, **kwargs):
            content = (
                "Una pequeña aventura.\n\n#Fashion #FANZ"
                if target_language == "es"
                else "Uma pequena aventura.\n\n#Fashion #FANZ"
            )
            return {
                "title": "Localized adventure",
                "content": content,
            }

        with (
            patch(
                "auctions.post_localization._resolve_source_language",
                return_value="en",
            ),
            patch(
                "auctions.ai_services.legacy_multilingual_translation."
                "_translate_target",
                side_effect=translate,
            ),
            patch.dict(
                "os.environ",
                {"FANZ_LEGACY_AI_SUFFIX_ENABLED": "false"},
            ),
        ):
            result = localize_feed_post(
                post,
                provider=SimpleNamespace(),
            )

        self.assertEqual(result["status"], "localized")

        translations = {
            row.language: row
            for row in post.translations.all()
        }

        self.assertEqual(set(translations), {"en", "es", "pt"})

        for language in ("es", "pt"):
            content = translations[language].content

            self.assertIn(
                plan.suffix.translations[language],
                content,
            )
            self.assertEqual(
                content.count(plan.destination.url),
                1,
            )
            self.assertTrue(
                content.endswith("#Fashion #FANZ")
            )

        original_spanish = translations["es"].content

        with patch(
            "auctions.post_localization._resolve_source_language",
            return_value="en",
        ):
            second = localize_feed_post(
                post,
                provider=SimpleNamespace(),
            )

        self.assertEqual(second["status"], "complete")

        translations["es"].refresh_from_db()
        self.assertEqual(
            translations["es"].content,
            original_spanish,
        )


class AdditionalPreparedAILocalizationTests(TestCase):
    """Verify remaining prepared AI publication types."""

    def _make_publication(self, *, campaign, sequence):
        from auctions.models import FeedPostTranslation

        username = f"Localized{campaign.title()}Test"

        user = get_user_model().objects.create_user(
            username=username,
            password="test-only-password",
        )

        key = f"ai:{campaign}:prepared"

        plan = plan_publication_ending(
            username=username,
            publication_key=key,
            sequence=sequence,
        )

        base = "A little adventure today.\n\n#Fashion #FANZ"

        if campaign == "gemma4":
            content = (
                "A little adventure today.\n"
                "Tell me your favorite story in my DMs."
                "\n\n#Fashion #FANZ"
            )
        else:
            content = append_approved_localized_cta(
                content=base,
                plan=plan,
                language="en",
            )

        post = FeedPost.objects.create(
            user=user,
            title="A little adventure",
            content=content,
            is_public=True,
        )

        for number in range(1, sequence):
            ScheduledPublication.objects.create(
                publication_key=f"ai:{campaign}:history-{number}",
                creator=user,
                source_path=f"history/{number}.jpg",
                scheduled_for=timezone.now(),
                status=ScheduledPublication.STATUS_QUEUED,
            )

        ScheduledPublication.objects.create(
            publication_key=key,
            creator=user,
            source_path="creator/prepared.jpg",
            campaign_key=f"ai_{campaign}",
            content=content,
            scheduled_for=timezone.now(),
            status=ScheduledPublication.STATUS_PUBLISHED,
            feed_post=post,
            published_at=timezone.now(),
        )

        return post, plan

    def test_credits_and_autopost_localization(self):
        for campaign, sequence in (
            ("credits", 8),
            ("autopost", 12),
        ):
            with self.subTest(campaign=campaign):
                post, plan = self._make_publication(
                    campaign=campaign,
                    sequence=sequence,
                )

                def translate(post, *, target_language, **kwargs):
                    return {
                        "title": "Localized adventure",
                        "content": (
                            "Una pequeña aventura.\n\n#Fashion #FANZ"
                            if target_language == "es"
                            else "Uma pequena aventura.\n\n#Fashion #FANZ"
                        ),
                    }

                with (
                    patch(
                        "auctions.post_localization."
                        "_resolve_source_language",
                        return_value="en",
                    ),
                    patch(
                        "auctions.ai_services."
                        "legacy_multilingual_translation."
                        "_translate_target",
                        side_effect=translate,
                    ),
                    patch.dict(
                        "os.environ",
                        {"FANZ_LEGACY_AI_SUFFIX_ENABLED": "true"},
                    ),
                ):
                    result = localize_feed_post(
                        post,
                        provider=SimpleNamespace(),
                    )

                self.assertEqual(result["status"], "localized")

                rows = {
                    row.language: row
                    for row in post.translations.all()
                }

                self.assertEqual(set(rows), {"en", "es", "pt"})

                for language in ("es", "pt"):
                    self.assertIn(
                        plan.suffix.translations[language],
                        rows[language].content,
                    )
                    self.assertEqual(
                        rows[language].content.count(
                            plan.destination.url
                        ),
                        1,
                    )

    def test_gemma_creative_ending_localizes_naturally(self):
        post, _plan = self._make_publication(
            campaign="gemma4",
            sequence=1,
        )

        original_ending = (
            "Tell me your favorite story in my DMs."
        )

        translated_endings = {
            "es": "Cuéntame tu historia favorita por mensaje.",
            "pt": "Conta-me a tua história favorita por mensagem.",
        }

        def translate(post, *, target_language, **kwargs):
            return {
                "title": "Localized adventure",
                "content": (
                    "Una pequeña aventura.\n"
                    + translated_endings["es"]
                    + "\n\n#Fashion #FANZ"
                    if target_language == "es"
                    else "Uma pequena aventura.\n"
                    + translated_endings["pt"]
                    + "\n\n#Fashion #FANZ"
                ),
            }

        with (
            patch(
                "auctions.post_localization."
                "_resolve_source_language",
                return_value="en",
            ),
            patch(
                "auctions.post_localization._translate_target",
                side_effect=translate,
            ) as translator,
            patch.dict(
                "os.environ",
                {"FANZ_LEGACY_AI_SUFFIX_ENABLED": "true"},
            ),
        ):
            result = localize_feed_post(
                post,
                provider=SimpleNamespace(),
            )

        self.assertEqual(result["status"], "localized")
        self.assertEqual(translator.call_count, 2)

        rows = {
            row.language: row
            for row in post.translations.all()
        }

        self.assertEqual(set(rows), {"en", "es", "pt"})
        self.assertIn(original_ending, rows["en"].content)

        for language in ("es", "pt"):
            self.assertIn(
                translated_endings[language],
                rows[language].content,
            )
            self.assertNotIn(
                original_ending,
                rows[language].content,
            )
            self.assertTrue(
                rows[language].content.endswith("#Fashion #FANZ")
            )
