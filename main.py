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

from quotes import QUOTES

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

# --- Supabase настройки ---
SUPABASE_URL = "https://foibyfoisadaaobwdmbq.supabase.co"
SUPABASE_KEY = "sb_publishable_36KIhuPO7H484TorQRuP3g_FDVBWlHj"

# --- ДОСТИЖЕНИЯ В СТИЛЕ СТЭТХЭМА С МЕДАЛЬКАМИ ---
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

# --- HTTP функции для работы с Supabase ---

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

# --- РАБОТА С ДАННЫМИ (Supabase) ---

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
        await supabase_insert("users", {"user_id": user_id})

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

# --- Хранилище последних цитат ---
last_quotes = {}

# --- Работа с прогрессом ---
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

# --- Работа с избранным ---
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

# --- ЗАДЕРЖКА ДЛЯ БЕСПЛАТНЫХ ПОЛЬЗОВАТЕЛЕЙ ---
async def apply_delay(user_id: int, message: types.Message):
    """Применяет задержку 10 секунд для бесплатных пользователей в личных чатах"""
    if message.chat.type in ["group", "supergroup"]:
        return
    
    is_premium = await get_premium_status(user_id)
    if not is_premium:
        wait_msg = await message.answer(
            "⏳ Подожди 10 секунд... (купи премиум за 30 Stars, чтобы убрать задержку!)"
        )
        await asyncio.sleep(10)
        await wait_msg.delete()

# --- Варианты утренних сообщений ---
MORNING_MESSAGES = [
    "🌅 Доброе утро! Вот твоя цитата дня:",
    "📖 Новый день — новая цитата:",
    "☀️ Отличное утро! Лови вдохновение:",
    "🌟 Доброе утро! Твоя цитата:",
    "🍀 Утро добрым не бывает, но цитата его исправит:",
]

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

# --- Установка меню команд ---
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
        f"Живи теперь с этим.\n\n"
        f"Нажми на кнопку, чтобы начать новый круг."
    )
    
    await reset_progress_for_user(user_id)
    
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
    users = await get_all_users()
    if not users:
        logger.info("Нет пользователей для уведомления")
        return
    
    for user_id in users:
        try:
            user_id_int = int(user_id)
            quote, threshold, emoji, achievement_text = await get_next_quote_for_user(user_id_int)
            morning_text = random.choice(MORNING_MESSAGES)
            
            if quote is None:
                await send_congratulation_to_user(user_id_int, user_id_int)
                continue
            
            last_quotes[user_id_int] = quote
            await bot.send_message(
                chat_id=user_id,
                text=f"{morning_text}\n\n📜 {quote}",
                parse_mode="HTML",
                reply_markup=get_quote_button(),
                disable_notification=False
            )
            logger.info(f"Уведомление с цитатой отправлено пользователю {user_id}")
            
            if achievement_text:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"{emoji} <b>Достижение!</b>\n\n{achievement_text}",
                    parse_mode="HTML"
                )
            
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

# --- ФУНКЦИЯ ПОКАЗА ИЗБРАННОГО ---
async def show_favorites_page(message: types.Message, user_id: str):
    # Проверяем премиум-статус
    is_premium = await get_premium_status(int(user_id))
    if not is_premium:
        await message.answer(
            "🔒 <b>Избранное доступно только с премиумом!</b>\n\n"
            "Купи премиум за 30 Stars, чтобы сохранять и просматривать цитаты.\n"
            "Отправь /premium — и получи доступ навсегда!",
            parse_mode="HTML"
        )
        return
    
    fav_list = await get_user_favorites(user_id)
    if not fav_list:
        await message.answer("📭 У вас пока нет избранных цитат.\n\nЧтобы сохранить цитату, получите её, а затем напишите /save")
        return
    
    text = "⭐ <b>Ваши избранные цитаты:</b>\n\n"
    keyboard = []
    
    for i, quote in enumerate(fav_list, 1):
        text += f"{i}. {quote}\n"
        if len(text) > 3500:
            text += "\n... и ещё несколько цитат"
            for j in range(i, len(fav_list)):
                short_quote = fav_list[j][:30] + "..." if len(fav_list[j]) > 30 else fav_list[j]
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"🗑️ {short_quote}",
                        callback_data=f"remove_fav_{j}"
                    )
                ])
            break
    
    if not keyboard:
        for i, quote in enumerate(fav_list):
            short_quote = quote[:30] + "..." if len(quote) > 30 else quote
            keyboard.append([
                InlineKeyboardButton(
                    text=f"🗑️ {short_quote}",
                    callback_data=f"remove_fav_{i}"
                )
            ])
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
    )

# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = str(message.from_user.id)
    await add_user_to_list(user_id)
    
    await reset_progress_for_user(int(user_id))
    await message.answer(
        "📖 <b>Привет! Я бот-цитатник</b>\n\n"
        "Нажми на кнопку ниже — я пришлю тебе случайную цитату!\n"
        f"Всего цитат: <b>{len(QUOTES)}</b>\n\n"
        "🌅 Каждое утро я буду присылать тебе цитату дня!\n"
        "Команды: /help — список всех команд\n\n"
        "⭐ Купи премиум за 30 Stars — и получи доступ к избранному и убирай задержку! /premium",
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
        "/premium — купить премиум (30 Stars)\n"
        "/status — проверить статус\n"
        "/help — это сообщение"
    )
    await message.answer(help_text, parse_mode="HTML")

# --- ПРЕМИУМ ---
@dp.message(Command("premium"))
async def buy_premium(message: types.Message):
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="🎖 Премиум-доступ к цитатнику",
        description="Неограниченные цитаты, эксклюзивные подборки и безлимитное избранное — навсегда! 🔥",
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
        payload = message.successful_payment.invoice_payload
        
        if payload == "premium_forever":
            # Начисляем премиум-статус
            user_id_str = str(user_id)
            existing = await supabase_get("users", user_id_str)
            if existing:
                await supabase_update("users", user_id_str, {"is_premium": True})
            else:
                await supabase_insert("users", {
                    "user_id": user_id_str,
                    "is_premium": True
                })
            await message.answer("🎉 Поздравляю! Премиум-доступ активирован навсегда!\n\nТеперь ты можешь пользоваться избранным и читать цитаты без задержек! 🚀")

# --- СТАТУС ---
@dp.message(Command("status"))
async def check_status(message: types.Message):
    user_id = message.from_user.id
    is_premium = await get_premium_status(user_id)
    
    if is_premium:
        await message.answer("🎖 <b>У вас есть премиум-доступ!</b>\n\n✅ Безлимитные цитаты\n✅ Без задержек\n✅ Избранное доступно\n\nСпасибо, что поддерживаешь бота! 🙌", parse_mode="HTML")
    else:
        await message.answer(
            "🔓 <b>У вас бесплатный доступ</b>\n\n"
            "⏳ Задержка 10 секунд между цитатами\n"
            "🔒 Избранное заблокировано\n\n"
            "Отправь /premium и купи премиум за 30 Stars! ⭐",
            parse_mode="HTML"
        )

# --- СОХРАНЕНИЕ ПОСЛЕДНЕЙ ЦИТАТЫ ---
@dp.message(Command("save"))
@dp.message(Command("сохранить"))
async def save_quote_command(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем премиум-статус
    is_premium = await get_premium_status(user_id)
    if not is_premium:
        await message.answer(
            "🔒 <b>Избранное доступно только с премиумом!</b>\n\n"
            "Купи премиум за 30 Stars, чтобы сохранять цитаты.\n"
            "Отправь /premium — и получи доступ навсегда!",
            parse_mode="HTML"
        )
        return
    
    if user_id not in last_quotes:
        await message.answer("❌ У вас нет последней цитаты для сохранения.\nСначала получите цитату!")
        return
    
    quote = last_quotes[user_id]
    if await add_favorite(user_id, quote):
        await message.answer("✅ Цитата сохранена в избранное!")
    else:
        await message.answer("⚠️ Цитата уже есть в избранном.")

# --- ИЗБРАННОЕ ---
@dp.message(Command("favorites"))
async def favorites_command(message: types.Message):
    user_id = str(message.from_user.id)
    await show_favorites_page(message, user_id)

# --- ОБРАБОТКА СЛОВА "ЦИТАТА" В СООБЩЕНИЯХ ---
@dp.message(lambda message: message.text and "цитата" in message.text.lower())
async def quote_by_keyword(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        chat_id = message.chat.id
        quote, threshold, emoji, achievement_text = await get_next_quote_for_user(chat_id)
        
        if quote is None:
            await send_congratulation(message)
        else:
            await message.answer(f"📜 {quote}", disable_notification=True)
            
            if achievement_text:
                await message.answer(
                    f"{emoji} <b>Достижение!</b>\n\n{achievement_text}",
                    parse_mode="HTML"
                )
    else:
        user_id = message.from_user.id
        
        # Применяем задержку для бесплатных
        await apply_delay(user_id, message)
        
        quote, threshold, emoji, achievement_text = await get_next_quote_for_user(user_id)
        
        if quote is None:
            await send_congratulation(message)
        else:
            last_quotes[user_id] = quote
            await message.answer(
                f"📜 {quote}",
                reply_markup=get_quote_button(),
                disable_notification=True
            )
            
            if achievement_text:
                await message.answer(
                    f"{emoji} <b>Достижение!</b>\n\n{achievement_text}",
                    parse_mode="HTML"
                )

@dp.message(Command("stop_notify"))
async def stop_notify_command(message: types.Message):
    user_id = str(message.from_user.id)
    await remove_user_from_list(user_id)
    await message.answer("❌ Ты отписался от ежедневных уведомлений.")

@dp.message(Command("broadcast"))
async def broadcast_command(message: types.Message):
    admin_id = 5251304637  # ЗАМЕНИТЕ НА ВАШ ID
    if message.from_user.id != admin_id:
        await message.answer("❌ У вас нет прав для этой команды.")
        return
    
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("❌ Введите текст для рассылки.\nПример: /broadcast Привет! Новые цитаты!")
        return
    
    users = await get_all_users()
    if not users:
        await message.answer("❌ Нет подписчиков для рассылки.")
        return
    
    sent = 0
    failed = 0
    
    for user_id in users:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=f"📢 <b>Обновление!</b>\n\n{text}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception as e:
            failed += 1
            logger.error(f"Не удалось отправить {user_id}: {e}")
    
    await message.answer(
        f"✅ Рассылка завершена!\n"
        f"📨 Отправлено: {sent}\n"
        f"❌ Не удалось: {failed}"
    )

@dp.message(Command("quote"))
async def quote_command(message: types.Message):
    user_id = message.from_user.id
    
    # Применяем задержку для бесплатных
    await apply_delay(user_id, message)
    
    quote, threshold, emoji, achievement_text = await get_next_quote_for_user(user_id)
    
    if quote is None:
        await send_congratulation(message)
    else:
        last_quotes[user_id] = quote
        await message.answer(
            f"📜 {quote}",
            reply_markup=get_quote_button(),
            disable_notification=True
        )
        
        if achievement_text:
            await message.answer(
                f"{emoji} <b>Достижение!</b>\n\n{achievement_text}",
                parse_mode="HTML"
            )

@dp.message(Command("reset"))
async def reset_command(message: types.Message):
    user_id = message.from_user.id
    await reset_progress_for_user(user_id)
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
    
    await reset_progress_for_user(user_id)
    
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
        
        # Применяем задержку для бесплатных
        await apply_delay(user_id, callback_query.message)
        
        quote, threshold, emoji, achievement_text = await get_next_quote_for_user(user_id)
        
        if quote is None:
            await send_congratulation(callback_query.message)
        else:
            last_quotes[user_id] = quote
            await callback_query.message.answer(
                f"📜 {quote}",
                reply_markup=get_quote_button(),
                disable_notification=True
            )
            
            if achievement_text:
                await callback_query.message.answer(
                    f"{emoji} <b>Достижение!</b>\n\n{achievement_text}",
                    parse_mode="HTML"
                )
        
        await callback_query.answer()
        
    except Exception as e:
        if "query is too old" in str(e) or "query ID is invalid" in str(e):
            await callback_query.message.answer(
                "⏳ Кнопка устарела. Нажми /start, чтобы получить новую!"
            )
        else:
            logger.error(f"Ошибка: {e}")

@dp.callback_query(lambda c: c.data and c.data.startswith("remove_fav_"))
async def remove_favorite_callback(callback_query: types.CallbackQuery):
    try:
        user_id = str(callback_query.from_user.id)
        index = int(callback_query.data.split("_")[2])
        fav_list = await get_user_favorites(user_id)
        
        # Проверяем премиум-статус
        is_premium = await get_premium_status(int(user_id))
        if not is_premium:
            await callback_query.answer("🔒 Только для премиум!", show_alert=True)
            return
        
        if index >= len(fav_list):
            await callback_query.answer("❌ Цитата не найдена.", show_alert=True)
            return
        
        quote = fav_list[index]
        if await remove_favorite(int(user_id), quote):
            await callback_query.answer("✅ Цитата удалена из избранного!", show_alert=True)
            await show_favorites_page(callback_query.message, user_id)
        else:
            await callback_query.answer("❌ Ошибка при удалении.", show_alert=True)
        
    except Exception as e:
        logger.error(f"Ошибка удаления из избранного: {e}")
        await callback_query.answer("❌ Ошибка при удалении.", show_alert=True)

@dp.callback_query(lambda c: c.data == "reset_progress")
async def reset_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    await reset_progress_for_user(user_id)
    first_quote, _, _, _ = await get_next_quote_for_user(user_id)
    
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
    
    await polling_task

if __name__ == "__main__":
    asyncio.run(main())
