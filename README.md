# Bitrix Telegram Bot

Telegram bot for creating Bitrix24 CRM deals from sales messages.

## What it does

1. Sales sends partner data in Telegram.
2. Bot parses fields.
3. Bot shows confirmation buttons.
4. After confirmation, bot creates a Bitrix24 deal.

## Required Railway variables

```env
TELEGRAM_BOT_TOKEN=
BITRIX_WEBHOOK_URL=
BITRIX_CATEGORY_ID=58
BITRIX_STAGE_ID=C58:NEW
BITRIX_DEFAULT_ASSIGNED_BY_ID=297435
DRY_RUN=1
```

Use `DRY_RUN=1` for the first test. Set `DRY_RUN=0` only when ready to create real deals.

## Run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

## Test message

```text
Название: TEST Telegram Deal
Бренд: Test Brand
Клиент: Test Company
Контакт: Али +998901234567
ИНН: 123456789
Адрес ресторана: Самарканд, ул. Навои 25
ФИО директора: Тест Директор
Название банка: Test Bank
Расчетный счет в банке: 20208000123456789001
ОКЭД: 56100
МФО: 00444
Юр. адрес компании: Самарканд, тестовый адрес
Количество торговых точек: 1
Номер телефона для аккаунта: +998901234567
Номер телефона для личного кабинета: +998901234567
Время работы заведения: 10:00-22:00
Время готовки: 20 минут
```
