#!/usr/bin/env python3
"""
Corre este script UNA SOLA VEZ para autenticar la sesión de Telegram.
Después de completar el login, run_bots.py arrancará sin pedir credenciales.

  python monitoreo/auth_telegram.py
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SESSION_FILE = Path(__file__).parent / "bot_pescador" / "sesiones" / "pescador_telegram"
API_ID   = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")


async def main():
    if not API_ID or not API_HASH:
        sys.exit("[ERROR] Falta TELEGRAM_API_ID o TELEGRAM_API_HASH en .env")

    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(str(SESSION_FILE), API_ID, API_HASH)
    await client.start()           # pide teléfono + código (solo esta vez)

    me = await client.get_me()
    print(f"\n✅ Sesión guardada como: {me.first_name} (@{me.username})")
    print(f"   Archivo: {SESSION_FILE}.session")
    print("\nYa puedes correr: python monitoreo/run_bots.py")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
