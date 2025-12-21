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

def get_subscription_info(user_id):
    """Получение информации о подписке"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT subscription_end FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        
        if not result or not result[0]:
            return None, 0
        
        try:
            subscription_end = datetime.strptime(result[0], '%Y-%m-%d').date()
        except:
            subscription_end = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').date()
        
        today = datetime.now().date()
        days_left = (subscription_end - today).days
        
        return subscription_end, max(0, days_left)
    except Exception as e:
        logger.error(f"Ошибка получения информации о подписке: {e}")
        return None, 0
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
        logger.info(f"✅ Платеж сохранен: {payment_id} для user_id={user_id}")
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

def get_last_payment(user_id):
    """Получение последнего платежа пользователя"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT payment_id, status, period_days FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Ошибка получения платежа: {e}")
        return None
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

# ============== ЗАГРУЗКА ТЕХНИК ==============
techniques_list = []
techniques_by_type = {}

try:
    with open('techniques.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Обрабатываем новую структуру JSON
        if 'techniques' in data:
            techniques_list = data['techniques']
            # Группируем по типам для удобства
            for tech in techniques_list:
                tech_type = tech.get('type', 'другое')
                if tech_type not in techniques_by_type:
                    techniques_by_type[tech_type] = []
                techniques_by_type[tech_type].append(tech)
        else:
            # Старая структура (словарь категорий)
            techniques_by_type = data
            for category, techs in data.items():
                techniques_list.extend(techs)
    
    logger.info(f"✅ Загружено {len(techniques_list)} техник из {len(techniques_by_type)} категорий")
except Exception as e:
    logger.error(f"❌ Ошибка загрузки techniques.json: {e}")
    techniques_list = []
    techniques_by_type = {
        "дыхание": [
            {
                "name": "Дыхание 4-7-8",
                "description": "Вдох на 4 счета, задержка на 7, выдох на 8.",
                "type": "дыхание",
                "steps": ["Вдох на 4", "Задержка на 7", "Выдох на 8"],
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
    "🔙 НАЗАД"
)

back_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
back_keyboard.row("🔙 НАЗАД В ГЛАВНОЕ МЕНЮ")

# Клавиатура для выбора типа техники
technique_type_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
technique_type_keyboard.row("🫁 Дыхание", "💪 Упражнение", "🧠 Фокус")
technique_type_keyboard.row("🎲 Случайная техника")
technique_type_keyboard.row("🔙 НАЗАД В ГЛАВНОЕ МЕНЮ")

# Клавиатура для выбора состояния
state_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
state_keyboard.row("😰 Стресс/Тревога", "😴 Усталость")
state_keyboard.row("😤 Раздражение", "😵 Перегрузка")
state_keyboard.row("🎯 Нужна концентрация", "🎲 Просто техника")
state_keyboard.row("🔙 НАЗАД В ГЛАВНОЕ МЕНЮ")

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
    logger.info(f"👤 Новый пользователь: {user_id} ({username})")

@bot.message_handler(commands=['help'])
def send_help(message):
    """Помощь"""
    help_text = (
        "🤖 *Анти-Выгорание Бот*\n\n"
        "📋 *Доступные команды:*\n\n"
        "• /start - Начать работу\n"
        "• /help - Эта справка\n"
        "• /profile - Ваш профиль\n"
        "• /check_sub - Проверить подписку\n"
        "• /check_payment - Проверить платеж\n"
        "• /test_payment - Тестовая активация подписки\n\n"
        "📱 *Основные функции:*\n"
        "• 🌟 Техника на каждый день (требуется подписка)\n"
        "• 💰 Подписка на доступ ко всем техникам\n"
        "• 👤 Профиль со статистикой\n\n"
        "💎 *Подписка открывает доступ к полной библиотеке техник!*"
    )
    
    try:
        bot.send_message(message.chat.id, help_text, parse_mode='Markdown')
    except:
        # Если Markdown не работает
        help_text_simple = (
            "🤖 Анти-Выгорание Бот\n\n"
            "Доступные команды:\n"
            "/start - Начать работу\n"
            "/help - Эта справка\n"
            "/profile - Ваш профиль\n"
            "/check_sub - Проверить подписку\n"
            "/check_payment - Проверить платеж\n"
            "/test_payment - Тестовая активация\n\n"
            "Основные функции:\n"
            "• Техника на каждый день (требуется подписка)\n"
            "• Подписка на доступ ко всем техникам\n"
            "• Профиль со статистикой\n\n"
            "Подписка открывает доступ к полной библиотеке техник!"
        )
        bot.send_message(message.chat.id, help_text_simple)

@bot.message_handler(func=lambda message: message.text == "🌟 ТЕХНИКА НА СЕГОДНЯ")
def daily_technique(message):
    """Техника на сегодня - выбор типа"""
    user_id = message.from_user.id
    
    if not check_subscription_in_db(user_id):
        response = (
            "🔒 *Эта функция доступна только по подписке!*\n\n"
            "✨ *Преимущества подписки:*\n"
            "• Персональная техника на каждый день\n"
            "• Доступ к полной библиотеке\n"
            "• Прогресс и статистика\n\n"
            "💎 *Тарифы:*\n"
            "• 1 месяц - 99₽\n"
            "• 3 месяца - 269₽\n"
            "• 12 месяцев - 799₽\n\n"
            "Нажмите '💰 ПОДПИСКА' для оформления."
        )
        
        try:
            bot.send_message(message.chat.id, response, reply_markup=main_menu_keyboard, parse_mode='Markdown')
        except:
            bot.send_message(message.chat.id, 
                           "🔒 Эта функция доступна только по подписке!\n\n"
                           "Преимущества подписки:\n"
                           "• Персональная техника на каждый день\n"
                           "• Доступ к полной библиотеке\n\n"
                           "Тарифы: 1 месяц - 99₽, 3 месяца - 269₽, 12 месяцев - 799₽\n\n"
                           "Нажмите '💰 ПОДПИСКА' для оформления.",
                           reply_markup=main_menu_keyboard)
        return
    
    # Спрашиваем, какую технику выбрать
    response = (
        "🌟 *ЧТО ВАМ НУЖНО СЕЙЧАС?*\n\n"
        "Выберите тип техники или ваше состояние:\n\n"
        "🫁 *Дыхание* - для успокоения и расслабления\n"
        "💪 *Упражнение* - для снятия физического напряжения\n"
        "🧠 *Фокус* - для концентрации и ментального баланса\n"
        "🎲 *Случайная* - доверьтесь выбору бота"
    )
    
    try:
        bot.send_message(message.chat.id, response, reply_markup=technique_type_keyboard, parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id,
                        "🌟 ЧТО ВАМ НУЖНО СЕЙЧАС?\n\n"
                        "Выберите тип техники:\n\n"
                        "🫁 Дыхание - для успокоения\n"
                        "💪 Упражнение - для снятия напряжения\n"
                        "🧠 Фокус - для концентрации\n"
                        "🎲 Случайная - доверьтесь выбору бота",
                        reply_markup=technique_type_keyboard)

def send_technique(message, tech_type=None):
    """Отправка техники пользователю"""
    if not techniques_list:
        bot.send_message(message.chat.id, "📚 Техники временно недоступны. Мы работаем над этим!", reply_markup=back_keyboard)
        return
    
    # Выбираем технику
    if tech_type:
        # Фильтруем по типу
        filtered_techniques = [t for t in techniques_list if t.get('type') == tech_type]
        if filtered_techniques:
            technique = random.choice(filtered_techniques)
        else:
            technique = random.choice(techniques_list)
    else:
        # Случайная техника
        technique = random.choice(techniques_list)
    
    tech_type = technique.get('type', 'другое')
    
    # Формируем название категории
    type_names = {
        'дыхание': '🫁 Дыхательные практики',
        'упражнение': '💪 Физические упражнения',
        'фокус': '🧠 Ментальные техники'
    }
    category_name = type_names.get(tech_type, f'📚 {tech_type.capitalize()}')
    
    # Формируем шаги
    steps_text = ""
    if 'steps' in technique and technique['steps']:
        steps_text = "\n\n📋 *Шаги выполнения:*\n"
        for i, step in enumerate(technique['steps'], 1):
            steps_text += f"{i}. {step}\n"
    
    response = (
        f"🌟 *ТЕХНИКА НА СЕГОДНЯ*\n\n"
        f"📁 *Категория:* {category_name}\n"
        f"🎯 *Название:* {technique['name']}\n\n"
        f"📝 *Описание:*\n{technique['description']}"
        f"{steps_text}\n"
        f"💡 *Совет:* {technique.get('tip', 'Выполняйте осознанно.')}"
    )
    
    try:
        bot.send_message(message.chat.id, response, reply_markup=back_keyboard, parse_mode='Markdown')
    except:
        # Упрощенная версия без Markdown
        steps_text = ""
        if 'steps' in technique and technique['steps']:
            steps_text = "\n\n📋 Шаги выполнения:\n"
            for i, step in enumerate(technique['steps'], 1):
                steps_text += f"{i}. {step}\n"
        
        simple_response = (
            f"🌟 ТЕХНИКА НА СЕГОДНЯ\n\n"
            f"📁 Категория: {category_name}\n"
            f"🎯 Название: {technique['name']}\n\n"
            f"📝 Описание:\n{technique['description']}"
            f"{steps_text}\n"
            f"💡 Совет: {technique.get('tip', 'Выполняйте осознанно.')}"
        )
        bot.send_message(message.chat.id, simple_response, reply_markup=back_keyboard)

@bot.message_handler(func=lambda message: message.text in ["🫁 Дыхание", "💪 Упражнение", "🧠 Фокус", "🎲 Случайная техника"])
def choose_technique_type(message):
    """Обработка выбора типа техники"""
    user_id = message.from_user.id
    
    if not check_subscription_in_db(user_id):
        bot.send_message(message.chat.id, "🔒 Эта функция доступна только по подписке!", reply_markup=main_menu_keyboard)
        return
    
    type_map = {
        "🫁 Дыхание": "дыхание",
        "💪 Упражнение": "упражнение",
        "🧠 Фокус": "фокус",
        "🎲 Случайная техника": None
    }
    
    tech_type = type_map.get(message.text)
    send_technique(message, tech_type)

@bot.message_handler(func=lambda message: message.text == "💰 ПОДПИСКА")
def subscription_menu(message):
    """Меню подписки"""
    user_id = message.from_user.id
    
    has_subscription = check_subscription_in_db(user_id)
    
    if has_subscription:
        # Получаем информацию о подписке
        subscription_end, days_left = get_subscription_info(user_id)
        
        if subscription_end:
            response = (
                "💰 *ВАША ПОДПИСКА*\n\n"
                f"✅ *Статус:* АКТИВНА\n"
                f"📅 *Дней осталось:* {days_left}\n"
                f"🏁 *Действует до:* {subscription_end.strftime('%d.%m.%Y')}\n\n"
                "✨ *Доступно:*\n"
                "• 🌟 Техника на каждый день\n"
                "• 📚 Полная библиотека\n"
                "• 📊 Статистика и прогресс"
            )
        else:
            response = "✅ Ваша подписка активна!"
    else:
        response = (
            "💰 *ПОДПИСКА*\n\n"
            "❌ *Статус:* НЕ АКТИВНА\n\n"
            "✨ *Преимущества подписки:*\n"
            "• 🌟 Персональная техника на каждый день\n"
            "• 📚 Доступ ко всем техникам\n"
            "• 📊 Отслеживание прогресса\n\n"
            "💎 *Стоимость:*\n"
            "• 1 месяц - 99₽\n"
            "• 3 месяца - 269₽\n"
            "• 12 месяцев - 799₽\n\n"
            "Нажмите '💰 КУПИТЬ ПОДПИСКУ' для оформления."
        )
    
    try:
        bot.send_message(message.chat.id, response, reply_markup=subscription_keyboard, parse_mode='Markdown')
    except:
        # Упрощенная версия без Markdown
        if has_subscription:
            subscription_end, days_left = get_subscription_info(user_id)
            if subscription_end:
                simple_response = (
                    f"💰 ВАША ПОДПИСКА\n\n"
                    f"✅ Статус: АКТИВНА\n"
                    f"📅 Дней осталось: {days_left}\n"
                    f"🏁 Действует до: {subscription_end.strftime('%d.%m.%Y')}\n\n"
                    f"Доступно:\n"
                    f"• Техника на каждый день\n"
                    f"• Полная библиотека\n"
                    f"• Статистика и прогресс"
                )
            else:
                simple_response = "✅ Ваша подписка активна!"
        else:
            simple_response = (
                "💰 ПОДПИСКА\n\n"
                "❌ Статус: НЕ АКТИВНА\n\n"
                "Преимущества подписки:\n"
                "• Персональная техника на каждый день\n"
                "• Доступ ко всем техникам\n"
                "• Отслеживание прогресса\n\n"
                "Стоимость:\n"
                "• 1 месяц - 99₽\n"
                "• 3 месяца - 269₽\n"
                "• 12 месяцев - 799₽\n\n"
                "Нажмите '💰 КУПИТЬ ПОДПИСКУ' для оформления."
            )
        
        bot.send_message(message.chat.id, simple_response, reply_markup=subscription_keyboard)

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
    
    try:
        bot.send_message(message.chat.id, response, reply_markup=tariff_keyboard, parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id,
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
                        "Выберите вариант:",
                        reply_markup=tariff_keyboard)
    
    logger.info(f"👤 Пользователь {user_id} выбирает тариф")

@bot.message_handler(func=lambda message: message.text in ["📅 1 МЕСЯЦ - 99₽", "📅 3 МЕСЯЦА - 269₽", "📅 12 МЕСЯЦЕВ - 799₽"])
def create_subscription_payment(message):
    """Создание платежа для выбранного тарифа"""
    user_id = message.from_user.id
    logger.info(f"👤 Пользователь {user_id} выбрал: {message.text}")
    
    # Определяем выбранный тариф
    tariff_map = {
        "📅 1 МЕСЯЦ - 99₽": {"amount": 99.00, "days": 30, "description": "Подписка на 1 месяц"},
        "📅 3 МЕСЯЦА - 269₽": {"amount": 269.00, "days": 90, "description": "Подписка на 3 месяца"},
        "📅 12 МЕСЯЦЕВ - 799₽": {"amount": 799.00, "days": 365, "description": "Подписка на 12 месяцев"}
    }
    
    tariff = tariff_map[message.text]
    
    try:
        # Пытаемся импортировать модуль оплаты
        from payment import create_payment
        logger.info("✅ Модуль payment найден")
        
        # Создаем платеж
        payment_id, payment_url = create_payment(
            user_id=user_id,
            amount=tariff["amount"],
            description=tariff["description"]
        )
        
        logger.info(f"✅ Создан платеж: {payment_id}")
        
    except ImportError:
        # Демо-режим
        logger.warning("⚠️ Модуль payment не найден, использую демо-режим")
        import uuid
        payment_id = f"demo_{uuid.uuid4().hex[:16]}"
        payment_url = f"https://yoomoney.ru/checkout/payments/v2/contract?orderId={payment_id}"
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания платежа: {e}")
        bot.send_message(
            message.chat.id,
            "⚠️ Произошла ошибка при создании платежа. Пожалуйста, попробуйте позже.",
            reply_markup=subscription_keyboard
        )
        return
    
    # Сохраняем платеж в БД
    save_payment_to_db(user_id, payment_id, tariff["amount"], tariff["days"])
    
    # БЕЗОПАСНАЯ версия сообщения (без Markdown)
    response = (
        "💳 ОПЛАТА ПОДПИСКИ\n\n"
        f"📋 Тариф: {message.text}\n"
        f"💰 Сумма: {tariff['amount']:.0f}₽\n"
        f"📅 Срок: {tariff['days']} дней\n\n"
        f"👉 Ссылка для оплаты:\n"
        f"{payment_url}\n\n"
        f"✅ После успешной оплаты:\n"
        f"• Подписка активируется автоматически\n"
        f"• Вы получите уведомление\n"
        f"• Сразу откроется доступ к техникам\n\n"
        f"🔍 Проверить статус: /check_payment\n\n"
        f"📋 ID платежа: {payment_id}\n\n"
        f"💡 Совет: Скопируйте ссылку и откройте в браузере."
    )
    
    bot.send_message(message.chat.id, response, reply_markup=back_keyboard)
    logger.info(f"✅ Отправлена ссылка на оплату пользователю {user_id}")

@bot.message_handler(func=lambda message: message.text == "🔙 НАЗАД")
def back_to_subscription_from_tariff(message):
    """Возврат из выбора тарифа в меню подписки"""
    subscription_menu(message)

@bot.message_handler(func=lambda message: message.text == "🔙 НАЗАД В ГЛАВНОЕ МЕНЮ")
def back_to_main(message):
    """Возврат в главное меню"""
    bot.send_message(message.chat.id, "Вы вернулись в главное меню:", reply_markup=main_menu_keyboard)

@bot.message_handler(func=lambda message: message.text == "👤 МОЙ ПРОФИЛЬ")
def user_profile(message):
    """Профиль пользователя"""
    user_id = message.from_user.id
    has_subscription = check_subscription_in_db(user_id)
    
    subscription_status = "✅ Активна" if has_subscription else "❌ Не активна"
    
    if has_subscription:
        subscription_end, days_left = get_subscription_info(user_id)
        if subscription_end:
            subscription_info_text = f"\n📅 Дней осталось: {days_left}\n🏁 Действует до: {subscription_end.strftime('%d.%m.%Y')}"
        else:
            subscription_info_text = ""
    else:
        subscription_info_text = ""
    
    response = (
        f"👤 ВАШ ПРОФИЛЬ\n\n"
        f"🆔 ID: {user_id}\n"
        f"👤 Имя: {message.from_user.first_name}\n"
        f"📊 Подписка: {subscription_status}{subscription_info_text}\n\n"
        f"✨ Для доступа к полному функционалу оформите подписку!"
    )
    
    bot.send_message(message.chat.id, response, reply_markup=back_keyboard)

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

@bot.message_handler(commands=['check_payment'])
def check_payment_command(message):
    """Проверка статуса платежа"""
    user_id = message.from_user.id
    
    payment_info = get_last_payment(user_id)
    
    if not payment_info:
        bot.send_message(message.chat.id, "❌ У вас нет платежей.")
        return
    
    payment_id, status, period_days = payment_info
    
    if status == 'succeeded':
        # Проверяем, активирована ли подписка
        if check_subscription_in_db(user_id):
            response = (
                f"✅ ПЛАТЕЖ УСПЕШЕН!\n\n"
                f"📋 ID: {payment_id[:12]}...\n"
                f"🎉 Подписка активна!\n\n"
                f"Теперь вам доступны все функции бота!\n"
                f"Нажмите «🌟 ТЕХНИКА НА СЕГОДНЯ»"
            )
        else:
            # Если платеж успешен, но подписка не активирована
            add_subscription_to_db(user_id, period_days)
            response = "🎉 Платеж подтвержден! Подписка активирована!"
    
    elif status == 'pending':
        try:
            from payment import check_payment_with_details
            
            payment_info_check = check_payment_with_details(payment_id)
            
            if payment_info_check and payment_info_check.get('status') == 'succeeded':
                add_subscription_to_db(user_id, period_days)
                update_payment_status(payment_id, 'succeeded')
                response = "🎉 Платеж подтвержден! Подписка активирована!"
            else:
                response = (
                    f"⏳ ПЛАТЕЖ В ОБРАБОТКЕ\n\n"
                    f"📋 ID: {payment_id[:12]}...\n\n"
                    f"Пожалуйста, подождите несколько минут.\n"
                    f"Обычно обработка занимает 1-2 минуты.\n\n"
                    f"Если прошло более 10 минут, напишите в поддержку: @avllks"
                )
        except:
            # В демо-режиме или при ошибке проверки
            response = (
                f"⏳ Платеж в обработке\n\n"
                f"ID: {payment_id[:12]}...\n\n"
                f"Если вы уже оплатили, нажмите /check_payment еще раз для проверки."
            )
    
    else:
        response = f"❌ Платеж не прошел. Статус: {status}"
    
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['check_sub'])
def check_subscription_command(message):
    """Проверка подписки"""
    user_id = message.from_user.id
    
    if check_subscription_in_db(user_id):
        subscription_end, days_left = get_subscription_info(user_id)
        if subscription_end:
            response = (
                f"✅ Ваша подписка активна!\n\n"
                f"📅 Дней осталось: {days_left}\n"
                f"🏁 Действует до: {subscription_end.strftime('%d.%m.%Y')}"
            )
        else:
            response = "✅ Ваша подписка активна!"
    else:
        response = (
            "❌ Подписка не активна\n\n"
            "Оформите подписку для доступа к полному функционалу бота.\n"
            "Нажмите '💰 ПОДПИСКА' для оформления."
        )
    
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['test_payment'])
def test_payment(message):
    """Тестовая активация подписки"""
    user_id = message.from_user.id
    
    # Активируем тестовую подписку на 30 дней
    add_subscription_to_db(user_id, 30)
    
    # Сохраняем тестовый платеж
    import uuid
    payment_id = f"test_{uuid.uuid4().hex[:8]}"
    save_payment_to_db(user_id, payment_id, 99.00, 30)
    
    # Обновляем статус платежа
    update_payment_status(payment_id, 'succeeded')
    
    response = (
        "🎉 ТЕСТОВАЯ ПОДПИСКА АКТИВИРОВАНА!\n\n"
        "✅ Подписка активирована на 30 дней\n"
        "🌟 Теперь доступны все функции бота\n\n"
        "Нажмите «🌟 ТЕХНИКА НА СЕГОДНЯ» чтобы начать!"
    )
    
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['profile'])
def profile_command(message):
    """Команда профиля"""
    user_profile(message)

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
        "👨‍💼 Панель администратора\n\nВыберите действие:",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callback(call):
    """Обработка админ-кнопок"""
    if str(call.from_user.id) != ADMIN_ID:
        return
    
    if call.data == "admin_stats":
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()