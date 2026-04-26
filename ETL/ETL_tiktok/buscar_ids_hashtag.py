#!/usr/bin/env python3
"""
buscar_ids_hashtag.py

Recorre páginas de hashtag en TikTok con Playwright,
extrae IDs de video y los guarda en videos.txt para
que example_script.py los procese.

Instalación:
    pip install playwright
    playwright install chromium

Uso:
    python buscar_ids_hashtag.py
"""

import asyncio
import re
from pathlib import Path

from playwright.async_api import async_playwright

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────

_ETL_TIKTOK_DIR = Path(__file__).parent
ARCHIVO_SALIDA   = str(_ETL_TIKTOK_DIR / "videos.txt")  # sobreescribible desde etl_tiktok.py

HASHTAGS = [
    "cjng",
    "4letras",
    "corridostumbados",
    "makabelico",
    "gentedelmayo",
    "delta1",
    "reclutamiento",
    "mz",
    "puromf",
    "lamaña",
    # "ondiados",       # emojis en URL no resuelven en TikTok
    # "belicones",
]

MAX_POR_HASHTAG  = 50    # IDs a recolectar por hashtag
ARCHIVO_SALIDA   = "videos.txt"
HEADLESS         = False  # False = abre ventana (útil para pasar captcha la 1ª vez)
PAUSA_SCROLL_MS  = 2000  # ms entre scrolls
PAUSA_HASHTAG_S  = 3     # segundos entre hashtags

# ─────────────────────────────────────────────


async def ids_de_hashtag(page, hashtag: str, max_videos: int) -> list[str]:
    url = f"https://www.tiktok.com/tag/{hashtag}"
    print(f"\n🔍 #{hashtag}")

    ids: set[str] = set()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(3_000)

        sin_cambios = 0

        while len(ids) < max_videos and sin_cambios < 4:
            links = await page.eval_on_selector_all(
                'a[href*="/video/"]',
                "els => els.map(e => e.href)",
            )
            antes = len(ids)
            for href in links:
                m = re.search(r"/video/(\d+)", href)
                if m:
                    ids.add(m.group(1))

            sin_cambios = 0 if len(ids) > antes else sin_cambios + 1
            print(f"   {len(ids)} IDs...   ", end="\r")

            await page.evaluate("window.scrollBy(0, window.innerHeight * 3)")
            await page.wait_for_timeout(PAUSA_SCROLL_MS)

    except Exception as e:
        print(f"\n   ❌ Error en #{hashtag}: {e}")

    resultado = list(ids)[:max_videos]
    print(f"   → {len(resultado)} IDs obtenidos")
    return resultado


async def main():
    todos: set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"),
            locale="es-MX",
            viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()

        for hashtag in HASHTAGS:
            nuevos = await ids_de_hashtag(page, hashtag, MAX_POR_HASHTAG)
            todos.update(nuevos)
            await asyncio.sleep(PAUSA_HASHTAG_S)

        await browser.close()

    ids_lista = sorted(todos)

    # Combina con IDs existentes en videos.txt (sin duplicar)
    ruta = Path(ARCHIVO_SALIDA)  # usa la ruta configurada (absoluta si vino de etl_tiktok)
    existentes: set[str] = set()
    if ruta.exists():
        existentes = {l.strip() for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()}

    combinados = sorted(existentes | set(ids_lista))
    ruta.write_text("\n".join(combinados), encoding="utf-8")

    nuevos_netos = len(set(ids_lista) - existentes)
    print(f"\n{'='*50}")
    print(f"✅ {len(ids_lista)} IDs encontrados ({nuevos_netos} nuevos)")
    print(f"   Total en '{ARCHIVO_SALIDA}': {len(combinados)}")
    print(f"\n   Siguiente paso:")
    print(f"   python script.py")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    asyncio.run(main())
