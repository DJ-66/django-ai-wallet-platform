"""WP03.3.2 legacy Founder recognition regression tests."""

from types import SimpleNamespace as NS

from django.test import SimpleTestCase

from auctions.ai_services.cta_links import campaign_link
from auctions.ai_services.legacy_publication_preparation import (
    plan_v2_publication_ending,
)
from auctions.legacy_marketing_presentation import (
    recognize_legacy_founder_marketing,
)


class LegacyFounderRecognitionTests(SimpleTestCase):

    caption = "Hello @Mia and @DJ."
    hashtags = "#Creator #FANZ"
    destination = "/auctions/founder/tienda/"

    def fixture(self, token="name"):
        for index in range(1000):
            username = f"Creator{index}"
            key = f"ai:wp0332:{index}"

            plan = plan_v2_publication_ending(
                username=username,
                publication_key=key,
                sequence=1,
            )

            if (
                plan.kind == "cta"
                and plan.suffix.campaign == "founder"
                and f"@{token}" in plan.suffix.translations["en"]
            ):
                break
        else:
            self.fail("Unable to construct deterministic fixture")

        closer = (
            "↳ 💋❤️😘 "
            + plan.suffix.translations["en"]
            + " XOXO 💕"
        )

        cta = campaign_link("founder", plan.destination)

        body = (
            self.caption + "\n\n"
            + closer + "\n\n" + cta
        )

        content = body + "\n\n" + self.hashtags

        post = NS(
            pk=100,
            user_id=200,
            is_paid=False,
            is_public=True,
            content=content,
            user=NS(
                username=username,
                profile=NS(is_platform_account=True),
            ),
        )

        publication = NS(
            status="published",
            campaign_key="ai_v2_founder",
            publication_key=key,
            feed_post_id=post.pk,
            creator_id=post.user_id,
            media_asset_id=None,
            content=content,
        )

        return post, publication, body, plan

    def recognize(self, post, publication, body):
        return recognize_legacy_founder_marketing(
            post=post,
            publication=publication,
            body=body,
        )

    def localized_body(self, closer, label="Comprar tu nombre"):
        return (
            self.caption + "\n\n"
            + closer + "\n\n"
            + f"[{label}]({self.destination})"
        )

    def test_canonical_founder_tokens(self):
        for token in ("name", "biz"):
            with self.subTest(token=token):
                post, pub, body, _ = self.fixture(token)

                result = self.recognize(post, pub, body)

                self.assertIsNotNone(result)
                self.assertEqual(result.caption, self.caption)
                self.assertEqual(result.promotional_token, token)
                self.assertEqual(
                    result.caption + "\n\n" + result.suffix,
                    body,
                )

    def test_historical_localized_variants(self):
        cases = (
            ("name", "↳ 💋❤️😘 Reclama tu @name. 👑 XOXO 💕"),
            ("name", "↳ 💋❤️😘 Garanta seu @name. 😘 XOXO 💕"),
            ("name", " RedirectTo 💋❤️😘 Tu @name. XOXO 💕"),
            ("name", " RedirectTo: 💋❤️😘 Tu @name. XOXO 💕"),
            ("name", "↳ 💋❤️😘 Tu @name. Cariñosamente, 😕"),
            ("name", "↳ 💋❤️😘 ¿Tu @name还在 disponible? 🙄 XOXO 💕"),
            ("biz", "➡️ 💋❤️😘 Apropiáte de tu @biz. 🔥 XOXO 💕"),
            ("biz", "↳ 💋❤️😘❝Owned your @biz.❞ XOXO 💕"),
            ("biz", "↳ 💋❤️😘 Adquira o seu @biz. 🔥 XOXO 💕"),
        )

        for token, closer in cases:
            with self.subTest(token=token, closer=closer):
                post, pub, _, _ = self.fixture(token)
                body = self.localized_body(closer)

                result = self.recognize(post, pub, body)

                self.assertIsNotNone(result)
                self.assertEqual(result.promotional_token, token)
                self.assertEqual(
                    result.caption + "\n\n" + result.suffix,
                    body,
                )

    def test_authorization_rejections(self):
        cases = (
            ("post", "is_paid", True),
            ("post", "is_public", False),
            ("post", "content", "Edited canonical content"),
            ("publication", "status", "queued"),
            ("publication", "campaign_key", "ai_v2_credits"),
            ("publication", "publication_key", "manual:100"),
            ("publication", "feed_post_id", 999),
            ("publication", "creator_id", 999),
            ("publication", "media_asset_id", 999),
            ("publication", "content", "Changed snapshot"),
        )

        for target, field, value in cases:
            with self.subTest(target=target, field=field):
                post, pub, body, _ = self.fixture()

                setattr(
                    post if target == "post" else pub,
                    field,
                    value,
                )

                self.assertIsNone(
                    self.recognize(post, pub, body)
                )

    def test_missing_publication(self):
        post, _, body, _ = self.fixture()
        self.assertIsNone(
            self.recognize(post, None, body)
        )

    def test_non_platform_owner(self):
        post, pub, body, _ = self.fixture()
        post.user.profile.is_platform_account = False

        self.assertIsNone(
            self.recognize(post, pub, body)
        )

    def test_missing_profile(self):
        post, pub, body, _ = self.fixture()
        del post.user.profile

        self.assertIsNone(
            self.recognize(post, pub, body)
        )

    def test_malformed_suffix_falls_back(self):
        post, pub, body, _ = self.fixture()

        cases = (
            body + "\n\n---\n\nAI commentary.",
            body.replace(self.destination, "https://example.com"),
            body.replace(self.destination, "/founder/tienda/"),
            body.replace("↳ 💋❤️😘 ", ""),
            body.replace("@name", "@name_extra"),
            body.replace("@name", "@biz"),
            body.replace("@name", "@name @name"),
            body.replace("@name", "@name @biz"),
        )

        for candidate in cases:
            with self.subTest(candidate=candidate):
                self.assertIsNone(
                    self.recognize(post, pub, candidate)
                )

    def test_matching_snapshot_alone_is_insufficient(self):
        post, pub, body, _ = self.fixture()

        post.content = post.content.replace(
            "@name", "@name edited"
        )
        pub.content = post.content

        self.assertIsNone(
            self.recognize(post, pub, body)
        )

    def test_unrelated_mentions_are_retained_for_renderer(self):
        post, pub, _, _ = self.fixture()

        body = self.localized_body(
            "↳ 💋❤️😘 Reclama tu @name. Hello @Mia. XOXO 💕"
        )

        result = self.recognize(post, pub, body)

        self.assertIsNotNone(result)
        self.assertIn("@Mia", result.suffix)
        self.assertIn("@DJ", result.caption)
        self.assertEqual(result.promotional_token, "name")

    def test_v2_selection_is_sequence_independent(self):
        for token in ("name", "biz"):
            post, pub, _, expected = self.fixture(token)

            for sequence in (1, 2, 4, 17, 100, 1000):
                with self.subTest(token=token, sequence=sequence):
                    actual = plan_v2_publication_ending(
                        username=post.user.username,
                        publication_key=pub.publication_key,
                        sequence=sequence,
                    )

                    self.assertEqual(actual.kind, expected.kind)
                    self.assertEqual(actual.personality, expected.personality)
                    self.assertEqual(actual.suffix, expected.suffix)
                    self.assertEqual(actual.destination, expected.destination)
