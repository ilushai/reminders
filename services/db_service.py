import sqlite3
import os

DB_PATH = "reminders.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                remind_at TEXT NOT NULL,
                remind_before INTEGER DEFAULT 0,
                text TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

def add_reminder(user_id, remind_at, remind_before, text):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO reminders (user_id, remind_at, remind_before, text, status)
            VALUES (?, ?, ?, ?, 'active');
        """, (user_id, remind_at, remind_before, text))
        conn.commit()

def get_all_reminders_for_user(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, remind_at, text, remind_before, status
            FROM reminders
            WHERE user_id = ?
            ORDER BY remind_at ASC
        """, (user_id,))
        return c.fetchall()

def get_due_reminders(now_iso):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, user_id, remind_at, text
            FROM reminders
            WHERE status = 'active' AND remind_at <= ?
            ORDER BY remind_at ASC
        """, (now_iso,))
        return c.fetchall()

def mark_reminder_sent(reminder_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE reminders SET status = 'sent' WHERE id = ?
        """, (reminder_id,))
        conn.commit()
