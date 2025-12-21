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

# Импорты из ваших модулей
from database import (
    add_user, get_user_stats, update_user_stats, 
    check_subscription, save_payment, update_payment,
    add_subscription, get_recent_payments, get_pending_payments
)
from payment import create_payment, check_payment, check_payment_with_details

# ============== АВТОМАТИЧЕСКОЕ СОЗДАНИЕ ТАБЛИЦ ==============
def init_database():
    """Создаёт все таблицы если их нет"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    print("🔧 Проверяю базу данных...")
    
    # 1. Таблица users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            subscription_end DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. Таблица payments
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
    
    conn.commit()
    
    # Проверяем что создалось
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"✅ Таблицы в базе: {tables}")
    
    conn.close()

# Запускаем создание таблиц сразу при импорте
init_database()
# ============== КОНЕЦ СОЗДАНИЯ ТАБЛИЦ ==============

# Загружаем переменные окружения из .env
load_dotenv()

# Настройки
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')
bot = telebot.TeleBot(TOKEN)

# Увеличиваем таймауты для Railway
import telebot.apihelper
telebot.apihelper.READ_TIMEOUT = 35
telebot.apihelper.CONNECT_TIMEOUT = 10
bot.skip_pending = True  # пропускаем старые сообщения

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка техник
with open('techniques.json', 'r', encoding='utf-8') as f:
    techniques = json.load(f)

# =================== КЛАВИАТУРЫ ===================

# Главное меню с красивыми кнопками
main_menu_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
main_menu_keyboard.row("🌟 ТЕХНИКА НА СЕГОДНЯ")
main_menu_keyboard.row("ℹ️ О ПРОЕКТЕ")
main_menu_keyboard.row("💰 ПОДПИСКА", "👤 МОЙ ПРОФИЛЬ")

# Меню подписки
subscription_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
subscription_keyboard.row("💰 КУПИТЬ ПОДПИСКУ")
subscription_keyboard.row("📊 ИНФОРМАЦИЯ О ПОДПИСКЕ")
subscription_keyboard.row("🔙 НАЗАД В ГЛАВНОЕ МЕНЮ")

# Клавиатура для выбора тарифа
tariff_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
tariff_keyboard.add(
    "📅 1 МЕСЯЦ - 99₽",
    "📅 3 МЕСЯЦА - 269₽",
    "📅 12 МЕСЯЦЕВ - 799₽",
    "🔙 НАЗАД В МЕНЮ ПОДПИСКИ"
)

# Кнопка только "Назад" для простых экранов
back_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
back_keyboard.row("🔙 НАЗАД В ГЛАВНОЕ МЕНЮ")

# =================== ОБРАБОТЧИКИ ===================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    # Добавляем пользователя в БД
    add_user(user_id, username)
    
    welcome_text = (
        f"🌟 Привет, {username}!\n\n"
        "Я — твой личный помощник в борьбе с выгоранием.\n\n"
        "✨ Что я умею:\n"
        "• Подбирать технику на каждый день\n"
        "• Хранить библиотеку анти-выгорательных практик\n"
        "• Помогать отслеживать твое состояние\n\n"
        "Выбери, что тебя интересует:"
    )
    
    bot.send_message(
        message.chat.id, 
        welcome_text,
        reply_markup=main_menu_keyboard
    )

@bot.message_handler(commands=['help'])
def send_help(message):
    """Помощь по командам"""
    help_text = (
        "🤖 *СПИСОК КОМАНД*\n\n"
        "Основные:\n"
        "`/start` - Запустить бота\n"
        "`/help` - Эта справка\n"
        "`/profile` - Ваш профиль\n"
        "`/check_sub` - Проверить подписку\n"
        "`/mystatus` - Детальный статус\n\n"
        "Для администратора:\n"
        "`/admin` - Панель управления\n"
        "`/allpayments` - Все платежи\n"
        "`/dbcheck` - Проверка БД\n"
        "`/activate USER_ID DAYS` - Активировать подписку\n"
    )
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['profile'])
def profile_command(message):
    """Команда профиля"""
    user_profile(message)

@bot.message_handler(func=lambda message: message.text == "🌟 ТЕХНИКА НА СЕГОДНЯ")
def daily_technique(message):
    """Техника на сегодня - только для подписчиков"""
    user_id = message.from_user.id
    
    # Проверяем подписку
    if not check_subscription(user_id):
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
    
    # Если подписка есть - показываем технику
    category = random.choice(list(techniques.keys()))
    technique = random.choice(techniques[category])
    
    response = (
        f"🌟 ТЕХНИКА НА СЕГОДНЯ\n\n"
        f"📁 Категория: {category}\n"
        f"🎯 Название: {technique['name']}\n\n"
        f"📝 Описание:\n{technique['description']}\n\n"
        f"⏱ Время выполнения: {technique.get('time', '5-10 минут')}\n\n"
        f"💡 Совет: {technique.get('tip', 'Выполняйте технику осознанно, сосредотачиваясь на процессе.')}"
    )
    
    bot.send_message(message.chat.id, response, reply_markup=back_keyboard)
    
    # Обновляем статистику
    update_user_stats(user_id, 'daily_techniques')

@bot.message_handler(func=lambda message: message.text == "ℹ️ О ПРОЕКТЕ")
def about_project(message):
    """Информация о проекте"""
    response = (
        "ℹ️ О ПРОЕКТЕ\n\n"
        "🤖 Анти-выгорание Бот\n\n"
        "Миссия: Помогать людям справляться с эмоциональным выгоранием и стрессом через простые и эффективные техники.\n\n"
        "🔧 Технологии:\n"
        "• Python + Telebot\n"
        "• SQLite для хранения данных\n"
        "• Интеграция с ЮКассой для оплаты\n\n"
        "📞 Контакты:\n"
        "По вопросам и предложениям: @avllks\n\n"
        "💖 Помни: Забота о себе - это не роскошь, а необходимость!"
    )
    
    bot.send_message(message.chat.id, response, reply_markup=back_keyboard)

@bot.message_handler(func=lambda message: message.text == "💰 ПОДПИСКА")
def subscription_menu(message):
    """Меню подписки"""
    user_id = message.from_user.id
    has_subscription = check_subscription(user_id)
    
    if has_subscription:
        status = "✅ АКТИВНА"
        days_left = "30"  # Здесь нужно добавить логику расчета дней
        response = (
            f"💰 ВАША ПОДПИСКА\n\n"
            f"Статус: {status}\n"
            f"Дней осталось: {days_left}\n\n"
            f"Что дает подписка:\n"
            f"• 🌟 Техника на каждый день\n"
            f"• 📚 Полная библиотека техник\n"
            f"• 📊 Статистика и прогресс\n"
            f"• 🔔 Напоминания и поддержка"
        )
    else:
        status = "❌ НЕ АКТИВНА"
        response = (
            f"💰 ПОДПИСКА\n\n"
            f"Статус: {status}\n\n"
            f"✨ Преимущества подписки:\n"
            f"• 🌟 Персональная техника на каждый день\n"
            f"• 📚 Доступ ко всем техникам\n"
            f"• 📊 Отслеживание прогресса\n"
            f"• 🔔 Регулярные напоминания\n\n"
            f"💎 Стоимость: 99₽/месяц\n\n"
            f"Нажмите '💰 КУПИТЬ ПОДПИСКУ' для оформления."
        )
    
    bot.send_message(message.chat.id, response, reply_markup=subscription_keyboard)

@bot.message_handler(func=lambda message: message.text == "👤 МОЙ ПРОФИЛЬ")
def user_profile(message):
    """Профиль пользователя"""
    user_id = message.from_user.id
    stats = get_user_stats(user_id)
    has_subscription = check_subscription(user_id)
    
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
    """Обработчик кнопки купить подписку"""
    choose_subscription_plan(message)

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
def back_to_subscription_menu(message):
    """Возврат в меню подписки"""
    response = "Вы вернулись в меню подписки:"
    bot.send_message(message.chat.id, response, reply_markup=subscription_keyboard)

@bot.message_handler(func=lambda message: message.text in ["📅 1 МЕСЯЦ - 99₽", "📅 3 МЕСЯЦА - 269₽", "📅 12 МЕСЯЦЕВ - 799₽"])
def create_subscription_payment(message):
    """Создание платежа для выбранного тарифа"""
    user_id = message.from_user.id
    
    # Проверяем, есть ли уже активная подписка
    if check_subscription(user_id):
        bot.send_message(
            message.chat.id,
            "⚠️ У вас уже есть активная подписка!\n\n"
            "Вы можете продлить ее после окончания текущего периода.\n"
            "Проверьте срок действия в вашем профиле.",
            reply_markup=subscription_keyboard
        )
        return
    
    # Определяем выбранный тариф
    tariff_map = {
        "📅 1 МЕСЯЦ - 99₽": {"amount": 99.00, "days": 30, "description": "Подписка на 1 месяц"},
        "📅 3 МЕСЯЦА - 269₽": {"amount": 269.00, "days": 90, "description": "Подписка на 3 месяца"},
        "📅 12 МЕСЯЦЕВ - 799₽": {"amount": 799.00, "days": 365, "description": "Подписка на 12 месяцев"}
    }
    
    tariff = tariff_map[message.text]
    
    # Создаем платеж в ЮКассе
    try:
        payment_id, payment_url = create_payment(
            user_id=user_id,
            amount=tariff["amount"],
            description=tariff["description"]
        )
        
        if not payment_id or not payment_url:
            raise Exception("Не удалось создать платеж")
        
        # Сохраняем платеж в БД
        save_payment(user_id, payment_id, tariff["amount"], tariff["days"])
        
        # Отправляем пользователю ссылку для оплаты
        response = (
            f"💳 ОПЛАТА ПОДПИСКИ\n\n"
            f"Тариф: {message.text}\n"
            f"Сумма: {tariff['amount']:.0f}₽\n"
            f"Срок: {tariff['days']} дней\n\n"
            f"👉 Для оплаты перейдите по ссылке:\n{payment_url}\n\n"
            f"После успешной оплаты подписка активируется автоматически.\n"
            f"Обычно это занимает 1-2 минуты.\n\n"
            f"🔍 Проверить статус оплаты: /check_payment"
        )
        
        bot.send_message(message.chat.id, response, reply_markup=back_keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка при создании платежа: {e}")
        bot.send_message(
            message.chat.id,
            "⚠️ Произошла ошибка при создании платежа. Пожалуйста, попробуйте позже.",
            reply_markup=subscription_keyboard
        )

def choose_subscription_plan(message):
    """Выбор тарифа подписки"""
    user_id = message.from_user.id
    
    # Проверяем, есть ли уже активная подписка
    if check_subscription(user_id):
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

@bot.message_handler(commands=['check_payment'])
def check_payment_status(message):
    """Проверка статуса последнего платежа"""
    user_id = message.from_user.id
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # Получаем последний платеж пользователя
    cursor.execute(
        "SELECT payment_id, status FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    )
    payment = cursor.fetchone()
    conn.close()
    
    if not payment:
        bot.send_message(
            message.chat.id,
            "❌ У вас нет платежей.\n"
            "Оформите подписку в меню '💰 ПОДПИСКА'.",
            reply_markup=main_menu_keyboard
        )
        return
    
    payment_id, status = payment
    
    if status == 'succeeded':
        bot.send_message(
            message.chat.id,
            f"✅ Ваш платеж `{payment_id[:12]}...` успешно обработан!\n"
            f"Подписка активна. Наслаждайтесь использованием бота!",
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard
        )
    elif status == 'pending':
        # Проверяем статус в ЮKassa
        try:
            payment_info = check_payment_with_details(payment_id)
            if payment_info and payment_info.get('status') == 'succeeded':
                bot.send_message(
                    message.chat.id,
                    "🎉 Платеж подтвержден! Подписка активирована!",
                    reply_markup=main_menu_keyboard
                )
            else:
                bot.send_message(
                    message.chat.id,
                    f"⏳ Платеж `{payment_id[:12]}...` еще обрабатывается.\n"
                    f"Пожалуйста, подождите несколько минут и проверьте снова.",
                    parse_mode='Markdown',
                    reply_markup=main_menu_keyboard
                )
        except Exception as e:
            logger.error(f"Ошибка проверки платежа {payment_id}: {e}")
            bot.send_message(
                message.chat.id,
                f"⚠️ Не удалось проверить статус платежа.\n"
                f"Попробуйте позже или обратитесь в поддержку: @avllks",
                reply_markup=main_menu_keyboard
            )
    else:
        bot.send_message(
            message.chat.id,
            f"❌ Платеж `{payment_id[:12]}...` имеет статус: {status}\n"
            f"Попробуйте оформить подписку заново.",
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard
        )

# =================== АДМИН-КОМАНДЫ ===================

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
        types.InlineKeyboardButton("🔄 Проверить все платежи", callback_data="admin_check_all_payments")
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
    
    if call.data == "admin_check_payments":
        # Принудительная проверка платежей
        payments = get_recent_payments(minutes=1440)  # за сутки
        
        bot.answer_callback_query(call.id, f"Найдено {len(payments)} платежей")
        
        if payments:
            message_text = "📋 *Последние платежи (за 24 часа):*\n\n"
            for p in payments[:15]:  # первые 15
                status_icon = "✅" if p['status'] == 'succeeded' else "🔄" if p['status'] == 'pending' else "❌"
                message_text += f"{status_icon} `{p['payment_id'][:12]}...`\n"
                message_text += f"👤 {p['user_id']} | 💰 {p['amount']}₽ | 📅 {p['period_days']}д\n"
                message_text += f"🕐 {p['created_at'][:19] if p['created_at'] else ''}\n\n"
            
            if len(payments) > 15:
                message_text += f"\n... и еще {len(payments) - 15}"
        else:
            message_text = "🤷‍♂️ *Нет платежей за последние сутки*"
        
        bot.send_message(call.message.chat.id, message_text, parse_mode='Markdown')
    
    elif call.data == "admin_check_all_payments":
        # Проверка всех pending платежей через ЮKassa
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT payment_id, user_id FROM payments WHERE status = 'pending'")
        pending_payments = cursor.fetchall()
        conn.close()
        
        bot.answer_callback_query(call.id, f"Проверяю {len(pending_payments)} платежей...")
        
        if pending_payments:
            processed = 0
            succeeded = 0
            
            for payment_id, user_id in pending_payments:
                try:
                    payment_info = check_payment_with_details(payment_id)
                    if payment_info and payment_info.get('status') == 'succeeded':
                        update_payment(payment_id, 'succeeded')
                        add_subscription(user_id, get_period_days(payment_id))
                        succeeded += 1
                    processed += 1
                except Exception as e:
                    logger.error(f"Ошибка проверки платежа {payment_id}: {e}")
            
            bot.send_message(
                call.message.chat.id,
                f"🔄 *Проверка завершена*\n\n"
                f"✅ Обработано: {processed}\n"
                f"🎉 Успешно: {succeeded}\n"
                f"⏳ Осталось в ожидании: {len(pending_payments) - succeeded}",
                parse_mode='Markdown'
            )
        else:
            bot.send_message(call.message.chat.id, "✅ Нет pending платежей для проверки", parse_mode='Markdown')
    
    elif call.data == "admin_stats":
        import sqlite3
        from datetime import datetime
        
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # Считаем пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Считаем активные подписки
        cursor.execute("SELECT COUNT(*) FROM users WHERE subscription_end >= date('now')")
        active_subs = cursor.fetchone()[0]
        
        # Считаем платежи
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
            f"• 🕐 Время: {datetime.now().strftime('%H:%M:%S')}\n"
            f"• 🔧 Режим: {'РАБОЧИЙ' if TOKEN else 'ТЕСТОВЫЙ'}",
            parse_mode='Markdown'
        )

def get_period_days(payment_id):
    """Получить количество дней подписки по payment_id"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT period_days FROM payments WHERE payment_id = ?", (payment_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 30

@bot.message_handler(commands=['activate'])
def activate_manual(message):
    """Ручная активация подписки (админ)"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ У вас нет доступа к этой команде.")
        return
    
    try:
        # Формат: /activate USER_ID DAYS
        parts = message.text.split()
        if len(parts) != 3:
            bot.send_message(
                message.chat.id,
                "❌ *Неверный формат*\n\n"
                "Используйте: `/activate USER_ID DAYS`\n"
                "Пример: `/activate 123456789 30`",
                parse_mode='Markdown'
            )
            return
        
        user_id = int(parts[1])
        days = int(parts[2])
        
        add_subscription(user_id, days)
        
        # Создаем запись о "платеже"
        payment_id = f"manual_{int(datetime.now().timestamp())}"
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO payments (payment_id, user_id, amount, period_days, status) 
               VALUES (?, ?, ?, ?, ?)""",
            (payment_id, user_id, 0.00, days, 'succeeded')
        )
        conn.commit()
        conn.close()
        
        bot.send_message(
            message.chat.id,
            f"✅ *Подписка активирована!*\n\n"
            f"👤 Пользователь: `{user_id}`\n"
            f"📅 Срок: {days} дней\n"
            f"Действует до: {(datetime.now() + timedelta(days=days)).strftime('%d.%m.%Y')}",
            parse_mode='Markdown'
        )
        
        # Уведомляем пользователя
        try:
            bot.send_message(
                user_id,
                "🎉 *ВАША ПОДПИСКА АКТИВИРОВАНА!*\n\n"
                f"Администратор активировал подписку на {days} дней.\n"
                "Теперь вам доступны все платные функции!\n\n"
                "Нажмите «🌟 ТЕХНИКА НА СЕГОДНЯ» чтобы начать.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {user_id}: {e}")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")

@bot.message_handler(commands=['check_sub'])
def check_subscription_command(message):
    """Проверка подписки пользователя"""
    user_id = message.from_user.id
    
    if check_subscription(user_id):
        bot.send_message(message.chat.id, "✅ Ваша подписка активна!")
    else:
        bot.send_message(message.chat.id, "❌ Подписка не активна")

# =================== НОВЫЕ АДМИН-КОМАНДЫ ДЛЯ ОТЛАДКИ ===================

@bot.message_handler(commands=['allpayments'])
def show_all_payments(message):
    """Показать все платежи в системе"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ У вас нет доступа к этой команде.")
        return
    
    import sqlite3
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # Получаем ВСЕ платежи
    cursor.execute("SELECT * FROM payments ORDER BY created_at DESC")
    all_payments = cursor.fetchall()
    
    response = f"📋 *ВСЕ ПЛАТЕЖИ В СИСТЕМЕ ({len(all_payments)}):*\n\n"
    
    if not all_payments:
        response += "❌ Нет ни одного платежа в базе"
    else:
        for p in all_payments[:20]:  # Ограничиваем 20
            payment_id, user_id, amount, days, status, created = p
            status_icon = "✅" if status == 'succeeded' else "🔄" if status == 'pending' else "❌"
            response += f"{status_icon} `{payment_id[:12]}...`\n"
            response += f"   👤 {user_id} | 💰 {amount}₽ | 📅 {days}д | 🏷 {status}\n"
            response += f"   🕐 {created[:19] if created else ''}\n\n"
    
    if len(all_payments) > 20:
        response += f"\n... и еще {len(all_payments) - 20} платежей"
    
    conn.close()
    
    bot.send_message(message.chat.id, response, parse_mode='Markdown')

@bot.message_handler(commands=['dbcheck'])
def check_database(message):
    """Проверка структуры базы данных"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ У вас нет доступа к этой команде.")
        return
    
    import sqlite3
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    response = "🗃️ *ПРОВЕРКА БАЗЫ ДАННЫХ*\n\n"
    
    # 1. Проверяем таблицы
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    response += f"📊 *Таблицы ({len(tables)}):*\n"
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        response += f"• `{table[0]}` - {count} записей\n"
    
    response += "\n"
    
    # 2. Проверяем структуру таблицы payments
    try:
        cursor.execute("PRAGMA table_info(payments)")
        columns = cursor.fetchall()
        response += "📋 *Структура таблицы payments:*\n"
        for col in columns:
            response += f"• `{col[1]}` ({col[2]})\n"
    except:
        response += "❌ Таблица `payments` не существует!\n"
    
    response += "\n"
    
    # 3. Проверяем последние 5 платежей
    try:
        cursor.execute("SELECT payment_id, user_id, status FROM payments ORDER BY created_at DESC LIMIT 5")
        recent = cursor.fetchall()
        response += "🕐 *Последние платежи:*\n"
        for p in recent:
            status_icon = "✅" if p[2] == 'succeeded' else "🔄" if p[2] == 'pending' else "❌"
            response += f"• `{p[0][:12]}...` - 👤{p[1]} - {status_icon} {p[2]}\n"
    except Exception as e:
        response += f"❌ Не удалось получить платежи: {e}\n"
    
    conn.close()
    
    bot.send_message(message.chat.id, response, parse_mode='Markdown')

@bot.message_handler(commands=['activatenow'])
def activate_now(message):
    """Экстренная активация подписки"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ У вас нет доступа к этой команде.")
        return
    
    import sqlite3
    from datetime import datetime, timedelta
    
    user_id = 360171560  # Ваш ID
    days = 365  # 12 месяцев
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # 1. Добавляем пользователя если нет
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username,