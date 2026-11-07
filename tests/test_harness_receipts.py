# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

from infoorgbench_harness.receipts import make_receipt


class ReceiptTests(unittest.TestCase):
    def test_receipt_is_content_free_and_drops_secrets_and_endpoints(self):
        receipt = make_receipt(
            harness="react-fc", model="m", backend="copilot", family="Recap",
            task_id="mini-001", status="completed", settings={"max_output_tokens": 128000},
            hashes={"packet_sha256": "a" * 64}, usage={"input_tokens": 4, "output_tokens": 2,
            "input_tokens_details": {"cached_tokens": 3}},
            versions={"harness": "1"},
        )
        text = json.dumps(receipt, sort_keys=True)
        for forbidden in ("prompt", "record", "endpoint", "authorization", "api_key", "secret"):
            self.assertNotIn(forbidden, text.lower())
        self.assertEqual(receipt["provider_reported_usage"]["input_tokens"], 4)
        self.assertEqual(receipt["provider_reported_usage"]["input_tokens_details"]["cached_tokens"], 3)


if __name__ == "__main__":
    unittest.main()
