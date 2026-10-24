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
        self.assertIn("context + HTTP_SINK_ARG_OFFSET) = (void *)record", source)

    def test_observer_uses_small_incremental_state_and_startup_probe(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("#define MAX_PERSISTENT_BYTES 192u", source)
        self.assertIn("observer_state_must_remain_small", source)
        self.assertIn("TIMER_BYTES + sizeof(struct observer_state) <= MAX_PERSISTENT_BYTES", source)
        self.assertNotIn("struct record records[MAX_OBJECTS]", source)
        self.assertIn("state->probe_sent == 0u", source)
        self.assertIn("state->page = -1", source)
        self.assertIn("resolve_object((void *)state->root", source)
        self.assertIn("advance_path((void *)state->root", source)

    def test_timer_is_ensured_before_stock_ui_timer(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        wrapper = source.split("ATTR_ENTRY void ap01_dark_skin_ui_timer_wrapper", 1)[1]
        self.assertLess(wrapper.find("state = ensure_state();"), wrapper.find("stock_ui_timer)(timer)"))


if __name__ == "__main__":
    unittest.main()
