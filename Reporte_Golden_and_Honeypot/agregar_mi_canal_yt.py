"""
agregar_mi_canal_yt.py — Agrega tu canal de YouTube al sistema de monitoreo.

El script resuelve tu handle (@tucanal) al channel_id real via YouTube API
y lo registra en monitoreo/bot_pescador/youtube/channels.json.

Uso:
  python agregar_mi_canal_yt.py @tuhandle
  python agregar_mi_canal_yt.py UCxxxxxxxxxxxxxxxxxxxxxxxxx  (si ya tienes el ID)

Después correr el monitor:
  cd ../monitoreo
  python bot_youtube.py --interval 60
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
import os

_THIS_DIR  = Path(__file__).parent
_ROOT      = _THIS_DIR.parent
_MONITOREO = _ROOT / "monitoreo"

load_dotenv(_ROOT / ".env")
sys.stdout.reconfigure(encoding="utf-8")

CHANNELS_JSON = _MONITOREO / "bot_pescador" / "youtube" / "channels.json"
API_KEY       = os.getenv("YOUTUBE_API_KEY", "")
YT_CHANNELS   = "https://www.googleapis.com/youtube/v3/channels"


def resolve_channel(handle_or_id: str) -> tuple[str, str]:
    """Devuelve (channel_id, title). Acepta @handle o UCxxx directo."""
    raw = handle_or_id.strip()

    if raw.startswith("UC") and len(raw) > 20:
        resp = requests.get(
            YT_CHANNELS,
            params={"part": "snippet", "id": raw, "key": API_KEY},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if items:
            return raw, items[0]["snippet"]["title"]
        return raw, raw

    handle = raw if raw.startswith("@") else f"@{raw}"
    resp = requests.get(
        YT_CHANNELS,
        params={"part": "snippet", "forHandle": handle, "key": API_KEY},
        timeout=15,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        print(f"❌  No se encontró el canal '{handle}' en YouTube.")
        print("   Verifica el handle o usa directamente el channel_id (UCxxx).")
        sys.exit(1)
    return items[0]["id"], items[0]["snippet"]["title"]


def add_to_channels_json(channel_id: str, title: str) -> None:
    data = json.loads(CHANNELS_JSON.read_text(encoding="utf-8"))

    if any(t["channel_id"] == channel_id for t in data["targets"]):
        print(f"✅  El canal ya está en channels.json: {title} ({channel_id})")
        return

    data["targets"].append({
        "channel_id":    channel_id,
        "channel_title": title,
        "added_at":      datetime.now(timezone.utc).date().isoformat(),
        "reason":        "cuenta propia — demo monitoreo",
        "risk_level":    "demo",
    })
    CHANNELS_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅  Agregado a channels.json: {title} ({channel_id})")


if __name__ == "__main__":
    if not API_KEY:
        print("❌  YOUTUBE_API_KEY no configurada en .env")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Uso: python agregar_mi_canal_yt.py @tuhandle")
        print("     python agregar_mi_canal_yt.py UCxxxxxxxxxxxxxxxxxxxxxxxxx")
        sys.exit(0)

    entrada = sys.argv[1]
    print(f"Buscando canal '{entrada}' en YouTube API...")

    channel_id, title = resolve_channel(entrada)
    print(f"Canal encontrado: {title} → {channel_id}")

    add_to_channels_json(channel_id, title)

    print()
    print("Para iniciar el monitoreo en tiempo real (ciclo cada 60s):")
    print(f"  cd {_MONITOREO}")
    print(f"  python bot_youtube.py --interval 60")
    print()
    print("Cuando subas un video o Short, aparecerá en high_risk.bot_results en ~1-3 min.")
