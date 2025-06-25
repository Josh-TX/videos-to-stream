import http.server
import socketserver
import functools
from datetime import datetime, UTC

PORT = 3000
DIRECTORY = "hls"
LAST_ACTIVITY_FILE = "last-activity.txt"

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Range, Content-Type, Origin, Accept')
        super().end_headers()

    def do_GET(self):
        if self.path.endswith(".m3u8"):
            self.update_last_activity()
        super().do_GET()

    def update_last_activity(self):
        try:
            now = datetime.now(UTC)
            with open(LAST_ACTIVITY_FILE, "w") as f:
                f.write(now.isoformat())
        except Exception as e:
            print(f"Error writing last activity file: {e}")

handler = functools.partial(CORSRequestHandler, directory=DIRECTORY)

with socketserver.TCPServer(("", PORT), handler) as httpd:
    print(f"Serving at http://0.0.0.0:{PORT}")
    httpd.serve_forever()
