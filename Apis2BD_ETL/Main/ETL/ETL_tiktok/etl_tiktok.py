#!/usr/bin/env python3
"""
etl_tiktok.py  —  Pipeline TikTok → MongoDB

Paso 1: buscar_ids_hashtag  →  recolecta IDs de hashtags y los escribe en videos.txt
Paso 2: TT_Content_Scraper  →  scrapea metadata de cada video (JSON locales)
Paso 3: MongoDB upload       →  inserta/actualiza en centinela.tiktok_videos / tiktok_usuarios

Uso directo:
    python ETL/ETL_tiktok/etl_tiktok.py

Desde main.py:
    import etl_tiktok; etl_tiktok.run_collection()
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError

ETL_TIKTOK_DIR = Path(__file__).parent
PROJECT_ROOT   = ETL_TIKTOK_DIR.parent.parent.parent

load_dotenv(PROJECT_ROOT.parent.parent / ".env")

if str(ETL_TIKTOK_DIR) not in sys.path:
    sys.path.insert(0, str(ETL_TIKTOK_DIR))

import buscar_ids_hashtag
from TT_Content_Scraper.tt_content_scraper import TT_Content_Scraper
from TT_Content_Scraper.src.object_tracker_db import ObjectTracker

# Configuración
VIDEOS_TXT   = ETL_TIKTOK_DIR / "videos.txt"
OUTPUT_DIR   = ETL_TIKTOK_DIR / "datos_tiktok"
PROGRESS_DB  = ETL_TIKTOK_DIR / "progress_tracking" / "scraping_progress.db"
WAIT_TIME    = 0.35
SCRAPE_FILES = False   # True = descarga mp4/jpeg/mp3

DB_NAME      = "centinela"
VIDEOS_COL   = "tiktok_videos"
USUARIOS_COL = "tiktok_usuarios"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [TikTok] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)


def paso1_recolectar_ids():
    log.info("PASO 1 — Recolectando IDs de hashtags")
    buscar_ids_hashtag.ARCHIVO_SALIDA = str(VIDEOS_TXT)
    asyncio.run(buscar_ids_hashtag.main())


def paso2_scrape_contenido():
    log.info("PASO 2 — Scrapeando contenido de los videos")

    if not VIDEOS_TXT.exists() or not VIDEOS_TXT.read_text(encoding="utf-8").strip():
        log.error("'%s' vacío o no existe. Abortando paso 2.", VIDEOS_TXT)
        sys.exit(1)

    ids = [l.strip() for l in VIDEOS_TXT.read_text(encoding="utf-8").splitlines() if l.strip()]
    log.info("%d IDs leídos de videos.txt", len(ids))

    tracker = ObjectTracker(str(PROGRESS_DB))
    tracker.add_objects(ids, type="content")
    stats = tracker.get_stats(type="content")
    log.info("Pendientes en tracker: %d", stats["pending"])
    tracker.close()

    scraper = TT_Content_Scraper(
        wait_time=WAIT_TIME,
        output_files_fp=str(OUTPUT_DIR),
        progress_file_fn=str(PROGRESS_DB))
    try:
        scraper.scrape_pending(only_content=True, scrape_files=SCRAPE_FILES)
    except KeyboardInterrupt:
        log.info("Scraping interrumpido por el usuario.")
    except AssertionError as e:
        log.info("Scraping finalizado: %s", e)


def _construir_doc_video(raw: dict) -> dict:
    v  = raw.get("video_metadata", {})
    f  = raw.get("file_metadata", {})
    m  = raw.get("music_metadata", {})
    a  = raw.get("author_metadata", {})
    ht = raw.get("hashtags_metadata", [])

    video_id = str(v.get("id") or f.get("id") or "")
    username = a.get("username", "")

    return {
        "_id":               video_id,
        "video_id":          video_id,
        "source":            "tiktok",
        "url":               f"https://www.tiktok.com/@{username}/video/{video_id}",
        "descripcion":       v.get("description", ""),
        "duracion_seg":      f.get("duration"),
        "fecha_publicacion": v.get("time_created"),
        "stats": {
            "vistas":      v.get("playcount"),
            "likes":       v.get("diggcount"),
            "comentarios": v.get("commentcount"),
            "compartidos": v.get("sharecount")},
        "musica": {
            "id":     m.get("id"),
            "titulo": m.get("title"),
            "autor":  m.get("author_name")},
        "hashtags":       [h["name"] for h in ht if h.get("name")],
        "autor_username": username,
        "recolectado_en": datetime.now(timezone.utc).isoformat(),
        "_raw":           raw}


def _construir_doc_usuario(raw: dict) -> dict:
    a = raw.get("author_metadata", {})
    username = a.get("username", "")
    return {
        "_id":            username,
        "username":       username,
        "user_id":        str(a.get("id", "")),
        "nombre":         a.get("name"),
        "bio":            a.get("signature"),
        "verificado":     a.get("verified", False),
        "url":            f"https://www.tiktok.com/@{username}",
        "actualizado_en": datetime.now(timezone.utc).isoformat()}


def paso3_subir_mongodb():
    log.info("PASO 3 — Cargando datos a MongoDB")

    uri = os.getenv("MONGODB_URI")
    if not uri:
        log.error("MONGODB_URI no configurada en .env")
        return

    carpeta = OUTPUT_DIR / "content_metadata"
    if not carpeta.exists():
        log.warning("No hay JSONs en %s", carpeta)
        return

    videos_raw = []
    for f in carpeta.glob("*.json"):
        try:
            videos_raw.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            log.warning("Error leyendo %s: %s", f.name, e)
    log.info("%d JSONs leídos", len(videos_raw))

    if not videos_raw:
        return

    client = MongoClient(uri)
    db = client[DB_NAME]
    col_videos   = db[VIDEOS_COL]
    col_usuarios = db[USUARIOS_COL]

    col_videos.create_index("autor_username", background=True)
    col_videos.create_index("hashtags", background=True)
    col_usuarios.create_index("username", unique=True, background=True)

    ops_v, ops_u = [], []
    usuarios_vistos: set = set()

    for raw in videos_raw:
        doc_v = _construir_doc_video(raw)
        doc_u = _construir_doc_usuario(raw)
        vid   = doc_v.get("_id")
        usr   = doc_u.get("_id")

        if not vid:
            continue
        ops_v.append(UpdateOne({"_id": vid}, {"$set": doc_v}, upsert=True))
        if usr and usr not in usuarios_vistos:
            ops_u.append(UpdateOne({"_id": usr}, {"$set": doc_u}, upsert=True))
            usuarios_vistos.add(usr)

    if ops_v:
        try:
            res = col_videos.bulk_write(ops_v, ordered=False)
            log.info("Videos guardados/actualizados: %d / %d",
                     res.upserted_count + res.modified_count, len(ops_v))
        except BulkWriteError as e:
            log.warning("Errores parciales en videos: %s", e.details)

    if ops_u:
        try:
            res = col_usuarios.bulk_write(ops_u, ordered=False)
            log.info("Usuarios guardados/actualizados: %d / %d",
                     res.upserted_count + res.modified_count, len(ops_u))
        except BulkWriteError as e:
            log.warning("Errores parciales en usuarios: %s", e.details)

    total_v = col_videos.count_documents({})
    total_u = col_usuarios.count_documents({})
    log.info("TikTok ETL completo → videos: %d | usuarios: %d", total_v, total_u)


def run_collection():
    paso1_recolectar_ids()
    paso2_scrape_contenido()
    paso3_subir_mongodb()


if __name__ == "__main__":
    run_collection()
