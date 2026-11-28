"""Localhost-only ops UI. It prepares calldata and records hashes. It does not sign or broadcast."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from tools.season1.ops_book import OpsBook, OpsRefused


def make_handler(book):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def _send(self, code, body):
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.client_address[0] not in ("127.0.0.1", "::1"):
                self._send(403, {"error": "localhost-only"})
                return
            path = urlparse(self.path)
            if path.path == "/api/orders":
                day = (parse_qs(path.query).get("day") or [None])[0]
                rows = []
                for order in book.orders.values():
                    if day and str(order.get("dayIndex")) != str(day):
                        continue
                    rows.append({
                        "orderId": str(order["orderId"]),
                        "recipient": order["recipient"],
                        "label": order["label"],
                        "tld": order["tld"],
                        "local": book.txs.get(str(order["orderId"])),
                        "accident": book.accident_instruction(order["orderId"]),
                    })
                self._send(200, {"orders": rows, "chainId": book.chain_id})
                return
            if path.path == "/app.js":
                script = (book.panel_dir / "app.js").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/javascript")
                self.send_header("Content-Length", str(len(script)))
                self.end_headers()
                self.wfile.write(script)
                return
            if path.path == "/":
                page = (book.panel_dir / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)
                return
            self._send(404, {"error": "not_found"})

        def do_POST(self):
            if self.client_address[0] not in ("127.0.0.1", "::1"):
                self._send(403, {"error": "localhost-only"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            path = urlparse(self.path).path
            try:
                if path == "/api/prepare":
                    body = book.prepare(payload["orderId"], payload["chainId"], payload["account"], None)
                    if "nonce" in body:
                        raise OpsRefused("nonce-must-not-be-set")
                    self._send(200, body)
                    return
                if path == "/api/submitted":
                    self._send(200, book.note_submitted(payload["orderId"], payload["hash"], payload.get("nonce")))
                    return
                if path == "/api/receipt":
                    self._send(200, book.note_receipt(payload["orderId"], payload["receipt"], payload.get("logs") or []))
                    return
            except OpsRefused as exc:
                self._send(409, {"error": str(exc)})
                return
            self._send(404, {"error": "not_found"})

    return Handler


def serve(book, port=8766):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(book))
    httpd.serve_forever()
