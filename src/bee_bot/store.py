"""Durable local state. Every writer obtains SQLite's process-wide write lock."""
import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = str(path)
        if self.path != ':memory:':
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA busy_timeout=30000')
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('PRAGMA synchronous=FULL')
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS objects (
                kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,
                PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, actor TEXT NOT NULL, operation TEXT NOT NULL,
                result TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS flags (id TEXT PRIMARY KEY);
        ''')
        self.connection.commit()

    def get(self, kind, identifier):
        row = self.connection.execute('SELECT data FROM objects WHERE kind=? AND id=?',
                                      (kind, identifier)).fetchone()
        return json.loads(row['data']) if row else None

    def put(self, kind, value):
        self.connection.execute('INSERT INTO objects(kind,id,data) VALUES(?,?,?) '
                                'ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data',
                                (kind, value['id'], json.dumps(value, ensure_ascii=False)))

    def all(self, kind):
        return [json.loads(row['data']) for row in self.connection.execute(
            'SELECT data FROM objects WHERE kind=? ORDER BY rowid', (kind,))]

    def flag(self, identifier):
        return self.connection.execute('INSERT OR IGNORE INTO flags(id) VALUES(?)',
                                       (identifier,)).rowcount == 1

    def close(self):
        self.connection.close()
