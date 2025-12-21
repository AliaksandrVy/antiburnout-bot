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

def get_all_pending_payments():
    """Получение всех pending платежей"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT payment_id, user_id, amount, period_days, created_at FROM payments WHERE status = 'pending' ORDER BY created_at DESC"
        )
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Ошибка получения pending платежей: {e}")
        return []
    finally:
        conn.close()

def get_all_payments():
    """Получение всех платежей из БД"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT payment_id, user_id, amount, period_days, status, created_at FROM payments ORDER BY created_at DESC"
        )
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Ошибка получения всех платежей: {e}")
        return []
    finally:
        conn.close()

def find_payment_by_id(payment_id):
    """Поиск платежа по ID"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT payment_id, user_id, amount, period_days, status, created_at FROM payments WHERE payment_id = ?",
            (payment_id,)
        )
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Ошибка поиска платежа: {e}")
        return None
    finally:
        conn.close()

def activate_by_payment_id(payment_id, user_id=None, period_days=None):
    """Активация подписки по payment_id из ЮКассы"""
    try:
        from payment import check_payment_with_details
        
        # Проверяем платеж в ЮКассе
        payment_info = check_payment_with_details(payment_id)
        
        if not payment_info:
            return False, "Платеж не найден в ЮКассе"
        
        if payment_info.get('status') != 'succeeded':
            return False, f"Платеж не успешен. Статус: {payment_info.get('status')}"
        
        # Если платеж есть в БД, используем данные из БД
        db_payment = find_payment_by_id(payment_id)
        
        if db_payment:
            db_payment_id, db_user_id, db_amount, db_period_days, db_status, db_created_at = db_payment
            user_id = db_user_id
            period_days = db_period_days
        else:
            # Если платежа нет в БД, нужно получить user_id из метаданных
            metadata = payment_info.get('metadata', {})
            user_id_from_meta = metadata.get('user_id')
            
            if not user_id and user_id_from_meta:
                user_id = user_id_from_meta
            
            if not user_id:
                return False, "Не удалось определить user_id. Платеж не найден в БД и нет метаданных."
            
            if not period_days:
                # Определяем период по сумме
                amount = float(payment_info.get('amount', 0))
                if amount >= 799:
                    period_days = 365
                elif amount >= 269:
                    period_days = 90
                elif amount >= 99:
                    period_days = 30
                else:
                    period_days = 30  # По умолчанию
            
            # Сохраняем платеж в БД
            save_payment_to_db(user_id, payment_id, float(payment_info.get('amount', 0)), period_days)
        
        # Активируем подписку
        if activate_subscription_with_notification(user_id, period_days, payment_id):
            update_payment_status(payment_id, 'succeeded')
            return True, f"Подписка активирована для user_id={user_id}, дней={period_days}"
        else:
            return False, "Не удалось активировать подписку"
            
    except ImportError:
        return False, "Модуль payment не найден"
    except Exception as e:
        logger.error(f"Ошибка активации по payment_id: {e}")
        return False, f"Ошибка: {str(e)}"

def activate_subscription_with_notification(user_id, period_days, payment_id=None):
    """Активация подписки с уведомлением пользователя"""
    try:
        # Активируем подписку
        if add_subscription_to_db(user_id, period_days):
            # Отправляем уведомление пользователю
            subscription_end, days_left = get_subscription_info(user_id)
            
            notification_text = (
                "🎉 *ПОДПИСКА АКТИВИРОВАНА!*\n\n"
                f"✅ Ваша подписка успешно активирована!\n"
                f"📅 Дней доступа: {days_left}\n"
            )
            
            if subscription_end:
                notification_text += f"🏁 Действует до: {subscription_end.strftime('%d.%m.%Y')}\n\n"
            
            notification_text += (
                "✨ Теперь вам доступны:\n"
                "• 🌟 Техника на каждый день\n"
                "• 📚 Полная библиотека техник\n"
                "• 📊 Статистика и прогресс\n\n"
                "Нажмите «🌟 ТЕХНИКА НА СЕГОДНЯ» чтобы начать!"
            )
            
            try:
                bot.send_message(user_id, notification_text, parse_mode='Markdown', reply_markup=main_menu_keyboard)
            except:
                # Упрощенная версия без Markdown
                simple_text = (
                    "🎉 ПОДПИСКА АКТИВИРОВАНА!\n\n"
                    f"✅ Ваша подписка успешно активирована!\n"
                    f"📅 Дней доступа: {days_left}\n"
                )
                if subscription_end:
                    simple_text += f"🏁 Действует до: {subscription_end.strftime('%d.%m.%Y')}\n\n"
                simple_text += (
                    "✨ Теперь вам доступны:\n"
                    "• Техника на каждый день\n"
                    "• Полная библиотека техник\n"
                    "• Статистика и прогресс\n\n"
                    "Нажмите «🌟 ТЕХНИКА НА СЕГОДНЯ» чтобы начать!"
                )
                bot.send_message(user_id, simple_text, reply_markup=main_menu_keyboard)
            
            logger.info(f"✅ Подписка активирована для user_id={user_id}, дней={period_days}")
            return True
        else:
            logger.error(f"❌ Не удалось активировать подписку для user_id={user_id}")
            return False
    except Exception as e:
        logger.error(f"Ошибка активации подписки с уведомлением: {e}")
        return False

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
    user_id = message.from_user.id
    is_admin = str(user_id) == ADMIN_ID
    
    help_text = (
        "🤖 *Анти-Выгорание Бот*\n\n"
        "📋 *Доступные команды:*\n\n"
        "• /start - Начать работу\n"
        "• /help - Эта справка\n"
        "• /profile - Ваш профиль\n"
        "• /check_sub - Проверить подписку\n"
        "• /check_payment - Проверить платеж\n"
    )
    
    if is_admin:
        help_text += (
            "\n👨‍💼 *Админ-команды:*\n"
            "• /admin - Панель администратора\n"
            "• /all_payments - Все платежи в БД\n"
            "• /activate_payments - Активировать pending платежи\n"
            "• /activate_by_id <payment_id> - Активировать по ID из ЮКассы\n"
            "• /test_payment - Тестовая активация подписки\n"
        )
    else:
        help_text += "• /test_payment - Тестовая активация подписки\n"
    
    help_text += (
        "\n📱 *Основные функции:*\n"
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
    if not save_payment_to_db(user_id, payment_id, tariff["amount"], tariff["days"]):
        logger.error(f"Не удалось сохранить платеж {payment_id} в БД")
    
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
    
    try:
        bot.send_message(message.chat.id, response, reply_markup=back_keyboard)
        logger.info(f"✅ Отправлена ссылка на оплату пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
        try:
            bot.send_message(
                message.chat.id,
                f"💳 Ссылка для оплаты: {payment_url}\n\nID платежа: {payment_id}",
                reply_markup=back_keyboard
            )
        except:
            logger.error(f"Критическая ошибка отправки сообщения пользователю {user_id}")

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
            if activate_subscription_with_notification(user_id, period_days, payment_id):
                response = "🎉 Платеж подтвержден! Подписка активирована!"
            else:
                response = "⚠️ Платеж подтвержден, но возникла ошибка при активации подписки. Обратитесь в поддержку: @avllks"
    
    elif status == 'pending':
        try:
            from payment import check_payment_with_details
            
            payment_info_check = check_payment_with_details(payment_id)
            
            if payment_info_check and payment_info_check.get('status') == 'succeeded':
                if activate_subscription_with_notification(user_id, period_days, payment_id):
                    update_payment_status(payment_id, 'succeeded')
                    response = "🎉 Платеж подтвержден! Подписка активирована!"
                else:
                    response = "⚠️ Платеж подтвержден, но возникла ошибка при активации подписки. Обратитесь в поддержку: @avllks"
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

@bot.message_handler(commands=['all_payments'])
def show_all_payments_command(message):
    """Показать все платежи в БД (только для админа)"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещен. Эта команда только для администратора.")
        return
    
    try:
        payments = get_all_payments()
        
        if not payments:
            bot.send_message(message.chat.id, "📊 В базе данных нет платежей.")
            return
        
        # Группируем по статусам
        by_status = {}
        for payment_id, user_id, amount, period_days, status, created_at in payments:
            if status not in by_status:
                by_status[status] = []
            by_status[status].append((payment_id, user_id, amount, period_days, created_at))
        
        response = "📊 *ВСЕ ПЛАТЕЖИ В БД:*\n\n"
        response += f"Всего: {len(payments)}\n\n"
        
        for status, status_payments in by_status.items():
            status_emoji = "✅" if status == "succeeded" else "⏳" if status == "pending" else "❌"
            response += f"{status_emoji} *{status.upper()}:* {len(status_payments)}\n"
        
        response += "\n*Детали по статусам:*\n\n"
        
        # Показываем последние 10 платежей
        for payment_id, user_id, amount, period_days, status, created_at in payments[:10]:
            status_emoji = "✅" if status == "succeeded" else "⏳" if status == "pending" else "❌"
            response += f"{status_emoji} {payment_id[:16]}...\n"
            response += f"   👤 {user_id} | 💰 {amount}₽ | 📅 {period_days}д | {created_at}\n\n"
        
        if len(payments) > 10:
            response += f"\n... и еще {len(payments) - 10} платежей"
        
        try:
            bot.send_message(message.chat.id, response, parse_mode='Markdown')
        except:
            bot.send_message(message.chat.id, response.replace('*', ''))
            
    except Exception as e:
        logger.error(f"Ошибка в show_all_payments_command: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")

@bot.message_handler(commands=['activate_payments'])
def activate_pending_payments_command(message):
    """Команда для активации всех пропущенных платежей (только для админа)"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещен. Эта команда только для администратора.")
        return
    
    try:
        # Получаем все pending платежи
        pending_payments = get_all_pending_payments()
        
        if not pending_payments:
            bot.send_message(message.chat.id, "✅ Нет платежей со статусом 'pending' для проверки.")
            return
        
        bot.send_message(
            message.chat.id,
            f"🔄 Начинаю проверку {len(pending_payments)} платежей...\n"
            "Это может занять некоторое время."
        )
        
        checked = 0
        activated = 0
        errors = []
        
        for payment_id, user_id, amount, period_days, created_at in pending_payments:
            try:
                checked += 1
                
                # Проверяем статус платежа в ЮКассе
                try:
                    from payment import check_payment_with_details
                    payment_info = check_payment_with_details(payment_id)
                    
                    if payment_info and payment_info.get('status') == 'succeeded':
                        # Активируем подписку с уведомлением
                        if activate_subscription_with_notification(user_id, period_days, payment_id):
                            update_payment_status(payment_id, 'succeeded')
                            activated += 1
                            logger.info(f"✅ Активирована подписка для payment_id={payment_id}, user_id={user_id}")
                        else:
                            errors.append(f"Не удалось активировать подписку для payment_id={payment_id}")
                    elif payment_info:
                        logger.info(f"⏳ Платеж {payment_id} еще в статусе: {payment_info.get('status')}")
                    else:
                        logger.warning(f"⚠️ Не удалось получить информацию о платеже {payment_id}")
                        
                except ImportError:
                    # Если модуль payment не доступен, пропускаем проверку через API
                    logger.warning(f"⚠️ Модуль payment не найден, пропускаю проверку {payment_id}")
                    errors.append(f"Модуль payment не найден для {payment_id}")
                except Exception as e:
                    logger.error(f"Ошибка проверки платежа {payment_id}: {e}")
                    errors.append(f"Ошибка проверки {payment_id}: {str(e)[:50]}")
                    
            except Exception as e:
                logger.error(f"Критическая ошибка обработки платежа {payment_id}: {e}")
                errors.append(f"Критическая ошибка {payment_id}: {str(e)[:50]}")
        
        # Формируем отчет
        report = (
            f"📊 *ОТЧЕТ О ПРОВЕРКЕ ПЛАТЕЖЕЙ*\n\n"
            f"✅ Проверено: {checked}\n"
            f"🎉 Активировано: {activated}\n"
        )
        
        if errors:
            report += f"\n⚠️ Ошибок: {len(errors)}\n"
            if len(errors) <= 5:
                for error in errors:
                    report += f"• {error}\n"
            else:
                report += f"• И еще {len(errors) - 5} ошибок...\n"
        
        try:
            bot.send_message(message.chat.id, report, parse_mode='Markdown')
        except:
            bot.send_message(message.chat.id, report.replace('*', ''))
            
    except Exception as e:
        logger.error(f"Критическая ошибка в activate_pending_payments_command: {e}")
        bot.send_message(message.chat.id, f"❌ Произошла ошибка: {str(e)}")

@bot.message_handler(commands=['activate_by_id'])
def activate_by_payment_id_command(message):
    """Активация подписки по payment_id из ЮКассы (только для админа)
    
    Использование: /activate_by_id <payment_id> [user_id] [period_days]
    Пример: /activate_by_id 2c8a3f5e-1234-5678-9abc-def012345678
    """
    if str(message.from_user.id) != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещен. Эта команда только для администратора.")
        return
    
    try:
        # Парсим команду
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(
                message.chat.id,
                "❌ Неверный формат команды.\n\n"
                "Использование: /activate_by_id <payment_id> [user_id] [period_days]\n\n"
                "Примеры:\n"
                "/activate_by_id 2c8a3f5e-1234-5678-9abc-def012345678\n"
                "/activate_by_id 2c8a3f5e-1234-5678-9abc-def012345678 123456789 30"
            )
            return
        
        payment_id = parts[1]
        user_id = int(parts[2]) if len(parts) > 2 else None
        period_days = int(parts[3]) if len(parts) > 3 else None
        
        bot.send_message(
            message.chat.id,
            f"🔄 Проверяю платеж {payment_id[:16]}...\nПожалуйста, подождите."
        )
        
        success, result_message = activate_by_payment_id(payment_id, user_id, period_days)
        
        if success:
            response = f"✅ *УСПЕШНО!*\n\n{result_message}"
        else:
            response = f"❌ *ОШИБКА*\n\n{result_message}"
        
        try:
            bot.send_message(message.chat.id, response, parse_mode='Markdown')
        except:
            bot.send_message(message.chat.id, response.replace('*', ''))
            
    except ValueError as e:
        bot.send_message(message.chat.id, f"❌ Ошибка формата: {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка в activate_by_payment_id_command: {e}")
        bot.send_message(message.chat.id, f"❌ Произошла ошибка: {str(e)}")

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
        types.InlineKeyboardButton("🔄 Запустить проверку", callback_data="admin_run_check"),
        types.InlineKeyboardButton("✅ Активировать пропущенные", callback_data="admin_activate_all")
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
        bot.answer_callback_query(call.id, "❌ Доступ запрещен")
        return
    
    try:
        if call.data == "admin_stats":
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            
            # Общая статистика
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE subscription_end IS NOT NULL AND subscription_end >= date('now')")
            active_subscriptions = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'succeeded'")
            successful_payments = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(amount) FROM payments WHERE status = 'succeeded'")
            total_revenue = cursor.fetchone()[0] or 0
            
            conn.close()
            
            stats_text = (
                f"📊 *СТАТИСТИКА БОТА*\n\n"
                f"👥 Всего пользователей: {total_users}\n"
                f"✅ Активных подписок: {active_subscriptions}\n"
                f"💳 Успешных платежей: {successful_payments}\n"
                f"💰 Общий доход: {total_revenue:.2f}₽"
            )
            
            try:
                bot.edit_message_text(
                    stats_text,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown'
                )
            except:
                bot.send_message(call.message.chat.id, stats_text.replace('*', ''))
            
            bot.answer_callback_query(call.id, "✅ Статистика обновлена")
        
        elif call.data == "admin_check_payments":
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT payment_id, user_id, amount, status, created_at 
                FROM payments 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            payments = cursor.fetchall()
            conn.close()
            
            if payments:
                payments_text = "🔍 *ПОСЛЕДНИЕ 10 ПЛАТЕЖЕЙ:*\n\n"
                for payment_id, user_id, amount, status, created_at in payments:
                    status_emoji = "✅" if status == "succeeded" else "⏳" if status == "pending" else "❌"
                    payments_text += f"{status_emoji} {payment_id[:12]}... | {amount}₽ | {status}\n"
                    payments_text += f"   👤 User: {user_id} | 📅 {created_at}\n\n"
            else:
                payments_text = "❌ Платежей пока нет"
            
            try:
                bot.edit_message_text(
                    payments_text,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown'
                )
            except:
                bot.send_message(call.message.chat.id, payments_text.replace('*', ''))
            
            bot.answer_callback_query(call.id, "✅ Список платежей обновлен")
        
        elif call.data == "admin_users":
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT user_id, username, first_name, subscription_end 
                FROM users 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            recent_users = cursor.fetchall()
            conn.close()
            
            users_text = f"👥 *ПОЛЬЗОВАТЕЛИ*\n\nВсего: {total_users}\n\n*Последние 10:*\n\n"
            for user_id, username, first_name, sub_end in recent_users:
                sub_status = "✅" if sub_end and datetime.strptime(sub_end.split()[0], '%Y-%m-%d').date() >= datetime.now().date() else "❌"
                users_text += f"{sub_status} {first_name} (@{username or 'нет'})\n"
                users_text += f"   ID: {user_id}\n\n"
            
            try:
                bot.edit_message_text(
                    users_text,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown'
                )
            except:
                bot.send_message(call.message.chat.id, users_text.replace('*', ''))
            
            bot.answer_callback_query(call.id, "✅ Список пользователей обновлен")
        
        elif call.data == "admin_run_check":
            # Запускаем проверку всех pending платежей
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            
            cursor.execute("SELECT payment_id, user_id, period_days FROM payments WHERE status = 'pending'")
            pending_payments = cursor.fetchall()
            conn.close()
            
            if not pending_payments:
                bot.answer_callback_query(call.id, "✅ Нет платежей для проверки")
                return
            
            checked = 0
            activated = 0
            
            for payment_id, user_id, period_days in pending_payments:
                try:
                    from payment import check_payment_with_details
                    payment_info = check_payment_with_details(payment_id)
                    
                    if payment_info and payment_info.get('status') == 'succeeded':
                        if activate_subscription_with_notification(user_id, period_days, payment_id):
                            update_payment_status(payment_id, 'succeeded')
                            activated += 1
                        else:
                            logger.error(f"Не удалось активировать подписку для payment_id={payment_id}")
                    
                    checked += 1
                except Exception as e:
                    logger.error(f"Ошибка проверки платежа {payment_id}: {e}")
            
            result_text = f"🔄 *ПРОВЕРКА ЗАВЕРШЕНА*\n\nПроверено: {checked}\nАктивировано: {activated}"
            
            try:
                bot.edit_message_text(
                    result_text,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown'
                )
            except:
                bot.send_message(call.message.chat.id, result_text.replace('*', ''))
            
            bot.answer_callback_query(call.id, f"✅ Проверено: {checked}, активировано: {activated}")
        
        elif call.data == "admin_activate_all":
            # Активируем все пропущенные платежи
            pending_payments = get_all_pending_payments()
            
            if not pending_payments:
                bot.answer_callback_query(call.id, "✅ Нет платежей для активации")
                try:
                    bot.edit_message_text(
                        "✅ Нет платежей со статусом 'pending' для активации.",
                        call.message.chat.id,
                        call.message.message_id
                    )
                except:
                    bot.send_message(call.message.chat.id, "✅ Нет платежей со статусом 'pending' для активации.")
                return
            
            # Отправляем сообщение о начале процесса
            try:
                bot.edit_message_text(
                    f"🔄 Проверяю {len(pending_payments)} платежей...\nПожалуйста, подождите.",
                    call.message.chat.id,
                    call.message.message_id
                )
            except:
                bot.send_message(call.message.chat.id, f"🔄 Проверяю {len(pending_payments)} платежей...")
            
            checked = 0
            activated = 0
            errors = []
            
            for payment_id, user_id, amount, period_days, created_at in pending_payments:
                try:
                    checked += 1
                    
                    # Проверяем статус платежа в ЮКассе
                    try:
                        from payment import check_payment_with_details
                        payment_info = check_payment_with_details(payment_id)
                        
                        if payment_info and payment_info.get('status') == 'succeeded':
                            # Активируем подписку с уведомлением
                            if activate_subscription_with_notification(user_id, period_days, payment_id):
                                update_payment_status(payment_id, 'succeeded')
                                activated += 1
                                logger.info(f"✅ Активирована подписка для payment_id={payment_id}, user_id={user_id}")
                            else:
                                errors.append(f"Не удалось активировать {payment_id[:12]}...")
                        elif payment_info:
                            logger.info(f"⏳ Платеж {payment_id} еще в статусе: {payment_info.get('status')}")
                        else:
                            logger.warning(f"⚠️ Не удалось получить информацию о платеже {payment_id}")
                            
                    except ImportError:
                        logger.warning(f"⚠️ Модуль payment не найден, пропускаю проверку {payment_id}")
                        errors.append(f"Модуль payment не найден")
                    except Exception as e:
                        logger.error(f"Ошибка проверки платежа {payment_id}: {e}")
                        errors.append(f"Ошибка: {str(e)[:30]}")
                        
                except Exception as e:
                    logger.error(f"Критическая ошибка обработки платежа {payment_id}: {e}")
                    errors.append(f"Критическая ошибка")
            
            # Формируем отчет
            result_text = (
                f"🔄 *АКТИВАЦИЯ ЗАВЕРШЕНА*\n\n"
                f"✅ Проверено: {checked}\n"
                f"🎉 Активировано: {activated}\n"
            )
            
            if errors:
                result_text += f"\n⚠️ Ошибок: {len(errors)}"
                if len(errors) <= 3:
                    for error in errors[:3]:
                        result_text += f"\n• {error}"
            
            try:
                bot.edit_message_text(
                    result_text,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown'
                )
            except:
                bot.send_message(call.message.chat.id, result_text.replace('*', ''))
            
            bot.answer_callback_query(call.id, f"✅ Проверено: {checked}, активировано: {activated}")
    
    except Exception as e:
        logger.error(f"Ошибка в admin_callback: {e}")
        import traceback
        logger.error(traceback.format_exc())
        try:
            bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)[:50]}")
        except:
            pass

# ============== ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК ==============
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Обработчик для всех необработанных сообщений"""
    try:
        # Игнорируем команды и кнопки, которые уже обработаны
        if message.text and message.text.startswith('/'):
            return
        
        # Для неизвестных сообщений отправляем подсказку
        bot.send_message(
            message.chat.id,
            "🤔 Я не понял ваше сообщение.\n\n"
            "Используйте кнопки меню или команды:\n"
            "/start - Главное меню\n"
            "/help - Справка",
            reply_markup=main_menu_keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка в handle_all_messages: {e}")

# Обработчик ошибок для callback-запросов
@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    """Обработчик для всех необработанных callback-запросов"""
    try:
        bot.answer_callback_query(call.id, "❌ Неизвестная команда")
    except Exception as e:
        logger.error(f"Ошибка в handle_all_callbacks: {e}")

# ============== ЗАПУСК БОТА ==============
if __name__ == '__main__':
    try:
        logger.info("🚀 Запуск бота...")
        logger.info(f"✅ Бот готов к работе. ID админа: {ADMIN_ID}")
        
        # Запускаем бота с обработкой ошибок
        bot.infinity_polling(
            timeout=10,
            long_polling_timeout=5,
            logger_level=logging.INFO,
            none_stop=True,  # Продолжать работу при ошибках
            interval=0  # Минимальная задержка между запросами
        )
        
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise