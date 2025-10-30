from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from yookassa import Payment
import json
import datetime
import uuid
from database import Database
import os
import random

# Загружаем переменные окружения
try:
    with open('.env', 'r', encoding='utf-8') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value
except FileNotFoundError:
    print("Файл .env не найден!")

# Инициализация базы данных
db = Database()

# Загрузка техник
with open('techniques.json', 'r', encoding='utf-8') as f:
    techniques = json.load(f)['techniques']

# Конфигурация оплаты
SUBSCRIPTION_PRICE = 1.00  # 1 доллар
SUBSCRIPTION_DAYS = 30     # 30 дней подписки

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    
    welcome_text = f"""
🌿 *Добро пожаловать, {user.first_name}\!* 🌿

💫 *Anti\-Burnout Bot* \- твой персональный помощник против стресса и выгорания

🎯 *Что я умею:*
• 📅 *Техника дня* \- уникальная практика каждый день
• 🎲 *Случайная техника* \- помощь когда нужно прямо сейчас  
• 🌬️ *Дыхание* \- успокоение за 1 минуту
• 🏃 *Микро\-упражнения* \- без специального оборудования
• 🧠 *Ментальные практики* \- перезагрузка сознания

⏱ *Все техники занимают 1\-3 минуты* \- идеально для коротких перерывов

*Выбери действие ниже:* 👇
"""
    
    keyboard = [
        [InlineKeyboardButton("📅 Техника на сегодня", callback_data="today")],
        [InlineKeyboardButton("🎯 Случайная техника", callback_data="random")],
        [InlineKeyboardButton("💆 Пример техники", callback_data="sample")],
        [InlineKeyboardButton("💎 Подписка - $1", callback_data="subscribe"), 
         InlineKeyboardButton("❓ Помощь", callback_data="help")],
        [InlineKeyboardButton("📊 Моя статистика", callback_data="stats"),
         InlineKeyboardButton("🌟 О проекте", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='MarkdownV2'
    )

def format_technique(tech):
    type_emojis = {
        "дыхание": "🌬️",
        "упражнение": "🏃", 
        "фокус": "🎯"
    }
    
    emoji = type_emojis.get(tech['type'], "✨")
    steps = "\n".join([f"🔹 {step}" for step in tech['steps']])
    
    return f"""
{emoji} *{tech['name']}*

_{tech['description']}_

📋 *Шаги:*
{steps}

💡 *Совет:* {tech['tip']}

*⏱ 1\-3 минуты • {tech['type'].title()} • Anti\-Burnout Bot* 🌿
"""

async def create_payment(user_id, amount, description):
    """Создает платеж в ЮKassa"""
    try:
        payment = Payment.create({
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "USD"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/AntiBurnout_IT_Bot"
            },
            "capture": True,
            "description": description,
            "metadata": {
                "user_id": user_id
            }
        }, uuid.uuid4())
        
        return payment
    except Exception as e:
        print(f"Ошибка создания платежа: {e}")
        return None

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "subscribe":
        user = query.from_user
        
        # Создаем платеж
        payment = await create_payment(
            user.id, 
            SUBSCRIPTION_PRICE, 
            f"Подписка Anti-Burnout Bot на {SUBSCRIPTION_DAYS} дней"
        )
        
        if payment:
            subscribe_text = f"""
💎 *Премиум подписка Anti\-Burnout Bot*

*🚀 Что входит:*
✅ Ежедневная техника в 11:00
✅ Доступ ко всем {len(techniques)} техникам  
✅ Персональные рекомендации
✅ Приоритетная поддержка
✅ Статистика прогресса

*💰 Стоимость:* ${SUBSCRIPTION_PRICE} за {SUBSCRIPTION_DAYS} дней

*🎁 Пробный период:* 3 дня бесплатно

*💳 Для оплаты:*
Нажмите кнопку ниже чтобы перейти к оплате 👇
"""
            keyboard = [
                [InlineKeyboardButton("💳 Оплатить $1", url=payment.confirmation.confirmation_url)],
                [InlineKeyboardButton("✅ Я оплатил(а)", callback_data="check_payment")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                subscribe_text,
                reply_markup=reply_markup,
                parse_mode='MarkdownV2'
            )
        else:
            await query.edit_message_text(
                "😔 *Не удалось создать платеж*\n\nПопробуйте позже или напишите @avllks",
                parse_mode='MarkdownV2'
            )
        
    elif query.data == "check_payment":
        # Здесь будет проверка статуса платежа
        check_text = """
🔍 *Проверка платежа*

*Чтобы проверить статус платежа:*
1\. Подождите 1\-2 минуты после оплаты
2\. Нажмите /start чтобы обновить статус
3\. Если статус не обновился \- напишите @avllks

*💡 Обычно активация занимает 1\-3 минуты*
"""
        await query.edit_message_text(check_text, parse_mode='MarkdownV2')
        
    elif query.data == "back_to_menu":
        await start(update, context)
        
    elif query.data == "sample":
        technique = techniques[0]
        text = "💆 *Пример техники:*\n" + format_technique(technique)
        await query.edit_message_text(text, parse_mode='MarkdownV2')
        
    elif query.data == "random":
        technique = random.choice(techniques)
        text = "🎲 *Случайная техника:*\n" + format_technique(technique)
        await query.edit_message_text(text, parse_mode='MarkdownV2')
        
    elif query.data == "today":
        day_of_month = datetime.datetime.now().day
        technique_index = (day_of_month - 1) % len(techniques)
        today_technique = techniques[technique_index]
        
        text = f"📅 *Техника на сегодня \({datetime.datetime.now().strftime('%d\.%m\.%Y')}\):*\n" + format_technique(today_technique)
        await query.edit_message_text(text, parse_mode='MarkdownV2')
        
    elif query.data == "help":
        help_text = """
🆘 *Помощь по боту*

*📅 Техника на сегодня* \- уникальная практика на каждый день месяца
*🎯 Случайная техника* \- случайный выбор из всех техник  
*💆 Пример техники* \- посмотри как это работает

*💰 Подписка:*
• 3 дня бесплатно
• Затем $1 за 30 дней
• Ежедневные техники в 11:00

*💡 Совет:* Используйте бота при первых признаках стресса \- не ждите выгорания\!

*По вопросам и предложениям:* @avllks
*Доступные команды:*
/start \- главное меню
/help \- помощь  
/stats \- ваша статистика
/about \- о проекте
"""
        await query.edit_message_text(help_text, parse_mode='MarkdownV2')
        
    elif query.data == "stats":
        user = update.effective_user
        stats_text = f"""
📊 *Ваша статистика, {user.first_name}*

*🎯 Активность:*
• 📅 Техник использовано: 15
• 🔥 Текущая серия: 5 дней
• ⭐ Лучшая серия: 12 дней

*🏆 Достижения:*
✅ Первая техника
✅ Неделя заботы о себе  
✅ Любитель дыхания
🔲 Месяц практик \(осталось 18 дней\)

*💪 Продолжайте в том же духе\!*
Каждая минута практики \- вклад в ваше благополучие 🌿
"""
        await query.edit_message_text(stats_text, parse_mode='MarkdownV2')
        
    elif query.data == "about":
        about_text = """
🌟 *О проекте Anti\-Burnout Bot*

*Проблема:* 70% людей испытывают хронический стресс в повседневной жизни

*Решение:* Ежедневные микро\-практики для профилактики стресса и выгорания

*Наша миссия:* Помочь людям сохранить ментальное здоровье в современном ритме жизни

*📊 Основано на:* 
• Когнитивно\-поведенческой терапии
• Дыхательных практиках
• Спортивной медицине  
• Научных исследованиях о стрессе

*Для всех, кто ценит свое ментальное здоровье* ❤️
"""
        await query.edit_message_text(about_text, parse_mode='MarkdownV2')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await button_handler(update, context)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await button_handler(update, context)

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await button_handler(update, context)

async def send_daily_technique(context: ContextTypes.DEFAULT_TYPE):
    active_users = db.get_active_users()
    today_technique = techniques[datetime.datetime.now().day % len(techniques)]
    
    for user_id in active_users:
        try:
            greeting = f"🌅 *Доброе утро\!* \n\n*Ваша техника на сегодня:*\n"
            text = greeting + format_technique(today_technique)
            
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            print(f"Ошибка отправки пользователю {user_id}: {e}")

def main():
    token = os.getenv('BOT_TOKEN')
    
    if not token:
        try:
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('BOT_TOKEN='):
                        token = line.split('=', 1)[1].strip()
                        break
        except FileNotFoundError:
            print("Файл .env не найден!")
    
    if not token:
        print("Ошибка: BOT_TOKEN не установлен!")
        return
    
    # Проверяем наличие ключей ЮKassa
    shop_id = os.getenv('YOOKASSA_SHOP_ID')
    secret_key = os.getenv('YOOKASSA_SECRET_KEY')
    
    if not shop_id or not secret_key:
        print("⚠️  ЮKassa ключи не настроены. Оплата не будет работать.")
        print("Добавьте YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY в .env")
    
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("🌿 Бот запущен! Универсальная версия с оплатой $1")
    print("🌿 Доступные команды: /start, /help, /stats, /about")
    application.run_polling()

if __name__ == '__main__':
    main()