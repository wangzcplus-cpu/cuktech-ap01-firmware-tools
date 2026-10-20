from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .observer_receiver import ObservationStore


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


if __name__ == "__main__":
    unittest.main()
