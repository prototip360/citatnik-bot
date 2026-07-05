import asyncio
import os
import random
import json
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# --- Импортируем цитаты из отдельного файла ---
from quotes import QUOTES

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

# --- Файл для сохранения прогресса ---
STATE_FILE = "state.json"

def load_state():
    """Загружает сохранённое состояние (порядок цитат и текущий индекс)"""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("shuffled_quotes", []), data.get("current_index", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        # Если файла нет — создаём новый перемешанный список
        shuffled = QUOTES.copy()
        random.shuffle(shuffled)
        return shuffled, 0

def save_state(shuffled_quotes, current_index):
    """Сохраняет текущее состояние в файл"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "shuffled_quotes": shuffled_quotes,
            "current_index": current_index
        }, f, ensure_ascii=False, indent=2)

# --- Загружаем состояние при запуске ---
shuffled_quotes, current_index = load_state()

def get_next_quote():
    """Возвращает следующую цитату и сохраняет прогресс"""
    global shuffled_quotes, current_index
    
    # Если дошли до конца — перемешиваем заново
    if current_index >= len(shuffled_quotes):
        shuffled_quotes = QUOTES.copy()
        random.shuffle(shuffled_quotes)
        current_index = 0
    
    quote = shuffled_quotes[current_index]
    current_index += 1
    
    # Сохраняем прогресс в файл
    save_state(shuffled_quotes, current_index)
    
    return quote

# --- Кнопка ---
def get_quote_button():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Новая цитата", callback_data="get_quote")]
        ]
    )

# --- Логирование ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Команда /start ---
@dp.message(Command("start"))
async def start_command(message: types.Message):
    # Сброс прогресса при команде /start
    global shuffled_quotes, current_index
    shuffled_quotes = QUOTES.copy()
    random.shuffle(shuffled_quotes)
    current_index = 0
    save_state(shuffled_quotes, current_index)
    
    await message.answer(
        "Нажми на кнопку ниже — я пришлю тебе случайную цитату!\n",
        parse_mode="HTML",
        reply_markup=get_quote_button()
    )

# --- Кнопка "Новая цитата" ---
@dp.callback_query(lambda c: c.data == "get_quote")
async def send_random_quote(callback_query: types.CallbackQuery):
    try:
        random_quote = get_next_quote()
        await callback_query.message.answer(
            f"📜 {random_quote}",
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

# --- Команда /quote ---
@dp.message(Command("quote"))
async def quote_command(message: types.Message):
    random_quote = get_next_quote()
    await message.answer(
        f"📜 {random_quote}",
        reply_markup=get_quote_button()
    )

# --- Команда /reset (сброс прогресса) ---
@dp.message(Command("reset"))
async def reset_command(message: types.Message):
    global shuffled_quotes, current_index
    shuffled_quotes = QUOTES.copy()
    random.shuffle(shuffled_quotes)
    current_index = 0
    save_state(shuffled_quotes, current_index)
    await message.answer("🔄 Прогресс сброшен. Цитаты начинаются сначала!")

# --- Запуск ---
async def main():
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
    logger.info(f"✅ Загружено {len(QUOTES)} цитат из файла quotes.py")
    logger.info(f"✅ Текущий прогресс: {current_index} из {len(QUOTES)}")
    
    await polling_task

if __name__ == "__main__":
    asyncio.run(main())
