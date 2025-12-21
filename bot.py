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
    print("Создайте файл .env с содержимым:")
    print("BOT_TOKEN=ваш_токен_бота")
    print("ADMIN_ID=ваш_телеграм_id")
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
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ============== БАЗА ДАННЫХ ==============
def init_database():
    """Инициализация базы данных"""
    conn = sqlite3.connect('users.db')
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

# Функции для работы с БД
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
        
        subscription_end = datetime.strptime(result[0], '%Y-%m-%d').date()
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
            created_at = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
            days_with_bot = (datetime.now() - created_at).days + 1
            stats_dict['days_with_bot'] = days_with_bot
        
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
               DO UPDATE SET stat_value = stat_value + 1, updated_at = CURRENT_TIMESTAMP""",
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
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления подписки: {e}")
        return False
    finally:
        conn.close()

# ============== ЗАГРУЗКА ТЕХНИК ==============
try:
    with open('techniques.json', 'r', encoding='utf-8') as f:
        techniques = json.load(f)
    logger.info(f"✅ Загружено {len(techniques)} категорий техник")
except FileNotFoundError:
    logger.error("❌ Файл techniques.json не найден! Создаю демо-данные...")
    techniques = {
        "Дыхательные практики": [
            {
                "name": "Дыхание 4-7-8",
                "description": "Вдох на 4 счета, задержка на 7, выдох на 8. Повторить 4 раза.",
                "time": "5 минут",
                "tip": "Делайте утром для спокойного дня."
            },
            {
                "name": "Диафрагмальное дыхание",
                "description": "Дышите животом, а не грудью. Медленно и глубоко.",
                "time": "3-5 минут",
                "tip": "Положите руку на живот для контроля."
            }
        ],
        "Медитации": [
            {
                "name": "Медитация осознанности",
                "description": "Сосредоточьтесь на дыхании, наблюдайте мысли без оценки.",
                "time": "10 минут",
                "tip": "Начинайте с 3-5 минут и увеличивайте постепенно."
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

# ============== ОСНОВНЫЕ ОБРАБОТЧИКИ ==============
@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Приветственное сообщение"""
    user_id = message.from_user.id
    username = message.from_user.username or "Пользователь"
    first_name = message.from_user.first_name or username
    
    # Добавляем пользователя в БД
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
    logger.info(f"👤 Пользователь {user_id} ({username}) начал работу с ботом")

@bot.message_handler(commands=['help'])
def send_help(message):
    """Справка по командам"""
    help_text = (
        "🤖 *СПИСОК КОМАНД*\n\n"
        "Основные:\n"
        "`/start` - Запустить бота\n"
        "`/help` - Эта справка\n"
        "`/profile` - Ваш профиль\n"
        "`/check_sub` - Проверить подписку\n"
        "`/check_payment` - Проверить платеж\n\n"
        "Для администратора:\n"
        "`/admin` - Панель управления\n"
        "`/allpayments` - Все платежи\n"
        "`/dbcheck` - Проверка БД\n\n"
        "💎 Подписка открывает доступ к ежедневным техникам!"
    )
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "🌟 ТЕХНИКА НА СЕГОДНЯ")
def daily_technique(message):
    """Выдача техники на сегодня"""
    user_id = message.from_user.id
    
    # Проверяем подписку
    if not check_subscription_in_db(user_id):
        bot.send_message(
            message.chat.id,
            "🔒 Эта функция доступна только по подписке!\n\n"
            "Оформите подписку, чтобы получать:\n"
            "• Персональную технику на каждый день\n"
            "• Доступ к полной библиотеке\n"
            "• Прогресс и статистику\n\n"
            "Нажмите '💰 ПОДПИСКА' для оформления.",
            reply_markup=main_menu_keyboard
        )
        return
    
    # Получаем случайную технику
    if techniques:
        category = random.choice(list(techniques.keys()))
        technique = random.choice(techniques[category])
        
        response = (
            f"🌟 ТЕХНИКА НА СЕГОДНЯ\n\n"
            f"📁 Категория: {category}\n"
            f"🎯 Название: {technique['name']}\n\n"
            f"📝 Описание:\n{technique['description']}\n\n"
            f"⏱ Время выполнения: {technique.get('time', '5-10 минут')}\n\n"
            f"💡 Совет: {technique.get('tip', 'Выполняйте технику осознанно.')}"
        )
    else:
        response = "📚 Техники временно недоступны. Мы работаем над этим!"
    
    bot.send_message(message.chat.id, response, reply_markup=back_keyboard)
    
    # Обновляем статистику
    update_user_stats_in_db(user_id, 'daily_techniques')

@bot.message_handler(func=lambda message: message.text == "ℹ️ О ПРОЕКТЕ")
def about_project(message):
    """Информация о проекте"""
    response = (
        "ℹ️ О ПРОЕКТЕ\n\n"
        "🤖 Анти-выгорание Бот\n\n"
        "Миссия: Помогать людям справляться с эмоциональным выгоранием и стрессом через простые и эффективные техники.\n\n"
        "📞 Контакты:\n"
        "По вопросам и предложениям: @avllks\n\n"
        "💖 Помни: Забота о себе - это не роскошь, а необходимость!"
    )
    
    bot.send_message(message.chat.id, response, reply_markup=back_keyboard)

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
            end_date = datetime.strptime(result[0], '%Y-%m-%d').date()
            today = datetime.now().date()
            days_left = (end_date - today).days
            
            response = (
                f"💰 ВАША ПОДПИСКА\n\n"
                f"✅ Статус: АКТИВНА\n"
                f"📅 Дней осталось: {days_left}\n"
                f"🏁 Действует до: {end_date.strftime('%d.%m.%Y')}\n\n"
                f"Что дает подписка:\n"
                f"• 🌟 Техника на каждый день\n"
                f"• 📚 Полная библиотека техник\n"
            )
        else:
            response = "✅ Ваша подписка активна!"
    else:
        response = (
            f"💰 ПОДПИСКА\n\n"
            f"❌ Статус: НЕ АКТИВНА\n\n"
            f"✨ Преимущества подписки:\n"
            f"• 🌟 Персональная техника на каждый день\n"
            f"• 📚 Доступ ко всем техникам\n"
            f"• 📊 Отслеживание прогресса\n\n"
            f"💎 Стоимость: 99₽/месяц\n\n"
            f"Нажмите '💰 КУПИТЬ ПОДПИСКУ' для оформления."
        )
    
    bot.send_message(message.chat.id, response, reply_markup=subscription_keyboard)

@bot.message_handler(func=lambda message: message.text == "👤 МОЙ ПРОФИЛЬ")
def user_profile(message):
    """Профиль пользователя"""
    user_id = message.from_user.id
    stats = get_user_stats_from_db(user_id)
    has_subscription = check_subscription_in_db(user_id)
    
    subscription_status = "✅ Активна" if has_subscription else "❌ Не активна"
    
    response = (
        f"👤 ВАШ ПРОФИЛЬ\n\n"
        f"🆔 ID: {user_id}\n"
        f"👤 Имя: {message.from_user.first_name}\n"
        f"📊 Подписка: {subscription_status}\n\n"
        f"📈 ВАША СТАТИСТИКА:\n"
        f"• Техник выполнено: {stats.get('daily_techniques', 0)}\n"
        f"• Дней с ботом: {stats.get('days_with_bot', 1)}\n"
        f"• Активность: {stats.get('activity_score', 0)} баллов\n\n"
        f"🎯 Цель: Заботиться о себе каждый день!"
    )
    
    bot.send_message(message.chat.id, response, reply_markup=back_keyboard)

@bot.message_handler(func=lambda message: message.text == "💰 КУПИТЬ ПОДПИСКУ")
def buy_subscription(message):
    """Начало покупки подписки"""
    user_id = message.from_user.id
    
    # Проверяем, есть ли уже активная подписка
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
        "💰 ВЫБЕРИТЕ ТАРИФ ПОДПИСКИ:\n\n"
        "📅 1 МЕСЯЦ - 99₽\n"
        "• Ежедневные техники\n"
        "• Полный доступ\n\n"
        "📅 3 МЕСЯЦА - 269₽\n"
        "• Экономия 28₽\n"
        "• Все преимущества\n\n"
        "📅 12 МЕСЯЦЕВ - 799₽\n"
        "• Экономия 389₽\n"
        "• Максимальная выгода\n\n"
        "Выберите вариант:"
    )
    
    bot.send_message(message.chat.id, response, reply_markup=tariff_keyboard)

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
    
    # Пытаемся импортировать функцию создания платежа
    try:
        from payment import create_payment
        payment_id, payment_url = create_payment(
            user_id=user_id,
            amount=tariff["amount"],
            description=tariff["description"]
        )
    except ImportError:
        # Заглушка для тестирования
        payment_id = f"test_{user_id}_{int(time.time())}"
        payment_url = "https://yookassa.ru/demo"
    
    # Сохраняем платеж в БД
    save_payment_to_db(user_id, payment_id, tariff["amount"], tariff["days"])
    
    # Отправляем пользователю ссылку для оплаты
    response = (
        f"💳 ОПЛАТА ПОДПИСКИ\n\n"
        f"Тариф: {message.text}\n"
        f"Сумма: {tariff['amount']:.0f}₽\n"
        f"Срок: {tariff['days']} дней\n\n"
        f"👉 Для оплаты перейдите по ссылке:\n{payment_url}\n\n"
        f"После успешной оплаты подписка активируется автоматически.\n"
        f"Обычно это занимает 1-2 минуты.\n\n"
        f"🔍 Проверить статус оплаты: /check_payment\n\n"
        f"ID платежа: `{payment_id}`"
    )
    
    bot.send_message(message.chat.id, response, reply_markup=back_keyboard, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "📊 ИНФОРМАЦИЯ О ПОДПИСКЕ")
def subscription_info(message):
    """Информация о подписке"""
    response = (
        "📊 ИНФОРМАЦИЯ О ПОДПИСКЕ\n\n"
        "💎 Тарифы:\n"
        "• 1 месяц: 99₽\n"
        "• 3 месяца: 269₽ (экономия 28₽)\n"
        "• 12 месяцев: 799₽ (экономия 389₽)\n\n"
        "✨ Что входит:\n"
        "✅ Персональные техники на каждый день\n"
        "✅ Полный доступ к библиотеке\n"
        "✅ Статистика и прогресс\n"
        "✅ Поддержка и советы\n\n"
        "🔄 Автопродление можно отключить в любой момент."
    )
    bot.send_message(message.chat.id, response, reply_markup=subscription_keyboard)

@bot.message_handler(func=lambda message: message.text == "🔙 НАЗАД В ГЛАВНОЕ МЕНЮ")
def back_to_main(message):
    """Возврат в главное меню"""
    response = "Вы вернулись в главное меню. Выберите действие:"
    bot.send_message(message.chat.id, response, reply_markup=main_menu_keyboard)

@bot.message_handler(func=lambda message: message.text == "🔙 НАЗАД В МЕНЮ ПОДПИСКИ")
def back_to_subscription(message):
    """Возврат в меню подписки"""
    subscription_menu(message)

@bot.message_handler(commands=['check_sub'])
def check_subscription_command(message):
    """Проверка подписки"""
    user_id = message.from_user.id
    
    if check_subscription_in_db(user_id):
        bot.send_message(message.chat.id, "✅ Ваша подписка активна!")
    else:
        bot.send_message(message.chat.id, "❌ Подписка не активна")

@bot.message_handler(commands=['check_payment'])
def check_payment_command(message):
    """Проверка последнего платежа"""
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
        bot.send_message(
            message.chat.id,
            f"✅ Ваш платеж успешно обработан!\nID: `{payment_id[:12]}...`\n\n"
            f"Подписка активирована. Наслаждайтесь использованием бота!",
            parse_mode='Markdown'
        )
    elif status == 'pending':
        bot.send_message(
            message.chat.id,
            f"⏳ Платеж обрабатывается...\nID: `{payment_id[:12]}...`\n\n"
            f"Если прошло более 5 минут, напишите в поддержку: @avllks",
            parse_mode='Markdown'
        )
    else:
        bot.send_message(
            message.chat.id,
            f"❌ Платеж не прошел.\nСтатус: {status}\n\n"
            f"Попробуйте оформить подписку заново.",
            parse_mode='Markdown'
        )

# ============== АДМИН КОМАНДЫ ==============
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    """Панель администратора"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ У вас нет доступа к этой команде.")
        return
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        types.InlineKeyboardButton("🔍 Проверить платежи", callback_data="admin_check_payments"),
        types.InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"),
        types.InlineKeyboardButton("🔄 Обновить БД", callback_data="admin_refresh_db")
    )
    
    bot.send_message(
        message.chat.id,
        "👨‍💼 *Панель администратора*\n\n"
        "Выберите действие:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callback(call):
    """Обработка админ-кнопок"""
    if str(call.from_user.id) != ADMIN_ID:
        bot.answer_callback_query(call.id, "⛔ Нет доступа")
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
        
        cursor.execute("SELECT SUM(amount) FROM payments WHERE status = 'succeeded'")
        total_revenue = cursor.fetchone()[0] or 0
        
        conn.close()
        
        bot.send_message(
            call.message.chat.id,
            f"📈 *Статистика бота*\n\n"
            f"• 👥 Всего пользователей: {total_users}\n"
            f"• ✅ Активных подписок: {active_subs}\n"
            f"• 💰 Всего платежей: {total_payments}\n"
            f"• 💎 Выручка: {total_revenue:.2f}₽\n\n"
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
                status_icon = "✅" if p[3] == 'succeeded' else "🔄" if p[3] == 'pending' else "❌"
                text += f"{status_icon} `{p[0][:12]}...`\n"
                text += f"👤 {p[1]} | 💰 {p[2]}₽ | {p[3]}\n\n"
        else:
            text = "🤷‍♂️ *Нет платежей*"
        
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
    
    bot.answer_callback_query(call.id)

@bot.message_handler(commands=['allpayments'])
def show_all_payments(message):
    """Показать все платежи"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ У вас нет доступа к этой команде.")
        return
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payments ORDER BY created_at DESC LIMIT 20")
    payments = cursor.fetchall()
    conn.close()
    
    text = f"📋 *Платежи (последние 20 из всех):*\n\n"
    
    if not payments:
        text += "❌ Нет платежей"
    else:
        for p in payments:
            status_icon = "✅" if p[4] == 'succeeded' else "🔄" if p[4] == 'pending' else "❌"
            text += f"{status_icon} `{p[0][:12]}...`\n"
            text += f"👤 {p[1]} | 💰 {p[2]}₽ | 📅 {p[3]}д | {p[4]}\n"
            text += f"🕐 {p[5][:19] if p[5] else ''}\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['dbcheck'])
def check_database_command(message):
    """Проверка БД"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ У вас нет доступа к этой команде.")
        return
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    text = "🗃️ *База данных:*\n\n"
    
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        text += f"• `{table[0]}` - {count} записей\n"
    
    conn.close()
    
    text += f"\n✅ База данных работает нормально"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['activate'])
def activate_subscription_command(message):
    """Ручная активация подписки"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ У вас нет доступа к этой команде.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.send_message(
                message.chat.id,
                "❌ Неверный формат\n\nИспользуйте: /activate USER_ID DAYS\nПример: /activate 123456789 30",
                parse_mode='Markdown'
            )
            return
        
        user_id = int(parts[1])
        days = int(parts[2])
        
        # Активируем подписку
        add_subscription_to_db(user_id, days)
        
        # Создаем запись о платеже
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        payment_id = f"manual_{int(time.time())}"
        cursor.execute(
            """INSERT INTO payments (payment_id, user_id, amount, period_days, status) 
               VALUES (?, ?, ?, ?, ?)""",
            (payment_id, user_id, 0.00, days, 'succeeded')
        )
        conn.commit()
        conn.close()
        
        bot.send_message(
            message.chat.id,
            f"✅ Подписка активирована!\n\n"
            f"👤 Пользователь: {user_id}\n"
            f"📅 Срок: {days} дней\n"
            f"Действует до: {(datetime.now() + timedelta(days=days)).strftime('%d.%m.%Y')}",
            parse_mode='Markdown'
        )
        
        # Уведомляем пользователя
        try:
            bot.send_message(
                user_id,
                f"🎉 ВАША ПОДПИСКА АКТИВИРОВАНА!\n\n"
                f"Администратор активировал подписку на {days} дней.\n"
                f"Теперь вам доступны все платные функции!\n\n"
                f"Нажмите «🌟 ТЕХНИКА НА СЕГОДНЯ» чтобы начать.",
                parse_mode='Markdown'
            )
        except:
            pass
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")

# ============== ЗАПУСК БОТА ==============
if __name__ == "__main__":
    logger.info("🤖 Запускаю бота...")
    print("=" * 50)
    print("🤖 Анти-Выгорание Бот")
    print(f"🔑 Токен: {'✅' if TOKEN else '❌'}")
    print(f"👨‍💼 Админ ID: {ADMIN_ID}")
    print("=" * 50)
    
    try:
        bot.polling(none_stop=True, interval=1, timeout=30)
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
        print(f"❌ Критическая ошибка: {e}")