# Currency Bot

This Telegram bot connects through an MTProto proxy and fetches Iran free-market prices for the US dollar, 18K gold, the euro, and the British pound. It uses the public [NerkhAra API](https://nerkhara.com/en/api/), which requires no API key, publishes prices in toman, and refreshes about every 10 minutes. Price messages credit NerkhAra and show the time each figure was read. The bot can send one-, three-, and six-month price charts, seven-day estimates, and one-shot price alerts backed by SQLite.

## Run with Docker Compose

Create an app at [my.telegram.org](https://my.telegram.org) to get `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`. Put those values and your BotFather token in a `.env` file in the project directory. You can set the complete MTProto proxy link as `MT_PROXY_URL`, or enter its server, port, and secret separately. Base64 encoded `dd` secrets from proxy links are normalized by the bot:

```dotenv
TOKEN=your_telegram_bot_token
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=your_telegram_api_hash
MT_PROXY_URL=tg://proxy?server=proxy.example.com&port=443&secret=your_mtproxy_secret
# Or use these three fields instead of MT_PROXY_URL:
# MT_PROXY_HOST=proxy.example.com
# MT_PROXY_PORT=443
# MT_PROXY_SECRET=your_mtproxy_secret
LOG_LEVEL=INFO
```

Build and start the bot:

```sh
sudo docker compose up --build -d
```

### Find and change the MTProto server

The helper fetches public proxy lists and caches candidates in `data/proxy-candidates.sqlite3`. It checks candidates one by one using the bot's Telethon transport and a Telegram MTProto ping, then stops at the first Telegram response. It needs `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` from `.env`, and tries a second feed if the first is unavailable. If both feeds are unreachable, it can test candidates from its local cache:

```sh
.venv/bin/python scripts/get_mtproxy.py
```

Confirm the prompt to save the first working proxy to `.env`, then apply it with `sudo docker compose up -d`; a plain `docker compose restart` keeps the old environment values. The helper clears `MT_PROXY_URL` so it cannot override the selected host, port, and secret. Public proxies are operated by third parties, may go offline or show sponsored channels, and are not suitable for sensitive traffic. A successful earlier handshake does not guarantee that a proxy is still online.

The bot runs in the background. Send `/start` to get current prices, open **Price charts** for 1-, 3-, or 6-month graphs, choose **7-day forecast** for an asset estimate, or use **Price alerts** to get a one-time message when an asset crosses a target price. Alerts are checked every five minutes, persist in the SQLite database, and are limited to 10 active alerts per user. The forecast compares a hold-last-price baseline with a damped log-linear trend using rolling backtests, and only uses the trend when it improves on the baseline. Its displayed range reflects recent backtest errors; it is not a guarantee. View logs with `sudo docker compose logs -f`; stop it with `sudo docker compose down`. The named volume keeps Telethon's session and SQLite history cache across container restarts. History refreshes every 12 hours and retains six months of daily prices. Keep `.env` private; it contains the bot token, API hash, and proxy secret.

## Run locally

With Python 3.14 and [uv](https://docs.astral.sh/uv/) installed, and the same values set in `.env`:

```sh
uv sync --frozen
uv run python -m app.main
```
