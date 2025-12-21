# payment.py
from yookassa import Configuration, Payment
import uuid
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# ДЕБАГ: проверим, загрузились ли переменные
shop_id = os.getenv('YOOKASSA_SHOP_ID')
secret_key = os.getenv('YOOKASSA_SECRET_KEY')

print(f"DEBUG: YOOKASSA_SHOP_ID = {shop_id}")
print(f"DEBUG: YOOKASSA_SECRET_KEY = {'*' * 20 if secret_key else 'NOT FOUND'}")

# Настройки ЮКассы
Configuration.account_id = shop_id
Configuration.secret_key = secret_key

def create_payment(user_id, amount, description, return_url="https://t.me"):
    """
    Создаёт платёж в ЮКассе
    Возвращает ссылку для оплаты и payment_id
    """
    # Проверяем, что ключи установлены
    if not Configuration.account_id or not Configuration.secret_key:
        raise ValueError("Не настроены ключи ЮКассы (account_id или secret_key)")
    
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
    """Проверяет статус платежа (простая версия)"""
    try:
        payment = Payment.find_one(payment_id)
        return payment.status  # pending, waiting_for_capture, succeeded, canceled
    except Exception as e:
        print(f"Ошибка при проверке платежа {payment_id}: {e}")
        return "unknown"

def check_payment_with_details(payment_id):
    """
    Проверяет статус платежа с деталями
    Возвращает словарь с полной информацией
    """
    try:
        payment = Payment.find_one(payment_id)
        
        result = {
            'status': payment.status,
            'payment_id': payment.id,
            'paid': getattr(payment, 'paid', False),
            'cancellation_reason': getattr(payment, 'cancellation_details', {}).get('reason', ''),
            'created_at': getattr(payment, 'created_at', None),
            'expires_at': getattr(payment, 'expires_at', None)
        }
        
        # Добавляем сумму, если есть
        if hasattr(payment, 'amount'):
            result['amount'] = payment.amount.value
            result['currency'] = payment.amount.currency
        
        # Добавляем описание, если есть
        if hasattr(payment, 'description'):
            result['description'] = payment.description
        
        # Добавляем метаданные, если есть
        if hasattr(payment, 'metadata'):
            result['metadata'] = payment.metadata
        
        # Добавляем способ оплаты, если есть
        if hasattr(payment, 'payment_method'):
            result['payment_method'] = payment.payment_method.type
        
        return result
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'payment_id': payment_id
        }