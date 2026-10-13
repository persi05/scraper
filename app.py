"""Local product catalogue for the author role in Lab 1.

Run with: python app.py
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
HOST = "127.0.0.1"
PORT = 8000
MIME = {".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".json": "application/json"}


class CatalogueHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = unquote(urlsplit(self.path).path)
        if path == "/":
            target = PUBLIC / "index.html"
        elif path.startswith("/page/"):
            number = path.removeprefix("/page/").strip("/")
            if not number.isdecimal() or not 1 <= int(number) <= 5:
                self.send_error(404)
                return
            target = PUBLIC / "index.html"
        elif path.startswith("/product/"):
            product_id = path.removeprefix("/product/").strip("/")
            if not product_id.isdecimal() or not 1 <= int(product_id) <= 400:
                self.send_error(404)
                return
            target = PUBLIC / "product.html"
        else:
            target = (PUBLIC / path.lstrip("/")).resolve()
            if PUBLIC.resolve() not in target.parents or target.suffix not in MIME:
                self.send_error(404)
                return
        try:
            content = target.read_bytes()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", f"{MIME[target.suffix]}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)


if __name__ == "__main__":
    if not (PUBLIC / "catalog.json").exists():
        raise SystemExit("Brak danych. Najpierw uruchom: python generate_data.py")
    server = ThreadingHTTPServer((HOST, PORT), CatalogueHandler)
    print(f"Katalog: http://{HOST}:{PORT}/page/1", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nZatrzymano.")
    finally:
        server.server_close()
