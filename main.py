import asyncio
import os
import random
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web  # Добавляем веб-сервер

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

QUOTES = [
    
    "«Лучше конец света\n       чем конец у Светы» #1",
    "«Лучше с друзьями на велике\n       чем с чертями на гелике» #2",
    "«Охранник рынка единственный\n       кто следит за базаром» #3",
    "«Когда я читаю книгу\n       книга получает знания» #4",
    "«Крути педали\n       пока не дали» #5",
    "«Когда я падаю\n       звезда загадывает желание» #6",
    "«Чистые пруды знаешь?\n       я почистил» #7",
    "«Бросил гранату\n       убил 50 человек\n       потом она взорвалась» #8",
    "«Если заблудился в лесу\n       иди домой» #9",
    "«Когда в России запретили инстаграм\n       я разрешил» #10",
]

def get_quote_button():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Новая цитата", callback_data="get_quote")]
        ]
    )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "📖 <b>Привет! Я бот-цитатник</b>\n\n"
        "Нажми на кнопку ниже — я пришлю тебе случайную цитату!",
        parse_mode="HTML",
        reply_markup=get_quote_button()
    )

@dp.callback_query(lambda c: c.data == "get_quote")
async def send_random_quote(callback_query: types.CallbackQuery):
    try:
        random_quote = random.choice(QUOTES)
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

@dp.message(Command("quote"))
async def quote_command(message: types.Message):
    random_quote = random.choice(QUOTES)
    await message.answer(
        f"📜 {random_quote}",
        reply_markup=get_quote_button()
    )

async def main():
    # Запускаем бота в фоне
    polling_task = asyncio.create_task(dp.start_polling(bot))
    
    # Запускаем веб-сервер для UptimeRobot
    app = web.Application()
    
    async def health_check(request):
        return web.Response(text="OK")
    
    app.router.add_get("/healthz", health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8000)
    await site.start()
    
    logger.info("✅ Бот-цитатник запущен!")
    logger.info("✅ Веб-сервер для UptimeRobot на порту 8000")
    
    await polling_task

if __name__ == "__main__":
    asyncio.run(main())
