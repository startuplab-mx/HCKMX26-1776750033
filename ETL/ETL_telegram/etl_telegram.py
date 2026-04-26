import asyncio
import json
import logging
import os
import re
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
from telethon.tl.types import (
    Channel, Chat, Message,
    MessageEntityMention, MessageEntityUrl, MessageEntityTextUrl,
    MessageEntityHashtag, MessageEntityBold)
from tqdm import tqdm

etl_dir = Path(__file__).parent.parent
if str(etl_dir) not in sys.path:
    sys.path.insert(0, str(etl_dir))

from scoring import full_analysis, channel_analysis

PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Telegram] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

LEXICON_PATH             = PROJECT_ROOT / "lexicon" / "narco_lexicon.json"
SESSION_FILE             = PROJECT_ROOT / "data" / "centinela_session"
MAX_MESSAGES_PER_CHANNEL = 1000
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


# Palabras comunes en español: si aparecen 2+ el texto se considera español
_ES_WORDS = frozenset([
    'de', 'la', 'el', 'en', 'es', 'un', 'que', 'los', 'las', 'por',
    'con', 'del', 'se', 'al', 'su', 'no', 'lo', 'ya', 'si', 'hay',
    'mas', 'para', 'pero', 'como', 'son', 'una', 'muy', 'bien', 'todo',
    'yo', 'mi', 'tu', 'nos', 'sus', 'les', 'fue', 'ser', 'tiene',
    'trabajo', 'jale', 'paga', 'plaza', 'gente', 'rancho', 'sueldo'])


def is_spanish(text):
    if not text or len(text.strip()) < 15:
        return True  # mensaje corto o solo emojis, conservar
    tl = text.lower()
    if any(c in tl for c in 'ñáéíóúü¿¡'):
        return True
    words = set(re.findall(r'\b\w+\b', tl))
    return len(words & _ES_WORDS) >= 2


def extract_entities(msg):
    mentions = []
    urls     = []
    hashtags = []
    for ent in (msg.entities or []):
        txt = msg.message[ent.offset: ent.offset + ent.length]
        if isinstance(ent, MessageEntityMention):
            mentions.append(txt)
        elif isinstance(ent, (MessageEntityUrl, MessageEntityTextUrl)):
            urls.append(getattr(ent, "url", txt))
        elif isinstance(ent, MessageEntityHashtag):
            hashtags.append(txt)
    return mentions, urls, hashtags


def extract_reactions(msg):
    """Devuelve dict emoji→count de las reacciones del mensaje."""
    reactions = {}
    if not getattr(msg, "reactions", None):
        return reactions
    for r in getattr(msg.reactions, "results", []):
        emoji = getattr(r.reaction, "emoticon", None) or str(r.reaction)
        reactions[emoji] = r.count
    return reactions


def extract_forward_info(msg):
    """Devuelve id y fecha del canal/usuario origen si el mensaje es un reenvio."""
    if not msg.fwd_from:
        return None, None
    fwd_date = msg.fwd_from.date.isoformat() if msg.fwd_from.date else None
    peer     = getattr(msg.fwd_from, "from_id", None)
    if peer is None:
        return None, fwd_date
    fwd_id = (getattr(peer, "channel_id", None) or
              getattr(peer, "user_id",    None) or
              getattr(peer, "chat_id",    None))
    return fwd_id, fwd_date


async def search_public_channels(client, query, limit=20):
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
                    "is_broadcast":       getattr(chat, "broadcast", False),
                    "is_megagroup":       getattr(chat, "megagroup", False),
                    "is_gigagroup":       getattr(chat, "gigagroup", False),
                    "verified":           getattr(chat, "verified", False),
                    "scam":               getattr(chat, "scam", False),
                    "fake":               getattr(chat, "fake", False),
                    "restricted":         getattr(chat, "restricted", False),
                    "no_forwards":        getattr(chat, "noforwards", False),
                    "join_to_send":       getattr(chat, "join_to_send", False)})
        log.info("Canales para '%s': %d", query, len(channels))
    except FloodWaitError as e:
        log.warning("FloodWait: esperando %ds", e.seconds)
        await asyncio.sleep(e.seconds)
    except Exception as e:
        log.error("Error buscando canales para '%s': %s", query, e)
    return channels


async def collect_channel_messages(client, channel_info, lexicon):
    """
    Retorna (messages, about_text) donde about_text es la descripcion del canal.
    Recolecta todos los mensajes en español sin filtro de keywords.
    """
    username   = channel_info["username"]
    messages   = []
    about_text = ""
    try:
        entity       = await client.get_entity(username)
        channel_name = getattr(entity, "username", username)
        channel_id   = entity.id
        about_text   = getattr(entity, "about", "") or ""

        async for msg in client.iter_messages(entity, limit=MAX_MESSAGES_PER_CHANNEL):
            if not isinstance(msg, Message) or not msg.message:
                continue
            if not is_spanish(msg.message):
                continue

            scoring              = full_analysis(msg.message, lexicon, platform="telegram")
            message_uid          = f"{channel_id}_{msg.id}"
            mentions, urls, tags = extract_entities(msg)
            reactions            = extract_reactions(msg)
            fwd_id, fwd_date     = extract_forward_info(msg)
            media_type           = type(msg.media).__name__ if msg.media else None

            messages.append({
                "message_uid":     message_uid,
                "source":          "telegram",
                "channel_name":    channel_name,
                "channel_id":      channel_id,
                "message_id":      msg.id,
                "date":            msg.date.isoformat() if msg.date else None,
                "edit_date":       msg.edit_date.isoformat() if msg.edit_date else None,
                "text":            msg.message,
                "views":           getattr(msg, "views", None),
                "forwards":        getattr(msg, "forwards", None),
                "reply_count":     (msg.replies.replies if msg.replies else None),
                "is_pinned":       bool(msg.pinned),
                "post_author":     getattr(msg, "post_author", None),
                "has_media":       bool(msg.media),
                "media_type":      media_type,
                "has_buttons":     bool(msg.reply_markup),
                "reactions":       reactions,
                "fwd_from_id":     fwd_id,
                "fwd_from_date":   fwd_date,
                "mentions":        mentions,
                "urls":            urls,
                "hashtags":        tags,
                "url":             f"https://t.me/{channel_name}/{msg.id}",
                "collected_at":    datetime.now(timezone.utc).isoformat(),
                "scoring":         scoring})

        log.info("@%s → %d mensajes en español", username, len(messages))

    except ChannelPrivateError:
        log.debug("Canal privado (omitido): @%s", username)
    except (UsernameInvalidError, UsernameNotOccupiedError):
        log.debug("Username invalido: @%s", username)
    except FloodWaitError as e:
        log.warning("FloodWait: esperando %ds", e.seconds)
        await asyncio.sleep(e.seconds)
    except Exception as e:
        log.error("Error en @%s: %s", username, type(e).__name__)
    return messages, about_text


async def run_collection_async(queries, max_queries=None):
    api_id   = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        log.error("TELEGRAM_API_ID o TELEGRAM_API_HASH no configurados en .env")
        return

    lexicon = load_lexicon()
    queries = queries if max_queries is None else queries[:max_queries]

    messages_col, channels_col = get_mongo_collections()
    visited_channels = set()
    total_messages   = 0

    async with TelegramClient(str(SESSION_FILE), int(api_id), api_hash) as client:
        for query in tqdm(queries, desc="Telegram queries"):
            found_channels = await search_public_channels(client, query)
            channel_ops    = []

            for ch in found_channels:
                username = ch.get("username")
                if not username or username in visited_channels:
                    continue
                visited_channels.add(username)

                ch_score             = channel_analysis(username, ch.get("title", ""), lexicon)
                messages, about_text = await collect_channel_messages(client, ch, lexicon)

                about_scoring = (full_analysis(about_text, lexicon, platform="telegram")
                                 if about_text else None)
                if about_text:
                    log.info("@%s about_score=%s",
                             username,
                             about_scoring.get("score_final") if about_scoring else 0)

                channel_doc = {
                    **ch,
                    "first_seen":      datetime.now(timezone.utc).isoformat(),
                    "about":           about_text,
                    "about_scoring":   about_scoring,
                    "channel_scoring": ch_score}

                if ch_score["score"] >= 10:
                    log.info("Canal sospechoso @%s (ch_score=%d)", username, ch_score["score"])

                channel_ops.append(
                    UpdateOne(
                        {"channel_id": ch["channel_id"]},
                        {"$setOnInsert": channel_doc},
                        upsert=True))

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


def run_collection(queries, max_queries=None):
    asyncio.run(run_collection_async(queries, max_queries))


if __name__ == "__main__":
    lexicon = load_lexicon()
    queries = lexicon["search_queries"]["telegram"]
    run_collection(queries)
