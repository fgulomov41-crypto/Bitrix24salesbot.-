import os
import logging
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
)

from parser import parse_partner_message, is_partner_request, format_preview
from bitrix_client import create_deal, get_deal_url

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DRY_RUN = os.getenv("DRY_RUN", "1") == "1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

pending_deals = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для создания сделок в Bitrix24.\n\n"
        "Отправь данные партнёра в формате:\n\n"
        "Название: Burger House\n"
        "Бренд: Burger House\n"
        "Клиент: Burger House LLC\n"
        "Контакт: Али +998901234567\n"
        "ИНН: 123456789\n"
        "Адрес ресторана: Самарканд, ул. Навои 25\n\n"
        "Я покажу карточку и предложу создать сделку."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    text = message.text.strip()
    if not is_partner_request(text):
        return

    data = parse_partner_message(text)
    if not data:
        await message.reply_text("Не смог распознать данные. Отправьте в формате Поле: значение.")
        return

    user = update.effective_user
    requested_by = f"{user.full_name} (@{user.username})" if user.username else user.full_name

    pending_key = f"{message.chat_id}:{message.message_id}"
    pending_deals[pending_key] = {
        "data": data,
        "requested_by": requested_by,
        "chat_id": message.chat_id,
        "message_id": message.message_id,
    }

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Создать сделку", callback_data=f"create:{pending_key}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"cancel:{pending_key}"),
        ]
    ])

    preview = format_preview(data)
    if DRY_RUN:
        preview += "\n\n🧪 Сейчас включён DRY_RUN=1 — сделка реально не создастся."

    await message.reply_text(preview, reply_markup=keyboard)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    if ":" not in data:
        return

    action, pending_key = data.split(":", 1)
    pending = pending_deals.get(pending_key)

    if not pending:
        await query.edit_message_text("⚠️ Заявка уже устарела или не найдена.")
        return

    if action == "cancel":
        pending_deals.pop(pending_key, None)
        await query.edit_message_text("❌ Создание сделки отменено.")
        return

    if action == "create":
        try:
            result = create_deal(pending["data"], requested_by=pending.get("requested_by", ""))
            pending_deals.pop(pending_key, None)

            if result.get("dry_run"):
                await query.edit_message_text(
                    "🧪 DRY_RUN=1\n\n"
                    "Сделка не создана, но данные успешно подготовлены.\n"
                    "Чтобы создавать сделки реально, поставь DRY_RUN=0 в Railway Variables."
                )
                return

            deal_id = result["deal_id"]
            deal_url = get_deal_url(deal_id)
            await query.edit_message_text(
                f"✅ Сделка создана в Bitrix24!\n\n"
                f"ID: {deal_id}\n"
                f"Ссылка: {deal_url}"
            )

        except Exception as e:
            logger.exception("Ошибка создания сделки")
            await query.edit_message_text(f"❌ Не удалось создать сделку.\n\nОшибка:\n{e}")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(60)
        .read_timeout(60)
        .write_timeout(60)
        .pool_timeout(60)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bitrix Telegram bot запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
