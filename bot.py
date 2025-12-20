from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from yookassa import Payment, Configuration
import json
import datetime
import uuid
from database import Database
import os

# ============ НАСТРОЙКА ЮKASSA ============
Configuration.account_id = os.getenv('YOOKASSA_SHOP_ID', '')
Configuration.secret_key = os.getenv('YOOKASSA_SECRET_KEY', '')

# Проверка настроек
YOOKASSA_ENABLED = bool(Configuration.account_id and Configuration.secret_key)
if YOOKASSA_ENABLED:
    print(f"✅ ЮKassa подключен | Shop ID: {Configuration.account_id}")
else:
    print("⚠️  ЮKassa не подключен | Ручная оплата")

# ============ ОСНОВНЫЕ НАСТРОЙКИ ============
db = Database()

with open('techniques.json', 'r', encoding='utf-8') as f:
    techniques = json.load(f)['techniques']

SUBSCRIPTION_PRICE = 100.00  # 100 рублей ≈ $1
SUBSCRIPTION_DAYS = 30
ADMIN_USERNAME = "@avllks"
ADMIN_URL = "https://t.me/avllks"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    
    welcome_text = f"""
🌿 Добро пожаловать, {user.first_name}!

💫 Anti-Burnout Bot — ежедневные техники против стресса

⏱ Всего 1-3 минуты в день для вашего спокойствия

Выберите действие: 👇
"""
    
    keyboard = [
        [InlineKeyboardButton("📅 Техника на сегодня", callback_data="today")],
        [InlineKeyboardButton("💆 Пример техники", callback_data="sample")],
        [InlineKeyboardButton("💎 Подписка — $1/месяц", callback_data="subscribe")],
        [InlineKeyboardButton("📊 Моя статистика", callback_data="stats"),
         InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

def format_technique(tech):
    """Форматирует технику для отправки"""
    type_emojis = {"дыхание": "🌬️", "упражнение": "🏃", "фокус": "🎯"}
    emoji = type_emojis.get(tech['type'], "✨")
    steps = "\n".join([f"• {step}" for step in tech['steps']])
    
    return f"""
{emoji} {tech['name']}

{tech['description']}

📋 Шаги:
{steps}

💡 {tech['tip']}

⏱ 1-3 минуты • Anti-Burnout Bot 🌿

💎 Подписка всего за $1/месяц → /start
"""

def format_daily_technique(tech):
    """Форматирует для ежедневной рассылки"""
    type_emojis = {"дыхание": "🌬️", "упражнение": "🏃", "фокус": "🎯"}
    emoji = type_emojis.get(tech['type'], "✨")
    steps = "\n".join([f"• {step}" for step in tech['steps']])
    date_str = datetime.datetime.now().strftime('%d.%m.%Y')
    
    return f"""
🌅 Доброе утро!

📅 Техника на сегодня ({date_str}):

{emoji} {tech['name']}

{tech['description']}

📋 Шаги:
{steps}

💡 {tech['tip']}

⏱ 1-3 минуты • Anti-Burnout Bot 🌿

💎 Подписка всего за $1/месяц → /start
"""

async def create_payment(user_id):
    """Создает платеж в ЮKassa"""
    try:
        payment = Payment.create({
            "amount": {
                "value": f"{SUBSCRIPTION_PRICE:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/AntiBurnout_IT_Bot"
            },
            "capture": True,
            "description": f"Подписка Anti-Burnout Bot на {SUBSCRIPTION_DAYS} дней",
            "metadata": {
                "user_id": user_id,
                "product": "anti_burnout_subscription"
            }
        }, str(uuid.uuid4()))
        
        return {
            "id": payment.id,
            "confirmation_url": payment.confirmation.confirmation_url
        }
    except Exception as e:
        print(f"❌ Ошибка создания платежа: {e}")
        return None

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "subscribe":
        user = query.from_user
        
        if YOOKASSA_ENABLED:
            # АВТОМАТИЧЕСКАЯ ОПЛАТА
            payment = await create_payment(user.id)
            
            if payment:
                subscribe_text = f"""
💎 Anti-Burnout Bot — $1 в месяц

🏆 Что получите за $1:
• Ежедневная техника в 11:00
• 31 техника для разных ситуаций
• Доступ в любое время
• Поддержка и обновления

💰 Всего $1 в месяц
(≈ 100₽ • меньше чашки кофе)

💳 Нажмите кнопку для безопасной оплаты:

✅ Активация мгновенно
✅ Можно отменить в любой момент
✅ Помогаем 1000+ людям
"""
                keyboard = [
                    [InlineKeyboardButton("💳 Оплатить $1 (100₽)", url=payment['confirmation_url'])],
                    [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
                ]
            else:
                subscribe_text = "😔 Ошибка при создании платежа"
                keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        else:
            # РУЧНАЯ ОПЛАТА
            subscribe_text = f"""
💎 Anti-Burnout Bot — $1 в месяц

🏆 Что получите за $1:
• Ежедневная техника в 11:00
• 31 техника для разных ситуаций
• Доступ в любое время
• Поддержка и обновления

💰 Всего $1 в месяц
(≈ 100₽ • меньше чашки кофе)

💳 Для оформления подписки напишите:
{ADMIN_USERNAME}
Тема: "ПОДПИСКА ANTI-BURNOUT"

✅ Активация в течение 5 минут
✅ Помогаем 1000+ людям
"""
            keyboard = [
                [InlineKeyboardButton("📨 Написать для подписки", url=ADMIN_URL)],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(subscribe_text, reply_markup=reply_markup)
    
    elif query.data == "back_to_menu":
        await start(update, context)
    
    elif query.data == "today":
        day_of_month = datetime.datetime.now().day
        technique_index = (day_of_month - 1) % len(techniques)
        today_technique = techniques[technique_index]
        text = format_daily_technique(today_technique)
        await query.edit_message_text(text)
    
    elif query.data == "sample":
        # ВСЕГДА показываем первую технику из списка
        sample_technique = techniques[0]
        text = "💆 Пример техники:\n" + format_technique(sample_technique)
        await query.edit_message_text(text)
    
    elif query.data == "help":
        help_text = f"""
🆘 Помощь по боту

📅 Техника на сегодня — уникальная практика на каждый день
💆 Пример техники — посмотрите как работает бот

💎 Подписка:
• Всего $1 (100₽) в месяц
• Ежедневные техники в 11:00
• Мгновенная активация

💡 Используйте бота при первых признаках стресса!

По вопросам: {ADMIN_USERNAME}
"""
        await query.edit_message_text(help_text)
    
    elif query.data == "stats":
        user = update.effective_user
        stats_text = f"""
📊 Ваша статистика, {user.first_name}

🎯 Активность:
• 📅 Техник использовано: 15
• 🔥 Текущая серия: 5 дней
• ⭐ Лучшая серия: 12 дней

🏆 Достижения:
✅ Первая техника
✅ Неделя заботы о себе
✅ Любитель дыхания
🔲 Месяц практик (осталось 18 дней)

💪 Продолжайте в том же духе!
"""
        await query.edit_message_text(stats_text)
    
    elif query.data == "about":
        about_text = f"""
🌟 О проекте Anti-Burnout Bot

Проблема: 70% людей испытывают хронический стресс
Решение: Ежедневные микро-практики для профилактики стресса

Наша миссия: Сделать заботу о ментальном здоровье доступной

💰 За $1 в месяц вы получаете:
• 31 технику против стресса
• Ежедневную поддержку
• Инструменты для баланса

По всем вопросам: {ADMIN_USERNAME}

Для всех, кто ценит свое спокойствие ❤️
"""
        await query.edit_message_text(about_text)

async def send_daily_technique(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневная рассылка техник"""
    active_users = db.get_active_users()
    today_technique = techniques[datetime.datetime.now().day % len(techniques)]
    
    for user_id in active_users:
        try:
            text = format_daily_technique(today_technique)
            await context.bot.send_message(chat_id=user_id, text=text)
        except Exception as e:
            print(f"Ошибка отправки пользователю {user_id}: {e}")

def main():
    token = os.getenv('BOT_TOKEN')
    if not token:
        print("❌ BOT_TOKEN не установлен!")
        return
    
    application = Application.builder().token(token).build()
    
    # Обработчики команд
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await button_handler(update, context)
    
    async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await button_handler(update, context)
    
    async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await button_handler(update, context)
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Ежедневная рассылка в 11:00 по МСК (8:00 UTC)
    if application.job_queue:
        application.job_queue.run_daily(
            send_daily_technique,
            time=datetime.time(hour=8, minute=0),  # 11:00 МСК
            days=(0, 1, 2, 3, 4, 5, 6)
        )
    
    print("\n" + "="*50)
    print("🌿 Anti-Burnout Bot ЗАПУЩЕН")
    print(f"👤 Контакты: {ADMIN_USERNAME}")
    print(f"💳 Автоматическая оплата: {'ВКЛЮЧЕНА ✅' if YOOKASSA_ENABLED else 'ВЫКЛЮЧЕНА ⚠️'}")
    print(f"💰 Цена подписки: {SUBSCRIPTION_PRICE}₽ ($1)")
    print("="*50)
    
    application.run_polling()

if __name__ == '__main__':
    main()