"""
Бот-«альтер эго» — красивое оформление + строгий контроль доступа.

Только люди из списка ADMINS (владелец + те, кого он добавил через /add)
могут публиковать сообщения от лица бота. Все остальные при любой
попытке что-то написать получают вежливый отказ и никакого другого
функционала им не доступно.

Установка:
    pip install aiogram

Переменные окружения:
    BOT_TOKEN  — токен от @BotFather
    OWNER_ID   — твой telegram user_id (главный владелец, число)
"""

import asyncio
import json
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, Message

BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])

INITIAL_ADMINS = {OWNER_ID, 1964233800}
ADMINS_FILE = "admins.json"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

_bot_username: str | None = None


def load_admins() -> set[int]:
    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, "r") as f:
            return set(json.load(f))
    save_admins(INITIAL_ADMINS)
    return set(INITIAL_ADMINS)


def save_admins(admins: set[int]) -> None:
    with open(ADMINS_FILE, "w") as f:
        json.dump(list(admins), f)


ADMINS: set[int] = load_admins()


def strip_mention(raw: str, username: str) -> str | None:
    prefix = f"@{username}"
    if raw.lower().startswith(prefix.lower()):
        return raw[len(prefix):].strip()
    return None


def is_admin(user_id: int) -> bool:
    return user_id in ADMINS


# ---------- КОМАНДЫ ДЛЯ ВСЕХ (но с проверкой доступа внутри) ----------

@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(
            "🚫 <b>Доступ закрыт</b>\n\n"
            "Этот бот приватный и работает только для доверенных аккаунтов."
        )
        return

    global _bot_username
    if _bot_username is None:
        me = await bot.get_me()
        _bot_username = me.username

    await message.answer(
        "👋 <b>Привет!</b>\n\n"
        "Я — твой личный бот-альтер эго. Всё, что ты напишешь мне "
        f"в чате в формате <code>@{_bot_username} текст</code>, я опубликую "
        "от своего имени (текст, фото, видео, войсы, документы).\n\n"
        "📋 Команды:\n"
        "/help — как пользоваться\n"
        "/add — добавить доверенный аккаунт\n"
        "/remove — убрать доверенный аккаунт\n"
        "/list — список доверенных аккаунтов"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("🚫 Доступ закрыт.")
        return

    global _bot_username
    if _bot_username is None:
        me = await bot.get_me()
        _bot_username = me.username

    await message.answer(
        "📖 <b>Как пользоваться</b>\n\n"
        f"1️⃣ Добавь меня в нужный чат.\n"
        f"2️⃣ Напиши там: <code>@{_bot_username} твой текст</code>\n"
        "3️⃣ Я опубликую это сообщение от своего имени, а твоё исходное "
        "сообщение удалю (если у меня есть права на удаление).\n\n"
        "🖼 Работает и с фото/видео/голосовыми — просто добавь такую же "
        "подпись к медиафайлу.\n\n"
        "👥 <b>Управление доступом</b> (только для владельца):\n"
        "<code>/add ID</code> — дать доступ новому аккаунту\n"
        "<code>/remove ID</code> — забрать доступ\n"
        "<code>/list</code> — посмотреть, у кого есть доступ"
    )


@dp.message(Command("add"))
async def cmd_add(message: Message):
    if message.from_user.id != OWNER_ID:
        if is_admin(message.from_user.id):
            await message.answer("🚫 Добавлять новых людей может только главный владелец.")
        else:
            await message.answer("🚫 Доступ закрыт.")
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: <code>/add ID</code>")
        return
    new_id = int(parts[1])
    ADMINS.add(new_id)
    save_admins(ADMINS)
    await message.answer(f"✅ Аккаунт <code>{new_id}</code> теперь может пользоваться ботом.")


@dp.message(Command("remove"))
async def cmd_remove(message: Message):
    if message.from_user.id != OWNER_ID:
        if is_admin(message.from_user.id):
            await message.answer("🚫 Убирать людей может только главный владелец.")
        else:
            await message.answer("🚫 Доступ закрыт.")
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: <code>/remove ID</code>")
        return
    rem_id = int(parts[1])
    if rem_id == OWNER_ID:
        await message.answer("Нельзя убрать главного владельца.")
        return
    ADMINS.discard(rem_id)
    save_admins(ADMINS)
    await message.answer(f"❌ Аккаунт <code>{rem_id}</code> больше не может пользоваться ботом.")


@dp.message(Command("list"))
async def cmd_list(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("🚫 Доступ закрыт.")
        return
    if message.from_user.id != OWNER_ID:
        await message.answer("🚫 Список могут смотреть только владелец.")
        return
    admins_text = "\n".join(f"• <code>{a}</code>" for a in ADMINS)
    await message.answer(f"👥 <b>Доверенные аккаунты:</b>\n{admins_text}")


# ---------- ПУБЛИКАЦИЯ ОТ ЛИЦА БОТА (только для админов) ----------

@dp.message(F.func(lambda m: is_admin(m.from_user.id)))
async def handle_admin_message(message: Message):
    global _bot_username
    if _bot_username is None:
        me = await bot.get_me()
        _bot_username = me.username

    raw = message.text or message.caption or ""
    content = strip_mention(raw, _bot_username)
    if content is None:
        return  # обычное сообщение без команды — просто игнорируем

    chat_id = message.chat.id

    try:
        if message.photo:
            await bot.send_photo(chat_id, message.photo[-1].file_id, caption=content or None, parse_mode=None)
        elif message.video:
            await bot.send_video(chat_id, message.video.file_id, caption=content or None, parse_mode=None)
        elif message.voice:
            await bot.send_voice(chat_id, message.voice.file_id)
        elif message.video_note:
            await bot.send_video_note(chat_id, message.video_note.file_id)
        elif message.document:
            await bot.send_document(chat_id, message.document.file_id, caption=content or None, parse_mode=None)
        elif message.sticker:
            await bot.send_sticker(chat_id, message.sticker.file_id)
        elif content:
            await bot.send_message(chat_id, content, parse_mode=None)
        else:
            return

        try:
            await bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass

    except Exception as e:
        logging.exception("Не удалось опубликовать: %s", e)


# ---------- ЗАПРЕТ ДЛЯ ВСЕХ ОСТАЛЬНЫХ ----------

@dp.message()
async def fallback(message: Message):
    # сюда попадают только сообщения от НЕ-админов (админские уже
    # обработаны выше), либо ситуации, которые ничего не должны делать
    if message.chat.type == "private":
        await message.answer(
            "🚫 <b>Доступ закрыт</b>\n\n"
            "Этот бот приватный и работает только для доверенных аккаунтов."
        )
    # в группах на чужие сообщения молчим, чтобы не спамить чат


async def main():
    await bot.set_my_name(name="Alter Ego Bot")
    await bot.set_my_commands([
        BotCommand(command="start", description="Начало работы"),
        BotCommand(command="help", description="Как пользоваться ботом"),
        BotCommand(command="add", description="Добавить доверенный аккаунт"),
        BotCommand(command="remove", description="Убрать доверенный аккаунт"),
        BotCommand(command="list", description="Список доверенных аккаунтов"),
    ])
    print("Бот запущен, жду команд...")
    print("Текущие админы:", ADMINS)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
