import asyncio
import os
import random
import json
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BotCommand, MenuButtonCommands
from aiohttp import web

from quotes import QUOTES

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

# --- Файл для сохранения прогресса ПОЛЬЗОВАТЕЛЕЙ ---
PROGRESS_FILE = "user_progress.json"

# --- Загрузка пользователей (для уведомлений) ---
USERS_FILE = "users.json"

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

# --- Загрузка прогресса для всех пользователей ---
def load_user_progress():
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_user_progress(progress):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

user_progress = load_user_progress()

def get_user_state(user_id: int):
    if str(user_id) not in user_progress:
        shuffled = QUOTES.copy()
        random.shuffle(shuffled)
        user_progress[str(user_id)] = {
            "shuffled_quotes": shuffled,
            "current_index": 0
        }
        save_user_progress(user_progress)
    return user_progress[str(user_id)]

def get_next_quote_for_user(user_id: int):
    state = get_user_state(user_id)
    shuffled = state["shuffled_quotes"]
    index = state["current_index"]
    
    if index >= len(shuffled):
        return None
    
    quote = shuffled[index]
    state["current_index"] = index + 1
    save_user_progress(user_progress)
    return quote

def reset_progress_for_user(user_id: int):
    shuffled = QUOTES.copy()
    random.shuffle(shuffled)
    user_progress[str(user_id)] = {
        "shuffled_quotes": shuffled,
        "current_index": 0
    }
    save_user_progress(user_progress)

# --- Варианты утренних сообщений ---
MORNING_MESSAGES = [
    "🌅 Доброе утро! Вот твоя цитата дня:",
    "📖 Новый день — новая цитата:",
    "☀️ Отличное утро! Лови вдохновение:",
    "🌟 Доброе утро! Твоя цитата:",
    "🍀 Утро добрым не бывает, но цитата его исправит:",
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

# --- Установка меню команд ---
async def set_commands():
    commands = [
        BotCommand(command="start", description="Начать заново"),
        BotCommand(command="quote", description="Получить цитату"),
        BotCommand(command="reset", description="Сбросить прогресс"),
        BotCommand(command="help", description="Помощь"),
    ]
    await bot.set_my_commands(commands)

# --- ЕЖЕДНЕВНОЕ УВЕДОМЛЕНИЕ ---
async def send_congratulation_to_user(user_id: int, chat_id: int):
    try:
        user = await bot.get_chat(user_id)
        user_name = user.first_name or user.username or "Друг"
    except:
        user_name = "Друг"
    
    caption = (
        f"🎉 <b>Поздравляю, {user_name}!</b> 🎉\n\n"
        f"Ты прошёл все <b>{len(QUOTES)}</b> цитат!\n"
        f"Нажми на кнопку, чтобы начать новый круг."
    )
    
    reset_progress_for_user(user_id)
    
    try:
        photo = FSInputFile("congratulation.jpg")
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            parse_mode="HTML",
            reply_markup=get_reset_button(),
            disable_notification=False
        )
    except FileNotFoundError:
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode="HTML",
            reply_markup=get_reset_button()
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке поздравления: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode="HTML",
            reply_markup=get_reset_button()
        )

async def send_daily_notification():
    if not users:
        logger.info("Нет пользователей для уведомления")
        return
    
    for user_id in users:
        try:
            quote = get_next_quote_for_user(user_id)
            morning_text = random.choice(MORNING_MESSAGES)
            
            if quote is None:
                await send_congratulation_to_user(user_id, user_id)
                continue
            
            await bot.send_message(
                chat_id=user_id,
                text=f"{morning_text}\n\n📜 {quote}",
                parse_mode="HTML",
                reply_markup=get_quote_button(),
                disable_notification=False
            )
            logger.info(f"Уведомление с цитатой отправлено пользователю {user_id}")
            
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление {user_id}: {e}")

async def daily_task():
    while True:
        now = datetime.now()
        target = datetime(now.year, now.month, now.day, 5, 0, 0)
        if now >= target:
            target = target + timedelta(days=1)
        
        wait_seconds = (target - now).total_seconds()
        logger.info(f"Следующее уведомление в {target.strftime('%H:%M')} UTC")
        await asyncio.sleep(wait_seconds)
        await send_daily_notification()

# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def start_command(message: types.Message):
    global users
    user_id = message.from_user.id
    users.add(user_id)
    save_users(users)
    
    reset_progress_for_user(user_id)
    await message.answer(
        "📖 <b>Привет! Я бот-цитатник</b>\n\n"
        "Нажми на кнопку ниже — я пришлю тебе случайную цитату!\n"
        f"Всего цитат: <b>{len(QUOTES)}</b>\n\n"
        "🌅 Каждое утро я буду присылать тебе цитату дня!\n"
        "Команды: /help — список всех команд",
        parse_mode="HTML",
        reply_markup=get_quote_button()
    )

@dp.message(Command("help"))
async def help_command(message: types.Message):
    help_text = (
        "📖 <b>Команды бота-цитатника</b>\n\n"
        "/start — начать заново\n"
        "/quote — получить следующую цитату\n"
        "/reset — сбросить прогресс\n"
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
    user_id = message.from_user.id
    quote = get_next_quote_for_user(user_id)
    if quote is None:
        await send_congratulation(message)
    else:
        await message.answer(
            f"📜 {quote}",
            reply_markup=get_quote_button(),
            disable_notification=True
        )

@dp.message(Command("reset"))
async def reset_command(message: types.Message):
    user_id = message.from_user.id
    reset_progress_for_user(user_id)
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
    user_id = message.from_user.id
    
    user = message.from_user
    user_name = user.first_name or user.username or "Друг"
    
    caption = (
        f"🎉 <b>Поздравляю, {user_name}!</b> 🎉\n\n"
        f"Ты прошёл все <b>{len(QUOTES)}</b> цитат!\n"
        f"Нажми на кнопку, чтобы начать новый круг."
    )
    
    reset_progress_for_user(user_id)
    
    try:
        photo = FSInputFile(photo_path)
        await message.answer_photo(
            photo=photo,
            caption=caption,
            parse_mode="HTML",
            reply_markup=get_reset_button(),
            disable_notification=True
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
        user_id = callback_query.from_user.id
        quote = get_next_quote_for_user(user_id)
        
        if quote is None:
            await send_congratulation(callback_query.message)
        else:
            await callback_query.message.answer(
                f"📜 {quote}",
                reply_markup=get_quote_button(),
                disable_notification=True
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
    user_id = callback_query.from_user.id
    reset_progress_for_user(user_id)
    first_quote = get_next_quote_for_user(user_id)
    
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
    await set_commands()
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    
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
