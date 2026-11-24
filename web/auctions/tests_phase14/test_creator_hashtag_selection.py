import random
import unittest

from auctions.ai_services.creator_hashtag_selection import (
    split_creator_hashtag_pool,
)


class CreatorHashtagSelectionTests(unittest.TestCase):

    POOL = [
        "AIInfluencer", "DigitalCreator", "Yoga",
        "Fitness", "Lifestyle", "Wellness",
        "Balance", "Movement", "Photography",
        "Flexibility", "Strength", "Mindfulness",
    ]

    def test_legacy_and_expanded_pools(self):
        for size in (6, 12):
            with self.subTest(size=size):
                pool = self.POOL[:size]

                rotating, approved = split_creator_hashtag_pool(
                    pool, rng=random.Random(42)
                )

                self.assertIn(rotating, pool)
                self.assertNotIn(rotating, approved)
                self.assertEqual(len(approved), size - 1)
                self.assertEqual(
                    set([rotating] + approved), set(pool)
                )

    def test_exactly_six_final_hashtags(self):
        for seed in range(100):
            rng = random.Random(seed)

            rotating, approved = split_creator_hashtag_pool(
                self.POOL, rng=rng
            )

            published = rng.sample(approved, 4)
            published += [rotating, "FANZ"]

            self.assertEqual(len(published), 6)
            self.assertEqual(
                len({tag.lower() for tag in published}), 6
            )
            self.assertEqual(published[-1], "FANZ")

    def test_no_mandatory_generic_identity(self):
        observed = {
            split_creator_hashtag_pool(
                self.POOL, rng=random.Random(seed)
            )[0]
            for seed in range(100)
        }

        self.assertEqual(observed, set(self.POOL))

    def test_case_insensitive_duplicates_rejected(self):
        with self.assertRaises(ValueError):
            split_creator_hashtag_pool(
                self.POOL + ["yoga"]
            )

    def test_invalid_characters_rejected(self):
        with self.assertRaises(ValueError):
            split_creator_hashtag_pool(
                self.POOL + ["#Invalid"]
            )

    def test_insufficient_pool_rejected(self):
        with self.assertRaises(ValueError):
            split_creator_hashtag_pool(self.POOL[:4])

    def test_fanz_excluded_from_candidate_pool(self):
        rotating, approved = split_creator_hashtag_pool(
            self.POOL + ["FANZ"],
            rng=random.Random(42),
        )

        self.assertNotIn(
            "fanz",
            {tag.lower() for tag in [rotating] + approved},
        )

    def test_original_pool_not_modified(self):
        pool = list(self.POOL)
        original = list(pool)

        split_creator_hashtag_pool(
            pool, rng=random.Random(42)
        )

        self.assertEqual(pool, original)

    def test_seeded_selection_is_reproducible(self):
        first = split_creator_hashtag_pool(
            self.POOL, rng=random.Random(42)
        )

        second = split_creator_hashtag_pool(
            self.POOL, rng=random.Random(42)
        )

        self.assertEqual(first, second)
