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
        self.assertIn("context + HTTP_SINK_ARG_OFFSET) = (void *)context", source)

    def test_observer_is_a_one_shot_wrapper_probe(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('"/tmp/.ap01-dark-skin-wrapper-probe-v5"', source)
        self.assertIn("AP01_O_RDWR_CREAT_TRUNC", source)
        self.assertIn("claim_wrapper_probe()", source)
        self.assertIn('"seq=0&page=-2&index=0&count=0&depth=0&path=wrapper"', source)
        self.assertIn("send_startup_probe();", source)
        for forbidden in (
            "struct observer_state", "struct record", "MAX_OBJECTS", "MAX_DEPTH",
            "stock_get_dispatch_index", "stock_get_child", "lv_obj_get_child",
            "lv_obj_get_child_count", "count_objects", "resolve_object", "advance_path",
            "LOOP_GLOBAL", "TIMER_BYTES", "stock_timer_init", "stock_timer_schedule",
            "ap01_dark_skin_observer_timer", "timer_loop", "ensure_probe_timer",
        ):
            self.assertNotIn(forbidden, source)

    def test_stock_ui_timer_runs_before_wrapper_probe(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        wrapper = source.split("ATTR_ENTRY void ap01_dark_skin_ui_timer_wrapper", 1)[1]
        stock = wrapper.find("stock_ui_timer)(timer)")
        claim = wrapper.find("claim_wrapper_probe()")
        probe = wrapper.find("send_startup_probe()")
        self.assertLess(stock, claim)
        self.assertLess(claim, probe)


if __name__ == "__main__":
    unittest.main()
