import telebot
from telebot import types
import sqlite3
import json
from datetime import datetime, timedelta
import random
import os
from dotenv import load_dotenv
from database import add_user, get_user_stats, update_user_stats, check_subscription, save_payment, update_payment
from payment import create_payment, check_payment

# Загружаем переменные окружения из .env
load_dotenv()

# Настройки
TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

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

# =================== ЗАПУСК БОТА ===================

if __name__ == '__main__':
    print("🤖 Бот запущен...")
    bot.infinity_polling()