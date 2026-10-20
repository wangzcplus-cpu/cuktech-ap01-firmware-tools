"""接收 AP01 只读对象树观察记录并保存为 JSONL。"""

from __future__ import annotations

import argparse
import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


class ObservationStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()

    def append(self, client: str, values: dict[str, list[str]]) -> None:
        record = {
            "received_at": datetime.now(timezone.utc).isoformat(),
            "client": client,
            **{key: value[-1] for key, value in values.items()},
        }
        payload = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(payload + "\n")
                stream.flush()


def make_handler(store: ObservationStore) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            request = urlsplit(self.path)
            if request.path == "/health":
                self._reply(200, b"ok\n")
                return
            if request.path != "/ap01-observe":
                self._reply(404, b"not found\n")
                return
            values = parse_qs(request.query, keep_blank_values=True)
            required = {"seq", "page", "index", "count", "path", "class", "x", "y", "w", "h"}
            if not required.issubset(values):
                self._reply(400, b"missing fields\n")
                return
            store.append(self.client_address[0], values)
            self._reply(200, b"ok\n")

        def _reply(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(ObservationStore(args.output.resolve())))
    print(f"AP01 observer receiver: http://{args.host}:{args.port}/health")
    print(f"JSONL: {args.output.resolve()}")
    server.serve_forever()


if __name__ == "__main__":
    main()
