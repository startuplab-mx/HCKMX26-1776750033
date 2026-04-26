#!/usr/bin/env python3
"""
etl_tiktok.py  —  Script maestro del pipeline TikTok

Paso 1: buscar_ids_hashtag.py  →  recolecta IDs y los escribe en videos.txt
Paso 2: TT_Content_Scraper     →  agrega los IDs al tracker y scrapea el contenido

Uso:
    python etl_tiktok.py
"""

import asyncio
import sys
from pathlib import Path

import buscar_ids_hashtag
from TT_Content_Scraper.tt_content_scraper import TT_Content_Scraper
from TT_Content_Scraper.src.object_tracker_db import ObjectTracker

# ─── Configuración ────────────────────────────────────────────────
VIDEOS_TXT      = "videos.txt"
OUTPUT_DIR      = "data/"
PROGRESS_DB     = "progress_tracking/scraping_progress.db"
WAIT_TIME       = 0.35
SCRAPE_FILES    = False   # True = descarga videos/imágenes/audio
# ──────────────────────────────────────────────────────────────────


def paso1_recolectar_ids():
    print("\n" + "=" * 55)
    print("PASO 1 — Recolectando IDs de hashtags")
    print("=" * 55)
    asyncio.run(buscar_ids_hashtag.main())


def paso2_scrape_contenido():
    print("\n" + "=" * 55)
    print("PASO 2 — Scrapeando contenido de los videos")
    print("=" * 55)

    ruta = Path(VIDEOS_TXT)
    if not ruta.exists() or not ruta.read_text(encoding="utf-8").strip():
        print(f"❌  '{VIDEOS_TXT}' vacío o no existe. Abortando paso 2.")
        sys.exit(1)

    ids = [l.strip() for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"→ {len(ids)} IDs leídos de '{VIDEOS_TXT}'")

    tracker = ObjectTracker(PROGRESS_DB)
    tracker.add_objects(ids, type="content")
    stats = tracker.get_stats(type="content")
    print(f"→ Pendientes en tracker: {stats['pending']:,}")
    tracker.close()

    scraper = TT_Content_Scraper(
        wait_time=WAIT_TIME,
        output_files_fp=OUTPUT_DIR,
        progress_file_fn=PROGRESS_DB,
    )
    try:
        scraper.scrape_pending(only_content=True, scrape_files=SCRAPE_FILES)
    except KeyboardInterrupt:
        print("\nScraping interrumpido por el usuario.")
    except AssertionError as e:
        print(f"Scraping finalizado: {e}")


if __name__ == "__main__":
    paso1_recolectar_ids()
    paso2_scrape_contenido()
