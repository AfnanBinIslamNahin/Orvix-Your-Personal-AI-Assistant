import sqlite3
from pathlib import Path


class Storage:
    def __init__(self, path='assistant.db'):
        self.path = Path(path)
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY, title TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE, role TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, body TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE, name TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            ''')

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def create_chat(self):
        with self.connect() as db:
            return db.execute('INSERT INTO chats(title) VALUES (?)', ('New chat',)).lastrowid

    def chats(self):
        with self.connect() as db:
            return db.execute('SELECT * FROM chats ORDER BY id DESC').fetchall()

    def messages(self, chat_id):
        with self.connect() as db:
            return db.execute('SELECT * FROM messages WHERE chat_id=? ORDER BY id', (chat_id,)).fetchall()

    def add_message(self, chat_id, role, body):
        with self.connect() as db:
            db.execute('INSERT INTO messages(chat_id,role,body) VALUES (?,?,?)', (chat_id, role, body))
            if role == 'user' and db.execute('SELECT COUNT(*) FROM messages WHERE chat_id=?', (chat_id,)).fetchone()[0] == 1:
                db.execute('UPDATE chats SET title=? WHERE id=?', (body[:52], chat_id))

    def delete_chat(self, chat_id):
        with self.connect() as db:
            db.execute('DELETE FROM chats WHERE id=?', (chat_id,))

    def notes(self):
        with self.connect() as db:
            return db.execute('SELECT * FROM notes ORDER BY id DESC').fetchall()

    def add_note(self, body):
        with self.connect() as db:
            db.execute('INSERT INTO notes(body) VALUES (?)', (body,))

    def delete_note(self, note_id):
        with self.connect() as db:
            db.execute('DELETE FROM notes WHERE id=?', (note_id,))

    def add_document(self, chat_id, name, body):
        with self.connect() as db:
            db.execute('INSERT INTO documents(chat_id,name,body) VALUES (?,?,?)', (chat_id, name, body))

    def documents(self, chat_id):
        with self.connect() as db:
            return db.execute('SELECT * FROM documents WHERE chat_id=? ORDER BY id DESC', (chat_id,)).fetchall()

    def delete_document(self, doc_id, chat_id):
        with self.connect() as db:
            db.execute('DELETE FROM documents WHERE id=? AND chat_id=?', (doc_id, chat_id))
