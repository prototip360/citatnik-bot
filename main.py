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
    "«Завтра рано вставать\n       встану послезавтра» #11",
    "«Чем богаче дача\n       джими джими ача ача» #12",
    "«Не суди да не судимым будешь не буди да небуди дабудай» #13",
    "«Както раз один городской тип купил поселок\n       теперь это поселок городского типа» #14",
    "«Не трогай правоохранительные органы\n       они могут возбудить» #15",
    "«Итоги года знаешь?\n       Я подвел» #16",
    "«Кто последний\n       тот отец» #17",
    "«Я конечно лысый\n       но от фена неотказался бы» #18",
    "«Некруто пить\n       Некруто врать\n       Круто маме помогать» #19",
    "«Когда я заблудился в лесу\n       все кабаны разбежались» #20",
    "«По настоящему несгибаемым человека делает не характер и воспитание\n       а межпозвоночная грыжа» #21",
    "«Не бойся ножа\n       Бойся вилки\n       Один удар\n       Четыре дырки» #22",
    "«Если тебе где-то не рады в рваных носках\n       то и в целых идти туда не стоит» #23",
    "«Мотоцикл это транспорт\n       дальше не придумал пока» #24",
    "«Ты ушла\n       Не смыв за собой\n       И я понял\n       Что дышу тобой» #25",
    "«Если на ногах ногти\n       то на руках рукти» #26",
    "«Хороший асфальт\n       на дороге не валяется» #27",
    "«Слова пацана знаешь?\n       Я сказал» #28",
    "«Не стоит рассчитывать на таксистов\n       они могут нас подвезти» #29",
    "«Шкаф не тумба\n       Тимон не Пумба» #30",
    "«Если пьянка не избежна\n       пить надо первым» #31",
    "«Я живу как положено\n       а положено у меня на все» #32",
    "«Не ложусь спать когда устал\n       чтобы усталость не думала что она что-то решает» #33",
    "«Когда меня рожали\n       тогда я и родился» #34",
    "«За двумя зайцами погонишься\n       не вытащишь рыбку из пруда» #35",
    "«Если ничего не есть\n       то можно проголодаться» #36",
    "«Нужно делать как нужно\n       как не нужно\n       делать не нужно» #37",
    "«Я настоящий экстремал\n       я срал в гостях и не смывал» #38",
    "«Когда я смотрю на солцне\n       оно щуриться» #39",
    "«Принять мужчину таким какой он есть\n       может только военкомат» #40",
    "«Если сделать греческий салат 31 декабря то на следующий день он станет древнегреческим» #41",
    "«Лучше жопа в тепле\n       чем тепло в жопе» #42",
    "«Если жена делает тебя счастливым\n       то какая разница чья это жена» #43",
    "«Пиджак армани\n       насвай в кармане» #44",
    "«Аллу Пугачеву знаешь?\n       Я напугал» #45",
    "«Я лысый\n       но меня не погоняешь» #46",
    "«Если есть на свете рай\n       то это Краснодарский край» #47",
    "«Сначала потом\n       затем снова опять» #48",
    "«Братья\n       не будьте сестрами» #49",
    "«Кто обзывается\n       тот сам так называется» #50",
    "«Wildberries знаешь?\n       Я там работаю» #51",
    "«Запомните\n       а то забудите» #52",
    "«Купил девушке крем для ухода\n       а она не уходит» #53",
    "«Лучше синица в руках\n       чем рука в синице» #54",
    "«Взял нож - режь\n       Взял дошик - ешь» #55",
    "«Посрать без пука\n       как поесть шашлык без лука» #56",
    "«Только подкалбучник будет отпрашиваться у жены в бар с кентами, настоящий мужчина и так знает что нельзя» #57",
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
