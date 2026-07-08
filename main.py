import asyncio
import os
import random
import json
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiohttp import web

# --- Импортируем цитаты ---
from quotes import QUOTES

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

# --- Файл для сохранения прогресса ---
STATE_FILE = "state.json"

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

# --- Загружаем состояние ---
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

# --- Кнопка "Новая цитата" ---
def get_quote_button():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Новая цитата", callback_data="get_quote")]
        ]
    )

# --- Кнопка "Начать заново" ---
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

# --- Команда /start ---
@dp.message(Command("start"))
async def start_command(message: types.Message):
    reset_progress()
    await message.answer(
        "Нажми на кнопку ниже — я пришлю тебе случайную цитату!\n"
        f"Всего цитат: <b>{len(QUOTES)}</b>",
        parse_mode="HTML",
        reply_markup=get_quote_button()
    )

# --- Отправка поздравления (одно сообщение: фото + подпись) ---
async def send_congratulation(message: types.Message):
    photo_path = "congratulation.jpg"
    
    # Подпись к фото
    caption = (
        f"🎉 <b>Поздравляю!</b> 🎉\n\n"
        f"Ты открыл все <b>{len(QUOTES)}</b> цитат!\n"
        f"Нажми на кнопку, чтобы начать новый круг."
    )
    
    try:
        with open(photo_path, "rb") as photo:
            await message.answer_photo(
                photo=InputFile(photo),
                caption=caption,
                parse_mode="HTML",
                reply_markup=get_reset_button()
            )
    except FileNotFoundError:
        # Если фото нет — отправляем текстом
        await message.answer(
            caption,
            parse_mode="HTML",
            reply_markup=get_reset_button()
        )

# --- Кнопка "Новая цитата" ---
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

# --- Кнопка "Начать заново" ---
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

# --- Команда /quote ---
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

# --- Команда /reset ---
@dp.message(Command("reset"))
async def reset_command(message: types.Message):
    reset_progress()
    await message.answer(
        f"🔄 Прогресс сброшен. Цитаты начинаются сначала!\n"
        f"Всего цитат: <b>{len(QUOTES)}</b>",
        parse_mode="HTML",
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
    logger.info(f"✅ Загружено {len(QUOTES)} цитат")
    
    await polling_task

if __name__ == "__main__":
    asyncio.run(main())
