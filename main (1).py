"""
Бот-«альтер эго» — версия по образцу.

Как это работает:
  - Всё, что пишут в чатах, где бот состоит (и в личке боту от посторонних),
    приходит тебе пересланным.
  - Ответь (Reply) на пересланное сообщение — ответ уйдёт от бота в тот
    самый чат, откуда пришло исходное сообщение.
  - /post <chat_id> <текст> — бот напишет в указанный чат от своего имени,
    без необходимости ждать входящее сообщение.

Ничего настраивать не нужно — токен и id вписаны прямо здесь.
Единственное, что нужно сделать в Telegram (не в коде):
  1. У @BotFather: выбери бота → /setprivacy → Disable.
  2. Открой личку с ботом и нажми Start (иначе бот не сможет
     написать тебе первым).
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
OWNER_ID = 1964233800
INITIAL_ADMINS = {OWNER_ID, 8407060682}
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

# (admin_id, message_id в чате админа) -> chat_id, откуда пришло исходное сообщение
forward_map: dict[tuple[int, int], int] = {}
# admin_id -> chat_id последнего чата, откуда что-то приходило (запасной вариант без Reply)
last_chat: dict[int, int] = {}


def is_admin(user_id: int) -> bool:
    return user_id in ADMINS


# ---------- КОМАНДЫ (тишина для чужих) ----------

@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "Бот запущен.\n"
        "— Сообщения из чатов, где я состою (и личные сообщения мне от "
        "посторонних), приходят вам пересланными.\n\n"
        "Чтобы ответить:\n"
        "• Reply на пересланное сообщение + <code>/reply текст</code> "
        "(можно прикрепить фото/видео)\n"
        "• или просто <code>/post chat_id текст</code> (тоже можно с фото/видео) "
        "— напишу в любой чат по его ID, без ожидания входящего\n\n"
        "/add ID — добавить доверенный аккаунт\n"
        "/remove ID — убрать доверенный аккаунт\n"
        "/list — список доверенных аккаунтов\n"
        "/chatid — показать id текущего чата (напиши в нужной группе)"
    )


@dp.message(Command("add"))
async def cmd_add(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /add ID")
        return
    new_id = int(parts[1])
    ADMINS.add(new_id)
    save_admins(ADMINS)
    await message.answer(f"✅ Аккаунт {new_id} добавлен.")


@dp.message(Command("remove"))
async def cmd_remove(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /remove ID")
        return
    rem_id = int(parts[1])
    if rem_id == OWNER_ID:
        await message.answer("Нельзя убрать главного владельца.")
        return
    ADMINS.discard(rem_id)
    save_admins(ADMINS)
    await message.answer(f"❌ Аккаунт {rem_id} удалён.")


@dp.message(Command("list"))
async def cmd_list(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    admins_text = "\n".join(f"• {a}" for a in ADMINS)
    await message.answer(f"Доверенные аккаунты:\n{admins_text}")


@dp.message(Command("chatid"))
async def cmd_chatid(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.reply(f"ID этого чата: {message.chat.id}")


# ---------- ОТПРАВКА КОНТЕНТА (текст/фото/видео/...) В ЧАТ ----------

async def deliver_content(message: Message, target_chat_id: int, override_text: str | None):
    try:
        if message.photo:
            caption = override_text if override_text else message.caption
            await bot.send_photo(target_chat_id, message.photo[-1].file_id, caption=caption, parse_mode=None)
        elif message.video:
            caption = override_text if override_text else message.caption
            await bot.send_video(target_chat_id, message.video.file_id, caption=caption, parse_mode=None)
        elif message.voice:
            await bot.send_voice(target_chat_id, message.voice.file_id)
        elif message.video_note:
            await bot.send_video_note(target_chat_id, message.video_note.file_id)
        elif message.document:
            caption = override_text if override_text else message.caption
            await bot.send_document(target_chat_id, message.document.file_id, caption=caption, parse_mode=None)
        elif message.sticker:
            await bot.send_sticker(target_chat_id, message.sticker.file_id)
        elif override_text:
            await bot.send_message(target_chat_id, override_text, parse_mode=None)
        elif message.text:
            await bot.send_message(target_chat_id, message.text, parse_mode=None)
        else:
            await message.answer("Нечего отправлять.")
            return
        await message.answer("Отправлено ✅")
    except Exception as e:
        logging.exception("Ошибка отправки: %s", e)
        await message.answer(f"❌ Ошибка: {e}")


# ---------- ПЕРЕСЫЛКА ВХОДЯЩИХ СООБЩЕНИЙ АДМИНАМ ----------

async def do_forward(message: Message):
    if message.from_user and is_admin(message.from_user.id):
        return  # сообщения самих админов сюда не попадают

    author = message.from_user.full_name if message.from_user else "Канал/аноним"
    uid = message.from_user.id if message.from_user else "—"

    for admin_id in ADMINS:
        try:
            sent = await bot.copy_message(admin_id, message.chat.id, message.message_id)
            forward_map[(admin_id, sent.message_id)] = message.chat.id
            info = await bot.send_message(
                admin_id,
                f"↑ от {author} (id {uid}). Ответьте Reply на сообщение выше "
                f"(или просто напишите мне — уйдёт сюда же).",
            )
            forward_map[(admin_id, info.message_id)] = message.chat.id
            last_chat[admin_id] = message.chat.id
        except Exception:
            logging.exception("Не удалось переслать админу %s", admin_id)


@dp.message(F.chat.type.in_({"group", "supergroup", "private"}))
async def forward_incoming(message: Message):
    await do_forward(message)


@dp.channel_post()
async def forward_channel(message: Message):
    await do_forward(message)


# ---------- REPLY АДМИНА НА ПЕРЕСЛАННОЕ СООБЩЕНИЕ ----------

@dp.message(
    F.chat.type == "private",
    F.func(lambda m: m.from_user and is_admin(m.from_user.id)),
)
async def handle_admin_message(message: Message):
    admin_id = message.from_user.id
    raw = (message.text or message.caption or "").strip()

    # --- /post chat_id [текст]   (можно с фото/видео/документом) ---
    if raw.lower().startswith("/post"):
        rest = raw[len("/post"):].strip()
        parts = rest.split(maxsplit=1)
        if not parts or not parts[0].lstrip("-").isdigit():
            await message.answer("Использование: /post chat_id [текст] — можно прикрепить фото/видео.")
            return
        chat_id = int(parts[0])
        override_text = parts[1] if len(parts) > 1 else None
        await deliver_content(message, chat_id, override_text)
        return

    # --- /reply текст   (используется как Reply на пересланное сообщение) ---
    if raw.lower().startswith("/reply"):
        if not message.reply_to_message:
            await message.answer("Команду /reply нужно писать как Reply на пересланное сообщение.")
            return
        target_chat_id = forward_map.get((admin_id, message.reply_to_message.message_id))
        if target_chat_id is None:
            target_chat_id = last_chat.get(admin_id)
        if target_chat_id is None:
            await message.answer("⚠️ Не нашёл, куда отправлять.")
            return
        override_text = raw[len("/reply"):].strip() or None
        await deliver_content(message, target_chat_id, override_text)
        return

    # --- запасной вариант: просто Reply или просто сообщение без команды ---
    target_chat_id = None
    if message.reply_to_message:
        target_chat_id = forward_map.get((admin_id, message.reply_to_message.message_id))
    if target_chat_id is None:
        target_chat_id = last_chat.get(admin_id)

    if target_chat_id is None:
        await message.answer("⚠️ Пока нет активного чата — дождись первого входящего сообщения.")
        return

    await deliver_content(message, target_chat_id, None)


async def main():
    await bot.set_my_name(name="Alter Ego Bot")
    await bot.set_my_commands([
        BotCommand(command="start", description="Начало работы"),
        BotCommand(command="post", description="Написать в чат по его ID"),
        BotCommand(command="chatid", description="Узнать ID текущего чата"),
        BotCommand(command="add", description="Добавить доверенный аккаунт"),
        BotCommand(command="remove", description="Убрать доверенный аккаунт"),
        BotCommand(command="list", description="Список доверенных аккаунтов"),
    ])
    print("Бот запущен, жду команд...")
    print("Текущие админы:", ADMINS)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
