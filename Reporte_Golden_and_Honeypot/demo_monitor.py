"""
demo_monitor.py — Monitor continuo sobre cuentas Golden.

Carga los usuarios de usuarios_ocr_golden_20260426_124217.json,
vigila centinela.tiktok_videos y genera una estampa en
high_risk.bot_results cada vez que detecta un video nuevo.

Para simular un cambio en una cuenta:
  python simular_cambio.py <username>

Opciones:
  --interval N     segundos entre ciclos (default: 10)
  --mi-cuenta @usr agrega tu propia cuenta TikTok al monitoreo
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_THIS_DIR = Path(__file__).parent
_ROOT     = _THIS_DIR.parent
_MONITOREO = _ROOT / "monitoreo"

sys.path.insert(0, str(_MONITOREO))
sys.path.insert(0, str(_ROOT / "Apis2BD_ETL" / "Main" / "ETL"))

sys.stdout.reconfigure(encoding="utf-8")

from mongo_conn import col_tiktok_videos, col_bot_state
from notifier  import send_alert

GOLDEN_JSON    = _THIS_DIR / "usuarios_ocr_golden_20260426_124217.json"
STATE_PLATFORM = "tiktok_demo"
DEFAULT_INTERVAL = 10


# ── Carga de targets ──────────────────────────────────────────────────────────

def load_golden_targets() -> list[dict]:
    users = json.loads(GOLDEN_JSON.read_text(encoding="utf-8"))
    targets = []
    for u in users:
        targets.append({
            "username":   u["username"],
            "user_id":    str(u.get("id", "")),
            "name":       u.get("name", u["username"]),
            "reason":     f"golden — etiquetado por {u.get('moderation', {}).get('taggedBy', '?')}",
            "risk_level": "alto",
            "db":         u.get("db", "golden"),
        })
    return targets


# ── Estado por cuenta (video IDs ya vistos) ───────────────────────────────────

def _state_id(username: str) -> str:
    return f"demo_{username}"


def _get_seen_ids(username: str) -> set[str]:
    doc = col_bot_state(STATE_PLATFORM).find_one({"_id": _state_id(username)})
    return set(doc.get("seen_ids", [])) if doc else set()


def _mark_seen(username: str, new_ids: list[str]) -> None:
    seen = _get_seen_ids(username) | set(new_ids)
    col_bot_state(STATE_PLATFORM).update_one(
        {"_id": _state_id(username)},
        {"$set": {
            "seen_ids":   list(seen)[-200:],
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )


# ── Baseline: evitar flood de alertas en el primer ciclo ─────────────────────

def initialize_baseline(targets: list[dict]) -> None:
    print("[init] Registrando baseline de videos existentes (solo videos NUEVOS generarán alertas)...")
    for target in targets:
        username = target["username"]
        if col_bot_state(STATE_PLATFORM).find_one({"_id": _state_id(username)}):
            continue  # ya inicializado en una corrida anterior
        existing = list(
            col_tiktok_videos()
            .find({"autor_username": username}, {"video_id": 1, "_id": 0})
        )
        seen_ids = [v["video_id"] for v in existing if v.get("video_id")]
        col_bot_state(STATE_PLATFORM).update_one(
            {"_id": _state_id(username)},
            {"$set": {
                "seen_ids":   seen_ids[-200:],
                "updated_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    print(f"[init] Listo. Monitoreando {len(targets)} cuentas.\n")


# ── Detección de videos nuevos ────────────────────────────────────────────────

def check_new_videos(target: dict) -> list[dict]:
    username = target["username"]
    seen_ids = _get_seen_ids(username)

    all_videos = list(
        col_tiktok_videos()
        .find({"autor_username": username})
        .sort("collected_at", -1)
        .limit(20)
    )

    new_videos = [
        v for v in all_videos
        if v.get("video_id") and v["video_id"] not in seen_ids
    ]

    if new_videos:
        _mark_seen(username, [v["video_id"] for v in new_videos])

    return new_videos


# ── Loop principal ────────────────────────────────────────────────────────────

def run_demo(targets: list[dict], interval: int = DEFAULT_INTERVAL) -> None:
    print("=" * 62)
    print("  CENTINELA — DEMO MONITOREO CONTINUO")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Cuentas: {len(targets)}  |  Ciclo: {interval}s")
    print("=" * 62)
    for t in targets:
        tag = "[TU CUENTA]" if t.get("mi_cuenta") else f"[{t['db'].upper()}]"
        print(f"  {tag:<12} @{t['username']:<30} {t['name']}")
    print("=" * 62)
    print("  Simular un cambio: python simular_cambio.py <username>")
    print("=" * 62)

    initialize_baseline(targets)

    cycle = 0
    while True:
        cycle += 1
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[{now}] Ciclo #{cycle} — revisando {len(targets)} cuentas...", end="  ")

        total_new = 0
        for target in targets:
            username = target["username"]
            try:
                new_videos = check_new_videos(target)
                for video in new_videos:
                    total_new += 1
                    scoring = video.get("scoring") or {"score_final": 0, "risk_level": "sin_scoring"}
                    sim_tag = " [SIMULADO]" if video.get("simulated") else ""
                    alerta_id = send_alert(
                        platform="tiktok",
                        account_id=username,
                        account_name=target.get("name", username),
                        event_type="nuevo_video_detectado",
                        data={
                            "video_id":          video.get("video_id"),
                            "url":               video.get("url"),
                            "descripcion":       video.get("descripcion", "")[:300],
                            "hashtags":          video.get("hashtags", []),
                            "fecha_publicacion": str(video.get("fecha_publicacion", "")),
                            "stats":             video.get("stats", {}),
                            "target_reason":     target.get("reason", ""),
                            "target_risk_level": target.get("risk_level", "alto"),
                            "simulated":         video.get("simulated", False),
                        },
                        score=scoring,
                    )
                    print()
                    print(f"  🚨 NUEVA ACTIVIDAD{sim_tag} @{username} → estampa guardada")
                    print(f"     alerta_id : {alerta_id}")
                    print(f"     video_id  : {video.get('video_id')}")
                    print(f"     descripcion: {video.get('descripcion', '')[:80]}")
            except Exception as e:
                print()
                print(f"  ⚠️  Error en @{username}: {e}")

        if total_new == 0:
            print(f"sin cambios. Próxima revisión en {interval}s...")
        else:
            print(f"\n  {total_new} evento(s) nuevos → high_risk.bot_results")

        time.sleep(interval)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo monitoreo continuo — Centinela")
    parser.add_argument("--interval",   type=int, default=DEFAULT_INTERVAL,
                        help="Segundos entre ciclos (default: 10)")
    parser.add_argument("--mi-cuenta",  type=str, default=None,
                        help="Tu username de TikTok para incluirlo en el monitoreo (ej: @mitusuario)")
    args = parser.parse_args()

    targets = load_golden_targets()

    if args.mi_cuenta:
        username = args.mi_cuenta.lstrip("@")
        if not any(t["username"].lower() == username.lower() for t in targets):
            targets.insert(0, {
                "username":   username,
                "user_id":    "",
                "name":       username,
                "reason":     "cuenta propia — demo",
                "risk_level": "demo",
                "db":         "demo",
                "mi_cuenta":  True,
            })
            print(f"[+] Tu cuenta @{username} agregada al monitoreo.")

    run_demo(targets, interval=args.interval)
