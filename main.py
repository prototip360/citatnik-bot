import asyncio
import os
import random
import json
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BotCommand, MenuButtonCommands, LabeledPrice, PreCheckoutQuery, SuccessfulPayment
from aiohttp import web
import aiohttp

try:
    from quotes import QUOTES
    logging.info(f"✅ Загружено {len(QUOTES)} цитат из quotes.py")
except Exception as e:
    logging.error(f"❌ ОШИБКА ЗАГРУЗКИ quotes.py: {e}")
    QUOTES = []

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

# --- Supabase настройки ---
SUPABASE_URL = "https://foibyfoisadaaobwdmbq.supabase.co"
SUPABASE_KEY = "sb_publishable_36KIhuPO7H484TorQRuP3g_FDVBWlHj"

# --- ДОСТИЖЕНИЯ ---
ACHIEVEMENTS = {
    10: {"emoji": "🥉", "text": "10 цитат. Так может каждый."},
    25: {"emoji": "🥉", "text": "25 цитат. Неплохо. Для начала."},
    50: {"emoji": "🥈", "text": "50 цитат. Мог бы и больше, но и так сойдёт."},
    100: {"emoji": "🥈", "text": "100 цитат. Теперь ты понимаешь, о чём я."},
    200: {"emoji": "🥇", "text": "200 цитат. Я бы сказал, что впечатлён, но я не впечатлительный."},
    300: {"emoji": "🥇", "text": "300 цитат. Ты всё ещё здесь. Упёртый, как баран."},
    400: {"emoji": "🏅", "text": "400 цитат. Я начинаю уважать твою настойчивость. Начинаю."},
    500: {"emoji": "🏅", "text": "500 цитат. Половина пути. Или ещё нет. Похуй."},
    600: {"emoji": "🌟", "text": "600 цитат. Ты серьёзно? Ладно, молодец. Только не говори, что я это сказал."},
    700: {"emoji": "🌟", "text": "700 цитат. Ты уже почти как я. Но не совсем."},
    800: {"emoji": "⭐", "text": "800 цитат. Я знаю, ты не остановишься. Упёртый, блин."},
    900: {"emoji": "👑", "text": "900 цитат. Ещё чуть-чуть и ты меня догонишь. Но не догонишь."},
}

# --- HTTP функции для Supabase ---
async def supabase_get(table: str, user_id: str = None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    if user_id:
        url += f"?user_id=eq.{user_id}"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                logging.warning(f"GET {table} статус {resp.status}")
                return []
        except Exception as e:
            logging.error(f"Ошибка GET {table}: {e}")
            return []

async def supabase_insert(table: str, data: dict):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data) as resp:
                return resp.status in [200, 201, 204]
        except Exception as e:
            logging.error(f"Ошибка INSERT {table}: {e}")
            return False

async def supabase_update(table: str, user_id: str, data: dict):
    url = f"{SUPABASE_URL}/rest/v1/{table}?user_id=eq.{user_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(url, headers=headers, json=data) as resp:
                return resp.status == 204
        except Exception as e:
            logging.error(f"Ошибка UPDATE {table}: {e}")
            return False

async def supabase_delete(table: str, user_id: str):
    url = f"{SUPABASE_URL}/rest/v1/{table}?user_id=eq.{user_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.delete(url, headers=headers) as resp:
                return resp.status == 204
        except Exception as e:
            logging.error(f"Ошибка DELETE {table}: {e}")
            return False

# --- РАБОТА С ДАННЫМИ ---
async def get_user_progress(user_id: str):
    data = await supabase_get("user_progress", user_id)
    return data[0] if data else None

async def save_user_progress_supabase(user_id: str, shuffled_quotes: list, current_index: int):
    existing = await get_user_progress(user_id)
    if existing:
        await supabase_update("user_progress", user_id, {
            "shuffled_quotes": shuffled_quotes,
            "current_index": current_index
        })
    else:
        await supabase_insert("user_progress", {
            "user_id": user_id,
            "shuffled_quotes": shuffled_quotes,
            "current_index": current_index
        })

async def get_user_favorites(user_id: str):
    data = await supabase_get("favorites", user_id)
    return data[0].get("quotes", []) if data else []

async def save_user_favorites(user_id: str, quotes: list):
    existing = await supabase_get("favorites", user_id)
    if existing:
        await supabase_update("favorites", user_id, {"quotes": quotes})
    else:
        await supabase_insert("favorites", {
            "user_id": user_id,
            "quotes": quotes
        })

async def is_user_exists(user_id: str):
    data = await supabase_get("users", user_id)
    return bool(data)

async def add_user_to_list(user_id: str):
    if not await is_user_exists(user_id):
        await supabase_insert("users", {"user_id": user_id, "is_premium": False})

async def get_all_users():
    data = await supabase_get("users")
    return [row["user_id"] for row in data]

async def remove_user_from_list(user_id: str):
    await supabase_delete("users", user_id)

async def get_premium_status(user_id: int):
    user_data = await supabase_get("users", str(user_id))
    if user_data:
        return user_data[0].get("is_premium", False)
    return False

# --- Хранилище ---
last_quotes = {}
last_request_time = {}

async def check_delay(user_id: int, message: types.Message) -> bool:
    if message.chat.type in ["group", "supergroup"]:
        return True
    
    is_premium = await get_premium_status(user_id)
    if is_premium:
        return True
    
    now = datetime.now()
    if user_id in last_request_time:
        elapsed = (now - last_request_time[user_id]).total_seconds()
        if elapsed < 10:
            wait_time = 10 - int(elapsed)
            wait_msg = await message.answer(
                f"⏳ Подожди ещё {wait_time} секунд..."
            )
            await asyncio.sleep(wait_time + 0.5)
            await wait_msg.delete()
            return False
    
    last_request_time[user_id] = now
    return True

async def get_user_state(user_id: int):
    user_id_str = str(user_id)
    existing = await get_user_progress(user_id_str)
    
    if not existing:
        shuffled = QUOTES.copy()
        random.shuffle(shuffled)
        await save_user_progress_supabase(user_id_str, shuffled, 0)
        return {"shuffled_quotes": shuffled, "current_index": 0}
    else:
        old_quotes = existing.get("shuffled_quotes", [])
        new_quotes = [q for q in QUOTES if q not in old_quotes]
        if new_quotes:
            old_quotes.extend(new_quotes)
            await save_user_progress_supabase(user_id_str, old_quotes, existing.get("current_index", 0))
            return {"shuffled_quotes": old_quotes, "current_index": existing.get("current_index", 0)}
        return {
            "shuffled_quotes": existing.get("shuffled_quotes", []),
            "current_index": existing.get("current_index", 0)
        }

async def get_next_quote_for_user(user_id: int):
    state = await get_user_state(user_id)
    shuffled = state["shuffled_quotes"]
    index = state["current_index"]
    
    if index >= len(shuffled):
        return None, None, None
    
    old_index = index
    quote = shuffled[index]
    state["current_index"] = index + 1
    await save_user_progress_supabase(str(user_id), shuffled, state["current_index"])
    
    for threshold, data in ACHIEVEMENTS.items():
        if old_index < threshold <= state["current_index"]:
            return quote, threshold, data["emoji"], data["text"]
    
    return quote, None, None, None

async def reset_progress_for_user(user_id: int):
    shuffled = QUOTES.copy()
    random.shuffle(shuffled)
    await save_user_progress_supabase(str(user_id), shuffled, 0)

async def add_favorite(user_id: int, quote: str):
    user_id_str = str(user_id)
    favorites = await get_user_favorites(user_id_str)
    if quote not in favorites:
        favorites.append(quote)
        await save_user_favorites(user_id_str, favorites)
        return True
    return False

async def remove_favorite(user_id: int, quote: str):
    user_id_str = str(user_id)
    favorites = await get_user_favorites(user_id_str)
    if quote in favorites:
        favorites.remove(quote)
        await save_user_favorites(user_id_str, favorites)
        return True
    return False

# --- КНОПКИ ---
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

async def set_commands():
    commands = [
        BotCommand(command="start", description="Начать заново"),
        BotCommand(command="quote", description="Получить цитату"),
        BotCommand(command="reset", description="Сбросить прогресс"),
        BotCommand(command="premium", description="Купить премиум (30 Stars)"),
        BotCommand(command="status", description="Проверить статус"),
        BotCommand(command="help", description="Помощь"),
    ]
    await bot.set_my_commands(commands)

# --- ДИАГНОСТИКА: Ловим ВСЕ сообщения ---
@dp.message()
async def catch_all(message: types.Message):
    """ВРЕМЕННО: диагностика всех сообщений"""
    logger.info(f"📩 ВСЕ: {message.text} | Чат: {message.chat.id} | Тип: {message.chat.type}")
    
    # Если это группа — отвечаем
    if message.chat.type in ["group", "supergroup"]:
        await message.answer("✅ Бот видит сообщение в группе!")

# --- ОСНОВНАЯ ОБРАБОТКА СЛОВА "ЦИТАТА" ---
@dp.message(lambda message: message.text and "цитата" in message.text.lower())
async def quote_by_keyword(message: types.Message):
    logger.info(f"🔍 СЛОВО 'ЦИТАТА' найдено! Чат: {message.chat.id}, Тип: {message.chat.type}")
    
    if message.chat.type in ["group", "supergroup"]:
        chat_id = message.chat.id
        logger.info(f"📢 Группа {chat_id}, выдаём цитату")
        quote, threshold, emoji, achievement_text = await get_next_quote_for_user(chat_id)
        
        if quote is None:
            await send_congratulation(message)
        else:
            await message.answer(f"📜 {quote}")
            if achievement_text:
                await message.answer(f"{emoji} <b>Достижение!</b>\n\n{achievement_text}", parse_mode="HTML")
        return
    
    user_id = message.from_user.id
    if not await check_delay(user_id, message):
        return
    
    quote, threshold, emoji, achievement_text = await get_next_quote_for_user(user_id)
    
    if quote is None:
        await send_congratulation(message)
    else:
        last_quotes[user_id] = quote
        await message.answer(f"📜 {quote}", reply_markup=get_quote_button())
        if achievement_text:
            await message.answer(f"{emoji} <b>Достижение!</b>\n\n{achievement_text}", parse_mode="HTML")

# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = str(message.from_user.id)
    await add_user_to_list(user_id)
    await reset_progress_for_user(int(user_id))
    await message.answer(
        f"📖 <b>Привет! Я бот-цитатник</b>\n\n"
        f"Всего цитат: <b>{len(QUOTES)}</b>",
        parse_mode="HTML",
        reply_markup=get_quote_button()
    )

@dp.message(Command("status"))
async def check_status(message: types.Message):
    user_id = message.from_user.id
    await add_user_to_list(str(user_id))
    is_premium = await get_premium_status(user_id)
    
    if is_premium:
        await message.answer("🎖 У вас есть премиум-доступ!", parse_mode="HTML")
    else:
        await message.answer("🔓 У вас бесплатный доступ", parse_mode="HTML")

@dp.message(Command("reset"))
async def reset_command(message: types.Message):
    user_id = message.from_user.id
    await reset_progress_for_user(user_id)
    await message.answer("🔄 Прогресс сброшен!")

@dp.message(Command("quote"))
async def quote_command(message: types.Message):
    user_id = message.from_user.id
    if not await check_delay(user_id, message):
        return
    quote, threshold, emoji, achievement_text = await get_next_quote_for_user(user_id)
    if quote is None:
        await send_congratulation(message)
    else:
        last_quotes[user_id] = quote
        await message.answer(f"📜 {quote}", reply_markup=get_quote_button())

@dp.message(Command("premium"))
async def buy_premium(message: types.Message):
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="🎖 Премиум-доступ",
        description="Премиум навсегда!",
        payload="premium_forever",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="⭐ 30 Stars", amount=30)],
        start_parameter="premium"
    )

@dp.pre_checkout_query()
async def pre_checkout_query(pre_checkout: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout.id, ok=True)

@dp.message()
async def successful_payment(message: types.Message):
    if message.successful_payment:
        user_id = message.from_user.id
        user_id_str = str(user_id)
        existing = await supabase_get("users", user_id_str)
        if existing:
            await supabase_update("users", user_id_str, {"is_premium": True})
        else:
            await supabase_insert("users", {"user_id": user_id_str, "is_premium": True})
        await message.answer("🎉 Премиум активирован!")

@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer("/start - начать\n/quote - цитата\n/reset - сброс\n/premium - купить\n/status - статус")

async def send_congratulation(message: types.Message):
    user_id = message.from_user.id
    await reset_progress_for_user(user_id)
    await message.answer(f"🎉 Поздравляю! Ты прошёл все {len(QUOTES)} цитат!", reply_markup=get_reset_button())

@dp.callback_query(lambda c: c.data == "get_quote")
async def send_random_quote(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not await check_delay(user_id, callback_query.message):
        await callback_query.answer()
        return
    quote, threshold, emoji, achievement_text = await get_next_quote_for_user(user_id)
    if quote is None:
        await send_congratulation(callback_query.message)
    else:
        last_quotes[user_id] = quote
        await callback_query.message.answer(f"📜 {quote}", reply_markup=get_quote_button())
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "reset_progress")
async def reset_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    await reset_progress_for_user(user_id)
    await callback_query.message.answer("🔄 Новый круг!", reply_markup=get_quote_button())
    await callback_query.answer()

# --- ЗАПУСК ---
async def main():
    await set_commands()
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    
    logging.info("✅ Бот запускается...")
    
    asyncio.create_task(dp.start_polling(bot))
    
    app = web.Application()
    async def health_check(request):
        return web.Response(text="OK")
    app.router.add_get("/healthz", health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8000)
    await site.start()
    
    logging.info("✅ Бот-цитатник запущен!")

if __name__ == "__main__":
    asyncio.run(main())
