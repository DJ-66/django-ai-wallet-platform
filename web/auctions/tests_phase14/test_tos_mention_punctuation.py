"""Protected mention punctuation regression tests."""

from django.test import SimpleTestCase

from auctions.post_localization import (
    PostLocalizationError,
    _mask_protected_tokens,
    _protected_tokens,
    _validate_preserved_tokens,
)


class TOSMentionPunctuationTests(SimpleTestCase):
    def test_sentence_period_is_not_part_of_mention(self):
        source = "Read the rules from @TOS"
        translated = "Lea las reglas de @TOS."

        self.assertEqual(
            _protected_tokens(source)["mentions"],
            ["@TOS"],
        )
        self.assertEqual(
            _protected_tokens(translated)["mentions"],
            ["@TOS"],
        )

        _validate_preserved_tokens(
            source, translated, language="es"
        )

    def test_internal_username_period_is_preserved(self):
        self.assertEqual(
            _protected_tokens("Hello @john.doe.")["mentions"],
            ["@john.doe"],
        )

    def test_changed_username_is_rejected(self):
        with self.assertRaises(PostLocalizationError):
            _validate_preserved_tokens(
                "Hello @TOS",
                "Hola @TOS2.",
                language="es",
            )

    def test_masking_preserves_sentence_period(self):
        masked, tokens = _mask_protected_tokens(
            "Read @TOS."
        )

        self.assertEqual(tokens, ["@TOS"])
        self.assertTrue(masked.endswith("END."))
