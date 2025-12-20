# payment.py
from yookassa import Configuration, Payment
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

# Настройки ЮКассы
Configuration.account_id = os.getenv('YOOKASSA_SHOP_ID')
Configuration.secret_key = os.getenv('YOOKASSA_SECRET_KEY')

def create_payment(user_id, amount, description, return_url="https://t.me/avllks"):
    """
    Создаёт платёж в ЮКассе
    Возвращает ссылку для оплаты и payment_id
    """
    # Генерируем уникальный id платежа
    idempotence_key = str(uuid.uuid4())
    
    # Создаём платёж
    payment = Payment.create({
        "amount": {
            "value": f"{amount:.2f}",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": return_url
        },
        "capture": True,
        "description": description,
        "metadata": {
            "user_id": user_id
        }
    }, idempotence_key)
    
    # Возвращаем ссылку для оплаты и id платежа
    payment_id = payment.id
    payment_url = payment.confirmation.confirmation_url
    
    return payment_id, payment_url

def check_payment(payment_id):
    """Проверяет статус платежа"""
    try:
        payment = Payment.find_one(payment_id)
        return payment.status  # pending, waiting_for_capture, succeeded, canceled
    except:
        return "unknown"