import os

# Попытка получить токен из переменной окружения (рекомендуется для продакшена)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Если переменной нет, берем из этого файла (для локальной разработки)
if not BOT_TOKEN:
    # ЗАМЕНИТЕ ЭТУ СТРОКУ НА ВАШ ТОКЕН ОТ @BotFather
    BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11" 

DB_NAME = "exchange_bot.db"
