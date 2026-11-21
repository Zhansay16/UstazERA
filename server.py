"""UstazERA: standard-library HTTP server and MunitoAI proxy.

Run: python server.py
"""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import argparse
import json
import threading
import webbrowser

API_KEY = 'munitoai_AlFRP-_JB4qgXOq4G1aITa7kOfgEXpYfx5LajDx9Voo'
MODEL = 'zai-org/glm-5.3-flash'
API_BASE = 'https://api.munito.ai/inference/v1'
STATIC_DIR = Path(__file__).resolve().parent / 'static'


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def reply(self, status, body):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def json_reply(self, status, value):
        self.reply(status, json.dumps(value, ensure_ascii=False).encode('utf-8'))

    def proxy(self, endpoint, payload=None):
        content = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
        request = Request(
            API_BASE + endpoint,
            data=content,
            headers={
                'Authorization': 'Bearer ' + API_KEY,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            method='GET' if content is None else 'POST',
        )
        try:
            try:
                response = urlopen(request, timeout=90)
            except HTTPError as error:
                response = error
            with response:
                status, body = response.status, response.read()
            self.reply(status, body.replace(API_KEY.encode('utf-8'), b'[redacted]'))
        except (URLError, TimeoutError, OSError):
            self.json_reply(502, {'error': {'message': 'Could not connect to MunitoAI. Check your internet connection.'}})

    def do_GET(self):
        route = self.path.split('?', 1)[0]
        if route == '/api/status':
            self.json_reply(200, {
                'service': 'ustazera-http-project', 'provider': 'MunitoAI',
                'configured': True, 'persistent': True, 'model': MODEL,
            })
        elif route == '/api/models':
            self.proxy('/models')
        else:
            super().do_GET()

    def do_POST(self):
        route = self.path.split('?', 1)[0]
        if route == '/api/settings':
            self.json_reply(200, {'configured': True, 'persistent': True, 'model': MODEL})
            return
        if route != '/api/chat/completions':
            self.json_reply(404, {'error': {'message': 'Route not found'}})
            return
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            payload['model'] = MODEL
            payload['stream'] = False
            payload['reasoning_effort'] = 'none'
        except (ValueError, TypeError):
            self.json_reply(400, {'error': {'message': 'Invalid JSON body'}})
            return
        self.proxy('/chat/completions', payload)


def main():
    parser = argparse.ArgumentParser(description='UstazERA HTTP server')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    browser_host = '127.0.0.1' if args.host == '0.0.0.0' else args.host
    address = 'http://' + browser_host + ':' + str(server.server_port) + '/'
    print('UstazERA: ' + address, flush=True)
    print('Keep this window open. Press Ctrl+C to stop.', flush=True)
    if not args.no_browser:
        opener = threading.Timer(0.3, webbrowser.open, args=(address,))
        opener.daemon = True
        opener.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
