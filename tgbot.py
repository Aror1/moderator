import asyncio
import logging
from datetime import datetime, timedelta

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ChatPermissions, ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramBadRequest

from classifier import is_toxic


BOT_TOKEN = "8296264601:AAFLcG2Hi8xV1P1TQlfv9qwuE2nJJh2S1l4"
WEATHER_API_KEY = "0ff35a61f1a94ffb82c0999ffb44273f"  # openweathermap.org

TOXICITY_THRESHOLD = 0.5
MAX_WARNINGS = 3
MUTE_DURATION = 60 * 10   # секунды
DELETE_TOXIC = True
MUTE_ON_WARNINGS = True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

warnings: dict[int, dict[int, int]] = {}


def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/weather"), KeyboardButton(text="/check")],
            [KeyboardButton(text="/warnings"), KeyboardButton(text="/help")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери команду...",
    )


def get_location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправить геопозицию", request_location=True)],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def get_warnings(chat_id: int, user_id: int) -> int:
    return warnings.get(chat_id, {}).get(user_id, 0)


def add_warning(chat_id: int, user_id: int) -> int:
    warnings.setdefault(chat_id, {})
    warnings[chat_id][user_id] = warnings[chat_id].get(user_id, 0) + 1
    return warnings[chat_id][user_id]


def reset_warnings(chat_id: int, user_id: int) -> None:
    if chat_id in warnings:
        warnings[chat_id].pop(user_id, None)


async def is_admin(chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except TelegramBadRequest:
        return False


async def get_city_name(session: aiohttp.ClientSession, lat: float, lon: float) -> str:
    url = "http://api.openweathermap.org/geo/1.0/reverse"
    params = {"lat": lat, "lon": lon, "limit": 1, "appid": WEATHER_API_KEY}
    try:
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data:
                    loc = data[0]
                    return loc.get("local_names", {}).get("ru") or loc.get("name", "")
    except Exception as e:
        logger.warning("Reverse geocoding: %s", e)
    return ""


async def get_weather_by_coords(lat: float, lon: float) -> dict | None:
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat, "lon": lon,
        "appid": WEATHER_API_KEY,
        "units": "metric", "lang": "ru",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.error("OpenWeather %s: %s", resp.status, await resp.text())
                    return None
                data = await resp.json()
            real_name = await get_city_name(session, lat, lon)
            if real_name:
                data["name"] = real_name
            return data
    except Exception as e:
        logger.error("Ошибка запроса погоды: %s", e)
        return None


def format_weather(data: dict) -> str:
    city    = data.get("name", "Неизвестно")
    country = data.get("sys", {}).get("country", "")

    temp       = data["main"]["temp"]
    feels_like = data["main"]["feels_like"]
    humidity   = data["main"]["humidity"]
    pressure   = data["main"]["pressure"]
    clouds     = data.get("clouds", {}).get("all", 0)
    desc       = data["weather"][0]["description"].capitalize()

    wind_speed = data["wind"]["speed"]
    wind_deg   = data["wind"].get("deg", 0)
    directions = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"]
    wind_dir   = directions[int((wind_deg + 22.5) / 45) % 8]

    sunrise = datetime.fromtimestamp(data["sys"]["sunrise"]).strftime("%H:%M")
    sunset  = datetime.fromtimestamp(data["sys"]["sunset"]).strftime("%H:%M")

    return (
        f"<b>Погода в {city}{', ' + country if country else ''}</b>\n\n"
        f"<b>Температура:</b> {temp:.1f}C\n"
        f"<b>Ощущается как:</b> {feels_like:.1f}C\n"
        f"<b>Давление:</b> {pressure} гПа\n"
        f"<b>Влажность:</b> {humidity}%\n"
        f"<b>Облачность:</b> {clouds}%\n\n"
        f"<b>Ветер:</b> {wind_speed} м/с, {wind_dir}\n\n"
        f"<b>Восход:</b> {sunrise}\n"
        f"<b>Закат:</b> {sunset}\n\n"
        f"<i>{desc}</i>\n"
        f"<i>{datetime.now().strftime('%H:%M %d.%m.%Y')}</i>"
    )



@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        f"Привет, <b>{message.from_user.first_name}</b>!\n\n"  # type: ignore
        "Я бот-модератор с функцией погоды.\n\n"
        "<b>Команды:</b>\n"
        "/weather — погода по геолокации\n"
        "/check — проверить текст на токсичность\n"
        "/warnings — мои предупреждения\n"
        "/resetwarn — сбросить предупреждения (ответом, для админов)\n"
        "/help — справка",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(),
    )


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>Справка</b>\n\n"
        "/weather — отправь геолокацию, получи погоду\n"
        "/check &lt;текст&gt; — проверить текст на токсичность\n"
        "/warnings — сколько предупреждений у тебя\n"
        "/resetwarn — (ответом на сообщение) сбросить предупреждения + снять мут\n\n"
        "<b>Модерация:</b>\n"
        f"Бот удаляет токсичные сообщения и мьютит после {MAX_WARNINGS} предупреждений.",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(),
    )


@dp.message(Command("weather"))
async def cmd_weather(message: Message) -> None:
    await message.answer(
        "Отправьте геопозицию, чтобы узнать погоду:",
        reply_markup=get_location_keyboard(),
    )


@dp.message(F.location)
async def location_handler(message: Message) -> None:
    lat = message.location.latitude  # type: ignore
    lon = message.location.longitude  # type: ignore

    loading = await message.answer("Получаю данные о погоде...")
    data = await get_weather_by_coords(lat, lon)

    if data:
        await loading.edit_text(format_weather(data), parse_mode="HTML")
    else:
        await loading.edit_text("Не удалось получить погоду. Попробуй позже.")

    await message.answer("Готово.", reply_markup=get_main_keyboard())


@dp.message(Command("check"))
async def cmd_check(message: Message) -> None:
    text = message.text.removeprefix("/check").strip()  # type: ignore
    if not text:
        await message.reply(
            "Укажи текст: <code>/check текст</code>",
            parse_mode="HTML",
            reply_markup=get_main_keyboard(),
        )
        return

    toxic, score = is_toxic(text, TOXICITY_THRESHOLD)
    label = "Токсично" if toxic else "Безопасно"
    
    logger.info("Уверенность в бане и классификации: {score:.1%}")

    await message.reply(
        f"<b>{label}</b>\n"
        f"Текст: <i>{text[:200]}</i>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(),
    )


@dp.message(Command("warnings"))
async def cmd_warnings(message: Message) -> None:
    if message.chat.type == "private":
        await message.answer("Эта команда работает только в группах.", reply_markup=get_main_keyboard())
        return
    user = message.from_user
    count = get_warnings(message.chat.id, user.id)  # type: ignore
    await message.reply(
        f"<b>{user.full_name}</b>, у тебя {count}/{MAX_WARNINGS} предупреждений.",  # type: ignore
        parse_mode="HTML",
    )


@dp.message(Command("resetwarn"))
async def cmd_resetwarn(message: Message) -> None:
    if not await is_admin(message.chat.id, message.from_user.id):  # type: ignore
        await message.reply("Только администраторы могут сбрасывать предупреждения.")
        return

    if not message.reply_to_message:
        await message.reply(
            "Ответь на сообщение пользователя командой <code>/resetwarn</code>",
            parse_mode="HTML",
        )
        return

    target = message.reply_to_message.from_user
    if not target:
        await message.reply("Не удалось определить пользователя.")
        return

    reset_warnings(message.chat.id, target.id)

    try:
        await bot.restrict_chat_member(
            message.chat.id,
            target.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_send_polls=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False,
            ),
        )
        await message.reply(
            f"Предупреждения <b>{target.full_name}</b> сброшены и мут снят.",
            parse_mode="HTML",
        )
    except TelegramBadRequest as e:
        logger.warning("Не удалось снять мут: %s", e)
        await message.reply(
            f"Предупреждения <b>{target.full_name}</b> сброшены.",
            parse_mode="HTML",
        )


@dp.message(F.text == "Отмена")
async def cancel_handler(message: Message) -> None:
    await message.answer("Отменено.", reply_markup=get_main_keyboard())



# moderation
@dp.message(F.text & F.chat.type.in_({"group", "supergroup"}))
async def moderate_message(message: Message) -> None:
    if await is_admin(message.chat.id, message.from_user.id):  # type: ignore
        return

    text = message.text or message.caption or ""
    if not text:
        return

    toxic, score = is_toxic(text, TOXICITY_THRESHOLD)
    logger.info(
        "chat=%s user=%s score=%.2f toxic=%s text=%.60r",
        message.chat.id, message.from_user.id, score, toxic, text,  # type: ignore
    )

    if not toxic:
        return

    user = message.from_user
    warn_count = add_warning(message.chat.id, user.id)  # type: ignore

    if DELETE_TOXIC:
        try:
            await message.delete()
        except TelegramBadRequest as e:
            logger.warning("Не удалось удалить сообщение: %s", e)

    if MUTE_ON_WARNINGS and warn_count >= MAX_WARNINGS:
        try:
            until = datetime.now() + timedelta(seconds=MUTE_DURATION) if MUTE_DURATION else None
            await bot.restrict_chat_member(
                message.chat.id,
                user.id,  # type: ignore
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until,
            )
            reset_warnings(message.chat.id, user.id)  # type: ignore
            duration_text = f"на {MUTE_DURATION // 60} мин." if MUTE_DURATION else "навсегда"
            await message.answer(
                f"<b>{user.full_name}</b> замьючен {duration_text} "  # type: ignore
                f"за систематические нарушения.",
                parse_mode="HTML",
            )
        except TelegramBadRequest as e:
            logger.warning("Не удалось замутить: %s", e)
    else:
        remaining = MAX_WARNINGS - warn_count
        await message.answer(
            f"<b>{user.full_name}</b>, сообщение удалено за токсичность "  # type: ignore
            f"(уверенность: {score:.0%}).\n"
            f"Предупреждение {warn_count}/{MAX_WARNINGS}. "
            f"Ещё {remaining} — мут.",
            parse_mode="HTML",
        )



# entry

async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())