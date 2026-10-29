import asyncio
import base64
import binascii
import logging
from urllib.parse import parse_qs, urlparse

from telethon import TelegramClient, connection, events

from app.bot.handlers import CurrencyBotHandlers
from app.config import Config
from app.core.logging_config import setup_logging
from app.currency.api_client import IranMarketDataProvider
from app.currency.formatter import CurrencyFormatter
from app.currency.history_cache import SQLiteHistoryCache
from app.currency.service import CurrencyService

logger = logging.getLogger(__name__)


def normalize_mtproxy_secret(secret: str) -> str:
    """Convert base64 dd-secrets to the hex form Telethon parses correctly."""
    secret = secret.strip()
    if secret[:2].lower() in ("dd", "ee"):
        return secret

    try:
        padding = "=" * (-len(secret) % 4)
        decoded = base64.b64decode(secret + padding, validate=True)
    except (ValueError, binascii.Error):
        return secret

    # These links encode the 0xdd marker plus the 16-byte MTProxy key as base64.
    # Telethon's base64 path truncates the 17-byte value without removing the marker.
    if len(decoded) == 17 and decoded[0] == 0xDD:
        return "dd" + decoded[1:].hex()
    return secret


async def main():
    setup_logging(Config.LOG_LEVEL)
    logger.info("Starting currency bot")

    required = {
        "TOKEN": Config.TELEGRAM_BOT_TOKEN,
        "TELEGRAM_API_ID": Config.TELEGRAM_API_ID,
        "TELEGRAM_API_HASH": Config.TELEGRAM_API_HASH,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )

    if Config.MT_PROXY_URL:
        proxy_params = parse_qs(urlparse(Config.MT_PROXY_URL).query)
        proxy_host = proxy_params.get("server", [None])[0]
        proxy_port = proxy_params.get("port", [None])[0]
        proxy_secret = proxy_params.get("secret", [None])[0]
    else:
        proxy_host = Config.MT_PROXY_HOST
        proxy_port = Config.MT_PROXY_PORT
        proxy_secret = Config.MT_PROXY_SECRET

    if not all((proxy_host, proxy_port, proxy_secret)):
        raise RuntimeError(
            "Set MT_PROXY_URL to your tg://proxy link, or set "
            "MT_PROXY_HOST, MT_PROXY_PORT, and MT_PROXY_SECRET"
        )

    currency_provider = IranMarketDataProvider()
    history_cache = SQLiteHistoryCache(Config.HISTORY_CACHE_DB, currency_provider)
    currency_service = CurrencyService(currency_provider)
    handlers = CurrencyBotHandlers(
        currency_service=currency_service,
        currency_formatter=CurrencyFormatter(),
        history_cache=history_cache,
    )

    client = TelegramClient(
        Config.TELEGRAM_SESSION,
        int(Config.TELEGRAM_API_ID),
        Config.TELEGRAM_API_HASH,
        connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,
        proxy=(
            proxy_host,
            int(proxy_port),
            normalize_mtproxy_secret(proxy_secret),
        ),
    )
    client.add_event_handler(
        handlers.handle_message,
        events.NewMessage(incoming=True),
    )

    try:
        await client.start(bot_token=Config.TELEGRAM_BOT_TOKEN)
        logger.info("Bot is connected through the MTProto proxy")
        await client.run_until_disconnected()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
