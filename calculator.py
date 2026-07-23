from collections import defaultdict
from database import get_dish_by_id, get_ingredients_for_dish

RESERVE = 1.07  # 7% запас

# Сортировка по отделам
DEPARTMENT_ORDER = [
    "🥩 Мясо и птица",
    "🐟 Рыба и морепродукты",
    "🧀 Молочные продукты",
    "🥚 Яйца",
    "🥔 Овощи",
    "🍎 Фрукты и ягоды",
    "🌿 Зелень и специи",
    "🫙 Консервы и соленья",
    "🍞 Бакалея",
    "🫒 Масла и соусы",
    "🍰 Кондитерские изделия",
    "🧂 Прочее",
]

INGREDIENT_DEPARTMENTS = {
    # Мясо и птица
    "куриное филе": "🥩 Мясо и птица",
    "свинина (шея)": "🥩 Мясо и птица",
    "баранина": "🥩 Мясо и птица",
    "говядина (стейк)": "🥩 Мясо и птица",
    "говяжий фарш": "🥩 Мясо и птица",
    "ветчина": "🥩 Мясо и птица",
    "колбаса вареная": "🥩 Мясо и птица",
    "колбаса сырокопченая": "🥩 Мясо и птица",
    "балык": "🥩 Мясо и птица",
    "сельдь соленая": "🐟 Рыба и морепродукты",
    "рыба (филе)": "🐟 Рыба и морепродукты",
    # Молочные продукты
    "пармезан": "🧀 Молочные продукты",
    "сыр фета": "🧀 Молочные продукты",
    "сыр твердый (ассорти)": "🧀 Молочные продукты",
    "сыр творожный": "🧀 Молочные продукты",
    "майонез": "🧀 Молочные продукты",
    "масло сливочное": "🧀 Молочные продукты",
    "молоко": "🧀 Молочные продукты",
    # Яйца
    "яйца": "🥚 Яйца",
    # Овощи
    "картофель": "🥔 Овощи",
    "свекла": "🥔 Овощи",
    "морковь": "🥔 Овощи",
    "лук репчатый": "🥔 Овощи",
    "лук красный": "🥔 Овощи",
    "помидоры": "🥔 Овощи",
    "помидоры черри": "🥔 Овощи",
    "огурцы свежие": "🥔 Овощи",
    "перец болгарский": "🥔 Овощи",
    "кабачок": "🥔 Овощи",
    "баклажан": "🥔 Овощи",
    "чеснок": "🥔 Овощи",
    "лимон": "🥔 Овощи",
    # Фрукты и ягоды
    "яблоки": "🍎 Фрукты и ягоды",
    "апельсины": "🍎 Фрукты и ягоды",
    "виноград": "🍎 Фрукты и ягоды",
    "клубника": "🍎 Фрукты и ягоды",
    "киви": "🍎 Фрукты и ягоды",
    # Зелень и специи
    "зелень": "🌿 Зелень и специи",
    "петрушка": "🌿 Зелень и специи",
    "розмарин": "🌿 Зелень и специи",
    "лист салата": "🌿 Зелень и специи",
    "специи": "🌿 Зелень и специи",
    "специи для шашлыка": "🌿 Зелень и специи",
    "специи для плова": "🌿 Зелень и специи",
    "соль": "🌿 Зелень и специи",
    "перец черный": "🌿 Зелень и специи",
    # Консервы и соленья
    "огурцы соленые": "🫙 Консервы и соленья",
    "помидоры соленые": "🫙 Консервы и соленья",
    "капуста квашеная": "🫙 Консервы и соленья",
    "горошек зеленый": "🫙 Консервы и соленья",
    "маслины": "🫙 Консервы и соленья",
    # Бакалея
    "рис": "🍞 Бакалея",
    "гренки": "🍞 Бакалея",
    "печенье для основы": "🍞 Бакалея",
    "сахар": "🍞 Бакалея",
    "орехи грецкие": "🍞 Бакалея",
    "мед": "🍞 Бакалея",
    # Масла и соусы
    "масло растительное": "🫒 Масла и соусы",
    "масло оливковое": "🫒 Масла и соусы",
    "соус цезарь": "🫒 Масла и соусы",
    "уксус столовый": "🫒 Масла и соусы",
    # Кондитерские изделия
    "торт (готовый)": "🍰 Кондитерские изделия",
    # Прочее
    "молоко": "🧂 Прочее",
}


def get_department(name: str) -> str:
    return INGREDIENT_DEPARTMENTS.get(name.strip().lower(), "🧂 Прочее")


def normalize_unit(amount: float, unit: str) -> tuple:
    """Всё переводим в кг/л/шт — никаких граммов и миллилитров.
    Штучные — до целых, кг/л — до десятых (единый формат округления)."""
    if unit == "г":
        return round(amount / 1000, 1), "кг"
    if unit == "мл":
        return round(amount / 1000, 1), "л"
    if unit in ("кг", "л"):
        return round(amount, 1), unit
    if unit == "шт":
        return int(round(amount)), "шт"
    return round(amount, 1), unit


def format_amount(amount, unit) -> str:
    if unit == "шт":
        return f"{int(round(amount))} шт"
    return f"{float(amount):.1f} {unit}"


def _capitalize(s: str) -> str:
    return s[0].upper() + s[1:] if s else s


def calculate_ingredients(guests: int, dish_ids: list) -> list:
    """
    Возвращает список словарей: {name, amount, unit, department}
    Отсортированных по отделам, внутри отдела — по алфавиту.
    Всё в кг/л/шт, с 7% запасом.
    """
    totals = defaultdict(float)  # (name_lower, unit_original) -> amount

    for dish_id in dish_ids:
        dish = get_dish_by_id(dish_id)
        if dish is None:
            continue
        serves = dish["serves"]
        multiplier = guests / serves
        ingredients = get_ingredients_for_dish(dish_id)
        for ing in ingredients:
            key = (ing["name"].strip().lower(), ing["unit"])
            totals[key] += ing["amount"] * multiplier

    # Применяем запас и переводим единицы
    merged = defaultdict(lambda: {"amount": 0.0, "unit": ""})
    for (name_lower, unit), amount in totals.items():
        amount_with_reserve = amount * RESERVE
        display_amount, display_unit = normalize_unit(amount_with_reserve, unit)
        # Объединяем по имени (на случай г+кг одного ингредиента)
        key = name_lower
        if merged[key]["unit"] == "" or merged[key]["unit"] == display_unit:
            merged[key]["amount"] += display_amount
            merged[key]["unit"] = display_unit
        else:
            # Разные единицы — добавляем как отдельную строку
            key = f"{name_lower}__{unit}"
            merged[key]["amount"] = display_amount
            merged[key]["unit"] = display_unit

    result = []
    for name_lower, data in merged.items():
        clean_name = name_lower.split("__")[0]
        dept = get_department(clean_name)
        disp_amount, disp_unit = normalize_unit(data["amount"], data["unit"])
        result.append({
            "name": _capitalize(clean_name),
            "amount": disp_amount,
            "unit": disp_unit,
            "department": dept,
        })

    # Сортировка: сначала по отделу (по порядку DEPARTMENT_ORDER), потом по имени
    dept_index = {d: i for i, d in enumerate(DEPARTMENT_ORDER)}
    result.sort(key=lambda x: (dept_index.get(x["department"], 99), x["name"]))
    return result
