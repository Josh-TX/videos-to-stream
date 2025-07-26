import http.server
import socketserver
import functools
import json
import os
import subprocess
import atexit
from datetime import datetime, UTC
from preset_manager import PresetManager

PORT = 3000
DIRECTORY = "serve"
LAST_ACTIVITY_FILE = "last-activity.txt"
PRESETS_FILE = "presets.json"

stream_process = None

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    preset_manager = PresetManager()

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, PUT, POST, OPTIONS')
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

    def do_POST(self):
        if self.path == "/restart":
            self.handle_restart()
        else:
            self.send_error(404, "Unsupported POST path")

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

    def handle_restart(self):
        try:
            restart_stream()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "message": "Stream restarted"}).encode("utf-8"))
        except Exception as e:
            self.send_error(500, f"Failed to restart stream: {e}")

    def update_last_activity(self):
        try:
            now = datetime.now(UTC)
            with open(LAST_ACTIVITY_FILE, "w") as f:
                f.write(now.isoformat())
        except Exception as e:
            print(f"Error writing last activity file: {e}")

def start_stream():
    global stream_process
    if stream_process and stream_process.poll() is None:
        stop_stream()
    
    stream_process = subprocess.Popen([
        'python3', '-u', 'app/stream.py'
    ])
    print(f"Started stream process with PID: {stream_process.pid}")

def stop_stream():
    global stream_process
    if stream_process and stream_process.poll() is None:
        print(f"Stopping stream process {stream_process.pid}")
        stream_process.terminate()
        try:
            stream_process.wait(timeout=5)  # Wait up to 5 seconds for graceful shutdown
        except subprocess.TimeoutExpired:
            print("Process didn't terminate gracefully, killing it")
            stream_process.kill()
            stream_process.wait()
        stream_process = None

def restart_stream():
    print("Restarting stream...")
    start_stream()

atexit.register(stop_stream)

start_stream()

handler = functools.partial(RequestHandler, directory=DIRECTORY)

with socketserver.TCPServer(("", PORT), handler) as httpd:
    print(f"Serving at http://0.0.0.0:{PORT}")
    httpd.serve_forever()