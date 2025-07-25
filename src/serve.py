import http.server
import socketserver
import functools
import json
import os
from datetime import datetime, UTC
from preset_manager import PresetManager

PORT = 3000
DIRECTORY = "serve"
LAST_ACTIVITY_FILE = "last-activity.txt"
PRESETS_FILE = "presets.json"

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    preset_manager = PresetManager()

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, PUT, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Range, Content-Type, Origin, Accept')
        if self.path.endswith(".m3u8"):
            self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == "/presets":
            self.handle_get_presets()
            return
        if self.path.endswith(".m3u8"):
            self.update_last_activity()
        super().do_GET()

    def do_PUT(self):
        if self.path == "/presets":
            self.handle_put_presets()
        else:
            self.send_error(404, "Unsupported PUT path")

    def handle_get_presets(self):
        presets = self.preset_manager.get_presets()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(presets).encode("utf-8"))

    def handle_put_presets(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self.send_error(400, "Empty request body")
            return

        try:
            body = self.rfile.read(content_length)
            presets = json.loads(body)
            if not isinstance(presets, list):
                self.send_error(400, "Expected a JSON array")
                return
            self.preset_manager.set_presets(presets)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
        except Exception as e:
            self.send_error(500, f"Failed to save presets: {e}")

    def update_last_activity(self):
        try:
            now = datetime.now(UTC)
            with open(LAST_ACTIVITY_FILE, "w") as f:
                f.write(now.isoformat())
        except Exception as e:
            print(f"Error writing last activity file: {e}")

handler = functools.partial(RequestHandler, directory=DIRECTORY)

with socketserver.TCPServer(("", PORT), handler) as httpd:
    print(f"Serving at http://0.0.0.0:{PORT}")
    httpd.serve_forever()
