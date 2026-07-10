import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

# ── выбор драйвера ──────────────────────────────────────────────────────────
if DATABASE_URL:
    import psycopg2
    import psycopg2.extras

    def get_conn():
        conn = psycopg2.connect(DATABASE_URL)
        return conn

    PLACEHOLDER = "%s"
else:
    import sqlite3
    DB_PATH = os.environ.get("DB_PATH", "karavan.db")

    def get_conn():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    PLACEHOLDER = "?"


def _ph(n=1):
    """Возвращает n плейсхолдеров через запятую."""
    return ", ".join([PLACEHOLDER] * n)


# ── инициализация ────────────────────────────────────────────────────────────

def init_db():
    conn = get_conn()
    c = conn.cursor()

    if DATABASE_URL:
        c.execute("""
            CREATE TABLE IF NOT EXISTS dishes (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                serves INTEGER NOT NULL DEFAULT 1
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS ingredients (
                id SERIAL PRIMARY KEY,
                dish_id INTEGER NOT NULL REFERENCES dishes(id),
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                unit TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                guests INTEGER NOT NULL,
                dish_ids TEXT NOT NULL,
                event_date TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS dishes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                serves INTEGER NOT NULL DEFAULT 1
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dish_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                unit TEXT NOT NULL,
                FOREIGN KEY (dish_id) REFERENCES dishes(id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                guests INTEGER NOT NULL,
                dish_ids TEXT NOT NULL,
                event_date TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)

    conn.commit()
    conn.close()
    _migrate()
    _seed_dishes()


def _migrate():
    """Добавляет новые колонки если их нет."""
    conn = get_conn()
    c = conn.cursor()
    try:
        if DATABASE_URL:
            c.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS event_date TEXT NOT NULL DEFAULT ''")
        else:
            c.execute("PRAGMA table_info(events)")
            cols = [row[1] for row in c.fetchall()]
            if "event_date" not in cols:
                c.execute("ALTER TABLE events ADD COLUMN event_date TEXT NOT NULL DEFAULT ''")
        conn.commit()
    except Exception as e:
        logger.warning(f"Migration: {e}")
    finally:
        conn.close()


def _seed_dishes():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM dishes")
    row = c.fetchone()
    count = row[0] if DATABASE_URL else row["COUNT(*)"] if hasattr(row, "keys") else row[0]
    if count > 0:
        conn.close()
        return

    DISHES = [
        ("Винегрет", "Салаты", 3, [
            ("Картофель", 300, "г"), ("Свекла", 250, "г"), ("Морковь", 150, "г"),
            ("Огурцы соленые", 150, "г"), ("Лук репчатый", 50, "г"), ("Масло растительное", 40, "мл"),
        ]),
        ("Цезарь", "Салаты", 3, [
            ("Куриное филе", 240, "г"), ("Лист салата", 150, "г"), ("Пармезан", 90, "г"),
            ("Соус Цезарь", 120, "мл"), ("Гренки", 60, "г"), ("Помидоры черри", 90, "г"),
        ]),
        ("Оливье", "Салаты", 3, [
            ("Картофель", 300, "г"), ("Колбаса вареная", 200, "г"), ("Морковь", 120, "г"),
            ("Огурцы соленые", 120, "г"), ("Горошек зеленый", 100, "г"),
            ("Яйца", 3, "шт"), ("Майонез", 120, "г"),
        ]),
        ("Греческий", "Салаты", 3, [
            ("Помидоры", 250, "г"), ("Огурцы свежие", 200, "г"), ("Перец болгарский", 150, "г"),
            ("Лук красный", 80, "г"), ("Сыр фета", 150, "г"), ("Маслины", 80, "г"),
            ("Масло оливковое", 50, "мл"),
        ]),
        ("Сельдь под шубой", "Салаты", 3, [
            ("Сельдь соленая", 200, "г"), ("Картофель", 200, "г"), ("Свекла", 300, "г"),
            ("Морковь", 120, "г"), ("Лук репчатый", 60, "г"), ("Яйца", 2, "шт"), ("Майонез", 150, "г"),
        ]),
        ("Шашлык из курицы", "Горячее", 1, [
            ("Куриное филе", 280, "г"), ("Лук репчатый", 50, "г"),
            ("Масло растительное", 15, "мл"), ("Специи для шашлыка", 5, "г"),
        ]),
        ("Шашлык из свинины", "Горячее", 1, [
            ("Свинина (шея)", 320, "г"), ("Лук репчатый", 60, "г"),
            ("Уксус столовый", 20, "мл"), ("Специи для шашлыка", 5, "г"),
        ]),
        ("Люля-кебаб", "Горячее", 1, [
            ("Говяжий фарш", 250, "г"), ("Лук репчатый", 50, "г"),
            ("Петрушка", 10, "г"), ("Специи", 5, "г"),
        ]),
        ("Плов", "Горячее", 1, [
            ("Рис", 120, "г"), ("Баранина", 150, "г"), ("Морковь", 80, "г"),
            ("Лук репчатый", 50, "г"), ("Масло растительное", 30, "мл"),
            ("Чеснок", 10, "г"), ("Специи для плова", 5, "г"),
        ]),
        ("Стейк", "Горячее", 1, [
            ("Говядина (стейк)", 300, "г"), ("Масло сливочное", 20, "г"),
            ("Чеснок", 5, "г"), ("Розмарин", 3, "г"), ("Соль", 3, "г"), ("Перец черный", 2, "г"),
        ]),
        ("Запеченная рыба", "Горячее", 1, [
            ("Рыба (филе)", 250, "г"), ("Лимон", 30, "г"),
            ("Масло оливковое", 20, "мл"), ("Зелень", 10, "г"), ("Специи", 5, "г"),
        ]),
        ("Картофель по-деревенски", "Гарниры", 1, [
            ("Картофель", 250, "г"), ("Масло растительное", 20, "мл"),
            ("Чеснок", 5, "г"), ("Специи", 3, "г"),
        ]),
        ("Картофельное пюре", "Гарниры", 1, [
            ("Картофель", 250, "г"), ("Молоко", 60, "мл"),
            ("Масло сливочное", 25, "г"), ("Соль", 3, "г"),
        ]),
        ("Рис", "Гарниры", 1, [
            ("Рис", 100, "г"), ("Масло сливочное", 15, "г"), ("Соль", 2, "г"),
        ]),
        ("Овощи гриль", "Гарниры", 1, [
            ("Перец болгарский", 80, "г"), ("Кабачок", 80, "г"), ("Баклажан", 80, "г"),
            ("Помидоры", 60, "г"), ("Масло оливковое", 20, "мл"), ("Специи", 3, "г"),
        ]),
        ("Мясная нарезка", "Закуски", 4, [
            ("Ветчина", 150, "г"), ("Колбаса сырокопченая", 150, "г"),
            ("Балык", 100, "г"), ("Зелень", 20, "г"),
        ]),
        ("Сырная тарелка", "Закуски", 4, [
            ("Сыр твердый (ассорти)", 250, "г"), ("Виноград", 100, "г"),
            ("Орехи грецкие", 40, "г"), ("Мед", 30, "г"),
        ]),
        ("Овощная нарезка", "Закуски", 4, [
            ("Помидоры", 200, "г"), ("Огурцы свежие", 200, "г"),
            ("Перец болгарский", 150, "г"), ("Зелень", 30, "г"),
        ]),
        ("Соленья", "Закуски", 4, [
            ("Огурцы соленые", 200, "г"), ("Помидоры соленые", 200, "г"),
            ("Капуста квашеная", 150, "г"),
        ]),
        ("Торт", "Десерты", 1, [("Торт (готовый)", 150, "г")]),
        ("Чизкейк", "Десерты", 1, [
            ("Сыр творожный", 120, "г"), ("Печенье для основы", 40, "г"),
            ("Масло сливочное", 20, "г"), ("Сахар", 30, "г"), ("Яйца", 1, "шт"),
        ]),
        ("Фруктовая тарелка", "Десерты", 1, [
            ("Яблоки", 80, "г"), ("Апельсины", 80, "г"), ("Виноград", 60, "г"),
            ("Клубника", 60, "г"), ("Киви", 40, "г"),
        ]),
    ]

    for name, category, serves, ingredients in DISHES:
        c.execute(
            f"INSERT INTO dishes (name, category, serves) VALUES ({_ph(3)}) RETURNING id" if DATABASE_URL
            else f"INSERT INTO dishes (name, category, serves) VALUES ({_ph(3)})",
            (name, category, serves),
        )
        if DATABASE_URL:
            dish_id = c.fetchone()[0]
        else:
            dish_id = c.lastrowid

        for ing_name, amount, unit in ingredients:
            c.execute(
                f"INSERT INTO ingredients (dish_id, name, amount, unit) VALUES ({_ph(4)})",
                (dish_id, ing_name, amount, unit),
            )

    conn.commit()
    conn.close()


# ── CRUD ─────────────────────────────────────────────────────────────────────

def _row_to_dict(row):
    if row is None:
        return None
    if DATABASE_URL:
        return dict(row)
    if hasattr(row, "keys"):
        return dict(row)
    return row


def get_all_dishes():
    conn = get_conn()
    c = conn.cursor()
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM dishes ORDER BY category, name")
    rows = c.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_dish_by_id(dish_id):
    conn = get_conn()
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        c = conn.cursor()
    c.execute(f"SELECT * FROM dishes WHERE id = {PLACEHOLDER}", (dish_id,))
    row = c.fetchone()
    conn.close()
    return _row_to_dict(row)


def get_ingredients_for_dish(dish_id):
    conn = get_conn()
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        c = conn.cursor()
    c.execute(f"SELECT * FROM ingredients WHERE dish_id = {PLACEHOLDER}", (dish_id,))
    rows = c.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def save_event(name, guests, dish_ids, event_date=""):
    conn = get_conn()
    c = conn.cursor()
    if DATABASE_URL:
        c.execute(
            f"INSERT INTO events (name, guests, dish_ids, event_date, created_at) VALUES ({_ph(5)}) RETURNING id",
            (name, guests, json.dumps(dish_ids), event_date, datetime.now().isoformat()),
        )
        event_id = c.fetchone()[0]
    else:
        c.execute(
            f"INSERT INTO events (name, guests, dish_ids, event_date, created_at) VALUES ({_ph(5)})",
            (name, guests, json.dumps(dish_ids), event_date, datetime.now().isoformat()),
        )
        event_id = c.lastrowid
    conn.commit()
    conn.close()
    return event_id


def get_all_events():
    conn = get_conn()
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        c = conn.cursor()
    c.execute("SELECT * FROM events ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_event_by_id(event_id):
    conn = get_conn()
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        c = conn.cursor()
    c.execute(f"SELECT * FROM events WHERE id = {PLACEHOLDER}", (event_id,))
    row = c.fetchone()
    conn.close()
    return _row_to_dict(row)


def delete_event(event_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"DELETE FROM events WHERE id = {PLACEHOLDER}", (event_id,))
    conn.commit()
    conn.close()
