import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from sui.tools import prepare_next_founder_coin as preparer


class PrepareNextFounderCoinTests(unittest.TestCase):
    def job(self):
        return {
            "economy_asset_id": 123,
            "founder_account_id": 456,
            "handle": "demo",
            "name": "DemoFanz",
            "symbol": "DEMOFANZ",
            "generated_package":
                "fanz_creator_demo",
            "publication_key":
                "founder-123-demo-v1",
            "network": "mainnet",
            "recipient_address":
                "0x" + "1" * 64,
        }

    def test_existing_payload_is_already_prepared(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            prepared = root / "prepared"
            generated = root / "generated"

            prepared.mkdir()
            generated.mkdir()

            payload = (
                prepared
                / "founder-123-demo-v1.json"
            )
            payload.write_text("{}")

            stdout = io.StringIO()

            with (
                patch.object(
                    preparer,
                    "PUBLICATION_ROOT",
                    prepared,
                ),
                patch.object(
                    preparer,
                    "GENERATED_ROOT",
                    generated,
                ),
                patch.object(
                    preparer.subprocess,
                    "run",
                ) as run,
                redirect_stdout(stdout),
            ):
                result = preparer.prepare_job(
                    self.job()
                )

            self.assertEqual(
                result["economy_asset_id"],
                123,
            )

            self.assertIn(
                "founder_coin_prepare_queue="
                "ALREADY_PREPARED",
                stdout.getvalue(),
            )

            run.assert_not_called()

    def test_orphaned_generated_package_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            prepared = root / "prepared"
            generated = root / "generated"

            prepared.mkdir()
            generated.mkdir()

            (
                generated
                / "fanz_creator_demo"
            ).mkdir()

            with (
                patch.object(
                    preparer,
                    "PUBLICATION_ROOT",
                    prepared,
                ),
                patch.object(
                    preparer,
                    "GENERATED_ROOT",
                    generated,
                ),
                self.assertRaises(
                    preparer.QueueError
                ),
            ):
                preparer.prepare_job(
                    self.job()
                )


if __name__ == "__main__":
    unittest.main()
