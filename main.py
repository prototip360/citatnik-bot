import asyncio
import os
import random
import json
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiohttp import web

from quotes import QUOTES

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

# --- Файлы ---
STATE_FILE = "state.json"
USERS_FILE = "users.json"

# --- Загрузка пользователей ---
def load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(users), f, ensure_ascii=False, indent=2)

users = load_users()

# --- Состояние цитат ---
def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("shuffled_quotes", []), data.get("current_index", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        shuffled = QUOTES.copy()
        random.shuffle(shuffled)
        return shuffled, 0

def save_state(shuffled_quotes, current_index):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "shuffled_quotes": shuffled_quotes,
            "current_index": current_index
        }, f, ensure_ascii=False, indent=2)

shuffled_quotes, current_index = load_state()

def get_next_quote():
    global shuffled_quotes, current_index
    if current_index >= len(shuffled_quotes):
        return None
    quote = shuffled_quotes[current_index]
    current_index += 1
    save_state(shuffled_quotes, current_index)
    return quote

def reset_progress():
    global shuffled_quotes, current_index
    shuffled_quotes = QUOTES.copy()
    random.shuffle(shuffled_quotes)
    current_index = 0
    save_state(shuffled_quotes, current_index)

# --- Варианты утренних сообщений ---
MORNING_MESSAGES = [
    "🌅 Доброе утро! Пора получить новую цитату!",
    "📖 Новый день — новая цитата!",
    "☀️ Отличное утро! Готов получить вдохновение?",
    "🌟 Доброе утро! Нажми на кнопку — получи цитату дня!",
    "🍀 Утро добрым не бывает, но цитата его исправит!",
    "Джейсон навалил, мудрости отборной. Пора разгрибать!",
]

def get_quote_button():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Новая цитата", callback_data="get_quote")]
        ]
    )

def get_reset_button():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Начать заново", callback_data="reset_progress")]
        ]
    )

# --- Логирование ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ЕЖЕДНЕВНОЕ УВЕДОМЛЕНИЕ ---
async def send_daily_notification():
    """Отправляет уведомление всем пользователям"""
    if not users:
        logger.info("Нет пользователей для уведомления")
        return
    
    morning_text = random.choice(MORNING_MESSAGES)
    
    for user_id in users:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=f"{morning_text}",
                parse_mode="HTML",
                reply_markup=get_quote_button()
            )
            logger.info(f"Уведомление отправлено пользователю {user_id}")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление {user_id}: {e}")

async def daily_task():
    """Задача, которая выполняется каждый день в 10:00"""
    while True:
        now = datetime.now()
        target = datetime(now.year, now.month, now.day, 10, 0, 0)
        if now >= target:
            target = target + timedelta(days=1)
        
        wait_seconds = (target - now).total_seconds()
        logger.info(f"Следующее уведомление в {target.strftime('%H:%M')}")
        await asyncio.sleep(wait_seconds)
        
        await send_daily_notification()

# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def start_command(message: types.Message):
    global users
    users.add(message.from_user.id)
    save_users(users)
    
    reset_progress()
    await message.answer(
        "Нажми на кнопку ниже — я пришлю тебе случайную цитату!\n"
        f"Всего цитат: <b>{len(QUOTES)}</b>\n\n"
        "🌅 Каждое утро я буду присылать тебе вдохновляющее сообщение!\n"
        "Команды: /help — список всех команд",
        parse_mode="HTML",
        reply_markup=get_quote_button()
    )

@dp.message(Command("help"))
async def help_command(message: types.Message):
    help_text = (
        "📖 <b>Команды бота-цитатника</b>\n\n"
        "/start — начать заново\n"
        "/reset — сбросить прогресс\n"
        "/stop_notify — отписаться от уведомлений\n"
        "/help — это сообщение"
    )
    await message.answer(help_text, parse_mode="HTML")

@dp.message(Command("stop_notify"))
async def stop_notify_command(message: types.Message):
    global users
    user_id = message.from_user.id
    if user_id in users:
        users.remove(user_id)
        save_users(users)
        await message.answer("❌ Ты отписался от ежедневных уведомлений.")
    else:
        await message.answer("Ты и так не подписан на уведомления.")

@dp.message(Command("quote"))
async def quote_command(message: types.Message):
    quote = get_next_quote()
    if quote is None:
        await send_congratulation(message)
    else:
        await message.answer(
            f"📜 {quote}",
            reply_markup=get_quote_button()
        )

@dp.message(Command("reset"))
async def reset_command(message: types.Message):
    reset_progress()
    await message.answer(
        f"🔄 Прогресс сброшен. Цитаты начинаются сначала!\n"
        f"Всего цитат: <b>{len(QUOTES)}</b>",
        parse_mode="HTML",
        reply_markup=get_quote_button()
    )

@dp.message(Command("congratulate"))
async def congratulate_command(message: types.Message):
    await send_congratulation(message)

# --- ПОЗДРАВЛЕНИЕ ---
async def send_congratulation(message: types.Message):
    photo_path = "congratulation.jpg"
    
    user = message.from_user
    if user.first_name:
        user_name = user.first_name
    elif user.username:
        user_name = f"@{user.username}"
    else:
        user_name = "Друг"
    
    caption = (
        f"🎉 <b>Поздравляю, {user_name}!</b> 🎉\n\n"
        f"Ты открыл все <b>{len(QUOTES)}</b> цитат!\n"
        f"Нажми на кнопку, чтобы начать новый круг."
    )
    
    try:
        photo = FSInputFile(photo_path)
        await message.answer_photo(
            photo=photo,
            caption=caption,
            parse_mode="HTML",
            reply_markup=get_reset_button()
        )
    except FileNotFoundError:
        await message.answer(
            caption,
            parse_mode="HTML",
            reply_markup=get_reset_button()
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке фото: {e}")
        await message.answer(
            caption,
            parse_mode="HTML",
            reply_markup=get_reset_button()
        )

# --- КНОПКИ ---
@dp.callback_query(lambda c: c.data == "get_quote")
async def send_random_quote(callback_query: types.CallbackQuery):
    try:
        quote = get_next_quote()
        
        if quote is None:
            await send_congratulation(callback_query.message)
        else:
            await callback_query.message.answer(
                f"📜 {quote}",
                reply_markup=get_quote_button()
            )
        
        await callback_query.answer()
        
    except Exception as e:
        if "query is too old" in str(e) or "query ID is invalid" in str(e):
            await callback_query.message.answer(
                "⏳ Кнопка устарела. Нажми /start, чтобы получить новую!"
            )
        else:
            logger.error(f"Ошибка: {e}")

@dp.callback_query(lambda c: c.data == "reset_progress")
async def reset_callback(callback_query: types.CallbackQuery):
    reset_progress()
    first_quote = shuffled_quotes[0]
    global current_index
    current_index = 1
    save_state(shuffled_quotes, current_index)
    
    await callback_query.message.answer(
        f"🔄 <b>Новый круг!</b>\n\n"
        f"Все цитаты перемешаны!\n"
        f"Первая цитата:\n\n"
        f"📜 {first_quote}",
        parse_mode="HTML",
        reply_markup=get_quote_button()
    )
    await callback_query.answer()

# --- ЗАПУСК ---
async def main():
    asyncio.create_task(daily_task())
    
    polling_task = asyncio.create_task(dp.start_polling(bot))
    
    app = web.Application()
    
    async def health_check(request):
        return web.Response(text="OK")
    
    app.router.add_get("/healthz", health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8000)
    await site.start()
    
    logger.info("✅ Бот-цитатник запущен!")
    logger.info(f"✅ Загружено {len(QUOTES)} цитат")
    logger.info(f"✅ Подписчиков на уведомления: {len(users)}")
    
    await polling_task

if __name__ == "__main__":
    asyncio.run(main())
