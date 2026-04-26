"""
Shared MongoDB connection for all Centinela bots.
Reads MONGODB_URI from .env — centinela y golden están en el mismo cluster.
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        uri = os.getenv("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI no configurada en .env")
        _client = MongoClient(uri)
    return _client


# ── Database accessors ────────────────────────────────────────────────────────

def get_centinela_db():
    return get_client()["centinela"]


def get_golden_db():
    return get_client()[os.getenv("MONGODB_GOLDEN_DB", "golden")]


# ── Collection shortcuts ──────────────────────────────────────────────────────

def col_tiktok_usuarios_orc():
    """golden.tiktok_usuarios_ORC — cuentas casi confirmadas (procesadas)."""
    return get_golden_db()["tiktok_usuarios_ORC"]


def col_tiktok_videos():
    return get_centinela_db()["tiktok_videos"]


def col_tiktok_usuarios():
    return get_centinela_db()["tiktok_usuarios"]


def col_telegram_messages():
    return get_centinela_db()["telegram_messages"]


def col_telegram_channels():
    return get_centinela_db()["telegram_channels"]


def col_youtube_items():
    return get_centinela_db()["youtube_items"]


def col_alertas():
    return get_centinela_db()["alertas_pescador"]


def get_high_risk_db():
    return get_client()["high_risk"]


def col_bot_results():
    return get_high_risk_db()["bot_results"]


def col_bot_state(platform: str):
    """Per-platform state tracker (last seen IDs / timestamps)."""
    return get_centinela_db()[f"bot_state_{platform}"]
