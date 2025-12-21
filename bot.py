import telebot
from telebot import types
import sqlite3
import json
from datetime import datetime, timedelta
import random
import os
from dotenv import load_dotenv
from database import add_user, get_user_stats, update_user_stats, check_subscription, save_payment, update_payment
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
    
    # 2. Таблица payments (ВАЖНО!)
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
bot = telebot.TeleBot(TOKEN)

# Увеличиваем таймауты для Railway
import telebot.apihelper
telebot.apihelper.READ_TIMEOUT = 35
telebot.apihelper.CONNECT_TIMEOUT = 10
bot.skip_pending = True  # пропускаем старые сообщения

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

# =================== АДМИН-КОМАНДЫ ===================

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    """Панель администратора"""
    if str(message.from_user.id) != os.getenv('ADMIN_ID'):
        return
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        types.InlineKeyboardButton("🔍 Проверить платежи", callback_data="admin_check_payments"),
        types.InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")
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
    if str(call.from_user.id) != os.getenv('ADMIN_ID'):
        return
    
    if call.data == "admin_check_payments":
        # Принудительная проверка платежей
        from database import get_recent_payments
        payments = get_recent_payments(minutes=1440)  # за сутки
        
        bot.answer_callback_query(call.id, f"Найдено {len(payments)} платежей")
        
        if payments:
            message_text = "📋 *Последние платежи:*\n\n"
            for p in payments[:10]:  # первые 10
                message_text += f"• {p['user_id']} - {p['amount']}₽ - {p['payment_id'][:8]}...\n"
            
            if len(payments) > 10:
                message_text += f"\n... и еще {len(payments) - 10}"
        else:
            message_text = "🤷‍♂️ *Нет платежей за последние сутки*"
        
        bot.send_message(call.message.chat.id, message_text, parse_mode='Markdown')
    
    elif call.data == "admin_stats":
        from database import Database
        db = Database()
        active_users = db.get_active_users()
        
        bot.send_message(
            call.message.chat.id,
            f"📈 *Статистика*\n\n"
            f"• Активных подписок: {len(active_users)}\n"
            f"• Время работы: {datetime.now().strftime('%H:%M:%S')}\n"
            f"• Режим: {'РАБОЧИЙ' if TOKEN else 'ТЕСТОВЫЙ'}",
            parse_mode='Markdown'
        )

@bot.message_handler(commands=['activate'])
def activate_manual(message):
    """Ручная активация подписки (админ)"""
    if str(message.from_user.id) != os.getenv('ADMIN_ID'):
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
        
        from database import add_subscription
        add_subscription(user_id, days)
        
        bot.send_message(
            message.chat.id,
            f"✅ *Подписка активирована!*\n\n"
            f"Пользователь: `{user_id}`\n"
            f"Срок: {days} дней\n"
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
        except:
            pass
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")

@bot.message_handler(commands=['check_sub'])
def check_subscription_command(message):
    """Проверка подписки пользователя"""
    user_id = message.from_user.id
    from database import check_subscription
    
    if check_subscription(user_id):
        bot.send_message(message.chat.id, "✅ Ваша подписка активна!")
    else:
        bot.send_message(message.chat.id, "❌ Подписка не активна")

# =================== НОВЫЕ АДМИН-КОМАНДЫ ДЛЯ ОТЛАДКИ ===================

@bot.message_handler(commands=['allpayments'])
def show_all_payments(message):
    """Показать все платежи в системе"""
    if str(message.from_user.id) != os.getenv('ADMIN_ID'):
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
        for p in all_payments:
            payment_id, user_id, amount, days, status, created = p
            status_icon = "✅" if status == 'succeeded' else "🔄" if status == 'pending' else "❌"
            response += f"{status_icon} `{payment_id[:12]}...`\n"
            response += f"   👤 {user_id} | 💰 {amount}₽ | 📅 {days}д | 🏷 {status}\n"
            response += f"   🕐 {created[:19] if created else ''}\n\n"
    
    conn.close()
    
    bot.send_message(message.chat.id, response, parse_mode='Markdown')

@bot.message_handler(commands=['dbcheck'])
def check_database(message):
    """Проверка структуры базы данных"""
    if str(message.from_user.id) != os.getenv('ADMIN_ID'):
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
            response += f"• `{p[0][:12]}...` - 👤{p[1]} - {p[2]}\n"
    except:
        response += "❌ Не удалось получить платежи\n"
    
    conn.close()
    
    bot.send_message(message.chat.id, response, parse_mode='Markdown')

@bot.message_handler(commands=['activatenow'])
def activate_now(message):
    """Экстренная активация подписки"""
    if str(message.from_user.id) != os.getenv('ADMIN_ID'):
        return
    
    import sqlite3
    from datetime import datetime, timedelta
    
    user_id = 360171560  # Ваш ID
    days = 365  # 12 месяцев
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # 1. Добавляем пользователя если нет
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user_id, 'avllks', 'Александр')
    )
    
    # 2. Активируем подписку
    new_end = (datetime.now() + timedelta(days=days)).date().isoformat()
    cursor.execute(
        "UPDATE users SET subscription_end = ? WHERE user_id = ?",
        (new_end, user_id)
    )
    
    # 3. Добавляем запись о "платеже"
    payment_id = f"manual_{int(datetime.now().timestamp())}"
    cursor.execute(
        """INSERT INTO payments (payment_id, user_id, amount, period_days, status) 
           VALUES (?, ?, ?, ?, ?)""",
        (payment_id, user_id, 799.00, days, 'succeeded')
    )
    
    conn.commit()
    
    # 4. Проверяем
    cursor.execute("SELECT subscription_end FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    
    if result and result[0]:
        bot.send_message(
            message.chat.id,
            f"✅ *ПОДПИСКА АКТИВИРОВАНА!*\n\n"
            f"👤 Пользователь: `{user_id}`\n"
            f"📅 Срок: {days} дней\n"
            f"🏁 Действует до: `{result[0]}`\n"
            f"💳 Платеж: `{payment_id[:12]}...`\n\n"
            f"*Теперь нажмите «🌟 ТЕХНИКА НА СЕГОДНЯ»*",
            parse_mode='Markdown'
        )
    else:
        bot.send_message(message.chat.id, "❌ Что-то пошло не так")

@bot.message_handler(commands=['mystatus'])
def my_status(message):
    """Детальная проверка статуса"""
    user_id = message.from_user.id
    
    import sqlite3
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    response = "🔍 *ВАШ СТАТУС*\n\n"
    
    # 1. Проверяем пользователя
    cursor.execute("SELECT subscription_end FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if user:
        sub_end = user[0]
        if sub_end:
            from datetime import date
            end_date = date.fromisoformat(sub_end)
            today = date.today()
            
            if end_date >= today:
                response += f"✅ *Подписка АКТИВНА*\n"
                response += f"Действует до: `{end_date}`\n"
                response += f"Осталось дней: `{(end_date - today).days}`\n"
            else:
                response += f"❌ *Подписка ИСТЕКЛА*\n"
                response += f"Истекла: `{end_date}`\n"
        else:
            response += "❌ *Подписка НЕ АКТИВИРОВАНА*\n"
    else:
        response += "❌ *Вы не найдены в базе*\n"
    
    # 2. Проверяем платежи
    cursor.execute("SELECT payment_id, amount, status FROM payments WHERE user_id = ?", (user_id,))
    payments = cursor.fetchall()
    
    response += f"\n💳 *Платежи ({len(payments)}):*\n"
    for p in payments:
        status_icon = "✅" if p[2] == 'succeeded' else "🔄" if p[2] == 'pending' else "❌"
        response += f"{status_icon} `{p[0][:12]}...` - {p[1]}₽ - {p[2]}\n"
    
    conn.close()
    
    bot.send_message(message.chat.id, response, parse_mode='Markdown')

# =================== НАВИГАЦИЯ "НАЗАД" ===================

@bot.message_handler(func=lambda message: message.text == "🔙 НАЗАД В ГЛАВНОЕ МЕНЮ")
def back_to_main(message):
    """Возврат в главное меню"""
    response = "Вы вернулись в главное меню. Выберите действие:"
    bot.send_message(message.chat.id, response, reply_markup=main_menu_keyboard)

@bot.message_handler(func=lambda message: message.text == "🔙 НАЗАД")
def back_to_subscription_menu(message):
    """Возврат в меню подписки"""
    response = "Вы вернулись в меню подписки:"
    bot.send_message(message.chat.id, response, reply_markup=subscription_keyboard)

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

@bot.message_handler(func=lambda message: message.text == "💰 КУПИТЬ ПОДПИСКУ")
def choose_subscription_plan(message):
    """Выбор тарифа подписки"""
    user_id = message.from_user.id
    
    # Создаем клавиатуру для выбора тарифа
    tariff_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    tariff_keyboard.row("📅 1 МЕСЯЦ - 99₽")
    tariff_keyboard.row("📅 3 МЕСЯЦА - 269₽")
    tariff_keyboard.row("📅 12 МЕСЯЦЕВ - 799₽")
    tariff_keyboard.row("🔙 НАЗАД")
    
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
    """Создание платежа для выбранного тарифа"""
    user_id = message.from_user.id
    
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
        print(f"Ошибка при создании платежа: {e}")
        bot.send_message(
            message.chat.id,
            "⚠️ Произошла ошибка при создании платежа. Пожалуйста, попробуйте позже.",
            reply_markup=subscription_keyboard
        )

@bot.message_handler(commands=['check_payment'])
def check_payment_status(message):
    """Проверка статуса последнего платежа"""
    user_id = message.from_user.id
    
    # Здесь нужно добавить логику получения последнего платежа пользователя
    # и проверки его статуса через check_payment()
    
    bot.send_message(
        message.chat.id,
        "🔍 Функция проверки платежа будет добавлена позже.\n"
        "Если вы оплатили, но подписка не активировалась,\n"
        "напишите в поддержку: @avllks",
        reply_markup=main_menu_keyboard
    )

# =================== АВТОМАТИЧЕСКАЯ ПРОВЕРКА ПЛАТЕЖЕЙ ===================

import threading
import time
from datetime import datetime
import logging

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Класс для автоматической обработки платежей и активации подписок"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.running = True
        self.check_interval = 30  # проверяем каждые 30 секунд
        logger.info("🔄 Инициализирован процессор платежей")
    
    def process_single_payment(self, payment_data):
        """Обрабатывает один платеж"""
        payment_id = payment_data['payment_id']
        user_id = payment_data['user_id']
        period_days = payment_data['period_days']
        
        logger.info(f"🔍 Проверяю платеж {payment_id} для пользователя {user_id}")
        
        try:
            # 1. Проверяем статус в ЮКассе
            payment_info = check_payment_with_details(payment_id)
            
            # ДЕБАГ: выводим что получили
            logger.info(f"DEBUG: Результат проверки: {payment_info}")
            
            if payment_info is None:
                logger.error(f"🔄 check_payment_with_details вернул None для {payment_id}")
                return False
                
            status = payment_info.get('status')
            
            if status == 'succeeded':
                logger.info(f"✅ Платеж {payment_id} успешен!")
                
                # 2. Активируем подписку в БД
                update_payment(payment_id, 'succeeded')
                
                # 3. Уведомляем пользователя
                self.notify_user_success(user_id, payment_id, period_days)
                
                return True
                
            elif status in ['canceled', 'failed']:
                logger.warning(f"❌ Платеж {payment_id} отменен: {status}")
                
                update_payment(payment_id, status)
                
                self.notify_user_failure(user_id, payment_id, status)
                
            elif status == 'not_found':
                logger.error(f"🔍 Платеж {payment_id} не найден в ЮКассе")
                
            elif status == 'error':
                logger.error(f"⚠️ Ошибка при проверке платежа {payment_id}: {payment_info.get('error')}")
                
            else:
                logger.info(f"⏳ Платеж {payment_id} еще в процессе: {status}")
                
        except Exception as e:
            logger.error(f"🚨 Критическая ошибка обработки платежа {payment_id}: {e}")
            
        return False
    
    def notify_user_success(self, user_id, payment_id, period_days):
        """Уведомляет пользователя об успешной активации подписки"""
        try:
            # Форматируем сообщение
            if period_days == 30:
                period_text = "1 месяц"
            elif period_days == 90:
                period_text = "3 месяца"
            elif period_days == 365:
                period_text = "12 месяцев"
            else:
                period_text = f"{period_days} дней"
            
            message = (
                "🎉 *ОПЛАТА ПОДТВЕРЖДЕНА!*\n\n"
                f"✅ Ваша подписка активирована на {period_text}\n"
                f"📋 ID платежа: `{payment_id[:12]}...`\n\n"
                "✨ *Теперь вам доступны:*\n"
                "• 🌟 Персональная техника на каждый день\n"
                "• 📚 Полная библиотека практик\n"
                "• 📊 Статистика и прогресс\n\n"
                "Нажмите «🌟 ТЕХНИКА НА СЕГОДНЯ» чтобы начать!\n\n"
                "_Спасибо, что выбрали наш сервис!_"
            )
            
            self.bot.send_message(
                user_id,
                message,
                parse_mode='Markdown'
            )
            
            logger.info(f"📨 Отправлено уведомление пользователю {user_id}")
            
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
    
    def notify_user_failure(self, user_id, payment_id, status):
        """Уведомляет пользователя об отмене платежа"""
        try:
            status_text = "отменен" if status == "canceled" else "не прошел"
            
            message = (
                f"⚠️ *Платеж {status_text}*\n\n"
                f"Платеж `{payment_id[:12]}...` не был завершен.\n\n"
                "Если вы произвели оплату, но получили это сообщение:\n"
                "1. Проверьте историю платежей в банке\n"
                "2. Если средства списаны - напишите в поддержку\n"
                "3. Попробуйте оплатить еще раз\n\n"
                "По всем вопросам: @avllks"
            )
            
            self.bot.send_message(
                user_id,
                message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление об ошибке: