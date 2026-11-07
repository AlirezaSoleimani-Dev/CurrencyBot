#!/usr/bin/env python3
"""Fetch recently verified public MTProto proxies, cache them, and select one."""

from __future__ import annotations

import asyncio
import os
import re
import secrets
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import dotenv_values
from telethon import TelegramClient, connection, functions
from telethon.sessions import StringSession

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
DB_FILE = ROOT / "data" / "proxy-candidates.sqlite3"
FEEDS = {
    "tgproxypink": "https://raw.githubusercontent.com/tgproxypink/telegram-proxy-list/main/mtproto.txt",
    "suryadev": "https://raw.githubusercontent.com/suryadev-sm/free-mtproto-proxy-list/main/proxies.txt",
}
LINK_RE = re.compile(r"(?:tg://proxy|https?://t\.me/proxy)\?[^\s\"'<>]+")
TEST_TIMEOUT = 15


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_telegram_credentials() -> tuple[int, str]:
    values = dotenv_values(ENV_FILE)
    api_id = os.environ.get("TELEGRAM_API_ID") or values.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH") or values.get("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env")
    return int(api_id), api_hash


def normalize_secret(secret: str) -> str:
    """Match the bot's normalization for base64-encoded dd proxy secrets."""
    if secret[:2].lower() in ("dd", "ee"):
        return secret
    import base64
    import binascii

    try:
        padding = "=" * (-len(secret) % 4)
        decoded = base64.b64decode(secret + padding, validate=True)
    except (ValueError, binascii.Error):
        return secret
    if len(decoded) == 17 and decoded[0] == 0xDD:
        return "dd" + decoded[1:].hex()
    return secret


async def probe_proxy(candidate: dict[str, str], api_id: int, api_hash: str) -> tuple[dict[str, str], bool, float, str]:
    """Require a successful Telegram MTProto PingRequest through this proxy."""
    client = TelegramClient(
        StringSession(),
        api_id,
        api_hash,
        connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,
        proxy=(candidate["host"], int(candidate["port"]), normalize_secret(candidate["secret"])),
        timeout=TEST_TIMEOUT,
        request_retries=0,
        connection_retries=0,
        auto_reconnect=False,
    )
    started = time.monotonic()
    try:
        async def connect_and_ping():
            await client.connect()
            return await client(functions.PingRequest(ping_id=secrets.randbits(63)))

        await asyncio.wait_for(connect_and_ping(), timeout=TEST_TIMEOUT)
        if not client.is_connected():
            return candidate, False, time.monotonic() - started, "connection closed before reply"
        return candidate, True, time.monotonic() - started, "Telegram MTProto ping replied"
    except Exception as exc:
        return candidate, False, time.monotonic() - started, type(exc).__name__
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def find_first_working_proxy(
    candidates: list[dict[str, str]], api_id: int, api_hash: str
) -> tuple[dict[str, str], float] | None:
    for candidate in candidates:
        candidate, passed, elapsed, reason = await probe_proxy(candidate, api_id, api_hash)
        label = f"{candidate['host']}:{candidate['port']}"
        if passed:
            print(f"[MTProto OK] {label} — {elapsed:.1f}s")
            return candidate, elapsed
        print(f"[unavailable] {label} — {reason}")
    return None


def fetch_candidates() -> list[dict[str, str]]:
    found: dict[tuple[str, int, str], dict[str, str]] = {}
    errors = []
    session = requests.Session()
    session.headers["User-Agent"] = "CurrencyBot-MTProxy-List/1.0"
    for feed_name, url in FEEDS.items():
        try:
            response = session.get(url, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            errors.append(f"{feed_name}: {exc}")
            continue
        for link in LINK_RE.findall(response.text):
            params = parse_qs(urlparse(link).query)
            host = params.get("server", [""])[0].strip()
            port_text = params.get("port", [""])[0]
            secret = params.get("secret", [""])[0].strip()
            if not host or not port_text.isdigit() or not secret:
                continue
            port = int(port_text)
            if not 1 <= port <= 65535:
                continue
            key = (host, port, secret)
            found.setdefault(key, {"host": host, "port": str(port), "secret": secret, "source": feed_name})
    if not found and errors:
        raise RuntimeError("; ".join(errors))
    return list(found.values())


def cache_candidates(candidates: list[dict[str, str]]) -> None:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_FILE) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS proxies (
            host TEXT NOT NULL, port INTEGER NOT NULL, secret TEXT NOT NULL,
            source TEXT NOT NULL, last_seen TEXT NOT NULL,
            PRIMARY KEY (host, port, secret)
        )""")
        stamp = now_iso()
        db.executemany("""INSERT INTO proxies (host, port, secret, source, last_seen)
            VALUES (:host, :port, :secret, :source, :last_seen)
            ON CONFLICT(host, port, secret) DO UPDATE SET
                source=excluded.source, last_seen=excluded.last_seen""",
            [{**item, "last_seen": stamp} for item in candidates])


def load_cached_candidates() -> list[dict[str, str]]:
    if not DB_FILE.exists():
        return []
    with sqlite3.connect(DB_FILE) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("""SELECT host, port, secret, source, last_seen FROM proxies
            ORDER BY last_seen DESC LIMIT 100""").fetchall()
    return [dict(row) for row in rows]


def update_env(candidate: dict[str, str]) -> None:
    if not ENV_FILE.is_file():
        raise RuntimeError(f"{ENV_FILE} not found. Create .env from the README first.")
    lines = ENV_FILE.read_text().splitlines()
    updates = {
        "MT_PROXY_URL": "",
        "MT_PROXY_HOST": candidate["host"],
        "MT_PROXY_PORT": candidate["port"],
        "MT_PROXY_SECRET": candidate["secret"],
    }
    seen: set[str] = set()

    def quote(value: str | int) -> str:
        value = str(value)
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    result = []
    for line in lines:
        stripped = line.lstrip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped and not stripped.startswith("#") else None
        if key in updates:
            if key not in seen:
                result.append(f"{key}={quote(updates[key])}")
                seen.add(key)
        else:
            result.append(line)
    for key, value in updates.items():
        if key not in seen:
            result.append(f"{key}={quote(value)}")
    ENV_FILE.write_text("\n".join(result) + "\n")


def main() -> int:
    try:
        api_id, api_hash = get_telegram_credentials()
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Cannot run MTProto checks: {exc}", file=sys.stderr)
        return 1

    from_cache = False
    try:
        candidates = fetch_candidates()
        if not candidates:
            raise RuntimeError("No compatible MTProto candidates were found in the feeds.")
        cache_candidates(candidates)
    except (requests.RequestException, RuntimeError, sqlite3.Error) as exc:
        candidates = load_cached_candidates()
        if not candidates:
            print(f"Could not refresh the proxy list and no cached candidates exist: {exc}", file=sys.stderr)
            return 1
        from_cache = True
        print(f"Feed refresh failed; offering previously cached candidates instead ({exc}).")

    if from_cache:
        print(f"Loaded {len(candidates)} older candidates from {DB_FILE.relative_to(ROOT)}.")
    else:
        print(f"Cached {len(candidates)} candidates in {DB_FILE.relative_to(ROOT)}.")
    print("These are public third-party proxies. Review their privacy implications before using one.")
    print(f"Checking up to {len(candidates)} candidates one by one; stopping at the first MTProto reply.")
    try:
        working = asyncio.run(find_first_working_proxy(candidates, api_id, api_hash))
    except KeyboardInterrupt:
        print("\nProxy checks cancelled; .env was not changed.", file=sys.stderr)
        return 130
    if not working:
        print("No candidate replied to an MTProto ping. .env was not changed.", file=sys.stderr)
        return 1

    selected, elapsed = working
    recency = f", cached {selected['last_seen']}" if from_cache else ""
    print(
        f"Found a working proxy: {selected['host']}:{selected['port']} "
        f"({elapsed:.1f}s, {selected['source']} list{recency})."
    )
    answer = input("Save it to .env? [Y/n]: ").strip().lower()
    if answer not in ("", "y", "yes"):
        print(".env was not changed.")
        return 0
    try:
        update_env(selected)
    except (OSError, RuntimeError) as exc:
        print(f"Could not update .env: {exc}", file=sys.stderr)
        return 1
    print(f"Saved {selected['host']}:{selected['port']} to .env. Apply it with:")
    print("  sudo docker compose up -d")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
