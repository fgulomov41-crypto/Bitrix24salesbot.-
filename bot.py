import os
import uuid
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
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)

pending_deals = {}


ENUM_QUESTIONS = [
    {
        "key": "segment",
        "label": "Сегмент",
        "field": "UF_CRM_1631703074015",
        "mode": "list",
        "options": [
            ("Кафе и рестораны", 3106),
            ("Ритейл", 9148),
            ("Продукты питания", 2894),
            ("Аптеки и медицина", 3596),
            ("Отдых и развлечения", 3598),
            ("Прочее", 3612),
        ],
    },
    {
        "key": "business_subtype",
        "label": "Подвид бизнеса",
        "field": "UF_CRM_1684768308532",
        "mode": "list",
        "options": [
            ("e-com", 8436),
            ("оффлайн торговля", 8438),
            ("услуги", 8440),
        ],
    },
    {
        "key": "pos_terminal",
        "label": "POS терминал клиента",
        "field": "UF_CRM_1681712449",
        "mode": "list",
        "options": [
            ("Rkeeper", 4954),
            ("IIKO", 4956),
            ("Трактир", 4958),
            ("Jowi", 4960),
            ("Poster", 4962),
            ("Другая", 4966),
        ],
    },
    {
        "key": "integration_method",
        "label": "Способ интеграции",
        "field": "UF_CRM_1684309706545",
        "mode": "single",
        "options": [
            ("POS", 5626),
            ("Vendor App", 5628),
            ("POS + Vendor APP", 10817),
        ],
    },
    {
        "key": "connection_type",
        "label": "Тип подключения",
        "field": "UF_CRM_1730374903870",
        "mode": "single",
        "options": [
            ("Наша доставка", 10819),
            ("Маркетплейс", 10820),
        ],
    },
    {
        "key": "vat",
        "label": "Плательщик НДС",
        "field": "UF_CRM_1684309797615",
        "mode": "single",
        "options": [
            ("0%", 5630),
            ("12%", 5632),
        ],
    },
    {
        "key": "restaurant_type",
        "label": "Тип ресторана",
        "field": "UF_CRM_1701236094",
        "mode": "list",
        "options": [
            ("Акции", 10124),
            ("Новинки", 10125),
            ("Food Mall", 10126),
            ("Лаваш", 10127),
            ("Бургеры", 10128),
            ("Обеды", 10129),
            ("Курочка", 10130),
            ("Плов", 10131),
            ("Суши", 10132),
            ("Milliy Taom", 10133),
            ("Шашлыки", 10134),
            ("Европа", 10135),
            ("Пицца", 10136),
            ("Десерты", 10137),
            ("Азия", 10138),
            ("Магазины", 10139),
            ("Завтраки", 10140),
            ("Турецкая", 10141),
            ("Премиум", 10142),
            ("Кофе", 10143),
            ("Индийская кухня", 17249),
        ],
    },
    {
        "key": "still_life",
        "label": "Натюрморт",
        "field": "UF_CRM_1686143457290",
        "mode": "single",
        "options": [
            ("Заглушка", 8736),
            ("Заглушка, требуется замена", 8738),
            ("Партнерский", 8740),
        ],
    },
    {
        "key": "menu_prices_received",
        "label": "Меню и цены получены",
        "field": "UF_CRM_1684321006608",
        "mode": "single",
        "options": [
            ("Да", 5710),
        ],
    },
    {
        "key": "photos_received",
        "label": "Фото получены",
        "field": "UF_CRM_1684320979712",
        "mode": "single",
        "options": [
            ("Да", 5708),
        ],
    },
    {
        "key": "ikpu_received",
        "label": "Получены ИКПУ коды",
        "field": "UF_CRM_1683201799229",
        "mode": "single",
        "options": [
            ("Да", 5444),
        ],
    },
    {
        "key": "auto_prices",
        "label": "Включить автоцены партнёру",
        "field": "UF_CRM_1747040237",
        "mode": "single",
        "options": [
            ("да", 11440),
            ("нет", 11441),
        ],
    },
    {
        "key": "prices_from",
        "label": "Цены забирать со всех точек либо с одной",
        "field": "UF_CRM_1747039844",
        "mode": "single",
        "options": [
            ("со всех", 11434),
            ("с одной", 11435),
        ],
    },
    {
        "key": "discount_method",
        "label": "Каким способом заводится скидка на позицию",
        "field": "UF_CRM_1747039945",
        "mode": "single",
        "options": [
            ("old price", 11436),
            ("вручную через контент", 11437),
        ],
    },
    {
        "key": "ckvz_mark",
        "label": "Отметка ЦКВЗ",
        "field": "UF_CRM_1777370857",
        "mode": "single",
        "options": [
            ("выставлена", 17574),
            ("не выставлена", 17575),
        ],
    },
]


def build_choice_keyboard(request_id: str, question_index: int, question: dict) -> InlineKeyboardMarkup:
    buttons = []
    row = []

    for option_index, (option_text, _option_value) in enumerate(question["options"]):
        row.append(
            InlineKeyboardButton(
                option_text,
                callback_data=f"enum:{request_id}:{question_index}:{option_index}"
            )
        )

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton(
            "⏭ Пропустить",
            callback_data=f"skip:{request_id}:{question_index}"
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            "✅ Завершить выбор",
            callback_data=f"finish:{request_id}:{question_index}"
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            "❌ Отмена",
            callback_data=f"cancel:{request_id}"
        )
    ])

    return InlineKeyboardMarkup(buttons)


def build_confirm_keyboard(request_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Создать сделку", callback_data=f"create:{request_id}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"cancel:{request_id}"),
        ]
    ])


def format_selected_options(pending: dict) -> str:
    selected = pending.get("selected_options", {})

    if not selected:
        return "Поля с вариантами: не выбраны"

    lines = ["Поля с вариантами:"]

    for label, value in selected.items():
        lines.append(f"{label}: {value}")

    return "\n".join(lines)


def format_final_preview(pending: dict) -> str:
    data = pending["data"]

    text = format_preview(data)
    text += "\n\n" + format_selected_options(pending)

    if DRY_RUN:
        text += "\n\n🧪 Сейчас включён DRY_RUN=1 — сделка реально не создастся."

    text += "\n\nСоздать сделку в Bitrix24?"

    return text


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
        "Я покажу карточку, затем предложу выбрать варианты кнопками."
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

    request_id = uuid.uuid4().hex[:12]

    pending_deals[request_id] = {
        "data": data,
        "requested_by": requested_by,
        "chat_id": message.chat_id,
        "message_id": message.message_id,
        "bitrix_fields": {},
        "selected_options": {},
    }

    preview = format_preview(data)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧩 Выбрать варианты", callback_data=f"start_enum:{request_id}"),
            InlineKeyboardButton("✅ Создать сразу", callback_data=f"create:{request_id}"),
        ],
        [
            InlineKeyboardButton("❌ Отмена", callback_data=f"cancel:{request_id}"),
        ]
    ])

    if DRY_RUN:
        preview += "\n\n🧪 Сейчас включён DRY_RUN=1 — сделка реально не создастся."

    await message.reply_text(preview, reply_markup=keyboard)


async def ask_enum_question(query, request_id: str, question_index: int):
    pending = pending_deals.get(request_id)

    if not pending:
        await query.edit_message_text("⚠️ Заявка уже устарела или не найдена.")
        return

    if question_index >= len(ENUM_QUESTIONS):
        await show_final_confirmation(query, request_id)
        return

    question = ENUM_QUESTIONS[question_index]

    text = (
        f"🧩 Выберите значение\n\n"
        f"{question_index + 1}/{len(ENUM_QUESTIONS)} — {question['label']}"
    )

    await query.edit_message_text(
        text,
        reply_markup=build_choice_keyboard(request_id, question_index, question)
    )


async def show_final_confirmation(query, request_id: str):
    pending = pending_deals.get(request_id)

    if not pending:
        await query.edit_message_text("⚠️ Заявка уже устарела или не найдена.")
        return

    pending["data"]["_bitrix_fields"] = pending.get("bitrix_fields", {})

    await query.edit_message_text(
        format_final_preview(pending),
        reply_markup=build_confirm_keyboard(request_id)
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    callback_data = query.data or ""
    parts = callback_data.split(":")

    action = parts[0]

    if action == "start_enum":
        request_id = parts[1]
        await ask_enum_question(query, request_id, 0)
        return

    if action == "enum":
        request_id = parts[1]
        question_index = int(parts[2])
        option_index = int(parts[3])

        pending = pending_deals.get(request_id)

        if not pending:
            await query.edit_message_text("⚠️ Заявка уже устарела или не найдена.")
            return

        question = ENUM_QUESTIONS[question_index]
        option_text, option_value = question["options"][option_index]

        field_code = question["field"]
        mode = question["mode"]

        if mode == "list":
            pending["bitrix_fields"][field_code] = [option_value]
        else:
            pending["bitrix_fields"][field_code] = option_value

        pending["selected_options"][question["label"]] = option_text

        await ask_enum_question(query, request_id, question_index + 1)
        return

    if action == "skip":
        request_id = parts[1]
        question_index = int(parts[2])
        await ask_enum_question(query, request_id, question_index + 1)
        return

    if action == "finish":
        request_id = parts[1]
        await show_final_confirmation(query, request_id)
        return

    if action == "cancel":
        request_id = parts[1]

        pending_deals.pop(request_id, None)

        await query.edit_message_text("❌ Создание сделки отменено.")
        return

    if action == "create":
        request_id = parts[1]
        pending = pending_deals.get(request_id)

        if not pending:
            await query.edit_message_text("⚠️ Заявка уже устарела или не найдена.")
            return

        try:
            pending["data"]["_bitrix_fields"] = pending.get("bitrix_fields", {})

            result = create_deal(
                pending["data"],
                requested_by=pending.get("requested_by", "")
            )

            pending_deals.pop(request_id, None)

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
            await query.edit_message_text(
                f"❌ Не удалось создать сделку.\n\nОшибка:\n{e}"
            )

        return


def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан в .env")

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
