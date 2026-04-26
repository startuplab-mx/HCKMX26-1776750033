"""
TikTok monitoring bot.

Sources de targets (se combinan):
  1. analytics/bot_pescador/tiktok/accounts.json
  2. golden.tiktok_usuarios_ORC  (cuentas ORC de la base)

Funcionamiento:
  - Consulta centinela.tiktok_videos para cada target.
  - Compara contra bot_state_tiktok para detectar videos nuevos.
  - Genera alertas en centinela.alertas_pescador + archivos JSON.

Cómo mantener los datos frescos:
  - Este bot DETECTA. El pipeline ETL_tiktok.py ALIMENTA la base.
  - Ejecuta ambos en paralelo: ETL cada N minutos, este bot continuamente.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT.parent / "Apis2BD_ETL" / "Main" / "ETL"))

from mongo_conn import col_tiktok_videos, col_tiktok_usuarios_orc, col_bot_state
from notifier import send_alert

TARGETS_FILE = _ROOT / "bot_pescador" / "tiktok" / "accounts.json"
DEFAULT_INTERVAL = 300


def _load_lexicon():
    lex_path = _ROOT.parent / "lexicon" / "narco_lexicon.json"
    if lex_path.exists():
        with open(lex_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _score(text: str) -> dict:
    try:
        from scoring import full_analysis
        return full_analysis(text or "", _load_lexicon(), platform="tiktok")
    except Exception:
        return {"score_final": 0, "risk_level": "sin_scoring"}


def _load_json_targets() -> list[dict]:
    if not TARGETS_FILE.exists():
        return []
    with open(TARGETS_FILE, encoding="utf-8") as f:
        return json.load(f).get("targets", [])


def _load_orc_targets() -> list[dict]:
    """Carga targets desde golden.tiktok_usuarios_ORC."""
    try:
        targets = []
        for doc in col_tiktok_usuarios_orc().find({}):
            username = doc.get("username") or str(doc.get("_id", ""))
            if not username:
                continue
            targets.append({
                "username": username,
                "user_id": str(doc.get("user_id", "")),
                "url": doc.get("url", f"https://www.tiktok.com/@{username}"),
                "reason": "ORC — golden.tiktok_usuarios_ORC",
                "risk_level": "alto",
            })
        return targets
    except Exception as e:
        print(f"[bot_tik] Error cargando ORC: {e}")
        return []


def load_targets() -> list[dict]:
    seen: set[str] = set()
    merged = []
    json_targets = _load_json_targets()
    orc_targets = _load_orc_targets()
    for t in json_targets + orc_targets:
        u = t.get("username", "").lower()
        if u and u not in seen:
            seen.add(u)
            merged.append(t)
    print(f"[bot_tik] {len(merged)} targets ({len(json_targets)} JSON + {len(orc_targets)} ORC)")
    return merged


def _get_last_seen(username: str):
    state = col_bot_state("tiktok").find_one({"_id": username})
    return state["last_video_date"] if state else None


def _update_last_seen(username: str, date):
    col_bot_state("tiktok").update_one(
        {"_id": username},
        {"$set": {"last_video_date": date, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


def check_new_videos(target: dict) -> list[dict]:
    username = target["username"]
    last_seen = _get_last_seen(username)

    query: dict = {"autor_username": username}
    if last_seen:
        query["fecha_publicacion"] = {"$gt": last_seen}

    videos = list(
        col_tiktok_videos()
        .find(query)
        .sort("fecha_publicacion", -1)
        .limit(20)
    )

    if videos:
        _update_last_seen(username, videos[0]["fecha_publicacion"])

    return videos


def run_monitor(interval: int = DEFAULT_INTERVAL):
    targets = load_targets()
    if not targets:
        print("[bot_tik] Sin targets. Agrega cuentas en bot_pescador/tiktok/accounts.json o en golden.tiktok_usuarios_ORC")
        return

    print(f"[bot_tik] Iniciando — {len(targets)} cuentas | ciclo cada {interval}s")

    while True:
        for target in targets:
            username = target["username"]
            try:
                new_videos = check_new_videos(target)
                for video in new_videos:
                    text = f"{video.get('descripcion', '')} {' '.join(video.get('hashtags', []))}"
                    scoring = video.get("scoring") or _score(text)
                    send_alert(
                        platform="tiktok",
                        account_id=username,
                        account_name=username,
                        event_type="nuevo_video",
                        data={
                            "video_id": video.get("video_id"),
                            "url": video.get("url"),
                            "descripcion": video.get("descripcion", "")[:400],
                            "hashtags": video.get("hashtags", []),
                            "fecha_publicacion": str(video.get("fecha_publicacion", "")),
                            "stats": video.get("stats", {}),
                            "target_reason": target.get("reason", ""),
                            "target_risk_level": target.get("risk_level", ""),
                        },
                        score=scoring,
                    )
            except Exception as e:
                print(f"[bot_tik] Error en {username}: {e}")

        print(f"[bot_tik] Ciclo completo. Próximo en {interval}s...")
        time.sleep(interval)


if __name__ == "__main__":
    run_monitor()
