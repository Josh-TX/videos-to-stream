import http.server
import socketserver
import functools

PORT = 3000
DIRECTORY = "hls"

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Range, Content-Type, Origin, Accept')
        super().end_headers()

handler = functools.partial(CORSRequestHandler, directory=DIRECTORY)

with socketserver.TCPServer(("", PORT), handler) as httpd:
    print(f"Serving at http://0.0.0.0:{PORT}")
    httpd.serve_forever()
