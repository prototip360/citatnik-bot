import asyncio
import os
import random
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

# --- Система "без повторений" ---
shuffled_quotes = QUOTES.copy()
random.shuffle(shuffled_quotes)
current_index = 0

def get_next_quote():
    """Возвращает следующую цитату из перемешанного списка."""
    global shuffled_quotes, current_index
    
    if current_index >= len(shuffled_quotes):
        shuffled_quotes = QUOTES.copy()
        random.shuffle(shuffled_quotes)
        current_index = 0
    
    quote = shuffled_quotes[current_index]
    current_index += 1
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
    await message.answer(
        "📖 <b>Привет! Я бот-цитатник</b>\n\n"
        "Нажми на кнопку ниже — я пришлю тебе случайную цитату!\n"
        "Ни одна цитата не повторится, пока не будут показаны все.",
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
    
    await polling_task

if __name__ == "__main__":
    asyncio.run(main())
