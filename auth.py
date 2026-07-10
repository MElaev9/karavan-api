import hashlib
import hmac
import os
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")


def _check_init_data(init_data: str, bot_token: str) -> bool:
    """Проверка подписи Telegram WebApp initData (см. core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app)."""
    parsed = dict(parse_qsl(init_data, strict_parsing=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return False

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed_hash, received_hash)


def require_telegram_auth(x_telegram_init_data: str = Header(default="")):
    """FastAPI-dependency: пропускает запрос только если initData подписан нашим ботом.

    Если BOT_TOKEN не задан (локальная разработка), проверка отключена.
    """
    if not BOT_TOKEN:
        return
    if not x_telegram_init_data or not _check_init_data(x_telegram_init_data, BOT_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid Telegram init data")
