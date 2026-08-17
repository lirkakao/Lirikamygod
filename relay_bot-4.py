"""
Telegram-бот-релей (расширенная версия).

Что делает:
1. Люди пишут боту в личку — сообщение (текст/фото/видео/файл/голосовое)
   пересылается всем владельцам бота.
2. Бот видит все сообщения в группах, где состоит. Различает обычные
   сообщения и ответы (Reply) на свои сообщения — вторые помечает и
   закрепляет у владельца, чтобы не терялись в потоке.
3. Владелец отвечает (Reply) на пересланное сообщение — бот отправляет
   этот ответ туда же, откуда пришло исходное сообщение (в личку или в ту же группу).
4. /post <chat_id> <текст> — бот публикует текст в любой чат от своего имени.
   Если сделать Reply на медиасообщение и написать /post <chat_id> без текста —
   бот опубликует это медиа.
5. /addadmin <user_id> — любой текущий владелец может добавить нового владельца.
6. /removeadmin <user_id> — удалить владельца из списка.
7. /listadmins — показать текущий список владельцев.
8. /chats — показать список чатов, откуда боту писали, и включена ли пересылка.
   /togglechat <chat_id> — включить/выключить пересылку сообщений из этого чата.

Требования: Python 3.9+, библиотека python-telegram-bot (v20+).
"""

import json
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ====== НАСТРОЙКИ ======
BOT_TOKEN = "ВАШ_ТОКЕН_ОТ_BOTFATHER"

# Начальный (главный) владелец — впишите свой числовой ID.
# Остальных можно будет добавлять командой /addadmin прямо в боте.
INITIAL_OWNER_ID = 123456789

MAP_FILE = "message_map.json"     # связка "id пересланного сообщения" -> откуда оно
OWNERS_FILE = "owners.json"       # список владельцев (сохраняется между перезапусками)
CHATS_FILE = "chats.json"         # список известных чатов и статус пересылки (вкл/выкл)

logging.basicConfig(level=logging.INFO)


# ---------- Хранилище: карта пересланных сообщений ----------
def load_map() -> dict:
    if os.path.exists(MAP_FILE):
        with open(MAP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_map(data: dict) -> None:
    with open(MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


# ---------- Хранилище: список владельцев ----------
def load_owners() -> list:
    if os.path.exists(OWNERS_FILE):
        with open(OWNERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    owners = [INITIAL_OWNER_ID]
    save_owners(owners)
    return owners


def save_owners(owners: list) -> None:
    with open(OWNERS_FILE, "w", encoding="utf-8") as f:
        json.dump(owners, f)


# ---------- Хранилище: известные чаты и статус пересылки ----------
def load_chats() -> dict:
    if os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_chats(data: dict) -> None:
    with open(CHATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


# ---------- Команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owners = load_owners()
    if update.effective_user.id in owners:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Список чатов", callback_data="menu:chats")],
            [InlineKeyboardButton("👥 Список владельцев", callback_data="menu:admins")],
            [
                InlineKeyboardButton("🔇 Выключить все чаты", callback_data="menu:disableall"),
                InlineKeyboardButton("🔊 Включить все чаты", callback_data="menu:enableall"),
            ],
        ])
        await update.message.reply_text(
            "Бот запущен.\n"
            "— Сообщения из ЛС и упоминания в группах приходят сюда пересланными.\n"
            "— Ответьте (Reply) на пересланное сообщение — ответ уйдёт туда же.\n"
            "— /post <chat_id> <текст> — написать текст в чат от имени бота.\n"
            "— Reply на медиа + /post <chat_id> — опубликовать это медиа в чат.\n"
            "— /addadmin <user_id> — добавить владельца.\n"
            "— /removeadmin <user_id> — удалить владельца.\n\n"
            "Быстрые действия ниже 👇",
            reply_markup=keyboard,
        )
    else:
        await update.message.reply_text("Напишите ваше сообщение, я передам его.")


async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owners = load_owners()
    if update.effective_user.id not in owners:
        return
    if not context.args:
        await update.message.reply_text("Использование: /addadmin <user_id>")
        return
    try:
        new_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return
    if new_id in owners:
        await update.message.reply_text("Этот пользователь уже владелец.")
        return
    owners.append(new_id)
    save_owners(owners)
    await update.message.reply_text(f"Добавлен новый владелец: {new_id}")


async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owners = load_owners()
    if update.effective_user.id not in owners:
        return
    if not context.args:
        await update.message.reply_text("Использование: /removeadmin <user_id>")
        return
    try:
        rem_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return
    if rem_id not in owners:
        await update.message.reply_text("Такого владельца нет в списке.")
        return
    if len(owners) == 1:
        await update.message.reply_text("Нельзя удалить последнего владельца.")
        return
    owners.remove(rem_id)
    save_owners(owners)
    await update.message.reply_text(f"Владелец {rem_id} удалён.")


async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owners = load_owners()
    if update.effective_user.id not in owners:
        return
    await update.message.reply_text("Владельцы бота:\n" + "\n".join(str(o) for o in owners))


def build_chats_view():
    """Собирает текст и клавиатуру со списком чатов и кнопками переключения."""
    chats = load_chats()
    if not chats:
        return "Пока нет известных чатов — бот ещё не получал сообщений.", None
    buttons = []
    for chat_id, info in chats.items():
        enabled = info.get("enabled", True)
        icon = "✅" if enabled else "🚫"
        title = info.get("title", "без названия")
        buttons.append([InlineKeyboardButton(f"{icon} {title}", callback_data=f"togglechat:{chat_id}")])
    text = "Известные чаты (нажмите, чтобы включить/выключить пересылку):"
    return text, InlineKeyboardMarkup(buttons)


async def list_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owners = load_owners()
    if update.effective_user.id not in owners:
        return
    text, keyboard = build_chats_view()
    await update.message.reply_text(text, reply_markup=keyboard)


async def toggle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owners = load_owners()
    if update.effective_user.id not in owners:
        return
    if not context.args:
        await update.message.reply_text("Использование: /togglechat <chat_id>")
        return
    chat_id = context.args[0]
    chats = load_chats()
    if chat_id not in chats:
        await update.message.reply_text("Такой чат не найден. Посмотрите список: /chats")
        return
    chats[chat_id]["enabled"] = not chats[chat_id].get("enabled", True)
    save_chats(chats)
    status = "включена" if chats[chat_id]["enabled"] else "выключена"
    await update.message.reply_text(f'Пересылка из «{chats[chat_id].get("title")}» теперь {status}.')


async def disable_all_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owners = load_owners()
    if update.effective_user.id not in owners:
        return
    chats = load_chats()
    count = 0
    for chat_id, info in chats.items():
        if info.get("type") != "private":  # ЛС не трогаем, это основной канал
            info["enabled"] = False
            count += 1
    save_chats(chats)
    await update.message.reply_text(f"Пересылка отключена для всех групповых чатов ({count} шт.).")


async def enable_all_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owners = load_owners()
    if update.effective_user.id not in owners:
        return
    chats = load_chats()
    count = 0
    for chat_id, info in chats.items():
        if info.get("type") != "private":
            info["enabled"] = True
            count += 1
    save_chats(chats)
    await update.message.reply_text(f"Пересылка включена для всех групповых чатов ({count} шт.).")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на инлайн-кнопки из /start и /chats."""
    query = update.callback_query
    owners = load_owners()
    if query.from_user.id not in owners:
        await query.answer("Недоступно.", show_alert=True)
        return

    data = query.data

    if data == "menu:chats":
        text, keyboard = build_chats_view()
        await query.edit_message_text(text, reply_markup=keyboard)
        await query.answer()

    elif data == "menu:admins":
        await query.answer()
        await query.message.reply_text("Владельцы бота:\n" + "\n".join(str(o) for o in owners))

    elif data == "menu:disableall":
        chats = load_chats()
        count = 0
        for chat_id, info in chats.items():
            if info.get("type") != "private":
                info["enabled"] = False
                count += 1
        save_chats(chats)
        await query.answer(f"Выключено чатов: {count}")

    elif data == "menu:enableall":
        chats = load_chats()
        count = 0
        for chat_id, info in chats.items():
            if info.get("type") != "private":
                info["enabled"] = True
                count += 1
        save_chats(chats)
        await query.answer(f"Включено чатов: {count}")

    elif data.startswith("togglechat:"):
        chat_id = data.split(":", 1)[1]
        chats = load_chats()
        if chat_id in chats:
            chats[chat_id]["enabled"] = not chats[chat_id].get("enabled", True)
            save_chats(chats)
            status = "включена" if chats[chat_id]["enabled"] else "выключена"
            await query.answer(f'Пересылка теперь {status}')
            # Обновляем список кнопок сразу же, чтобы было видно новый статус
            text, keyboard = build_chats_view()
            await query.edit_message_text(text, reply_markup=keyboard)
        else:
            await query.answer("Чат не найден.", show_alert=True)


async def post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owners = load_owners()
    if update.effective_user.id not in owners:
        return

    msg = update.message

    # Если это Reply на медиасообщение — копируем его в указанный чат
    if msg.reply_to_message:
        if not context.args:
            await msg.reply_text("Использование: /post <chat_id> (в ответ на медиа)")
            return
        chat_id = context.args[0]
        try:
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=msg.chat_id,
                message_id=msg.reply_to_message.message_id,
            )
            await msg.reply_text("Опубликовано.")
        except Exception as e:
            await msg.reply_text(f"Ошибка: {e}")
        return

    # Иначе — обычная отправка текста
    if len(context.args) < 2:
        await msg.reply_text(
            "Использование: /post <chat_id> <текст>\nили Reply на медиа с /post <chat_id>"
        )
        return
    chat_id = context.args[0]
    text = " ".join(context.args[1:])
    try:
        await context.bot.send_message(chat_id=chat_id, text=text)
        await msg.reply_text("Опубликовано.")
    except Exception as e:
        await msg.reply_text(f"Ошибка: {e}")


# ---------- Основной обработчик сообщений ----------
async def incoming_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owners = load_owners()
    user = update.effective_user
    msg = update.message
    chat = update.effective_chat

    # --- Сообщение от владельца: возможно, это ответ кому-то ---
    if user.id in owners:
        # Реагируем ТОЛЬКО если это Reply именно на сообщение самого бота
        # (например, на пересланное сообщение). Обычные ответы другим людям
        # в чате бот полностью игнорирует и ничего не пишет.
        is_reply_to_bot = (
            msg.reply_to_message
            and msg.reply_to_message.from_user
            and msg.reply_to_message.from_user.id == context.bot.id
        )
        if is_reply_to_bot:
            id_map = load_map()
            key = str(msg.reply_to_message.message_id)
            target = id_map.get(key)
            if target:
                await context.bot.copy_message(
                    chat_id=target["chat_id"],
                    from_chat_id=msg.chat_id,
                    message_id=msg.message_id,
                    reply_to_message_id=target.get("message_id"),
                )
                await msg.reply_text("Отправлено.")
            elif chat.type == "private":
                # Показываем ошибку только в личке с ботом, не в общих чатах
                await msg.reply_text("Не нашёл, кому отвечать.")
        return

    # --- Сообщение от постороннего ---
    chat_label = "ЛС" if chat.type == "private" else f"группа «{chat.title}»"
    id_map = load_map()

    # Регистрируем чат в списке известных (если новый) и проверяем,
    # не выключена ли для него пересылка вручную через /togglechat
    chats = load_chats()
    chat_key = str(chat.id)
    chat_title = user.full_name if chat.type == "private" else (chat.title or chat_key)
    if chat_key not in chats:
        chats[chat_key] = {"title": chat_title, "type": chat.type, "enabled": True}
        save_chats(chats)
    elif chats[chat_key].get("title") != chat_title:
        chats[chat_key]["title"] = chat_title
        save_chats(chats)

    if not chats[chat_key].get("enabled", True):
        return  # пересылка из этого чата выключена владельцем

    # Различаем: обычное сообщение из чата, ответ боту в чате, или сообщение в ЛС боту.
    # Ответы и личные сообщения помечаем и закрепляем, чтобы не терялись в потоке.
    is_reply_to_bot_here = (
        msg.reply_to_message
        and msg.reply_to_message.from_user
        and msg.reply_to_message.from_user.id == context.bot.id
    )

    if chat.type == "private":
        kind_label = "📌 Вам написали в ЛС"
        should_pin = True
    elif is_reply_to_bot_here:
        kind_label = "📌 Вам ответ"
        should_pin = True
    else:
        kind_label = "🆕 Новое сообщение из чата"
        should_pin = False

    for owner_id in owners:
        forwarded = await context.bot.forward_message(
            chat_id=owner_id,
            from_chat_id=chat.id,
            message_id=msg.message_id,
        )
        # Закрепляем эту конкретную ветку переписки за пересланным сообщением,
        # чтобы Reply от владельца всегда уходил именно в это сообщение/чат
        id_map[str(forwarded.message_id)] = {
            "chat_id": chat.id,
            "message_id": msg.message_id,
        }
        notification = await context.bot.send_message(
            chat_id=owner_id,
            text=(
                f"{kind_label}\n"
                f"от {user.full_name} (id {user.id}), {chat_label}.\n"
                f"Ответьте Reply на сообщение выше, чтобы ответить туда же."
            ),
        )

        if should_pin:
            try:
                await context.bot.pin_chat_message(
                    chat_id=owner_id,
                    message_id=notification.message_id,
                    disable_notification=False,
                )
            except Exception as e:
                logging.warning(f"Не удалось закрепить сообщение у {owner_id}: {e}")

    save_map(id_map)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post_command))
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(CommandHandler("listadmins", list_admins))
    app.add_handler(CommandHandler("chats", list_chats))
    app.add_handler(CommandHandler("togglechat", toggle_chat))
    app.add_handler(CommandHandler("disableallchats", disable_all_chats))
    app.add_handler(CommandHandler("enableallchats", enable_all_chats))

    media_filter = (
        filters.TEXT
        | filters.PHOTO
        | filters.VIDEO
        | filters.Document.ALL
        | filters.VOICE
        | filters.AUDIO
        | filters.Sticker.ALL
    )
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(media_filter & ~filters.COMMAND, incoming_message))

    app.run_polling()


if __name__ == "__main__":
    main()
