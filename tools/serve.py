"""Static dev server for web/ on http://127.0.0.1:8090 (no caching). --lan to serve on the local network too."""
import http.server, os, sys
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web'))
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache'); super().end_headers()
host = '0.0.0.0' if '--lan' in sys.argv else '127.0.0.1'
print(f'serving web/ on http://{host}:8090'); http.server.ThreadingHTTPServer((host, 8090), H).serve_forever()
