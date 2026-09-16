"""Persistent SQLite document storage for the single-worker desktop API."""
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace


def project(doc, projection):
    doc = json.loads(json.dumps(doc))
    if not projection:
        return doc
    included = [k for k, v in projection.items() if v and k != '_id']
    if included:
        return {k: doc[k] for k in included if k in doc}
    for key, value in projection.items():
        if value:
            continue
        parts, parent = key.split('.'), doc
        for part in parts[:-1]:
            parent = parent.get(part, {})
        parent.pop(parts[-1], None)
    return doc


class Cursor:
    def __init__(self, docs, projection):
        self.docs, self.projection = docs, projection

    def sort(self, key, direction):
        self.docs.sort(key=lambda d: d.get(key, ''), reverse=direction < 0)
        return self

    async def to_list(self, length):
        return [project(d, self.projection) for d in self.docs[:length]]


class Collection:
    def __init__(self, connection, name):
        self.connection, self.name = connection, name

    def _matching(self, query):
        rows = self.connection.execute('SELECT rowid, body FROM documents WHERE collection = ?', (self.name,)).fetchall()
        return [(rowid, doc) for rowid, body in rows for doc in [json.loads(body)]
                if all(doc.get(k) == v for k, v in query.items())]

    def find(self, query, projection=None):
        return Cursor([doc for _, doc in self._matching(query)], projection)

    async def find_one(self, query, projection=None, sort=None):
        cursor = self.find(query, projection)
        for key, direction in reversed(sort or []):
            cursor.sort(key, direction)
        docs = await cursor.to_list(1)
        return docs[0] if docs else None

    async def insert_one(self, doc):
        with self.connection:
            self.connection.execute('INSERT INTO documents(collection, body) VALUES (?, ?)',
                                    (self.name, json.dumps(doc, allow_nan=False)))

    async def replace_one(self, query, doc, upsert=False):
        matches = self._matching(query)
        if matches:
            with self.connection:
                self.connection.execute('UPDATE documents SET body = ? WHERE rowid = ?',
                                        (json.dumps(doc, allow_nan=False), matches[0][0]))
        elif upsert:
            await self.insert_one(doc)

    async def delete_one(self, query):
        matches = self._matching(query)
        if matches:
            with self.connection:
                self.connection.execute('DELETE FROM documents WHERE rowid = ?', (matches[0][0],))
        return SimpleNamespace(deleted_count=int(bool(matches)))


class LocalDatabase:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute('CREATE TABLE IF NOT EXISTS documents (collection TEXT NOT NULL, body TEXT NOT NULL)')
        self.connection.execute('CREATE INDEX IF NOT EXISTS collection_idx ON documents(collection)')
        self.connection.commit()

    def __getattr__(self, name):
        return Collection(self.connection, name)

    def close(self):
        self.connection.close()
