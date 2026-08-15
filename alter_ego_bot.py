"""
Бот-«альтер эго» v3 — личный кабинет.

Как это работает:
  - Всё, что пишут в чатах, где состоит бот, прилетает тебе в личку
    с кнопкой «↩️ Ответить».
  - Нажимаешь кнопку → бот просит написать ответ → твой следующий
    текст/фото/видео уходит в тот самый чат от лица бота.
  - Можно и без кнопки: просто напиши боту в личку — сообщение уйдёт
    в последний чат, откуда тебе что-то прилетало.
  - Обычные люди (не из списка доверенных) не получают от бота вообще
    никакого ответа — ни на /start, ни на что-либо ещё. Полная тишина.

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
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])

INITIAL_ADMINS = {OWNER_ID, 1964233800}
ADMINS_FILE = "admins.json"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- хранение списка доверенных ---

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


def is_admin(user_id: int) -> bool:
    return user_id in ADMINS


# pending_reply[admin_id] = (target_chat_id, original_message_id) — если admin нажал "Ответить"
pending_reply: dict[int, tuple[int, int]] = {}
# last_chat[admin_id] = chat_id — куда уйдёт ответ, если кнопку не нажимали
last_chat: dict[int, int] = {}


# ---------- КОМАНДЫ (полная тишина для чужих) ----------

@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        return  # ничего не отвечаем посторонним
    await message.answer(
        "👋 <b>Привет!</b>\n\n"
        "Я пересылаю тебе сюда всё, что пишут в чатах, где я состою. "
        "Под каждым сообщением есть кнопка «↩️ Ответить» — нажми и напиши "
        "текст, фото или видео, я опубликую это от своего имени в том же чате.\n\n"
        "Можно и без кнопки — просто напиши мне, и сообщение уйдёт в последний "
        "чат, откуда тебе что-то приходило.\n\n"
        "📋 Команды:\n"
        "/help — справка\n"
        "/add — добавить доверенный аккаунт\n"
        "/remove — убрать доверенный аккаунт\n"
        "/list — список доверенных аккаунтов"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "📖 <b>Как пользоваться</b>\n\n"
        "1️⃣ Добавь меня в нужный чат.\n"
        "2️⃣ Когда там кто-то напишет — сообщение придёт тебе сюда с кнопкой "
        "«↩️ Ответить».\n"
        "3️⃣ Нажми кнопку, напиши ответ (текст/фото/видео/голосовое/документ) — "
        "я опубликую это в том чате от своего имени.\n\n"
        "👥 <b>Управление доступом</b> (только владелец):\n"
        "<code>/add ID</code> — дать доступ\n"
        "<code>/remove ID</code> — забрать доступ\n"
        "<code>/list</code> — посмотреть список"
    )


@dp.message(Command("add"))
async def cmd_add(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: <code>/add ID</code>")
        return
    new_id = int(parts[1])
    ADMINS.add(new_id)
    save_admins(ADMINS)
    await message.answer(f"✅ Аккаунт <code>{new_id}</code> добавлен.")


@dp.message(Command("remove"))
async def cmd_remove(message: Message):
    if message.from_user.id != OWNER_ID:
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
    await message.answer(f"❌ Аккаунт <code>{rem_id}</code> удалён.")


@dp.message(Command("list"))
async def cmd_list(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    admins_text = "\n".join(f"• <code>{a}</code>" for a in ADMINS)
    await message.answer(f"👥 <b>Доверенные аккаунты:</b>\n{admins_text}")


# ---------- ПЕРЕСЫЛКА СООБЩЕНИЙ ИЗ ГРУПП АДМИНАМ ----------

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def forward_group_message(message: Message):
    if message.from_user and message.from_user.is_bot:
        return
    if is_admin(message.from_user.id):
        return  # свои же сообщения себе не пересылаем

    author = message.from_user.full_name if message.from_user else "Кто-то"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="↩️ Ответить",
            callback_data=f"reply:{message.chat.id}:{message.message_id}",
        )
    ]])

    for admin_id in ADMINS:
        try:
            if message.text:
                await bot.send_message(
                    admin_id,
                    f"👤 <b>{author}</b>:\n{message.text}",
                    reply_markup=keyboard,
                )
            else:
                caption = f"👤 {author}"
                if message.caption:
                    caption += f": {message.caption}"
                await bot.copy_message(
                    admin_id, message.chat.id, message.message_id,
                    caption=caption, reply_markup=keyboard,
                )
            last_chat[admin_id] = message.chat.id
        except Exception:
            logging.exception("Не удалось переслать админу %s", admin_id)


# ---------- КНОПКА "ОТВЕТИТЬ" ----------

@dp.callback_query(F.data.startswith("reply:"))
async def on_reply_button(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    _, chat_id, message_id = callback.data.split(":")
    pending_reply[callback.from_user.id] = (int(chat_id), int(message_id))
    await callback.answer("Напиши ответ следующим сообщением ✍️")


# ---------- ОТВЕТ АДМИНА В ЛИЧКЕ → ПУБЛИКАЦИЯ В ЧАТЕ ----------

@dp.message(F.chat.type == "private", F.func(lambda m: is_admin(m.from_user.id)))
async def handle_admin_reply(message: Message):
    admin_id = message.from_user.id

    if admin_id in pending_reply:
        target_chat_id, reply_to_id = pending_reply.pop(admin_id)
    elif admin_id in last_chat:
        target_chat_id, reply_to_id = last_chat[admin_id], None
    else:
        await message.answer(
            "⚠️ Пока не откуда брать чат для ответа — дождись первого "
            "сообщения из группы или нажми «↩️ Ответить» под ним."
        )
        return

    try:
        if message.text:
            await bot.send_message(target_chat_id, message.text, reply_to_message_id=reply_to_id, parse_mode=None)
        elif message.photo:
            await bot.send_photo(target_chat_id, message.photo[-1].file_id, caption=message.caption, reply_to_message_id=reply_to_id, parse_mode=None)
        elif message.video:
            await bot.send_video(target_chat_id, message.video.file_id, caption=message.caption, reply_to_message_id=reply_to_id, parse_mode=None)
        elif message.voice:
            await bot.send_voice(target_chat_id, message.voice.file_id, reply_to_message_id=reply_to_id)
        elif message.video_note:
            await bot.send_video_note(target_chat_id, message.video_note.file_id, reply_to_message_id=reply_to_id)
        elif message.document:
            await bot.send_document(target_chat_id, message.document.file_id, caption=message.caption, reply_to_message_id=reply_to_id, parse_mode=None)
        elif message.sticker:
            await bot.send_sticker(target_chat_id, message.sticker.file_id, reply_to_message_id=reply_to_id)
        else:
            return
        last_chat[admin_id] = target_chat_id
    except Exception as e:
        logging.exception("Не удалось опубликовать ответ: %s", e)
        await message.answer("❌ Не получилось опубликовать. Проверь, что я всё ещё есть в том чате.")


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
