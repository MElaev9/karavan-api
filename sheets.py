import os
import json
import logging
from collections import defaultdict
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from calculator import DEPARTMENT_ORDER, format_amount

logger = logging.getLogger(__name__)

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1RTQix5kQRZeClKjC6ZDDQA0j6IlusJ_uJcFjAv34UPI")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
INDEX_SHEET_NAME = "📋 Все события"

# Цвета
COLOR_DARK   = {"red": 0.13, "green": 0.13, "blue": 0.13}   # почти чёрный — заголовок
COLOR_BLUE   = {"red": 0.27, "green": 0.51, "blue": 0.71}   # синий — шапки таблиц
COLOR_GREEN  = {"red": 0.42, "green": 0.66, "blue": 0.31}   # зелёный — отдел
COLOR_LIGHT  = {"red": 0.95, "green": 0.95, "blue": 0.95}   # светло-серый — чередование строк
COLOR_WHITE  = {"red": 1.0,  "green": 1.0,  "blue": 1.0}
COLOR_TEXT_W = {"red": 1.0,  "green": 1.0,  "blue": 1.0}    # белый текст


def _get_service():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS environment variable is not set")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


# ── Главный лист ──────────────────────────────────────────────────────────────

def _get_or_create_index_sheet(service) -> int:
    sheet = service.spreadsheets()
    spreadsheet = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
    for s in spreadsheet.get("sheets", []):
        if s["properties"]["title"] == INDEX_SHEET_NAME:
            return s["properties"]["sheetId"]

    resp = sheet.batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{"addSheet": {"properties": {
            "title": INDEX_SHEET_NAME, "index": 0,
        }}}]}
    ).execute()
    sheet_id = resp["replies"][0]["addSheet"]["properties"]["sheetId"]

    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{INDEX_SHEET_NAME}'!A1:D1",
        valueInputOption="RAW",
        body={"values": [["Мероприятие", "Гостей", "Дата", "Блюд"]]},
    ).execute()

    sheet.batchUpdate(spreadsheetId=SPREADSHEET_ID, body={"requests": [
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": COLOR_DARK,
                "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": COLOR_TEXT_W},
                "horizontalAlignment": "CENTER",
            }},
            "fields": "userEnteredFormat",
        }},
        {"autoResizeDimensions": {"dimensions": {
            "sheetId": sheet_id, "dimension": "COLUMNS",
            "startIndex": 0, "endIndex": 4,
        }}},
    ]}).execute()
    return sheet_id


def _add_to_index(service, event_name, guests, dish_count, date_str, target_sheet_title):
    sheet = service.spreadsheets()
    _get_or_create_index_sheet(service)

    spreadsheet = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
    target_gid = None
    for s in spreadsheet.get("sheets", []):
        if s["properties"]["title"] == target_sheet_title:
            target_gid = s["properties"]["sheetId"]
            break

    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{INDEX_SHEET_NAME}'!A:A",
    ).execute()
    next_row = len(result.get("values", [])) + 1

    safe_name = event_name.replace('"', '""')
    sheet_url = (f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
                 f"/edit?gid={target_gid}#gid={target_gid}&range=A1")

    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{INDEX_SHEET_NAME}'!A{next_row}:D{next_row}",
        valueInputOption="USER_ENTERED",
        body={"values": [[
            f'=ГИПЕРССЫЛКА("{sheet_url}";"{safe_name}")',
            guests, date_str, dish_count,
        ]]},
    ).execute()


# ── Основной экспорт ──────────────────────────────────────────────────────────

def export_event_to_sheets(event_name: str, guests: int,
                           dish_names: list, ingredients: list,
                           event_date: str = "") -> str:
    service = _get_service()
    sheet = service.spreadsheets()

    date_str = datetime.now().strftime("%d.%m.%Y")
    sheet_title = f"{event_name} {date_str}"[:100]

    resp = sheet.batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{"addSheet": {"properties": {"title": sheet_title}}}]}
    ).execute()
    sheet_id = resp["replies"][0]["addSheet"]["properties"]["sheetId"]

    # ── Группируем ингредиенты по отделам ────────────────────────────────────
    by_dept = defaultdict(list)
    for ing in ingredients:
        by_dept[ing["department"]].append(ing)

    # ── Строим данные двух колонок ────────────────────────────────────────────
    # Левая часть (A:B): название, гости, дата, меню
    left = []
    left.append([f"🎉 {event_name}", ""])
    left.append(["👥 Гостей:", guests])
    left.append(["📅 Дата:", event_date if event_date else date_str])
    left.append(["🗓️ Создано:", date_str])
    left.append(["", ""])
    left.append(["🍽️ МЕНЮ", ""])
    left.append(["№", "Блюдо"])
    for i, name in enumerate(dish_names, 1):
        left.append([i, name])

    # Правая часть (D:G): список закупки
    right_start_row = 1  # строка начала (1-based)
    right = []
    right.append(["🛒 СПИСОК ЗАКУПКИ (+7% запас)", "", "", ""])
    right.append(["Отдел", "Продукт", "Количество", "Ед. изм."])

    dept_rows = []  # запоминаем строки отделов для форматирования
    for dept in DEPARTMENT_ORDER:
        items = by_dept.get(dept, [])
        if not items:
            continue
        first = True
        dept_start = len(right) + right_start_row  # 1-based row
        for ing in items:
            amount = ing["amount"]
            unit = ing["unit"]
            amount_str = str(int(amount)) if unit == "шт" else f"{float(amount):.3f}".rstrip("0").rstrip(".")
            right.append([dept if first else "", ing["name"], amount_str, unit])
            first = False
        dept_rows.append((dept_start, dept_start + len(items) - 1))
        right.append(["", "", "", ""])

    # ── Записываем данные ─────────────────────────────────────────────────────
    # Левая колонка A:B
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{sheet_title}'!A1",
        valueInputOption="RAW",
        body={"values": left},
    ).execute()

    # Правая колонка D:G (смещение на 3 колонки)
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{sheet_title}'!D1",
        valueInputOption="RAW",
        body={"values": right},
    ).execute()

    # ── Форматирование ────────────────────────────────────────────────────────
    menu_header_row = 5   # строка "🍽️ МЕНЮ" (0-based = 5)
    menu_col_row = 6      # строка "№ Блюдо" (0-based = 6)
    buy_header_row = 0    # строка "🛒 СПИСОК ЗАКУПКИ" в правой части (0-based = 0)
    buy_col_row = 1       # строка "Отдел Продукт..." (0-based = 1)

    requests = [
        # Ширина колонок
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 160}, "fields": "pixelSize",
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2},
            "properties": {"pixelSize": 180}, "fields": "pixelSize",
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 3},
            "properties": {"pixelSize": 20}, "fields": "pixelSize",
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 3, "endIndex": 4},
            "properties": {"pixelSize": 160}, "fields": "pixelSize",
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 4, "endIndex": 5},
            "properties": {"pixelSize": 180}, "fields": "pixelSize",
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 5, "endIndex": 6},
            "properties": {"pixelSize": 90}, "fields": "pixelSize",
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 6, "endIndex": 7},
            "properties": {"pixelSize": 70}, "fields": "pixelSize",
        }},

        # Заголовок мероприятия (A1)
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": {
                "backgroundColor": COLOR_DARK,
                "textFormat": {"bold": True, "fontSize": 14, "foregroundColor": COLOR_TEXT_W},
            }},
            "fields": "userEnteredFormat",
        }},
        # Merge заголовка A1:B1
        {"mergeCells": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": 2},
            "mergeType": "MERGE_ALL",
        }},

        # Строки гостей/даты — жирная левая колонка
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 5,
                      "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {"userEnteredFormat": {
                "textFormat": {"bold": True},
            }},
            "fields": "userEnteredFormat.textFormat",
        }},

        # Заголовок МЕНЮ (A6)
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": menu_header_row,
                      "endRowIndex": menu_header_row + 1,
                      "startColumnIndex": 0, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": {
                "backgroundColor": COLOR_BLUE,
                "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": COLOR_TEXT_W},
            }},
            "fields": "userEnteredFormat",
        }},
        {"mergeCells": {
            "range": {"sheetId": sheet_id, "startRowIndex": menu_header_row,
                      "endRowIndex": menu_header_row + 1,
                      "startColumnIndex": 0, "endColumnIndex": 2},
            "mergeType": "MERGE_ALL",
        }},

        # Шапка таблицы меню (№ Блюдо)
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": menu_col_row,
                      "endRowIndex": menu_col_row + 1,
                      "startColumnIndex": 0, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": {
                "backgroundColor": COLOR_LIGHT,
                "textFormat": {"bold": True},
            }},
            "fields": "userEnteredFormat",
        }},

        # Заголовок СПИСОК ЗАКУПКИ (D1)
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": buy_header_row,
                      "endRowIndex": buy_header_row + 1,
                      "startColumnIndex": 3, "endColumnIndex": 7},
            "cell": {"userEnteredFormat": {
                "backgroundColor": COLOR_DARK,
                "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": COLOR_TEXT_W},
                "horizontalAlignment": "CENTER",
            }},
            "fields": "userEnteredFormat",
        }},
        {"mergeCells": {
            "range": {"sheetId": sheet_id, "startRowIndex": buy_header_row,
                      "endRowIndex": buy_header_row + 1,
                      "startColumnIndex": 3, "endColumnIndex": 7},
            "mergeType": "MERGE_ALL",
        }},

        # Шапка таблицы закупки (Отдел Продукт...)
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": buy_col_row,
                      "endRowIndex": buy_col_row + 1,
                      "startColumnIndex": 3, "endColumnIndex": 7},
            "cell": {"userEnteredFormat": {
                "backgroundColor": COLOR_BLUE,
                "textFormat": {"bold": True, "foregroundColor": COLOR_TEXT_W},
                "horizontalAlignment": "CENTER",
            }},
            "fields": "userEnteredFormat",
        }},

        # Заморозить первую строку
        {"updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount",
        }},
    ]

    # Форматирование отделов (зелёный фон для названия отдела)
    for dept_start, dept_end in dept_rows:
        r = dept_start + 1  # +1 для шапки, 0-based
        requests.append({"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": r, "endRowIndex": r + 1,
                      "startColumnIndex": 3, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {
                "backgroundColor": COLOR_GREEN,
                "textFormat": {"bold": True, "foregroundColor": COLOR_TEXT_W},
            }},
            "fields": "userEnteredFormat",
        }})

    sheet.batchUpdate(spreadsheetId=SPREADSHEET_ID, body={"requests": requests}).execute()

    # Добавляем в главный лист
    _add_to_index(service, event_name, guests, len(dish_names),
                  event_date if event_date else date_str, sheet_title)

    return (f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
            f"/edit?gid={sheet_id}#gid={sheet_id}")


# ── Удаление ──────────────────────────────────────────────────────────────────

def delete_sheet_for_event(event_name: str):
    service = _get_service()
    sheet = service.spreadsheets()

    spreadsheet = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
    for s in spreadsheet.get("sheets", []):
        title = s["properties"]["title"]
        if title.startswith(event_name):
            sheet_id = s["properties"]["sheetId"]
            sheet.batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"requests": [{"deleteSheet": {"sheetId": sheet_id}}]},
            ).execute()
            logger.info(f"Deleted sheet '{title}'")
            break

    _remove_from_index(service, event_name)


def _remove_from_index(service, event_name: str):
    sheet = service.spreadsheets()
    try:
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{INDEX_SHEET_NAME}'!A:A",
            valueRenderOption="FORMULA",
        ).execute()
        values = result.get("values", [])

        row_index = None
        for i, row in enumerate(values):
            if not row:
                continue
            cell = str(row[0])
            if f'"{event_name}"' in cell or cell == event_name:
                row_index = i
                break

        if row_index is None:
            logger.warning(f"'{event_name}' not found in index")
            return

        spreadsheet = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
        index_id = None
        for s in spreadsheet.get("sheets", []):
            if s["properties"]["title"] == INDEX_SHEET_NAME:
                index_id = s["properties"]["sheetId"]
                break

        if index_id is not None:
            sheet.batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"requests": [{"deleteDimension": {
                    "range": {"sheetId": index_id, "dimension": "ROWS",
                              "startIndex": row_index, "endIndex": row_index + 1}
                }}]},
            ).execute()
    except Exception as e:
        logger.warning(f"Could not remove from index: {e}")
