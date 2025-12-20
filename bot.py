import telebot
from telebot import types
import sqlite3
import json
from datetime import datetime, timedelta
import random
import os
from database import add_user, get_user_stats, update_user_stats, check_subscription, add_subscription

# Настройки
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

# Загрузка техник
with open('techniques.json', 'r', encoding='utf-8') as f:
    techniques = json.load(f)

# =================== КЛАВИАТУРЫ ===================

# Главное меню с красивыми кнопками
main_menu_keyboard = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="🌟 ТЕХНИКА НА СЕГОДНЯ")],
        [types.KeyboardButton(text="📚 БИБЛИОТЕКА ТЕХНИК"), types.KeyboardButton(text="ℹ️ О ПРОЕКТЕ")],
        [types.KeyboardButton(text="💰 ПОДПИСКА"), types.KeyboardButton(text="👤 МОЙ ПРОФИЛЬ")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# Меню библиотеки
library_keyboard = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="🧘 ДЫХАТЕЛЬНЫЕ")],
        [types.KeyboardButton(text="💪 ФИЗИЧЕСКИЕ")],
        [types.KeyboardButton(text="🧠 ПСИХОЛОГИЧЕСКИЕ")],
        [types.KeyboardButton(text="🔙 НАЗАД В ГЛАВНОЕ МЕНЮ")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# Меню подписки
subscription_keyboard = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="💰 КУПИТЬ ПОДПИСКУ")],
        [types.KeyboardButton(text="📊 ИНФОРМАЦИЯ О ПОДПИСКЕ")],
        [types.KeyboardButton(text="🔙 НАЗАД В ГЛАВНОЕ МЕНЮ")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# Кнопка только "Назад" для простых экранов
back_keyboard = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="🔙 НАЗАД В ГЛАВНОЕ МЕНЮ")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

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

@bot.message_handler(func=lambda message: message.text == "📚 БИБЛИОТЕКА ТЕХНИК")
def library_menu(message):
    """Меню библиотеки техник"""
    response = (
        "📚 БИБЛИОТЕКА ТЕХНИК\n\n"
        "Выберите категорию техник:\n\n"
        "🧘 ДЫХАТЕЛЬНЫЕ - техники для успокоения и снятия стресса\n"
        "💪 ФИЗИЧЕСКИЕ - упражнения для тела и энергии\n"
        "🧠 ПСИХОЛОГИЧЕСКИЕ - ментальные практики и установки"
    )
    
    bot.send_message(message.chat.id, response, reply_markup=library_keyboard)

@bot.message_handler(func=lambda message: message.text in ["🧘 ДЫХАТЕЛЬНЫЕ", "💪 ФИЗИЧЕСКИЕ", "🧠 ПСИХОЛОГИЧЕСКИЕ"])
def show_category(message):
    """Показывает техники выбранной категории"""
    category_map = {
        "🧘 ДЫХАТЕЛЬНЫЕ": "дыхательные",
        "💪 ФИЗИЧЕСКИЕ": "физические", 
        "🧠 ПСИХОЛОГИЧЕСКИЕ": "психологические"
    }
    
    category = category_map[message.text]
    tech_list = techniques.get(category, [])
    
    if not tech_list:
        bot.send_message(message.chat.id, "Техники в этой категории пока не добавлены.", reply_markup=library_keyboard)
        return
    
    response = f"📚 {message.text} ТЕХНИКИ:\n\n"
    for i, tech in enumerate(tech_list[:10], 1):  # Показываем первые 10
        response += f"{i}. {tech['name']}\n"
        response += f"   ⏱ {tech.get('time', '5-10 мин')}\n"
        response += f"   {tech['description'][:100]}...\n\n"
    
    response += "Для просмотра подробного описания конкретной техники напишите её номер."
    bot.send_message(message.chat.id, response, reply_markup=library_keyboard)

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
        "По вопросам и предложениям: @ваш_контакт\n\n"
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
            f"💎 Стоимость: 299₽/месяц\n\n"
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

# =================== НАВИГАЦИЯ "НАЗАД" ===================

@bot.message_handler(func=lambda message: message.text == "🔙 НАЗАД В ГЛАВНОЕ МЕНЮ")
def back_to_main(message):
    """Возврат в главное меню"""
    response = "Вы вернулись в главное меню. Выберите действие:"
    bot.send_message(message.chat.id, response, reply_markup=main_menu_keyboard)

@bot.message_handler(func=lambda message: message.text == "📊 ИНФОРМАЦИЯ О ПОДПИСКЕ")
def subscription_info(message):
    """Информация о подписке"""
    response = (
        "📊 ИНФОРМАЦИЯ О ПОДПИСКЕ\n\n"
        "💎 Тарифы:\n"
        "• 1 месяц: 299₽\n"
        "• 3 месяца: 799₽ (скидка 10%)\n"
        "• 12 месяцев: 2399₽ (скидка 33%)\n\n"
        "✨ Что входит:\n"
        "✅ Персональные техники на каждый день\n"
        "✅ Полный доступ к библиотеке\n"
        "✅ Статистика и прогресс\n"
        "✅ Поддержка и советы\n\n"
        "🔄 Автопродление можно отключить в любой момент."
    )
    bot.send_message(message.chat.id, response, reply_markup=subscription_keyboard)

@bot.message_handler(func=lambda message: message.text == "💰 КУПИТЬ ПОДПИСКУ")
def buy_subscription(message):
    """Покупка подписки (заглушка для ЮКассы)"""
    response = (
        "💰 ОФОРМЛЕНИЕ ПОДПИСКИ\n\n"
        "Выберите период:\n\n"
        "1️⃣ 1 месяц - 299₽\n"
        "2️⃣ 3 месяца - 799₽\n"
        "3️⃣ 12 месяцев - 2399₽\n\n"
        "В ближайшее время здесь будет интеграция с ЮКассой для оплаты.\n"
        "А пока вы можете воспользоваться демо-версией функций."
    )
    bot.send_message(message.chat.id, response, reply_markup=subscription_keyboard)

# =================== ЗАПУСК БОТА ===================

if __name__ == '__main__':
    print("🤖 Бот запущен...")
    bot.infinity_polling()