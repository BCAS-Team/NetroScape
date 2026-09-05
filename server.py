"""Local static host for Netroscape's bundled pages."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

HOST = "127.0.0.1"
PORT = 9003
ROOT = Path(__file__).resolve().parent
GOOGLE_ENTRY = "/google/classic-google.neocities.org/index.html"


class NetroscapeRequestHandler(SimpleHTTPRequestHandler):
    """Serve the workspace while giving /google a stable local entry point."""

    def do_GET(self):
        path = urlsplit(self.path).path.rstrip("/") or "/"
        if path == "/google":
            query = urlsplit(self.path).query
            location = GOOGLE_ENTRY + (f"?{query}" if query else "")
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, format_string, *args):
        print(f"[netroscape-server] {self.address_string()} - {format_string % args}")


def create_server(host=HOST, port=PORT):
    handler = partial(NetroscapeRequestHandler, directory=str(ROOT))
    return ThreadingHTTPServer((host, port), handler)


def start_server(host=HOST, port=PORT):
    try:
        server = create_server(host, port)
    except OSError as error:
        if getattr(error, "winerror", None) not in (10013, 10048):
            raise
        server = create_server(host, 0)
    thread = Thread(target=server.serve_forever, name="netroscape-http", daemon=True)
    thread.start()
    return server


if __name__ == "__main__":
    with create_server() as server:
        print(f"Serving {ROOT} at http://{HOST}:{PORT}/google/")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass