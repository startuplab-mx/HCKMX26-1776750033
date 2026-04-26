"""
YouTube monitoring bot (polling).

- Lee targets de bot_pescador/youtube/channels.json
- Consulta YouTube Data API v3 por videos nuevos en cada canal
- Guarda nuevos videos en centinela.youtube_items
- Genera alerta en centinela.alertas_pescador + archivo JSON

Variables .env requeridas:
  YOUTUBE_API_KEY

Opcional:
  YOUTUBE_POLL_INTERVAL   (segundos, default 3600)
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT.parent / "Apis2BD_ETL" / "Main" / "ETL"))

from mongo_conn import col_youtube_items, col_bot_state
from notifier import send_alert

TARGETS_FILE     = _ROOT / "bot_pescador" / "youtube" / "channels.json"
DEFAULT_INTERVAL = int(os.getenv("YOUTUBE_POLL_INTERVAL", "3600"))
API_KEY          = os.getenv("YOUTUBE_API_KEY", "")
YT_SEARCH_URL    = "https://www.googleapis.com/youtube/v3/search"


def _load_lexicon():
    lex_path = _ROOT.parent / "lexicon" / "narco_lexicon.json"
    if lex_path.exists():
        with open(lex_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _score(title: str, description: str) -> dict:
    try:
        from scoring import full_analysis
        return full_analysis(f"{title} {description}", _load_lexicon(), platform="youtube")
    except Exception:
        return {"score_final": 0, "risk_level": "sin_scoring"}


def load_targets() -> list[dict]:
    if not TARGETS_FILE.exists():
        print(f"[bot_youtube] Targets no encontrado: {TARGETS_FILE}")
        return []
    with open(TARGETS_FILE, encoding="utf-8") as f:
        return json.load(f).get("targets", [])


def _get_last_checked(channel_id: str) -> str:
    """ISO datetime de la última revisión; default: hace 24 horas."""
    state = col_bot_state("youtube").find_one({"_id": channel_id})
    if state and state.get("last_checked"):
        return state["last_checked"]
    return (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()


def _update_last_checked(channel_id: str):
    col_bot_state("youtube").update_one(
        {"_id": channel_id},
        {"$set": {"last_checked": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


def fetch_new_videos(channel_id: str, published_after: str) -> list[dict]:
    if not API_KEY:
        print("[bot_youtube] YOUTUBE_API_KEY no configurada en .env")
        return []

    params = {
        "key":            API_KEY,
        "channelId":      channel_id,
        "part":           "snippet",
        "order":          "date",
        "publishedAfter": published_after,
        "maxResults":     10,
        "type":           "video",
    }
    try:
        resp = requests.get(YT_SEARCH_URL, params=params, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[bot_youtube] API error para {channel_id}: {e}")
        return []

    videos = []
    for item in resp.json().get("items", []):
        snippet = item.get("snippet", {})
        video_id = item["id"]["videoId"]
        videos.append({
            "video_id":      video_id,
            "channel_id":    channel_id,
            "channel_title": snippet.get("channelTitle", ""),
            "title":         snippet.get("title", ""),
            "description":   snippet.get("description", ""),
            "published_at":  snippet.get("publishedAt", ""),
            "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            "url":           f"https://www.youtube.com/watch?v={video_id}",
            "source":        "youtube",
            "collected_at":  datetime.now(timezone.utc).isoformat(),
            "bot_pescador":  True,
        })
    return videos


def run_monitor(interval: int = DEFAULT_INTERVAL):
    targets = load_targets()
    if not targets:
        print("[bot_youtube] Sin targets. Agrega canales en bot_pescador/youtube/channels.json")
        return

    if not API_KEY:
        print("[bot_youtube] YOUTUBE_API_KEY requerida en .env")
        return

    print(f"[bot_youtube] Iniciando — {len(targets)} canales | ciclo cada {interval}s")

    while True:
        for target in targets:
            channel_id    = target["channel_id"]
            channel_title = target.get("channel_title", channel_id)

            try:
                published_after = _get_last_checked(channel_id)
                new_videos = fetch_new_videos(channel_id, published_after)
                _update_last_checked(channel_id)

                for video in new_videos:
                    # Guardar en MongoDB
                    try:
                        col_youtube_items().update_one(
                            {"video_id": video["video_id"]},
                            {"$set": video},
                            upsert=True,
                        )
                    except Exception as e:
                        print(f"[bot_youtube] MongoDB: {e}")

                    scoring = _score(video["title"], video["description"])

                    send_alert(
                        platform="youtube",
                        account_id=channel_id,
                        account_name=channel_title,
                        event_type="nuevo_video",
                        data={
                            "video_id":          video["video_id"],
                            "url":               video["url"],
                            "title":             video["title"],
                            "description":       video["description"][:400],
                            "published_at":      video["published_at"],
                            "channel_title":     channel_title,
                            "target_reason":     target.get("reason", ""),
                            "target_risk_level": target.get("risk_level", ""),
                        },
                        score=scoring,
                    )

                if new_videos:
                    print(f"[bot_youtube] {channel_title}: {len(new_videos)} videos nuevos")

            except Exception as e:
                print(f"[bot_youtube] Error en {channel_title}: {e}")

        print(f"[bot_youtube] Ciclo completo. Próximo en {interval}s...")
        time.sleep(interval)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                        help="Segundos entre ciclos (default: YOUTUBE_POLL_INTERVAL o 3600)")
    args = parser.parse_args()
    run_monitor(interval=args.interval)
