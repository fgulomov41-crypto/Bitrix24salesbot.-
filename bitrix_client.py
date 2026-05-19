import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

WEBHOOK = os.getenv("BITRIX_WEBHOOK_URL", "").rstrip("/")
CATEGORY_ID = int(os.getenv("BITRIX_CATEGORY_ID", "58"))
STAGE_ID = os.getenv("BITRIX_STAGE_ID", "C58:NEW")
DEFAULT_ASSIGNED_BY_ID = int(os.getenv("BITRIX_DEFAULT_ASSIGNED_BY_ID", "297435"))
DRY_RUN = os.getenv("DRY_RUN", "1") == "1"

# Only safe text/number/url fields are filled automatically.
# Enumeration/boolean fields are intentionally left for managers to fill in Bitrix manually.
FIELD_MAPPING = {
    "Название": "TITLE",
    "ИНН": "UF_CRM_1730198850",
    "Номер договора": "UF_CRM_1669358388218",
    "Адрес ресторана": "UF_CRM_1682671296431",
    "ФИО директора": "UF_CRM_1683720999095",
    "Название банка": "UF_CRM_1683720954828",
    "Расчетный счет в банке": "UF_CRM_1682671131552",
    "Расчётный счет в банке": "UF_CRM_1682671131552",
    "ОКЭД": "UF_CRM_1682671193275",
    "МФО": "UF_CRM_1682671206730",
    "Юр. адрес компании": "UF_CRM_1682675196598",
    "Количество торговых точек": "UF_CRM_1667232334499",
    "Адреса торговых точек": "UF_CRM_1684320587456",
    "Номер телефона для аккаунта": "UF_CRM_1686143533955",
    "Номер телефона для личного кабинета": "UF_CRM_1741710602549",
    "Ссылка на обменник": "UF_CRM_1686143257167",
    "Ссылка на YEats": "UF_CRM_1689085305475",
    "Время работы заведения": "UF_CRM_1686143065646",
    "Время готовки": "UF_CRM_1686143094287",
    "Лог группа": "UF_CRM_1686634327304",
}


def build_comments(data, requested_by=""):
    lines = ["Данные из Telegram-заявки:", ""]

    if requested_by:
        lines.append(f"Отправил: {requested_by}")
        lines.append("")

    for key, value in data.items():
        if value not in (None, ""):
            lines.append(f"{key}: {value}")

    return "\n".join(lines)


def build_deal_fields(data, requested_by=""):
    title = data.get("Название") or data.get("Бренд") or data.get("Клиент") or "Новая точка из Telegram"

    fields = {
        "TITLE": title,
        "CATEGORY_ID": CATEGORY_ID,
        "STAGE_ID": STAGE_ID,
        "ASSIGNED_BY_ID": DEFAULT_ASSIGNED_BY_ID,
        "COMMENTS": build_comments(data, requested_by=requested_by),
        "SOURCE_DESCRIPTION": "Telegram bot",
    }

    for human_name, bitrix_code in FIELD_MAPPING.items():
        value = data.get(human_name)
        if value not in (None, ""):
            fields[bitrix_code] = value

    return fields


def create_deal(data, requested_by=""):
    if not WEBHOOK:
        raise RuntimeError("BITRIX_WEBHOOK_URL is not set")

    fields = build_deal_fields(data, requested_by=requested_by)

    if DRY_RUN:
        return {
            "dry_run": True,
            "fields": fields,
            "message": "DRY_RUN=1, deal was not created",
        }

    url = f"{WEBHOOK}/crm.deal.add.json"
    response = requests.post(url, json={"fields": fields}, timeout=30)

    try:
        result = response.json()
    except Exception:
        raise RuntimeError(f"Bitrix returned non-JSON response: {response.text}")

    if "error" in result:
        raise RuntimeError(json.dumps(result, ensure_ascii=False, indent=2))

    deal_id = result.get("result")
    if not deal_id:
        raise RuntimeError(json.dumps(result, ensure_ascii=False, indent=2))

    return {
        "dry_run": False,
        "deal_id": deal_id,
        "fields": fields,
    }


def get_deal_url(deal_id):
    return f"https://bitrix.uzum.com/crm/deal/details/{deal_id}/"
