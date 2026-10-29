import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Storage:
    def __init__(self, path=None, timeout=15.0):
        self.path = (
            Path(path) if path is not None
            else Path(__file__).resolve().parent / 'assistant.db'
        )
        self.timeout = timeout
        with self.session() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY, title TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE, role TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, body TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE, name TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            ''')

    def connect(self):
        """Create and return a raw SQLite connection.
        Caller is responsible for closing it, or use session() for automatic management."""
        db = sqlite3.connect(self.path, timeout=self.timeout)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    @contextmanager
    def session(self):
        """Context manager managing transaction and ensuring deterministic connection closure."""
        db = self.connect()
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_chat(self):
        with self.session() as db:
            return db.execute('INSERT INTO chats(title) VALUES (?)', ('New chat',)).lastrowid

    def chats(self):
        with self.session() as db:
            return db.execute('SELECT * FROM chats ORDER BY id DESC').fetchall()

    def messages(self, chat_id):
        with self.session() as db:
            return db.execute('SELECT * FROM messages WHERE chat_id=? ORDER BY id', (chat_id,)).fetchall()

    def add_message(self, chat_id, role, body):
        with self.session() as db:
            db.execute('INSERT INTO messages(chat_id,role,body) VALUES (?,?,?)', (chat_id, role, body))
            count_row = db.execute('SELECT COUNT(*) FROM messages WHERE chat_id=?', (chat_id,)).fetchone()
            title_row = db.execute('SELECT title FROM chats WHERE id=?', (chat_id,)).fetchone()
            if role == 'user' and count_row and count_row[0] == 1 and title_row and title_row[0] == 'New chat':
                db.execute('UPDATE chats SET title=? WHERE id=?', (body[:52], chat_id))

    def rename_chat(self, chat_id, title):
        with self.session() as db:
            db.execute('UPDATE chats SET title=? WHERE id=?', (title, chat_id))

    def edit_user_message(self, chat_id, message_id, body):
        with self.session() as db:
            old_message = db.execute(
                'SELECT body FROM messages WHERE id=? AND chat_id=? AND role=?',
                (message_id, chat_id, 'user'),
            ).fetchone()
            if not old_message:
                return False

            db.execute(
                'UPDATE messages SET body=? WHERE id=? AND chat_id=? AND role=?',
                (body, message_id, chat_id, 'user'),
            )
            db.execute(
                'DELETE FROM messages WHERE chat_id=? AND id>?',
                (chat_id, message_id),
            )

            first_user = db.execute(
                'SELECT MIN(id) FROM messages WHERE chat_id=? AND role=?',
                (chat_id, 'user'),
            ).fetchone()[0]
            title = db.execute(
                'SELECT title FROM chats WHERE id=?', (chat_id,)
            ).fetchone()
            if first_user == message_id and title and title[0] == old_message[0][:52]:
                db.execute(
                    'UPDATE chats SET title=? WHERE id=?',
                    (body[:52], chat_id),
                )
            return True

    def delete_chat(self, chat_id):
        with self.session() as db:
            db.execute('DELETE FROM chats WHERE id=?', (chat_id,))

    def notes(self):
        with self.session() as db:
            return db.execute('SELECT * FROM notes ORDER BY id DESC').fetchall()

    def add_note(self, body):
        with self.session() as db:
            db.execute('INSERT INTO notes(body) VALUES (?)', (body,))

    def delete_note(self, note_id):
        with self.session() as db:
            db.execute('DELETE FROM notes WHERE id=?', (note_id,))

    def add_document(self, chat_id, name, body):
        with self.session() as db:
            db.execute('INSERT INTO documents(chat_id,name,body) VALUES (?,?,?)', (chat_id, name, body))

    def documents(self, chat_id):
        with self.session() as db:
            return db.execute('SELECT * FROM documents WHERE chat_id=? ORDER BY id DESC', (chat_id,)).fetchall()

    def delete_document(self, doc_id, chat_id):
        with self.session() as db:
            db.execute('DELETE FROM documents WHERE id=? AND chat_id=?', (doc_id, chat_id))
