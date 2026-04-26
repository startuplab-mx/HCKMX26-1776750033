"""
Orquestador — lanza los tres bots en paralelo.

  python analytics/run_bots.py

TikTok  → hilo independiente (polling cada 5 min)
YouTube → hilo independiente (polling cada 1 hora)
Telegram → loop asyncio principal (tiempo real, event-driven)
"""

import asyncio
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bot_tik
import bot_youtube
import bot_telegram


def _thread(name: str, fn, *args):
    t = threading.Thread(target=fn, args=args, daemon=True, name=name)
    t.start()
    return t


async def main():
    tiktok_t  = _thread("bot-tiktok",  bot_tik.run_monitor,     300)
    youtube_t = _thread("bot-youtube",  bot_youtube.run_monitor, 3600)

    print("[run_bots] Hilos TikTok y YouTube iniciados.")
    print("[run_bots] Iniciando bot Telegram (loop principal)...")

    await bot_telegram.run_monitor()   # bloquea hasta desconexión

    tiktok_t.join(timeout=5)
    youtube_t.join(timeout=5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[run_bots] Bots detenidos.")
