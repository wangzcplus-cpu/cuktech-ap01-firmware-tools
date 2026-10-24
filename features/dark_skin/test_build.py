from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .observer_receiver import ObservationStore


SOURCE = Path(__file__).with_name("object_observer.c")


class ReceiverTest(unittest.TestCase):
    def test_jsonl_record(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as selected:
            output = Path(selected) / "records.jsonl"
            ObservationStore(output).append(
                "192.168.50.53",
                {"page": ["0"], "path": ["root"], "w": ["320"]},
            )
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(record["client"], "192.168.50.53")
            self.assertEqual(record["page"], "0")
            self.assertEqual(record["path"], "root")
            self.assertEqual(record["w"], "320")

    def test_observer_uses_verified_stock_webclient_context(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("#define HTTP_RESPONSE_BYTES 4096u", source)
        self.assertIn("#define HTTP_SINK_OFFSET 60u", source)
        self.assertIn("#define HTTP_SINK_ARG_OFFSET 64u", source)
        self.assertIn("(void *)discard_response_sink", source)
        self.assertIn("context + HTTP_SINK_ARG_OFFSET", source)


if __name__ == "__main__":
    unittest.main()
