"""Short-lived authenticated loopback transport; never exports browser cookies."""
import hmac
import json
import queue
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .state import ROOT, RUNTIME

PORT = 43187


class BridgeError(RuntimeError):
    pass


def ensure_extension_config():
    path = ROOT / 'extension' / 'local-config.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({'port': PORT, 'token': secrets.token_hex(32)}), encoding='utf-8')
    config = json.loads(path.read_text(encoding='utf-8'))
    if config.get('port') != PORT or not isinstance(config.get('token'), str) or len(config['token']) != 64:
        raise BridgeError('擴充功能本機配對設定損壞，請聯絡維護者。')
    return config


class Bridge:
    def __init__(self, token=None, port=PORT):
        self.token = token or ensure_extension_config()['token']
        self.port = port
        self.pairing_file = RUNTIME / 'extension-pair.json' if token is None else None
        self.origin = None
        if self.pairing_file and self.pairing_file.exists():
            self.origin = json.loads(self.pairing_file.read_text(encoding='utf-8'))['origin']
        self.queue = queue.Queue()
        self.pending = {}
        self.lock = threading.Lock()

    def __enter__(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def allowed(self):
                browser_origin = self.headers.get('Origin', '')
                declared_origin = self.headers.get('X-Civit-Helper-Origin', '')
                origin = browser_origin or declared_origin
                if (self.headers.get('Host') != f'127.0.0.1:{owner.port}'
                        or not re.fullmatch(r'chrome-extension://[a-p]{32}', origin)
                        or (browser_origin and declared_origin and browser_origin != declared_origin)
                        or not hmac.compare_digest(self.headers.get('X-Civit-Helper-Token', ''), owner.token)):
                    return False
                with owner.lock:
                    if owner.origin is None:
                        owner.origin = origin
                        if owner.pairing_file:
                            owner.pairing_file.parent.mkdir(parents=True, exist_ok=True)
                            owner.pairing_file.write_text(json.dumps({'origin': origin}), encoding='utf-8')
                    return owner.origin == origin

            def reply(self, code, data):
                body = json.dumps(data).encode('utf-8')
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                if self.headers.get('Origin') == owner.origin:
                    self.send_header('Access-Control-Allow-Origin', owner.origin)
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self):
                origin = self.headers.get('Origin', '')
                if (self.headers.get('Host') != f'127.0.0.1:{owner.port}'
                        or not re.fullmatch(r'chrome-extension://[a-p]{32}', origin)
                        or (owner.origin and owner.origin != origin)):
                    self.reply(403, {'error': 'forbidden'})
                    return
                self.send_response(204)
                self.send_header('Access-Control-Allow-Origin', origin)
                self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'X-Civit-Helper-Token,X-Civit-Helper-Origin,Content-Type')
                self.end_headers()

            def do_GET(self):
                if not self.allowed():
                    self.reply(403, {'error': 'forbidden'})
                    return
                if self.path != '/poll':
                    self.reply(404, {})
                    return
                command = None
                while True:
                    try:
                        candidate = owner.queue.get_nowait()
                    except queue.Empty:
                        break
                    with owner.lock:
                        valid = candidate['id'] in owner.pending
                    if valid and candidate['expiresAt'] > int(time.time() * 1000):
                        command = candidate
                        break
                self.reply(200, {'command': command})

            def do_POST(self):
                if not self.allowed():
                    self.reply(403, {'error': 'forbidden'})
                    return
                if self.path != '/result':
                    self.reply(404, {})
                    return
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 4_000_000:
                        raise ValueError()
                    data = json.loads(self.rfile.read(size))
                    if not isinstance(data, dict) or type(data.get('ok')) is not bool:
                        raise ValueError()
                except (ValueError, TypeError):
                    self.reply(400, {})
                    return
                with owner.lock:
                    entry = owner.pending.get(data.get('id'))
                    if not entry or entry['event'].is_set():
                        self.reply(409, {'error': 'unknown_or_finished_command'})
                        return
                    entry['result'] = data
                    entry['event'].set()
                self.reply(200, {'accepted': True})

        try:
            self.server = ThreadingHTTPServer(('127.0.0.1', self.port), Handler)
        except OSError as exc:
            raise BridgeError('工具本機連接埠已被占用，請確認沒有另一個工具正在執行。') from exc
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def command(self, op, timeout=90, **arguments):
        command_id = secrets.token_hex(16)
        event = threading.Event()
        entry = {'event': event, 'result': None}
        with self.lock:
            self.pending[command_id] = entry
        self.queue.put({'id': command_id, 'op': op, 'expiresAt': int((time.time() + timeout) * 1000), **arguments})
        try:
            if not event.wait(timeout):
                raise BridgeError('Chrome 擴充功能未連線或回應逾時；請確認日常 Chrome 已開啟並載入 Civit Helper。進度已保留。')
            data = entry['result']
            if not data['ok']:
                # Worker sends fixed task errors, not arbitrary page URLs or auth data.
                code = data.get('code', 'EXTENSION_ERROR')
                error = BridgeError(str(data.get('error', '擴充功能執行失敗。')))
                error.code = code
                raise error
            return data.get('result')
        finally:
            with self.lock:
                self.pending.pop(command_id, None)
