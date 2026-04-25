import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    FloodWaitError,
    UsernameInvalidError,
    UsernameNotOccupiedError)
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import Channel, Chat, Message
from tqdm import tqdm

etl_dir = Path(__file__).parent.parent
if str(etl_dir) not in sys.path:
    sys.path.insert(0, str(etl_dir))

from scoring import full_analysis

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
load_dotenv(PROJECT_ROOT / "centinela_data_explorer" / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Telegram] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

LEXICON_PATH             = PROJECT_ROOT / "centinela_data_explorer" / "lexicon" / "narco_lexicon.json"
SESSION_FILE             = PROJECT_ROOT / "centinela_data_explorer" / "data" / "centinela_session"
MAX_MESSAGES_PER_CHANNEL = 200
SLEEP_BETWEEN_CHANNELS   = 2


def load_lexicon():
    with open(LEXICON_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_mongo_collections():
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI no configurada en .env")
    client = MongoClient(uri)
    db     = client["centinela"]
    db["telegram_messages"].create_index("message_uid", unique=True, background=True)
    db["telegram_channels"].create_index("channel_id",  unique=True, background=True)
    return db["telegram_messages"], db["telegram_channels"]


def build_keyword_set(lexicon):
    keywords = set()
    frases = lexicon.get("recruitment_phrases", {})
    if isinstance(frases, dict):
        for phrase in frases.get("explicit", {}).get("phrases", []):
            keywords.add(phrase.lower())
        for phrase in frases.get("soft", {}).get("phrases", []):
            keywords.add(phrase.lower())
    elif isinstance(frases, list):
        for phrase in frases:
            keywords.add(phrase.lower())
    for cdata in lexicon.get("hashtags", {}).values():
        for tag in cdata.get("tags", []):
            keywords.add(tag.lower().lstrip("#"))
    for emoji in lexicon.get("emojis", {}).keys():
        keywords.add(emoji)
    return keywords


def message_matches_lexicon(text, keywords):
    if not text:
        return False
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


async def search_public_channels(client, query, limit=10):
    channels = []
    try:
        result = await client(SearchRequest(q=query, limit=limit))
        for chat in result.chats:
            if isinstance(chat, (Channel, Chat)) and getattr(chat, "username", None):
                channels.append({
                    "channel_id":         chat.id,
                    "username":           chat.username,
                    "title":              getattr(chat, "title", ""),
                    "participants_count": getattr(chat, "participants_count", None),
                    "is_broadcast":       getattr(chat, "broadcast", False)})
        log.info("Canales para '%s': %d", query, len(channels))
    except FloodWaitError as e:
        log.warning("FloodWait: esperando %ds", e.seconds)
        await asyncio.sleep(e.seconds)
    except Exception as e:
        log.error("Error buscando canales para '%s': %s", query, e)
    return channels


async def collect_channel_messages(client, channel_info, keywords, lexicon):
    username = channel_info["username"]
    messages = []
    try:
        entity       = await client.get_entity(username)
        channel_name = getattr(entity, "username", username)
        channel_id   = entity.id

        async for msg in client.iter_messages(entity, limit=MAX_MESSAGES_PER_CHANNEL):
            if not isinstance(msg, Message) or not msg.message:
                continue
            if not message_matches_lexicon(msg.message, keywords):
                continue
            scoring     = full_analysis(msg.message, lexicon, platform="telegram")
            message_uid = f"{channel_id}_{msg.id}"
            messages.append({
                "message_uid":  message_uid,
                "source":       "telegram",
                "channel_name": channel_name,
                "channel_id":   channel_id,
                "message_id":   msg.id,
                "date":         msg.date.isoformat() if msg.date else None,
                "text":         msg.message,
                "views":        getattr(msg, "views", None),
                "forwards":     getattr(msg, "forwards", None),
                "url":          f"https://t.me/{channel_name}/{msg.id}",
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "scoring":      scoring})

        log.info("@%s → %d mensajes relevantes", username, len(messages))

    except ChannelPrivateError:
        log.debug("Canal privado (omitido): @%s", username)
    except (UsernameInvalidError, UsernameNotOccupiedError):
        log.debug("Username invalido: @%s", username)
    except FloodWaitError as e:
        log.warning("FloodWait: esperando %ds", e.seconds)
        await asyncio.sleep(e.seconds)
    except Exception as e:
        log.error("Error en @%s: %s", username, type(e).__name__)
    return messages


async def run_collection_async(queries, max_queries=10):
    api_id   = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        log.error("TELEGRAM_API_ID o TELEGRAM_API_HASH no configurados en .env")
        return

    lexicon  = load_lexicon()
    keywords = build_keyword_set(lexicon)
    queries  = queries[:max_queries]

    messages_col, channels_col = get_mongo_collections()
    visited_channels = set()
    total_messages   = 0

    async with TelegramClient(str(SESSION_FILE), int(api_id), api_hash) as client:
        for query in tqdm(queries, desc="Telegram queries"):
            found_channels = await search_public_channels(client, query)
            channel_ops = []

            for ch in found_channels:
                username = ch.get("username")
                if not username or username in visited_channels:
                    continue
                visited_channels.add(username)

                channel_doc = {**ch, "first_seen": datetime.now(timezone.utc).isoformat()}
                channel_ops.append(
                    UpdateOne(
                        {"channel_id": ch["channel_id"]},
                        {"$setOnInsert": channel_doc},
                        upsert=True))

                messages = await collect_channel_messages(client, ch, keywords, lexicon)
                if messages:
                    msg_ops = [
                        UpdateOne(
                            {"message_uid": m["message_uid"]},
                            {"$set": m},
                            upsert=True)
                        for m in messages]
                    result = messages_col.bulk_write(msg_ops, ordered=False)
                    saved  = result.upserted_count + result.modified_count
                    total_messages += saved
                    log.info("@%s → %d mensajes en MongoDB", username, saved)

                await asyncio.sleep(SLEEP_BETWEEN_CHANNELS)

            if channel_ops:
                channels_col.bulk_write(channel_ops, ordered=False)

    log.info(
        "Telegram ETL completo: %d mensajes, %d canales unicos",
        total_messages,
        len(visited_channels))


def run_collection(queries, max_queries=10):
    asyncio.run(run_collection_async(queries, max_queries))


if __name__ == "__main__":
    lexicon = load_lexicon()
    queries = lexicon["search_queries"]["telegram"]
    run_collection(queries, max_queries=10)
