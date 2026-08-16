"""
Бот-«альтер эго» — максимально простая версия.

Как это работает:
  - Всё, что пишут в чатах, где состоит бот, прилетает тебе в личку.
  - Всё, что ты пишешь боту в личке — публикуется от его имени в
    последнем чате, откуда тебе что-то приходило. Просто пиши — и всё.
  - Обычные люди не получают от бота вообще никакого ответа.

Ничего настраивать не нужно — токен и id вписаны прямо здесь.
Единственное, что нужно сделать в Telegram (не в коде):
  1. У @BotFather: выбери бота → /setprivacy → Disable
     (иначе бот не увидит сообщения в группе).
  2. Открой личку с ботом и нажми Start (иначе бот не сможет
     написать тебе первым — так устроен Telegram).
  3. Добавь бота в нужный чат.
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

# ---------- НАСТРОЙКИ (уже вписаны, менять не нужно) ----------
BOT_TOKEN = "8086318948:AAH4AwIor37onOeBgOkQChGVDwrEKVbHgJw"
OWNER_ID = 8407060682
INITIAL_ADMINS = {OWNER_ID, 1964233800}
# ----------------------------------------------------------------

ADMINS_FILE = "admins.json"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


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
last_chat: dict[int, int] = {}  # last_chat[admin_id] = chat_id, куда слать ответ


def is_admin(user_id: int) -> bool:
    return user_id in ADMINS


# ---------- КОМАНДЫ (тишина для чужих) ----------

@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "👋 <b>Готово!</b>\n\n"
        "Добавь меня в чат — и всё, что там напишут, будет приходить сюда. "
        "Чтобы ответить — просто пиши мне здесь, сообщение улетит в чат от моего имени.\n\n"
        "/help — справка\n"
        "/add ID — добавить доверенный аккаунт\n"
        "/remove ID — убрать доверенный аккаунт\n"
        "/list — список доверенных аккаунтов"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "📖 Всё просто:\n\n"
        "1️⃣ Добавь меня в чат.\n"
        "2️⃣ Кто-то там напишет — сообщение придёт тебе сюда.\n"
        "3️⃣ Ты пишешь мне текст/фото/видео здесь — я публикую это в том же "
        "чате от своего имени.\n\n"
        "<code>/add ID</code> — дать доступ новому аккаунту\n"
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
    if message.from_user and is_admin(message.from_user.id):
        return  # свои сообщения себе не пересылаем

    author = message.from_user.full_name if message.from_user else "Кто-то"

    for admin_id in ADMINS:
        try:
            if message.text:
                await bot.send_message(admin_id, f"👤 <b>{author}</b>:\n{message.text}")
            else:
                caption = f"👤 {author}"
                if message.caption:
                    caption += f": {message.caption}"
                await bot.copy_message(admin_id, message.chat.id, message.message_id, caption=caption)
            last_chat[admin_id] = message.chat.id
        except Exception:
            logging.exception("Не удалось переслать админу %s", admin_id)


# ---------- СООБЩЕНИЕ АДМИНА В ЛИЧКЕ → ПУБЛИКАЦИЯ В ЧАТЕ ----------

@dp.message(F.chat.type == "private", F.func(lambda m: m.from_user and is_admin(m.from_user.id)))
async def handle_admin_reply(message: Message):
    admin_id = message.from_user.id

    target_chat_id = last_chat.get(admin_id)
    if target_chat_id is None:
        await message.answer(
            "⚠️ Пока нет чата, куда отправить — дождись первого сообщения "
            "из группы (или напиши там что-нибудь сам, чтобы чат стал активным)."
        )
        return

    try:
        if message.text:
            await bot.send_message(target_chat_id, message.text, parse_mode=None)
        elif message.photo:
            await bot.send_photo(target_chat_id, message.photo[-1].file_id, caption=message.caption, parse_mode=None)
        elif message.video:
            await bot.send_video(target_chat_id, message.video.file_id, caption=message.caption, parse_mode=None)
        elif message.voice:
            await bot.send_voice(target_chat_id, message.voice.file_id)
        elif message.video_note:
            await bot.send_video_note(target_chat_id, message.video_note.file_id)
        elif message.document:
            await bot.send_document(target_chat_id, message.document.file_id, caption=message.caption, parse_mode=None)
        elif message.sticker:
            await bot.send_sticker(target_chat_id, message.sticker.file_id)
        else:
            return
    except Exception as e:
        logging.exception("Не удалось опубликовать ответ: %s", e)
        await message.answer("❌ Не получилось опубликовать. Проверь, что я всё ещё в том чате.")


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
