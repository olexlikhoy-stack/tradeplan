#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, sqlite3, os, hashlib, secrets

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tradeplan.db')
API_TOKEN = os.environ.get('TP_TOKEN', 'tradeplan2026')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('CREATE TABLE IF NOT EXISTS entries (id INTEGER PRIMARY KEY, data TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS checklist (id TEXT PRIMARY KEY, checked INTEGER NOT NULL)')
    conn.commit()
    return conn

class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def _auth(self):
        token = self.headers.get('Authorization', '').replace('Bearer ', '')
        return token == API_TOKEN

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if not self._auth():
            return self._json(401, {'error': 'unauthorized'})
        if self.path == '/api/sync':
            conn = get_db()
            entries = []
            for row in conn.execute('SELECT data FROM entries ORDER BY id DESC'):
                entries.append(json.loads(row[0]))
            checked = {}
            for row in conn.execute('SELECT id, checked FROM checklist'):
                checked[row[0]] = bool(row[1])
            conn.close()
            return self._json(200, {'entries': entries, 'checkedItems': checked})
        self._json(404, {'error': 'not found'})

    def do_POST(self):
        if not self._auth():
            return self._json(401, {'error': 'unauthorized'})
        if self.path == '/api/sync':
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            conn = get_db()
            if 'entries' in body:
                for e in body['entries']:
                    conn.execute('INSERT OR REPLACE INTO entries (id, data) VALUES (?, ?)',
                                 (e['id'], json.dumps(e, ensure_ascii=False)))
            if 'checkedItems' in body:
                for k, v in body['checkedItems'].items():
                    conn.execute('INSERT OR REPLACE INTO checklist (id, checked) VALUES (?, ?)',
                                 (k, int(v)))
            conn.commit()
            conn.close()
            return self._json(200, {'ok': True})
        self._json(404, {'error': 'not found'})

    def log_message(self, fmt, *args):
        print(f"[tradeplan] {args[0]}")

if __name__ == '__main__':
    port = int(os.environ.get('TP_PORT', 3000))
    server = HTTPServer(('0.0.0.0', port), Handler)
    print(f'TradePlan sync running on port {port}')
    server.serve_forever()
