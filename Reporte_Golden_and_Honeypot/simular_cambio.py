"""
simular_cambio.py — Inyecta un video simulado en centinela.tiktok_videos.

Simula lo que pasaría cuando el ETL detecta un nuevo post en una cuenta
monitoreada. El demo_monitor.py lo pescará en el siguiente ciclo y
guardará la estampa en high_risk.bot_results.

Uso:
  python simular_cambio.py                        # muestra lista de targets
  python simular_cambio.py <username>             # inyecta para esa cuenta
  python simular_cambio.py <username> "mi texto"  # con descripción custom
  python simular_cambio.py @mitusuario "nuevo vid demo"  # tu propia cuenta
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_THIS_DIR  = Path(__file__).parent
_ROOT      = _THIS_DIR.parent
_MONITOREO = _ROOT / "monitoreo"

sys.path.insert(0, str(_MONITOREO))
sys.stdout.reconfigure(encoding="utf-8")

from mongo_conn import col_tiktok_videos

GOLDEN_JSON = _THIS_DIR / "usuarios_ocr_golden_20260426_124217.json"


def load_users() -> dict[str, dict]:
    data = json.loads(GOLDEN_JSON.read_text(encoding="utf-8"))
    return {u["username"]: u for u in data}


def inject_video(username: str, descripcion: str | None, user_info: dict | None) -> None:
    ts       = int(datetime.now(timezone.utc).timestamp())
    video_id = f"SIM_{username}_{ts}"

    if descripcion is None:
        descripcion = f"[SIMULADO] Nuevo contenido detectado en @{username}"

    nombre = (user_info or {}).get("name", username) if user_info else username
    uid    = str((user_info or {}).get("id", "")) if user_info else ""

    doc = {
        "video_id":          video_id,
        "autor_username":    username,
        "autor_id":          uid,
        "autor_nickname":    nombre,
        "url":               f"https://www.tiktok.com/@{username}/video/{video_id}",
        "descripcion":       descripcion,
        "hashtags":          ["demo", "centinela"],
        "fecha_publicacion": datetime.now(timezone.utc).isoformat(),
        "locationCreated":   "MX",
        "stats": {
            "digg":    0,
            "share":   0,
            "play":    1,
            "comment": 0,
            "collect": 0,
        },
        "video_meta": {
            "duration":   15,
            "definition": "720p",
            "format":     "mp4",
        },
        "scoring": {
            "score_final": 0,
            "risk_level":  "sin_scoring",
        },
        "source":       "tiktok",
        "bot_pescador": True,
        "simulated":    True,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }

    col_tiktok_videos().insert_one(doc)

    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    print("=" * 60)
    print(f"  [{now}] VIDEO SIMULADO INYECTADO")
    print("=" * 60)
    print(f"  username   : @{username}")
    print(f"  nombre     : {nombre}")
    print(f"  video_id   : {video_id}")
    print(f"  descripcion: {descripcion[:60]}")
    print("=" * 60)
    print("  El demo_monitor.py lo detectará en el próximo ciclo.")
    print("  Colección  : centinela.tiktok_videos")
    print("  Estampa    : high_risk.bot_results")
    print("=" * 60)


if __name__ == "__main__":
    users = load_users()

    if len(sys.argv) < 2:
        print("Cuentas disponibles en golden:")
        print(f"  {'username':<35} {'nombre'}")
        print("  " + "-" * 55)
        for uname, u in users.items():
            tagged_by = u.get("moderation", {}).get("taggedBy", "?")
            print(f"  @{uname:<34} {u.get('name', ''):<25} (por {tagged_by})")
        print()
        print("Uso: python simular_cambio.py <username> [\"descripcion\"]")
        print("     python simular_cambio.py el_jc95")
        print("     python simular_cambio.py @mitusuario \"nuevo video demo\"")
        sys.exit(0)

    raw_user    = sys.argv[1].lstrip("@")
    descripcion = sys.argv[2] if len(sys.argv) >= 3 else None
    user_info   = users.get(raw_user)

    inject_video(raw_user, descripcion, user_info)
