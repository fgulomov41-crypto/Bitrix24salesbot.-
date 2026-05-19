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


FIELD_MAPPING = {
    "Название": "TITLE",

    # Проверено по готовой сделке
    "Бренд": "UF_CRM_1667234851735",

    # ИНН по готовой сделке
    "ИНН": "UF_CRM_APP_CPV_FIELD",

    "Номер договора": "UF_CRM_1669358388218",
    "Адрес ресторана": "UF_CRM_1682671296431",
    "Локация": "UF_CRM_1667900312618",
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


def bitrix_call(method: str, payload: dict) -> dict:
    if not WEBHOOK:
        raise RuntimeError("BITRIX_WEBHOOK_URL не задан в .env")

    url = f"{WEBHOOK}/{method}.json"
    response = requests.post(url, json=payload, timeout=30)

    try:
        result = response.json()
    except Exception:
        raise RuntimeError(f"Bitrix вернул не JSON: {response.text}")

    if "error" in result:
        raise RuntimeError(json.dumps(result, ensure_ascii=False, indent=2))

    return result


def build_comments(data: dict, requested_by: str = "") -> str:
    lines = ["Данные из Telegram-заявки:", ""]

    if requested_by:
        lines.append(f"Отправил: {requested_by}")
        lines.append("")

    for key, value in data.items():
        if key.startswith("_"):
            continue

        if value not in (None, ""):
            lines.append(f"{key}: {value}")

    return "\n".join(lines)


def normalize_company_name(data: dict) -> str:
    return (
        data.get("Клиент")
        or data.get("Компания")
        or data.get("Клиент (Компания)")
        or ""
    ).strip()


def find_company_by_title(company_name: str):
    if not company_name:
        return None

    result = bitrix_call(
        "crm.company.list",
        {
            "filter": {
                "TITLE": company_name
            },
            "select": ["ID", "TITLE"]
        }
    )

    companies = result.get("result", [])

    if companies:
        return companies[0].get("ID")

    return None


def create_company(data: dict):
    company_name = normalize_company_name(data)

    if not company_name:
        return None

    fields = {
        "TITLE": company_name,
        "ASSIGNED_BY_ID": DEFAULT_ASSIGNED_BY_ID,
        "COMMENTS": build_comments(data),
    }

    phone = (
        data.get("Номер телефона для аккаунта")
        or data.get("Номер телефона для личного кабинета")
        or data.get("Телефон")
        or ""
    )

    if phone:
        fields["PHONE"] = [
            {
                "VALUE": phone,
                "VALUE_TYPE": "WORK"
            }
        ]

    result = bitrix_call(
        "crm.company.add",
        {
            "fields": fields
        }
    )

    return result.get("result")


def get_or_create_company(data: dict):
    company_name = normalize_company_name(data)

    if not company_name:
        return None

    existing_company_id = find_company_by_title(company_name)

    if existing_company_id:
        return existing_company_id

    return create_company(data)


def build_deal_fields(data: dict, requested_by: str = "") -> dict:
    title = (
        data.get("Название")
        or data.get("Бренд")
        or data.get("Клиент")
        or data.get("Компания")
        or "Новая точка из Telegram"
    )

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

    # Поля, выбранные кнопками в Telegram.
    # Они уже приходят готовыми в формате Bitrix:
    # {"UF_CRM_1681712449": [4956], "UF_CRM_1730374903870": 10819}
    extra_fields = data.get("_bitrix_fields", {})

    for bitrix_code, value in extra_fields.items():
        if value not in (None, ""):
            fields[bitrix_code] = value

    return fields


def create_deal(data: dict, requested_by: str = "") -> dict:
    fields = build_deal_fields(data, requested_by=requested_by)

    company_name = normalize_company_name(data)

    if company_name:
        company_id = get_or_create_company(data)
        if company_id:
            fields["COMPANY_ID"] = company_id

    if DRY_RUN:
        return {
            "dry_run": True,
            "fields": fields,
            "message": "DRY_RUN=1, сделка не создана",
        }

    result = bitrix_call(
        "crm.deal.add",
        {
            "fields": fields
        }
    )

    deal_id = result.get("result")

    if not deal_id:
        raise RuntimeError(json.dumps(result, ensure_ascii=False, indent=2))

    return {
        "dry_run": False,
        "deal_id": deal_id,
        "fields": fields,
    }


def get_deal_url(deal_id) -> str:
    return f"https://bitrix.uzum.com/crm/deal/details/{deal_id}/"
