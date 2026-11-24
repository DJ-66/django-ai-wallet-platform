"""Regression tests for SunsetCam marketing campaigns."""

from collections import Counter
from unittest import TestCase

from auctions.sunsetcam_cta import (
    CAMPAIGN_ORDER,
    COPY,
    DESTINATIONS,
    LABELS,
    LANGUAGES,
    decorate_sunsetcam_caption,
    select_campaign,
)


class SunsetCamCTATests(TestCase):

    def test_campaign_rotation(self):
        actual = [
            select_campaign(number)[0]
            for number in range(1, 13)
        ]
        self.assertEqual(actual, list(CAMPAIGN_ORDER) * 4)

    def test_balanced_distribution(self):
        counts = Counter(
            select_campaign(number)[0]
            for number in range(1, 1201)
        )
        self.assertEqual(
            counts,
            {
                "business": 400,
                "identity": 400,
                "real_estate": 400,
            },
        )

    def test_all_variants_selected(self):
        selections = {
            select_campaign(number)
            for number in range(1, 13)
        }
        self.assertEqual(len(selections), 12)

    def test_rotation_repeats(self):
        for number in range(1, 100):
            self.assertEqual(
                select_campaign(number),
                select_campaign(number + 12),
            )

    def test_invalid_capture_numbers(self):
        for number in (0, -1, None, True, "1", 1.5):
            with self.subTest(number=number):
                with self.assertRaises(ValueError):
                    select_campaign(number)

    def test_complete_localization(self):
        for campaign in CAMPAIGN_ORDER:
            self.assertEqual(
                set(LABELS[campaign]),
                set(LANGUAGES),
            )
            for variant in COPY[campaign]:
                self.assertEqual(
                    set(variant),
                    set(LANGUAGES),
                )
                for message in variant.values():
                    self.assertTrue(message.strip())

    def test_all_localized_captions(self):
        caption = "Original SunsetCam caption. ❤️"
        tags = (
            "#SunsetCam #MorningCam #Encarnacion "
            "#ParanaRiver #Paraguay #MorningView "
            "#LiveSunsetCam"
        )
        original = caption + "\n\n" + tags

        for number in range(1, 13):
            campaign, variant = select_campaign(number)

            for language in LANGUAGES:
                with self.subTest(
                    number=number,
                    language=language,
                ):
                    result = decorate_sunsetcam_caption(
                        content=original,
                        language=language,
                        capture_number=number,
                    )

                    link = (
                        f"[{LABELS[campaign][language]}]"
                        f"({DESTINATIONS[campaign]})"
                    )

                    expected = "\n\n".join([
                        caption,
                        COPY[campaign][variant][language],
                        link,
                        tags,
                    ])

                    self.assertEqual(result, expected)
                    self.assertEqual(result.count(link), 1)
                    self.assertEqual(
                        result.rsplit("\n\n", 1)[1],
                        tags,
                    )
                    self.assertLessEqual(len(result), 2500)

    def test_deterministic_retry(self):
        kwargs = {
            "content": "Original caption\n\n#SunsetCam",
            "language": "en",
            "capture_number": 490,
        }
        self.assertEqual(
            decorate_sunsetcam_caption(**kwargs),
            decorate_sunsetcam_caption(**kwargs),
        )

    def test_duplicate_decoration_rejected(self):
        for number in range(1, 13):
            for language in LANGUAGES:
                decorated = decorate_sunsetcam_caption(
                    content="Original caption\n\n#SunsetCam",
                    language=language,
                    capture_number=number,
                )
                with self.assertRaises(ValueError):
                    decorate_sunsetcam_caption(
                        content=decorated,
                        language=language,
                        capture_number=number,
                    )

    def test_invalid_captions_rejected(self):
        for content in (
            None,
            "",
            "No hashtag separator",
            "\n\n#SunsetCam",
            "Caption\n\n",
            "Caption\n\nNot hashtags",
        ):
            with self.subTest(content=content):
                with self.assertRaises(ValueError):
                    decorate_sunsetcam_caption(
                        content=content,
                        language="en",
                        capture_number=1,
                    )

    def test_unsupported_language(self):
        with self.assertRaises(ValueError):
            decorate_sunsetcam_caption(
                content="Caption\n\n#SunsetCam",
                language="fr",
                capture_number=1,
            )

    def test_content_limit(self):
        with self.assertRaises(ValueError):
            decorate_sunsetcam_caption(
                content="A" * 2500 + "\n\n#SunsetCam",
                language="en",
                capture_number=1,
            )

    def test_approved_destinations(self):
        self.assertEqual(
            DESTINATIONS,
            {
                "business": "/b/create/",
                "identity": "/founder/tienda/",
                "real_estate": "/founder/tienda/",
            },
        )
