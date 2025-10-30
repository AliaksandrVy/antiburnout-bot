import sqlite3
import datetime

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('users.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                subscription_end DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name):
        self.conn.execute(
            'INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)',
            (user_id, username, first_name)
        )
        self.conn.commit()
    
    def get_active_users(self):
        cursor = self.conn.execute(
            'SELECT user_id FROM users WHERE subscription_end >= date("now") OR subscription_end IS NULL'
        )
        return [row[0] for row in cursor]
    
    def update_subscription(self, user_id, days_duration=30):
        new_end_date = datetime.date.today() + datetime.timedelta(days=days_duration)
        self.conn.execute(
            'UPDATE users SET subscription_end = ? WHERE user_id = ?',
            (new_end_date, user_id)
        )
        self.conn.commit()
    
    def update_subscription(self, user_id, days_duration=30):
        new_end_date = datetime.date.today() + datetime.timedelta(days=days_duration)
        self.conn.execute(
            'UPDATE users SET subscription_end = ? WHERE user_id = ?',
            (new_end_date, user_id)
        )
        self.conn.commit()

    def get_user_subscription(self, user_id):
        cursor = self.conn.execute(
            'SELECT subscription_end FROM users WHERE user_id = ?',
            (user_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else None