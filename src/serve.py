import http.server
import socketserver
import functools
import json
import re
import os
import subprocess
import atexit
import signal
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
        if self.path == "/files":
            self.handle_get_files()
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
            signal_stream_presets_changed()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
        except Exception as e:
            self.send_error(500, f"Failed to save presets: {e}")

    def handle_get_files(self):
        active_preset = self.preset_manager.get_active_preset()
        suppressed_files, neutral_files, boosted_files, excluded_files = get_files(active_preset)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps([suppressed_files, neutral_files, boosted_files, excluded_files]).encode("utf-8"))

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

def get_files(active_preset):
    # this is largely copy-pasted from stream.py. 
    # first recreate stream.py's settings object
    class Settings:
        pass
    settings = Settings()
    settings.input_root_dir = "/media"
    video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', 'mpeg'}
    settings.base_directory = active_preset["BASE_DIRECTORY"].strip(" \t\n\r/\\")
    settings.exclude_startswith_csv = active_preset["EXCLUDE_STARTSWITH_CSV"].strip(" \t\n\r")
    settings.exclude_contains_csv = active_preset["EXCLUDE_CONTAINS_CSV"].strip(" \t\n\r")
    settings.exclude_notstartswith_csv = active_preset["EXCLUDE_NOTSTARTSWITH_CSV"].strip(" \t\n\r")
    settings.exclude_notcontains_csv = active_preset["EXCLUDE_NOTCONTAINS_CSV"].strip(" \t\n\r")
    settings.boosted_startswith_csv = active_preset["BOOSTED_STARTSWITH_CSV"].strip(" \t\n\r")
    settings.boosted_contains_csv = active_preset["BOOSTED_CONTAINS_CSV"].strip(" \t\n\r")
    settings.boosted_notstartswith_csv = active_preset["BOOSTED_NOTSTARTSWITH_CSV"].strip(" \t\n\r")
    settings.boosted_notcontains_csv = active_preset["BOOSTED_NOTCONTAINS_CSV"].strip(" \t\n\r")
    settings.boosted_factor = int(active_preset["BOOSTED_FACTOR"])
    settings.suppressed_startswith_csv = active_preset["SUPPRESSED_STARTSWITH_CSV"].strip(" \t\n\r")
    settings.suppressed_contains_csv = active_preset["SUPPRESSED_CONTAINS_CSV"].strip(" \t\n\r")
    settings.suppressed_notstartswith_csv = active_preset["SUPPRESSED_NOTSTARTSWITH_CSV"].strip(" \t\n\r")
    settings.suppressed_notcontains_csv = active_preset["SUPPRESSED_NOTCONTAINS_CSV"].strip(" \t\n\r")
    settings.suppressed_factor = int(active_preset["SUPPRESSED_FACTOR"])

    # now the only difference is that we're also tracking excluded_files
    excluded_files = []
    suppressed_files = []
    neutral_files = []
    boosted_files = []
    def get_contain_pattern(csv):
        if not csv:
            return None
        lower_terms = [term.strip().lower() for term in csv.split(",") if term.strip()]
        return re.compile("|".join(re.escape(term) for term in lower_terms))
    def get_startswith_list(csv):
        if not csv:
            return None
        return [term.strip().lstrip("/").lower() for term in csv.split(",") if term.strip()]
    exclude_startswith_list = get_startswith_list(settings.exclude_startswith_csv)
    exclude_contains_pattern = get_contain_pattern(settings.exclude_contains_csv)
    exclude_notstartswith_list = get_startswith_list(settings.exclude_notstartswith_csv)
    exclude_notcontains_pattern = get_contain_pattern(settings.exclude_notcontains_csv)

    boosted_startswith_list = get_startswith_list(settings.boosted_startswith_csv)
    boosted_contains_pattern = get_contain_pattern(settings.boosted_contains_csv)
    boosted_notstartswith_list = get_startswith_list(settings.boosted_notstartswith_csv)
    boosted_notcontains_pattern = get_contain_pattern(settings.boosted_notcontains_csv)

    suppressed_startswith_list = get_startswith_list(settings.suppressed_startswith_csv)
    suppressed_contains_pattern = get_contain_pattern(settings.suppressed_contains_csv)
    suppressed_notstartswith_list = get_startswith_list(settings.suppressed_notstartswith_csv)
    suppressed_notcontains_pattern = get_contain_pattern(settings.suppressed_notcontains_csv)

    stack = [os.path.join(settings.input_root_dir, settings.base_directory)]
    while stack:
        current_dir = stack.pop()
        with os.scandir(current_dir) as it:
            for entry in it:
                if entry.is_dir():
                    stack.append(entry.path)
                elif not entry.is_file():
                    continue 
                if not os.path.splitext(entry.name)[1].lower() in video_extensions:
                    continue
                path = os.path.relpath(entry.path, start=settings.input_root_dir)
                if settings.base_directory:
                    lower_path = path[len(settings.base_directory) + 1:].lower()
                else:
                    lower_path = path.lower()
                if (
                    (exclude_startswith_list and any(lower_path.startswith(p) for p in exclude_startswith_list))
                    or (exclude_contains_pattern and bool(exclude_contains_pattern.search(lower_path)))
                    or (exclude_notstartswith_list and not any(lower_path.startswith(p) for p in exclude_notstartswith_list))
                    or (exclude_notcontains_pattern and not bool(exclude_notcontains_pattern.search(lower_path)))
                ):
                    excluded_files.append(path)
                    continue
                bias=0
                if (
                    (boosted_startswith_list and any(lower_path.startswith(p) for p in boosted_startswith_list))
                    or (boosted_contains_pattern and bool(boosted_contains_pattern.search(lower_path)))
                    or (boosted_notstartswith_list and not any(lower_path.startswith(p) for p in boosted_notstartswith_list))
                    or (boosted_notcontains_pattern and not bool(boosted_notcontains_pattern.search(lower_path)))
                ):
                    bias+=1
                if (
                    (suppressed_startswith_list and any(lower_path.startswith(p) for p in suppressed_startswith_list))
                    or (suppressed_contains_pattern and bool(suppressed_contains_pattern.search(lower_path)))
                    or (suppressed_notstartswith_list and not any(lower_path.startswith(p) for p in suppressed_notstartswith_list))
                    or (suppressed_notcontains_pattern and not bool(suppressed_notcontains_pattern.search(lower_path)))
                ):
                    bias-=1
                if bias == -1:
                    suppressed_files.append(path)
                elif bias == 0:
                    neutral_files.append(path)
                else:
                    boosted_files.append(path)
    return (suppressed_files, neutral_files, boosted_files, excluded_files)

def start_stream():
    global stream_process
    if stream_process and stream_process.poll() is None:
        stop_stream()
    
    stream_process = subprocess.Popen([
        'python3', '-u', 'stream.py'
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

def signal_stream_presets_changed():
    global stream_process
    if stream_process and stream_process.poll() is None:
        try:
            stream_process.send_signal(signal.SIGUSR1)
            print("Sent presets changed signal to stream process")
        except Exception as e:
            print(f"Failed to signal stream process: {e}")
    else:
        print("No running stream process to signal")

atexit.register(stop_stream)

start_stream()

handler = functools.partial(RequestHandler, directory=DIRECTORY)

with socketserver.TCPServer(("", PORT), handler) as httpd:
    print(f"Serving at http://0.0.0.0:{PORT}")
    httpd.serve_forever()