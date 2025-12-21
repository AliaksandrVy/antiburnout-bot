import telebot
from telebot import types
import sqlite3
import json
from datetime import datetime, timedelta
import random
import os
import threading
import time
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройки
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID', '360171560')

if not TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не найден в .env файле!")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# Настраиваем таймауты
import telebot.apihelper
telebot.apihelper.READ_TIMEOUT = 35
telebot.apihelper.CONNECT_TIMEOUT = 10
bot.skip_pending = True

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============== БАЗА ДАННЫХ ==============
def init_database():
    """Инициализация базы данных"""
    conn = sqlite3.connect('users.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            subscription_end DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица платежей
    cursor.execute('''
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
    
    # Таблица статистики
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_stats (
            user_id INTEGER,
            stat_key TEXT,
            stat_value INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, stat_key),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")

# Инициализируем БД
init_database()

# ============== ФУНКЦИИ БАЗЫ ДАННЫХ ==============
def add_user_to_db(user_id, username, first_name=None):
    """Добавление пользователя в БД"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user_id, username, first_name or username)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления пользователя: {e}")
        return False
    finally:
        conn.close()

def check_subscription_in_db(user_id):
    """Проверка подписки пользователя"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT subscription_end FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        
        if not result or not result[0]:
            return False
        
        try:
            subscription_end = datetime.strptime(result[0], '%Y-%m-%d').date()
        except:
            # Если формат другой
            subscription_end = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').date()
            
        return subscription_end >= datetime.now().date()
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        return False
    finally:
        conn.close()

def get_user_stats_from_db(user_id):
    """Получение статистики пользователя"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT stat_key, stat_value FROM user_stats WHERE user_id = ?",
            (user_id,)
        )
        stats = cursor.fetchall()
        
        # Преобразуем в словарь
        stats_dict = {}
        for key, value in stats:
            stats_dict[key] = value
        
        # Добавляем дни с ботом
        cursor.execute(
            "SELECT created_at FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        if result:
            try:
                created_at = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
            except:
                created_at = datetime.strptime(result[0], '%Y-%m-%d')
            days_with_bot = (datetime.now() - created_at).days + 1
            stats_dict['days_with_bot'] = max(1, days_with_bot)
        
        # Убедимся что все ключи есть
        if 'daily_techniques' not in stats_dict:
            stats_dict['daily_techniques'] = 0
        if 'activity_score' not in stats_dict:
            stats_dict['activity_score'] = 0
        if 'days_with_bot' not in stats_dict:
            stats_dict['days_with_bot'] = 1
            
        return stats_dict
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return {'daily_techniques': 0, 'days_with_bot': 1, 'activity_score': 0}
    finally:
        conn.close()

def update_user_stats_in_db(user_id, stat_key):
    """Обновление статистики пользователя"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO user_stats (user_id, stat_key, stat_value) 
               VALUES (?, ?, 1)
               ON CONFLICT(user_id, stat_key) 
               DO UPDATE SET stat_value = stat_value + 1""",
            (user_id, stat_key)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления статистики: {e}")
        return False
    finally:
        conn.close()

def save_payment_to_db(user_id, payment_id, amount, period_days):
    """Сохранение платежа"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO payments (payment_id, user_id, amount, period_days, status) 
               VALUES (?, ?, ?, ?, 'pending')""",
            (payment_id, user_id, amount, period_days)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения платежа: {e}")
        return False
    finally:
        conn.close()

def add_subscription_to_db(user_id, days):
    """Добавление подписки"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        new_end = (datetime.now() + timedelta(days=days)).date().isoformat()
        cursor.execute(
            "UPDATE users SET subscription_end = ? WHERE user_id = ?",
            (new_end, user_id)
        )
        conn.commit()
        logger.info(f"✅ Подписка добавлена для user_id={user_id} на {days} дней")
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления подписки: {e}")
        return False
    finally:
        conn.close()

def update_payment_status(payment_id, status):
    """Обновление статуса платежа"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE payments SET status = ? WHERE payment_id = ?",
            (status, payment_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления платежа: {e}")
        return False
    finally:
        conn.close()

def get_pending_payments():
    """Получение pending платежей"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT payment_id, user_id, period_days FROM payments WHERE status = 'pending'"
        )
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Ошибка получения платежей: {e}")
        return []
    finally:
        conn.close()

# ============== ПЛАТЕЖНАЯ СИСТЕМА ==============
class PaymentSystem:
    """Система обработки платежей"""
    
    @staticmethod
    def create_payment(user_id, amount, description):
        """Создание платежа (заглушка или реальная интеграция)"""
        try:
            # Пробуем импортировать реальный модуль
            from payment import create_payment as create_yookassa_payment
            payment_id, payment_url = create_yookassa_payment(user_id, amount, description)
            logger.info(f"✅ Создан платеж через ЮKassa: {payment_id}")
        except ImportError:
            # Заглушка для тестирования
            import uuid
            payment_id = f"demo_{uuid.uuid4().hex[:16]}"
            payment_url = f"https://yoomoney.ru/checkout/payments/v2/contract?orderId={payment_id}"
            logger.info(f"✅ Создан демо-платеж: {payment_id}")
        except Exception as e:
            logger.error(f"Ошибка создания платежа: {e}")
            payment_id = f"error_{int(time.time())}"
            payment_url = "https://yoomoney.ru"
        
        return payment_id, payment_url
    
    @staticmethod
    def check_payment(payment_id):
        """Проверка статуса платежа"""
        try:
            from payment import check_payment_with_details
            result = check_payment_with_details(payment_id)
            if result and 'status' in result:
                return result['status']
        except ImportError:
            # Для демо: рандомно возвращаем успешный статус
            import random
            return 'succeeded' if random.random() > 0.5 else 'pending'
        except Exception as e:
            logger.error(f"Ошибка проверки платежа: {e}")
        
        return 'unknown'

# ============== АВТОПРОВЕРКА ПЛАТЕЖЕЙ ==============
class PaymentProcessor:
    """Автоматическая обработка платежей"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.running = True
        self.check_interval = 60  # 60 секунд
    
    def process_payments(self):
        """Обработка всех pending платежей"""
        try:
            pending_payments = get_pending_payments()
            
            for payment_id, user_id, period_days in pending_payments:
                status = PaymentSystem.check_payment(payment_id)
                
                if status == 'succeeded':
                    # Активируем подписку
                    add_subscription_to_db(user_id, period_days)
                    update_payment_status(payment_id, 'succeeded')
                    
                    # Уведомляем пользователя
                    self.notify_user(user_id, payment_id, period_days, True)
                    
                    logger.info(f"✅ Платеж {payment_id} успешно обработан")
                    
                elif status in ['canceled', 'failed']:
                    update_payment_status(payment_id, status)
                    self.notify_user(user_id, payment_id, period_days, False)
                    
        except Exception as e:
            logger.error(f"Ошибка в process_payments: {e}")
    
    def notify_user(self, user_id, payment_id, period_days, success):
        """Уведомление пользователя"""
        try:
            if success:
                message = (
                    f"🎉 *ОПЛАТА ПОДТВЕРЖДЕНА!*\n\n"
                    f"✅ Ваша подписка активирована на {period_days} дней\n"
                    f"📋 ID платежа: `{payment_id[:12]}...`\n\n"
                    "✨ *Теперь вам доступны:*\n"
                    "• 🌟 Персональная техника на каждый день\n"
                    "• 📚 Полная библиотека практик\n"
                    "• 📊 Статистика и прогресс\n\n"
                    "Нажмите «🌟 ТЕХНИКА НА СЕГОДНЯ» чтобы начать!\n\n"
                    "_Спасибо, что выбрали наш сервис!_"
                )
            else:
                message = (
                    f"⚠️ *ПЛАТЕЖ НЕ ПРОШЕЛ*\n\n"
                    f"Платеж `{payment_id[:12]}...` не был завершен.\n\n"
                    "Попробуйте оплатить еще раз или обратитесь в поддержку: @avllks"
                )
            
            self.bot.send_message(user_id, message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {user_id}: {e}")
    
    def run(self):
        """Запуск процессора в отдельном потоке"""
        while self.running:
            try:
                self.process_payments()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Ошибка в PaymentProcessor: {e}")
                time.sleep(300)  # Ждем 5 минут при ошибке

# ============== ЗАГРУЗКА ТЕХНИК ==============
try:
    with open('techniques.json', 'r', encoding='utf-8') as f:
        techniques = json.load(f)
    logger.info(f"✅ Загружено {len(techniques)} категорий техник")
except:
    logger.error("❌ Файл techniques.json не найден! Создаю демо-данные...")
    techniques = {
        "Дыхательные практики": [
            {
                "name": "Дыхание 4-7-8",
                "description": "Вдох на 4 счета, задержка на 7, выдох на 8.",
                "time": "5 минут",
                "tip": "Делайте утром для спокойного дня."
            }
        ]
    }

# ============== КЛАВИАТУРЫ ==============
main_menu_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
main_menu_keyboard.row("🌟 ТЕХНИКА НА СЕГОДНЯ")
main_menu_keyboard.row("ℹ️ О ПРОЕКТЕ")
main_menu_keyboard.row("💰 ПОДПИСКА", "👤 МОЙ ПРОФИЛЬ")

subscription_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
subscription_keyboard.row("💰 КУПИТЬ ПОДПИСКУ")
subscription_keyboard.row("📊 ИНФОРМАЦИЯ О ПОДПИСКЕ")
subscription_keyboard.row("🔙 НАЗАД В ГЛАВНОЕ МЕНЮ")

tariff_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
tariff_keyboard.add(
    "📅 1 МЕСЯЦ - 99₽",
    "📅 3 МЕСЯЦА - 269₽",
    "📅 12 МЕСЯЦЕВ - 799₽",
    "🔙 НАЗАД В МЕНЮ ПОДПИСКИ"
)

back_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
back_keyboard.row("🔙 НАЗАД В ГЛАВНОЕ МЕНЮ")

# ============== ОБРАБОТЧИКИ ==============
@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Приветственное сообщение"""
    user_id = message.from_user.id
    username = message.from_user.username or "Пользователь"
    first_name = message.from_user.first_name or username
    
    add_user_to_db(user_id, username, first_name)
    
    welcome_text = (
        f"🌟 Привет, {first_name}!\n\n"
        "Я — твой личный помощник в борьбе с выгоранием.\n\n"
        "✨ Что я умею:\n"
        "• Подбирать технику на каждый день\n"
        "• Хранить библиотеку анти-выгорательных практик\n"
        "• Помогать отслеживать твое состояние\n\n"
        "Выбери, что тебя интересует:"
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu_keyboard)

@bot.message_handler(func=lambda message: message.text == "🌟 ТЕХНИКА НА СЕГОДНЯ")
def daily_technique(message):
    """Техника на сегодня"""
    user_id = message.from_user.id
    
    if not check_subscription_in_db(user_id):
        bot.send_message(
            message.chat.id,
            "🔒 *Эта функция доступна только по подписке!*\n\n"
            "✨ *Преимущества подписки:*\n"
            "• Персональная техника на каждый день\n"
            "• Доступ к полной библиотеке\n"
            "• Прогресс и статистика\n\n"
            "💎 *Тарифы:*\n"
            "• 1 месяц - 99₽\n"
            "• 3 месяца - 269₽\n"
            "• 12 месяцев - 799₽\n\n"
            "Нажмите '💰 ПОДПИСКА' для оформления.",
            reply_markup=main_menu_keyboard,
            parse_mode='Markdown'
        )
        return
    
    # Если подписка есть
    if techniques:
        category = random.choice(list(techniques.keys()))
        technique = random.choice(techniques[category])
        
        response = (
            f"🌟 *ТЕХНИКА НА СЕГОДНЯ*\n\n"
            f"📁 *Категория:* {category}\n"
            f"🎯 *Название:* {technique['name']}\n\n"
            f"📝 *Описание:*\n{technique['description']}\n\n"
            f"⏱ *Время выполнения:* {technique.get('time', '5-10 минут')}\n\n"
            f"💡 *Совет:* {technique.get('tip', 'Выполняйте технику осознанно.')}"
        )
    else:
        response = "📚 Техники временно недоступны. Мы работаем над этим!"
    
    bot.send_message(message.chat.id, response, reply_markup=back_keyboard, parse_mode='Markdown')
    update_user_stats_in_db(user_id, 'daily_techniques')

@bot.message_handler(func=lambda message: message.text == "💰 ПОДПИСКА")
def subscription_menu(message):
    """Меню подписки"""
    user_id = message.from_user.id
    
    has_subscription = check_subscription_in_db(user_id)
    
    if has_subscription:
        # Получаем информацию о подписке
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT subscription_end FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            try:
                end_date = datetime.strptime(result[0], '%Y-%m-%d').date()
            except:
                end_date = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').date()
            
            today = datetime.now().date()
            days_left = (end_date - today).days
            
            if days_left > 0:
                response = (
                    f"💰 *ВАША ПОДПИСКА*\n\n"
                    f"✅ *Статус:* АКТИВНА\n"
                    f"📅 *Дней осталось:* {days_left}\n"
                    f"🏁 *Действует до:* {end_date.strftime('%d.%m.%Y')}\n\n"
                    f"✨ *Доступно:*\n"
                    f"• 🌟 Техника на каждый день\n"
                    f"• 📚 Полная библиотека\n"
                    f"• 📊 Статистика"
                )
            else:
                response = "❌ Ваша подписка истекла. Продлите ее!"
        else:
            response = "✅ Ваша подписка активна!"
    else:
        response = (
            f"💰 *ПОДПИСКА*\n\n"
            f"❌ *Статус:* НЕ АКТИВНА\n\n"
            f"✨ *Преимущества подписки:*\n"
            f"• 🌟 Персональная техника на каждый день\n"
            f"• 📚 Доступ ко всем техникам\n"
            f"• 📊 Отслеживание прогресса\n\n"
            f"💎 *Стоимость:*\n"
            f"• 1 месяц - 99₽\n"
            f"• 3 месяца - 269₽\n"
            f"• 12 месяцев - 799₽\n\n"
            f"Нажмите '💰 КУПИТЬ ПОДПИСКУ' для оформления."
        )
    
    bot.send_message(message.chat.id, response, reply_markup=subscription_keyboard, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "💰 КУПИТЬ ПОДПИСКУ")
def buy_subscription(message):
    """Начало покупки подписки"""
    user_id = message.from_user.id
    
    if check_subscription_in_db(user_id):
        bot.send_message(
            message.chat.id,
            "⚠️ У вас уже есть активная подписка!\n\n"
            "Вы можете продлить ее после окончания текущего периода.\n"
            "Проверьте срок действия в вашем профиле.",
            reply_markup=subscription_keyboard
        )
        return
    
    response = (
        "💰 *ВЫБЕРИТЕ ТАРИФ ПОДПИСКИ:*\n\n"
        "📅 *1 МЕСЯЦ - 99₽*\n"
        "• Ежедневные техники\n"
        "• Полный доступ\n\n"
        "📅 *3 МЕСЯЦА - 269₽*\n"
        "• Экономия 28₽\n"
        "• Все преимущества\n\n"
        "📅 *12 МЕСЯЦЕВ - 799₽*\n"
        "• Экономия 389₽\n"
        "• Максимальная выгода\n\n"
        "Выберите вариант:"
    )
    
    bot.send_message(message.chat.id, response, reply_markup=tariff_keyboard, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text in ["📅 1 МЕСЯЦ - 99₽", "📅 3 МЕСЯЦА - 269₽", "📅 12 МЕСЯЦЕВ - 799₽"])
def create_subscription_payment(message):
    """Создание платежа"""
    user_id = message.from_user.id
    
    # Определяем выбранный тариф
    tariff_map = {
        "📅 1 МЕСЯЦ - 99₽": {"amount": 99.00, "days": 30, "description": "Подписка на 1 месяц"},
        "📅 3 МЕСЯЦА - 269₽": {"amount": 269.00, "days": 90, "description": "Подписка на 3 месяца"},
        "📅 12 МЕСЯЦЕВ - 799₽": {"amount": 799.00, "days": 365, "description": "Подписка на 12 месяцев"}
    }
    
    tariff = tariff_map[message.text]
    
    # Создаем платеж
    payment_id, payment_url = PaymentSystem.create_payment(
        user_id=user_id,
        amount=tariff["amount"],
        description=tariff["description"]
    )
    
    # Сохраняем платеж в БД
    save_payment_to_db(user_id, payment_id, tariff["amount"], tariff["days"])
    
    # Отправляем пользователю ссылку для оплаты
    response = (
        f"💳 *ОПЛАТА ПОДПИСКИ*\n\n"
        f"📋 *Тариф:* {message.text}\n"
        f"💰 *Сумма:* {tariff['amount']:.0f}₽\n"
        f"📅 *Срок:* {tariff['days']} дней\n\n"
        f"👉 *Для оплаты перейдите по ссылке:*\n{payment_url}\n\n"
        f"✅ *После успешной оплаты:*\n"
        f"• Подписка активируется автоматически\n"
        f"• Вы получите уведомление\n"
        f"• Сразу откроется доступ к техникам\n\n"
        f"🔍 *Проверить статус оплаты:* /check_payment\n\n"
        f"📋 *ID платежа:* `{payment_id}`"
    )
    
    bot.send_message(message.chat.id, response, reply_markup=back_keyboard, parse_mode='Markdown')

@bot.message_handler(commands=['check_payment'])
def check_payment_command(message):
    """Проверка платежа"""
    user_id = message.from_user.id
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT payment_id, status FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    )
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        bot.send_message(message.chat.id, "❌ У вас нет платежей.")
        return
    
    payment_id, status = result
    
    if status == 'succeeded':
        # Проверяем, активирована ли подписка
        if check_subscription_in_db(user_id):
            response = (
                f"✅ *ПЛАТЕЖ УСПЕШЕН!*\n\n"
                f"📋 ID: `{payment_id[:12]}...`\n"
                f"🎉 *Подписка активна!*\n\n"
                f"Теперь вам доступны все функции бота!\n"
                f"Нажмите «🌟 ТЕХНИКА НА СЕГОДНЯ»"
            )
        else:
            # Если платеж успешен, но подписка не активирована - активируем
            cursor.execute("SELECT period_days FROM payments WHERE payment_id = ?", (payment_id,))
            period_result = cursor.fetchone()
            if period_result:
                add_subscription_to_db(user_id, period_result[0])
                response = f"✅ Подписка активирована! Теперь доступны все функции."
    
    elif status == 'pending':
        # Проверяем текущий статус
        current_status = PaymentSystem.check_payment(payment_id)
        
        if current_status == 'succeeded':
            # Находим период и активируем
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            cursor.execute("SELECT period_days FROM payments WHERE payment_id = ?", (payment_id,))
            period_result = cursor.fetchone()
            if period_result:
                add_subscription_to_db(user_id, period_result[0])
                update_payment_status(payment_id, 'succeeded')
                response = f"🎉 *Платеж подтвержден! Подписка активирована!*"
            conn.close()
        else:
            response = (
                f"⏳ *ПЛАТЕЖ В ОБРАБОТКЕ*\n\n"
                f"📋 ID: `{payment_id[:12]}...`\n\n"
                f"Пожалуйста, подождите несколько минут.\n"
                f"Обычно обработка занимает 1-2 минуты.\n\n"
                f"Если прошло более 10 минут, напишите в поддержку: @avllks"
            )
    else:
        response = f"❌ Платеж не прошел. Статус: {status}"
    
    bot.send_message(message.chat.id, response, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "👤 МОЙ ПРОФИЛЬ")
def user_profile(message):
    """Профиль пользователя"""
    user_id = message.from_user.id
    stats = get_user_stats_from_db(user_id)
    has_subscription = check_subscription_in_db(user_id)
    
    subscription_status = "✅ Активна" if has_subscription else "❌ Не активна"
    
    response = (
        f"👤 *ВАШ ПРОФИЛЬ*\n\n"
        f"🆔 ID: {user_id}\n"
        f"👤 Имя: {message.from_user.first_name}\n"
        f"📊 Подписка: {subscription_status}\n\n"
        f"📈 *СТАТИСТИКА:*\n"
        f"• Техник выполнено: {stats.get('daily_techniques', 0)}\n"
        f"• Дней с ботом: {stats.get('days_with_bot', 1)}\n"
        f"• Активность: {stats.get('activity_score', 0)} баллов\n\n"
        f"🎯 *Цель:* Заботиться о себе каждый день!"
    )
    
    bot.send_message(message.chat.id, response, reply_markup=back_keyboard, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "🔙 НАЗАД В ГЛАВНОЕ МЕНЮ")
def back_to_main(message):
    """Возврат в главное меню"""
    bot.send_message(message.chat.id, "Вы вернулись в главное меню:", reply_markup=main_menu_keyboard)

@bot.message_handler(func=lambda message: message.text == "🔙 НАЗАД В МЕНЮ ПОДПИСКИ")
def back_to_subscription(message):
    """Возврат в меню подписки"""
    subscription_menu(message)

@bot.message_handler(func=lambda message: message.text == "ℹ️ О ПРОЕКТЕ")
def about_project(message):
    """Информация о проекте"""
    response = (
        "ℹ️ *О ПРОЕКТЕ*\n\n"
        "🤖 *Анти-выгорание Бот*\n\n"
        "Миссия: Помогать людям справляться с эмоциональным выгоранием и стрессом через простые и эффективные техники.\n\n"
        "📞 *Контакты:*\n"
        "По вопросам и предложениям: @avllks\n\n"
        "💖 *Помни:* Забота о себе - это не роскошь, а необходимость!"
    )
    
    bot.send_message(message.chat.id, response, reply_markup=back_keyboard, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "📊 ИНФОРМАЦИЯ О ПОДПИСКЕ")
def subscription_info(message):
    """Информация о подписке"""
    response = (
        "📊 *ИНФОРМАЦИЯ О ПОДПИСКЕ*\n\n"
        "💎 *Тарифы:*\n"
        "• 1 месяц: 99₽\n"
        "• 3 месяца: 269₽ (экономия 28₽)\n"
        "• 12 месяцев: 799₽ (экономия 389₽)\n\n"
        "✨ *Что входит:*\n"
        "✅ Персональные техники на каждый день\n"
        "✅ Полный доступ к библиотеке\n"
        "✅ Статистика и прогресс\n"
        "✅ Поддержка и советы\n\n"
        "🔄 Автопродление можно отключить в любой момент."
    )
    bot.send_message(message.chat.id, response, reply_markup=subscription_keyboard, parse_mode='Markdown')

@bot.message_handler(commands=['check_sub'])
def check_subscription_command(message):
    """Команда проверки подписки"""
    user_id = message.from_user.id
    
    if check_subscription_in_db(user_id):
        bot.send_message(message.chat.id, "✅ Ваша подписка активна!")
    else:
        bot.send_message(
            message.chat.id,
            "❌ Подписка не активна\n\n"
            "Оформите подписку для доступа к полному функционалу бота.",
            reply_markup=subscription_keyboard
        )

# ============== АДМИН КОМАНДЫ ==============
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    """Панель администратора"""
    if str(message.from_user.id) != ADMIN_ID:
        return
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        types.InlineKeyboardButton("🔍 Проверить платежи", callback_data="admin_check_payments"),
        types.InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"),
        types.InlineKeyboardButton("🔄 Запустить проверку", callback_data="admin_run_check")
    )
    
    bot.send_message(
        message.chat.id,
        "👨‍💼 *Панель администратора*\n\nВыберите действие:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callback(call):
    """Обработка админ-кнопок"""
    if str(call.from_user.id) != ADMIN_ID:
        return
    
    if call.data == "admin_stats":
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE subscription_end >= date('now')")
        active_subs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM payments")
        total_payments = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
        pending_payments = cursor.fetchone()[0]
        
        conn.close()
        
        bot.send_message(
            call.message.chat.id,
            f"📈 *Статистика бота*\n\n"
            f"• 👥 Всего пользователей: {total_users}\n"
            f"• ✅ Активных подписок: {active_subs}\n"
            f"• 💰 Всего платежей: {total_payments}\n"
            f"• ⏳ Ожидающих платежей: {pending_payments}\n\n"
            f"• 🕐 Время: {datetime.now().strftime('%H:%M:%S')}",
            parse_mode='Markdown'
        )
    
    elif call.data == "admin_check_payments":
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT payment_id, user_id, amount, status FROM payments ORDER BY created_at DESC LIMIT 10")
        payments = cursor.fetchall()
        conn.close()
        
        if payments:
            text = "📋 *Последние 10 платежей:*\n\n"
            for p in payments:
                status_icon = "✅" if p[3] == 's