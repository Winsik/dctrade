import sqlite3
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import asyncio

TOKEN = "YOUR_BOT_TOKEN"
DB_NAME = "exchange_bot.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Инициализация БД
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        give_type TEXT,      -- void, kb, dubloon
        give_amount INTEGER,
        give_server INTEGER,
        take_type TEXT,      -- void, kb, dubloon
        take_amount INTEGER,
        take_server INTEGER,
        status TEXT DEFAULT 'active',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

# Добавление предложения
def add_offer(user_id, give_type, give_amt, give_srv, take_type, take_amt, take_srv):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""INSERT INTO offers 
                 (user_id, give_type, give_amount, give_server, take_type, take_amount, take_server) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (user_id, give_type, give_amt, give_srv, take_type, take_amt, take_srv))
    conn.commit()
    
    # Ищем совпадения сразу после добавления
    matches = find_matches(user_id, give_type, give_amt, give_srv, take_type, take_amt, take_srv)
    conn.close()
    return matches

# Поиск прямых пар (Бартер)
def find_matches(new_uid, g_type, g_amt, g_srv, t_type, t_amt, t_srv):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Ищем тех, кто:
    # 1. Отдает то, что нам нужно (t_type, t_srv)
    # 2. Хочет получить то, что мы отдаем (g_type, g_srv)
    # Примечание: Здесь мы игнорируем точное количество для поиска контакта, 
    # но в реальном чате пользователи договорятся о курсе. 
    # Или можно фильтровать по amount, если хотим строгий автоматический матч.
    
    query = """
        SELECT user_id, give_amount, take_amount FROM offers 
        WHERE status = 'active' 
        AND user_id != ?
        AND give_type = ? 
        AND give_server = ?
        AND take_type = ?
        AND take_server = ?
    """
    
    c.execute(query, (new_uid, t_type, t_srv, g_type, g_srv))
    rows = c.fetchall()
    conn.close()
    
    matches = []
    for row in rows:
        match_uid, their_give_amt, their_take_amt = row
        # Здесь можно добавить проверку курса, если нужно строго:
        # Например, если new_user отдает 5, а match_user хочет получить ровно 5.
        # Но чаще в играх курс плавающий, поэтому просто даем контакт.
        matches.append({
            'user_id': match_uid,
            'their_offer': f"Отдает {their_give_amt} {t_type} (S{t_srv}) за {their_take_amt} {g_type} (S{g_srv})"
        })
        
    return matches

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Бот обмена ресурсами!\n\n"
        "Формат добавления:\n"
        "/add <что_отдаю> <кол-во> <сервер_отдачи> <что_беру> <кол-во> <сервер_получения>\n\n"
        "Типы: void, kb, dubloon\n"
        "Пример: /add void 5 12 kb 3 5\n"
        "(Отдам 5 пустот на 12 сервере за 3 КБ на 5 сервере)"
    )

@dp.message(Command("add"))
async def cmd_add(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) != 7:
            await message.answer("❌ Ошибка формата.\nИспользуйте: /add type amt srv type amt srv")
            return
        
        _, g_type, g_amt, g_srv, t_type, t_amt, t_srv = parts
        
        # Валидация
        valid_types = ['void', 'kb', 'dubloon']
        if g_type not in valid_types or t_type not in valid_types:
            await message.answer("❌ Неверный тип ресурса. Доступны: void, kb, dubloon")
            return
            
        g_amt, g_srv, t_amt, t_srv = int(g_amt), int(g_srv), int(t_amt), int(t_srv)
        
        if not (1 <= g_srv <= 18 and 1 <= t_srv <= 18):
            await message.answer("❌ Номер сервера должен быть от 1 до 18")
            return

        matches = add_offer(message.from_user.id, g_type, g_amt, g_srv, t_type, t_amt, t_srv)
        
        if matches:
            text = f"✅ Предложение добавлено! Найдено {len(matches)} потенциальных партнеров:\n\n"
            for m in matches:
                # Важно: не светим ID без согласия, лучше предложить написать в ЛС
                text += f"• Пользователь (ID: {m['user_id']})\n  Его условия: {m['their_offer']}\n\n"
            text += "Напишите им в личные сообщения для сделки."
            await message.answer(text)
            
            # Уведомляем партнеров
            for m in matches:
                try:
                    await bot.send_message(
                        m['user_id'], 
                        f"🔔 Новое встречное предложение!\n"
                        f"@{message.from_user.username or message.from_user.id} хочет обменяться с вами.\n"
                        f"Его условия: Отдает {g_amt} {g_type} (S{g_srv}) за {t_amt} {t_type} (S{t_srv})"
                    )
                except:
                    pass
        else:
            await message.answer("✅ Предложение добавлено в базу. Ожидайте встречных предложений.")
            
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}")

@dp.message(Command("my"))
async def cmd_my(message: types.Message):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM offers WHERE user_id = ? AND status = 'active'", (message.from_user.id,))
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        await message.answer("У вас нет активных предложений.")
        return
        
    text = "Ваши активные предложения:\n"
    for r in rows:
        # r: id, uid, g_type, g_amt, g_srv, t_type, t_amt, t_srv, status, date
        text += f"ID:{r[0]} | Отдам {r[3]} {r[2]} (S{r[4]}) <-> Возьму {r[6]} {r[5]} (S{r[7]})\n"
    
    text += "\nЧтобы удалить, напишите /del <ID>"
    await message.answer(text)

@dp.message(Command("del"))
async def cmd_del(message: types.Message):
    try:
        offer_id = int(message.text.split()[1])
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        # Проверяем, что удаляет именно владелец
        c.execute("SELECT user_id FROM offers WHERE id = ?", (offer_id,))
        res = c.fetchone()
        
        if res and res[0] == message.from_user.id:
            c.execute("UPDATE offers SET status = 'closed' WHERE id = ?", (offer_id,))
            conn.commit()
            await message.answer(f"Предложение {offer_id} удалено.")
        else:
            await message.answer("Ошибка: неверный ID или это не ваше предложение.")
        conn.close()
    except:
        await message.answer("Используйте: /del <ID>")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
