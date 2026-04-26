"""
Telegram monitoring bot (real-time).

- Lee targets de bot_pescador/telegram/channels.json
- Se une a canales públicos y escucha mensajes nuevos vía Telethon events
- Guarda cada mensaje en centinela.telegram_messages
- Genera alerta en centinela.alertas_pescador + archivo JSON

Variables .env requeridas:
  TELEGRAM_API_ID
  TELEGRAM_API_HASH

Opcional (para reenviar alertas a quien hace el reporte):
  TELEGRAM_ALERT_BOT_TOKEN
  TELEGRAM_ALERT_CHAT_ID
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import Message

load_dotenv()

_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT.parent / "Apis2BD_ETL" / "Main" / "ETL"))

from mongo_conn import col_telegram_messages, col_telegram_channels
from notifier import send_alert

TARGETS_FILE = _ROOT / "bot_pescador" / "telegram" / "channels.json"
SESSION_FILE = str(_ROOT / "bot_pescador" / "sesiones" / "pescador_telegram")

API_ID   = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")


def _load_lexicon():
    lex_path = _ROOT.parent / "lexicon" / "narco_lexicon.json"
    if lex_path.exists():
        with open(lex_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _score(text: str) -> dict:
    try:
        from scoring import full_analysis
        return full_analysis(text or "", _load_lexicon(), platform="telegram")
    except Exception:
        return {"score_final": 0, "risk_level": "sin_scoring"}


def load_targets() -> list[dict]:
    if not TARGETS_FILE.exists():
        print(f"[bot_telegram] Targets no encontrado: {TARGETS_FILE}")
        return []
    with open(TARGETS_FILE, encoding="utf-8") as f:
        return json.load(f).get("targets", [])


async def _verify_channel(client: TelegramClient, username: str) -> bool:
    try:
        await client.get_entity(username)
        print(f"[bot_telegram] ✅ Acceso confirmado: @{username}")
        return True
    except Exception as e:
        print(f"[bot_telegram] ❌ Sin acceso a @{username}: {e}")
        return False


async def run_monitor():
    targets = load_targets()
    if not targets:
        print("[bot_telegram] Sin targets. Agrega canales en bot_pescador/telegram/channels.json")
        return

    if not API_ID or not API_HASH:
        print("[bot_telegram] Falta TELEGRAM_API_ID / TELEGRAM_API_HASH en .env")
        return

    Path(SESSION_FILE).parent.mkdir(parents=True, exist_ok=True)

    usernames   = [t["username"] for t in targets]
    target_map  = {t["username"]: t for t in targets}

    async with TelegramClient(SESSION_FILE, API_ID, API_HASH) as client:
        # Verificar acceso (canales públicos no requieren join explícito)
        accessible = [u for u in usernames if await _verify_channel(client, u)]
        if not accessible:
            print("[bot_telegram] Ningún canal accesible.")
            return

        # Registrar canales en MongoDB
        for t in targets:
            try:
                entity = await client.get_entity(t["username"])
                doc = {
                    "channel_id":         getattr(entity, "id", None),
                    "username":           t["username"],
                    "title":              getattr(entity, "title", t.get("title", "")),
                    "participants_count": getattr(entity, "participants_count", 0),
                    "is_broadcast":       getattr(entity, "broadcast", False),
                    "first_seen":         datetime.now(timezone.utc).isoformat(),
                    "bot_pescador":       True,
                }
                col_telegram_channels().update_one(
                    {"username": t["username"]},
                    {"$setOnInsert": doc},
                    upsert=True,
                )
            except Exception:
                pass

        print(f"[bot_telegram] Monitoreando {len(accessible)} canales en tiempo real...")

        @client.on(events.NewMessage(chats=accessible))
        async def handler(event):
            msg: Message = event.message
            chat = await event.get_chat()
            channel_username = getattr(chat, "username", str(chat.id)) or str(chat.id)
            target_info = target_map.get(channel_username, {})

            text    = msg.text or ""
            scoring = _score(text)

            # Persistir en MongoDB
            msg_doc = {
                "message_uid":  f"{chat.id}_{msg.id}",
                "source":       "telegram",
                "channel_id":   chat.id,
                "channel_name": channel_username,
                "message_id":   msg.id,
                "date":         msg.date.isoformat() if msg.date else None,
                "text":         text,
                "views":        getattr(msg, "views",    0) or 0,
                "forwards":     getattr(msg, "forwards", 0) or 0,
                "has_media":    bool(msg.media),
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "scoring":      scoring,
                "bot_pescador": True,
            }
            try:
                col_telegram_messages().update_one(
                    {"message_uid": msg_doc["message_uid"]},
                    {"$set": msg_doc},
                    upsert=True,
                )
            except Exception as e:
                print(f"[bot_telegram] MongoDB: {e}")

            send_alert(
                platform="telegram",
                account_id=str(chat.id),
                account_name=channel_username,
                event_type="nuevo_mensaje",
                data={
                    "message_id": msg.id,
                    "url":        f"https://t.me/{channel_username}/{msg.id}",
                    "text":       text[:500],
                    "date":       str(msg.date),
                    "views":      msg_doc["views"],
                    "forwards":   msg_doc["forwards"],
                    "has_media":  msg_doc["has_media"],
                    "target_reason":     target_info.get("reason", ""),
                    "target_risk_level": target_info.get("risk_level", ""),
                },
                score=scoring,
            )

            risk = scoring.get("risk_level", "—")
            print(f"[bot_telegram] @{channel_username} | {risk} | {text[:60]}...")

        await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(run_monitor())
