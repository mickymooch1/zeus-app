"""Additive Hub-only SQLite tables. Never reads or writes legacy credit balances."""
import json
import sqlite3
import time
from contextlib import contextmanager

from .config import HubError

SCHEMA = '''
CREATE TABLE IF NOT EXISTS hub_balances (
 user_id TEXT NOT NULL, mode TEXT NOT NULL, balance INTEGER NOT NULL CHECK(balance>=0),
 PRIMARY KEY(user_id,mode));
CREATE TABLE IF NOT EXISTS hub_ledger (
 user_id TEXT NOT NULL, mode TEXT NOT NULL, reference TEXT NOT NULL, delta INTEGER NOT NULL,
 created_at REAL NOT NULL, PRIMARY KEY(user_id,mode,reference));
CREATE TABLE IF NOT EXISTS hub_conversations (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL, mode TEXT NOT NULL, feature TEXT NOT NULL,
 title TEXT NOT NULL, created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS hub_conversations_owner ON hub_conversations(user_id,mode,created_at);
CREATE TABLE IF NOT EXISTS hub_requests (
 user_id TEXT NOT NULL, request_id TEXT NOT NULL, mode TEXT NOT NULL, conversation_id TEXT NOT NULL,
 feature TEXT NOT NULL, prompt TEXT NOT NULL, fingerprint TEXT NOT NULL, reserved INTEGER NOT NULL,
 zeus_credits_charged INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL, progress TEXT NOT NULL,
 result TEXT, error TEXT, created_at REAL NOT NULL, expires_at REAL NOT NULL,
 PRIMARY KEY(user_id,request_id));
CREATE INDEX IF NOT EXISTS hub_requests_owner_time ON hub_requests(user_id,mode,created_at);
CREATE INDEX IF NOT EXISTS hub_requests_conversation ON hub_requests(conversation_id,created_at);
CREATE TABLE IF NOT EXISTS hub_usage (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, request_id TEXT NOT NULL,
 feature TEXT NOT NULL, mode TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
 input_tokens INTEGER, output_tokens INTEGER, estimated_cost REAL,
 zeus_credits_charged INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, status TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS hub_usage_request ON hub_usage(user_id,request_id);
'''


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connection() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connection(self, write=False):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            if write:
                conn.execute('BEGIN IMMEDIATE')
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _delta(self, conn, user, mode, reference, delta):
        old = conn.execute('SELECT delta FROM hub_ledger WHERE user_id=? AND mode=? AND reference=?', (user, mode, reference)).fetchone()
        if old:
            if old['delta'] != delta:
                raise HubError('Credit transaction reference already used.', 409)
            return
        conn.execute('INSERT OR IGNORE INTO hub_balances VALUES (?,?,0)', (user, mode))
        conn.execute('UPDATE hub_balances SET balance=balance+? WHERE user_id=? AND mode=?', (delta, user, mode))
        conn.execute('INSERT INTO hub_ledger VALUES (?,?,?,?,?)', (user, mode, reference, delta, time.time()))

    def grant(self, user, mode, amount, reference):
        if mode not in ('live', 'development', 'beta') or type(amount) is not int or amount < 0:
            raise ValueError('Invalid Hub grant')
        with self.connection(True) as conn:
            self._delta(conn, user, mode, 'grant:' + reference, amount)

    def balance(self, user, mode):
        with self.connection() as conn:
            row = conn.execute('SELECT balance FROM hub_balances WHERE user_id=? AND mode=?', (user, mode)).fetchone()
            return row['balance'] if row else 0

    def recover(self, user):
        with self.connection(True) as conn:
            rows = conn.execute("SELECT * FROM hub_requests WHERE user_id=? AND status='running' AND expires_at<?", (user, time.time())).fetchall()
            for row in rows:
                self._finish(conn, row, 'failed', None, 0, 'Request interrupted. Reserved Hub credits refunded; start a new request.')
                conn.execute("UPDATE hub_usage SET status='unknown' WHERE user_id=? AND request_id=? AND status='running'", (user, row['request_id']))

    def reserve(self, user, mode, request_id, conversation_id, feature, prompt, amount, fingerprint, per_minute, daily):
        now = time.time()
        with self.connection(True) as conn:
            old = conn.execute('SELECT * FROM hub_requests WHERE user_id=? AND request_id=?', (user, request_id)).fetchone()
            if old:
                if old['fingerprint'] != fingerprint or old['mode'] != mode:
                    raise HubError('Request ID was already used for different content.', 409)
                return {'duplicate': True, **dict(old)}
            recent = conn.execute('SELECT COUNT(*) FROM hub_requests WHERE user_id=? AND mode=? AND created_at>?', (user, mode, now - 60)).fetchone()[0]
            day_start = int(now // 86400) * 86400
            today = conn.execute('SELECT COUNT(*) FROM hub_requests WHERE user_id=? AND mode=? AND created_at>=?', (user, mode, day_start)).fetchone()[0]
            if recent >= per_minute or today >= daily:
                raise HubError('Hub request limit reached. Please try again later.', 429)
            balance = conn.execute('SELECT balance FROM hub_balances WHERE user_id=? AND mode=?', (user, mode)).fetchone()
            if not balance or balance['balance'] < amount:
                raise HubError('Insufficient Zeus Hub credits. Music and video credits cannot be used here.', 402)
            conversation = conn.execute('SELECT * FROM hub_conversations WHERE id=?', (conversation_id,)).fetchone()
            if conversation and (conversation['user_id'] != user or conversation['mode'] != mode or conversation['feature'] != feature):
                raise HubError('Conversation not found.', 404)
            if conn.execute("SELECT 1 FROM hub_requests WHERE conversation_id=? AND status='running'", (conversation_id,)).fetchone():
                raise HubError('Zeus is already working on this conversation.', 409)
            if not conversation:
                conn.execute('INSERT INTO hub_conversations VALUES (?,?,?,?,?,?)', (conversation_id, user, mode, feature, prompt[:90], now))
            self._delta(conn, user, mode, 'reserve:' + request_id, -amount)
            conn.execute('''INSERT INTO hub_requests
                (user_id,request_id,mode,conversation_id,feature,prompt,fingerprint,reserved,status,progress,created_at,expires_at)
                VALUES (?,?,?,?,?,?,?,?,'running','Zeus is preparing your request…',?,?)''',
                (user, request_id, mode, conversation_id, feature, prompt, fingerprint, amount, now, now + 300))
            return {'duplicate': False, 'request_id': request_id}

    def progress(self, user, request_id, message):
        with self.connection(True) as conn:
            conn.execute("UPDATE hub_requests SET progress=? WHERE user_id=? AND request_id=? AND status='running'", (message, user, request_id))

    def start_usage(self, user, request_id, model, estimated_cost=0):
        with self.connection(True) as conn:
            row = conn.execute("SELECT * FROM hub_requests WHERE user_id=? AND request_id=? AND status='running'", (user, request_id)).fetchone()
            if not row:
                raise HubError('Request is no longer active.', 409)
            return conn.execute('''INSERT INTO hub_usage(user_id,request_id,feature,mode,provider,model,created_at,estimated_cost,status)
                VALUES(?,?,?,?,?,?,?,?,'running')''', (user, request_id, row['feature'], row['mode'], model.provider, model.model, time.time(), estimated_cost)).lastrowid

    def finish_usage(self, usage_id, result=None, status='succeeded'):
        result = result or {}
        with self.connection(True) as conn:
            conn.execute('UPDATE hub_usage SET input_tokens=?,output_tokens=?,estimated_cost=COALESCE(?,estimated_cost),model=COALESCE(?,model),status=? WHERE id=?',
                         (result.get('input_tokens'), result.get('output_tokens'), result.get('estimated_cost'), result.get('model'), status, usage_id))

    def usage(self, user, request_id):
        with self.connection() as conn:
            return [dict(r) for r in conn.execute('SELECT * FROM hub_usage WHERE user_id=? AND request_id=? ORDER BY id', (user, request_id))]

    def _finish(self, conn, row, status, result, charge, error):
        charge = min(row['reserved'], max(0, charge)) if status == 'succeeded' else 0
        self._delta(conn, row['user_id'], row['mode'], 'refund:' + row['request_id'], row['reserved'] - charge)
        conn.execute('UPDATE hub_requests SET status=?,result=?,zeus_credits_charged=?,error=?,progress=? WHERE user_id=? AND request_id=?',
                     (status, json.dumps(result) if result else None, charge, error, 'Complete' if status == 'succeeded' else 'Request failed', row['user_id'], row['request_id']))
        usages = conn.execute("SELECT id,estimated_cost FROM hub_usage WHERE user_id=? AND request_id=? AND status='succeeded' ORDER BY id", (row['user_id'], row['request_id'])).fetchall()
        total = sum(u['estimated_cost'] or 0 for u in usages)
        remaining = charge
        for i, usage in enumerate(usages):
            allocated = remaining if i == len(usages) - 1 else (int(charge * (usage['estimated_cost'] or 0) / total) if total else 0)
            conn.execute('UPDATE hub_usage SET zeus_credits_charged=? WHERE id=?', (allocated, usage['id']))
            remaining -= allocated

    def finish(self, user, request_id, status, result, charge, error=None):
        with self.connection(True) as conn:
            row = conn.execute('SELECT * FROM hub_requests WHERE user_id=? AND request_id=?', (user, request_id)).fetchone()
            if row and row['status'] == 'running':
                self._finish(conn, row, status, result, charge, error)

    def request(self, user, request_id):
        with self.connection() as conn:
            row = conn.execute('SELECT * FROM hub_requests WHERE user_id=? AND request_id=?', (user, request_id)).fetchone()
            if not row:
                raise HubError('Request not found.', 404)
            result = dict(row)
            result['result'] = json.loads(result['result']) if result['result'] else None
            result.pop('fingerprint')
            return result

    def history(self, user, mode):
        with self.connection() as conn:
            return [dict(r) for r in conn.execute('SELECT * FROM hub_conversations WHERE user_id=? AND mode=? ORDER BY created_at DESC LIMIT 100', (user, mode))]

    def conversation(self, user, mode, conversation_id, feature=None):
        with self.connection() as conn:
            row = conn.execute('SELECT * FROM hub_conversations WHERE id=? AND user_id=? AND mode=?', (conversation_id, user, mode)).fetchone()
            if not row or (feature and row['feature'] != feature):
                raise HubError('Conversation not found.', 404)
            ids = [r[0] for r in conn.execute('SELECT request_id FROM hub_requests WHERE conversation_id=? AND user_id=? ORDER BY created_at LIMIT 200', (conversation_id, user))]
        return {'conversation': dict(row), 'requests': [{**self.request(user, r), 'usage': self.usage(user, r)} for r in ids]}
