from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import json
import datetime
from database import Database
import os

# Вручную загружаем переменные из .env файла
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("💰 Оформить подписку", callback_data="subscribe")],
        [InlineKeyboardButton("🔍 Пример техники", callback_data="sample")],
        [InlineKeyboardButton("🎯 Случайная техника", callback_data="random")],
        [InlineKeyboardButton("📅 Техника на сегодня", callback_data="today")]  # ← ДОБАВЛЕНО
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\n"
        "Я бот против выгорания для IT-специалистов.\n\n"
        "Используй кнопки ниже чтобы получить техники для расслабления и фокусировки.",
        reply_markup=reply_markup
    )

def format_technique(tech):
    steps = "\n".join([f"• {step}" for step in tech['steps']])
    return f"**{tech['name']}**\n\n{tech['description']}\n\n{steps}\n\n💡 {tech['tip']}"

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "subscribe":
        await query.edit_message_text(
            "💳 Оформление подписки\n\n"
            "Стоимость: $10 в месяц\n"
            "Первые 3 дня — бесплатно!\n\n"
            "Для оплаты напишите @ваш_аккаунт"
        )
    elif query.data == "sample":
        technique = techniques[0]
        text = format_technique(technique)
        await query.edit_message_text(text, parse_mode='Markdown')
    elif query.data == "random":
        import random
        technique = random.choice(techniques)
        text = format_technique(technique)
        await query.edit_message_text(text, parse_mode='Markdown')
    elif query.data == "today":  # ← ДОБАВЛЕН ОБРАБОТЧИК
        # Техника на сегодня - выбирается по номеру дня месяца
        day_of_month = datetime.datetime.now().day
        technique_index = (day_of_month - 1) % len(techniques)  # -1 потому что индексы с 0
        today_technique = techniques[technique_index]
        
        text = format_technique(today_technique)
        text = f"📅 **Техника на сегодня ({datetime.datetime.now().strftime('%d.%m.%Y')}):**\n\n{text}"
        
        await query.edit_message_text(text, parse_mode='Markdown')

def main():
    # Получаем токен из переменных окружения
    token = os.getenv('BOT_TOKEN')
    
    # Если не нашли в переменных окружения, пробуем прочитать из .env вручную
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
        print("Проверь файл .env в папке:", os.getcwd())
        return
    
    application = Application.builder().token(token).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("Бот запущен! (с кнопкой 'Техника на сегодня')")
    print("Для выхода нажмите Ctrl+C")
    application.run_polling()

if __name__ == '__main__':
    main()