import sqlite3
import datetime

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('users.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        # Таблица пользователей
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                subscription_end DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица платежей
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                user_id INTEGER,
                amount REAL,
                period_days INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
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

    def get_user_subscription(self, user_id):
        cursor = self.conn.execute(
            'SELECT subscription_end FROM users WHERE user_id = ?',
            (user_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else None
    
    def add_payment(self, payment_id, user_id, amount, period_days):
        """Сохраняет информацию о платеже"""
        self.conn.execute(
            'INSERT INTO payments (payment_id, user_id, amount, period_days) VALUES (?, ?, ?, ?)',
            (payment_id, user_id, amount, period_days)
        )
        self.conn.commit()
    
    def update_payment_status(self, payment_id, status):
        """Обновляет статус платежа"""
        self.conn.execute(
            'UPDATE payments SET status = ? WHERE payment_id = ?',
            (status, payment_id)
        )
        
        # Если платеж успешный, обновляем подписку
        if status == 'succeeded':
            cursor = self.conn.execute(
                'SELECT user_id, period_days FROM payments WHERE payment_id = ?',
                (payment_id,)
            )
            result = cursor.fetchone()
            if result:
                user_id, period_days = result
                self.update_subscription(user_id, period_days)
        
        self.conn.commit()

# Функции для импорта в bot.py
def add_user(user_id, username):
    """Добавляет пользователя в БД"""
    db = Database()
    db.add_user(user_id, username, username)
    return True

def get_user_stats(user_id):
    """Возвращает статистику пользователя (заглушка)"""
    return {
        'daily_techniques': 0,
        'days_with_bot': 1,
        'activity_score': 0
    }

def update_user_stats(user_id, stat_type):
    """Обновляет статистику пользователя (заглушка)"""
    pass

def check_subscription(user_id):
    """Проверяет активна ли подписка"""
    db = Database()
    subscription_end = db.get_user_subscription(user_id)
    if subscription_end:
        return datetime.date.fromisoformat(str(subscription_end)) >= datetime.date.today()
    return False

def add_subscription(user_id, days=30, payment_id=None):
    """Добавляет подписку пользователю"""
    db = Database()
    db.update_subscription(user_id, days)
    return True

def save_payment(user_id, payment_id, amount, period_days):
    """Сохраняет платеж в БД"""
    db = Database()
    db.add_payment(payment_id, user_id, amount, period_days)
    return True

def update_payment(payment_id, status):
    """Обновляет статус платежа"""
    db = Database()
    db.update_payment_status(payment_id, status)
    return True

# НОВЫЕ ФУНКЦИИ ДЛЯ АВТОПОДПИСКИ
def get_recent_payments(minutes=5):
    """
    Возвращает платежи за последние N минут
    Используется для проверки свежих платежей
    """
    conn = sqlite3.connect('users.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Получаем платежи созданные не позднее N минут назад
    cursor.execute('''
        SELECT payment_id, user_id, amount, period_days 
        FROM payments 
        WHERE status = 'pending' 
        AND datetime(created_at) > datetime('now', ?)
    ''', (f'-{minutes} minutes',))
    
    payments = []
    for row in cursor.fetchall():
        payments.append({
            'payment_id': row[0],
            'user_id': row[1],
            'amount': row[2],
            'period_days': row[3]
        })
    
    conn.close()
    return payments

def get_user_by_id(user_id):
    """Получает данные пользователя по ID"""
    conn = sqlite3.connect('users.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result

def get_payment_by_id(payment_id):
    """Получает данные платежа по ID"""
    conn = sqlite3.connect('users.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM payments WHERE payment_id = ?', (payment_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result