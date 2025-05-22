import sqlite3
conn = sqlite3.connect("reminders.db")
cursor = conn.cursor()
cursor.execute("DELETE FROM reminders WHERE remind_at IS NULL OR remind_at = '' OR remind_at = 'NEEDS_CLARIFICATION'")
conn.commit()
conn.close()
