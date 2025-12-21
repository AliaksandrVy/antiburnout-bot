# webhook_server.py - отдельный сервер для вебхуков ЮКассы
from flask import Flask, request, jsonify
import hmac
import hashlib
import os
import logging
from database import update_payment

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/webhook/yookassa', methods=['POST'])
def yookassa_webhook():
    """Обработчик вебхуков от ЮКассы"""
    try:
        # 1. Проверяем секретный ключ
        secret_key = os.getenv('YOOKASSA_WEBHOOK_SECRET')
        if not secret_key:
            logger.error("YOOKASSA_WEBHOOK_SECRET не настроен")
            return jsonify({'error': 'Webhook secret not configured'}), 500
        
        # 2. Проверяем подпись
        body = request.get_data()
        signature = hmac.new(
            secret_key.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        received_signature = request.headers.get('Yookassa-Signature', '')
        
        if not hmac.compare_digest(signature, received_signature):
            logger.warning("Неверная подпись вебхука")
            return jsonify({'error': 'Invalid signature'}), 400
        
        # 3. Обрабатываем событие
        data = request.json
        event = data.get('event')
        payment = data.get('object', {})
        payment_id = payment.get('id')
        
        logger.info(f"📨 Вебхук: {event} для платежа {payment_id}")
        
        if event == 'payment.succeeded':
            # Активируем подписку
            update_payment(payment_id, 'succeeded')
            logger.info(f"✅ Платеж {payment_id} успешен (через вебхук)")
            
        elif event == 'payment.canceled':
            update_payment(payment_id, 'canceled')
            logger.info(f"❌ Платеж {payment_id} отменен (через вебхук)")
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Ошибка обработки вебхука: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка здоровья сервера"""
    return jsonify({'status': 'ok', 'service': 'yookassa-webhook'})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info(f"🚀 Вебхук-сервер запущен на порту {port}")
    app.run(host='0.0.0.0', port=port)