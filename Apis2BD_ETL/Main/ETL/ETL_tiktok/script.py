#!/usr/bin/env python3
"""
TikTok → MongoDB
Scrapea videos + info del usuario y carga a MongoDB Atlas.

Instalación:
    pip install pymongo TT_Content_Scraper dnspython

Uso:
    1. Pon tus IDs de video en el archivo videos.txt (uno por línea)
    2. Ejecuta: python tiktok_to_mongodb.py
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError

_SCRIPT_DIR  = Path(__file__).parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent.parent
load_dotenv(_PROJECT_ROOT.parent.parent / ".env")

if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from TT_Content_Scraper import TT_Content_Scraper


# Configuración
MONGO_URI       = os.getenv("MONGODB_URI")   # cargado desde .env
DB_NAME         = "centinela"
VIDEOS_COL      = "tiktok_videos"
USUARIOS_COL    = "tiktok_usuarios"

ARCHIVO_IDS        = str(_SCRIPT_DIR / "videos.txt")
CARPETA_SALIDA     = str(_SCRIPT_DIR / "datos_tiktok")
WAIT_TIME          = 1.0
DESCARGAR_ARCHIVOS = False


def conectar_mongo():
    """Conecta a MongoDB Atlas y devuelve (db, col_videos, col_usuarios)."""
    if not MONGO_URI:
        raise RuntimeError("MONGODB_URI no configurada en .env")
    print("Conectando a MongoDB...")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")          # lanza excepción si falla
    db = client[DB_NAME]
    print(f"Conectado a la base de datos: '{DB_NAME}'\n")
    return db, db[VIDEOS_COL], db[USUARIOS_COL]


def leer_ids(archivo: str) -> list[str]:
    """Lee IDs de video desde un archivo de texto."""
    ruta = Path(archivo)
    if not ruta.exists():
        print(f"Archivo '{archivo}' no encontrado.")
        print("   Crea un archivo con IDs de video, uno por linea.")
        return []
    ids = [l.strip() for l in ruta.read_text().splitlines() if l.strip()]
    print(f"{len(ids)} IDs cargados desde {archivo}")
    return ids


def scrapear_videos(ids: list[str]):
    """Descarga metadata (y opcionalmente archivos) con TT_Content_Scraper."""
    if not ids:
        return

    scraper = TT_Content_Scraper(
        wait_time=WAIT_TIME,
        output_files_fp=CARPETA_SALIDA,
        progress_file_fn=os.path.join(CARPETA_SALIDA, "progreso.db"),
        clear_console=False)

    scraper.add_objects(ids=ids, type="content", title="research_batch")

    print("Scrapeando videos...")
    try:
        scraper.scrape_pending(
            only_content=True,
            scrape_files=DESCARGAR_ARCHIVOS)
        print("Scraping completado\n")
    except AssertionError:
        # Todos los IDs ya estaban en progreso.db (scrapeados antes)
        # Los JSONs ya existen en carpeta, se cargarán igual a MongoDB
        print("Todos los IDs ya fueron scrapeados. Cargando JSONs existentes...\n")


def leer_jsons_videos() -> list[dict]:
    """Lee todos los JSON de metadata ya descargados."""
    carpeta = Path(CARPETA_SALIDA) / "content_metadata"
    if not carpeta.exists():
        print(f"Carpeta {carpeta} no encontrada.")
        return []

    videos = []
    for f in carpeta.glob("*.json"):
        try:
            videos.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"  Error leyendo {f.name}: {e}")
    print(f"{len(videos)} archivos JSON leidos")
    return videos


def construir_doc_video(raw: dict) -> dict:
    v  = raw.get("video_metadata",    {})
    f  = raw.get("file_metadata",     {})
    m  = raw.get("music_metadata",    {})
    a  = raw.get("author_metadata",   {})
    ht = raw.get("hashtags_metadata", [])

    video_id  = str(v.get("id") or f.get("id") or "")
    username  = a.get("username", "")

    return {
        "_id":          video_id,
        "video_id":     video_id,
        "url":          f"https://www.tiktok.com/@{username}/video/{video_id}",
        "descripcion":  v.get("description", ""),
        "duracion_seg": f.get("duration"),
        "fecha_publicacion": v.get("time_created"),
        "stats": {
            "vistas":      v.get("playcount"),
            "likes":       v.get("diggcount"),
            "comentarios": v.get("commentcount"),
            "compartidos": v.get("sharecount"),
            "guardados":   v.get("collectcount"),
            "reposts":     v.get("repostcount"),
        },
        "musica": {
            "id":     m.get("id"),
            "titulo": m.get("title"),
            "autor":  m.get("author_name"),
        },
        "hashtags":       [h["name"] for h in ht if h.get("name")],
        "es_anuncio":     v.get("is_ad", False),
        "privado":        v.get("private_item", False),
        "autor_username": username,
        "scrapeado_en":   datetime.now(timezone.utc),
        "_raw":           raw,
    }


def construir_doc_usuario(raw: dict) -> dict:
    a = raw.get("author_metadata", {})
    username = a.get("username", "")
    return {
        "_id":       username,
        "username":  username,
        "user_id":   str(a.get("id", "")),
        "nombre":    a.get("name"),
        "bio":       a.get("signature"),
        "verificado": a.get("verified", False),
        "privado":   a.get("private_account", False),
        "url":       f"https://www.tiktok.com/@{username}",
        "actualizado_en": datetime.now(timezone.utc),
    }


def upsert_a_mongo(col_videos, col_usuarios, videos_raw: list[dict]):
    """
    Inserta o actualiza documentos en MongoDB.
    Usa upsert para no duplicar si ya existe el _id.
    """
    ops_videos   = []
    ops_usuarios = []
    usuarios_vistos = set()

    for raw in videos_raw:
        doc_video   = construir_doc_video(raw)
        doc_usuario = construir_doc_usuario(raw)

        vid = doc_video.get("_id")
        usr = doc_usuario.get("_id")

        if not vid:
            print("  Video sin ID, omitido")
            continue

        # Video: upsert por _id
        ops_videos.append(
            UpdateOne({"_id": vid}, {"$set": doc_video}, upsert=True)
        )

        # Usuario: upsert solo la primera vez que aparece en este lote
        if usr and usr not in usuarios_vistos:
            ops_usuarios.append(
                UpdateOne({"_id": usr}, {"$set": doc_usuario}, upsert=True)
            )
            usuarios_vistos.add(usr)

    # Escritura a MongoDB
    videos_ok = usuarios_ok = 0

    if ops_videos:
        try:
            res = col_videos.bulk_write(ops_videos, ordered=False)
            videos_ok = res.upserted_count + res.modified_count
        except BulkWriteError as bwe:
            print(f"  Errores parciales en videos: {bwe.details}")

    if ops_usuarios:
        try:
            res = col_usuarios.bulk_write(ops_usuarios, ordered=False)
            usuarios_ok = res.upserted_count + res.modified_count
        except BulkWriteError as bwe:
            print(f"  Errores parciales en usuarios: {bwe.details}")

    print(f"Videos guardados/actualizados:   {videos_ok} / {len(ops_videos)}")
    print(f"Usuarios guardados/actualizados: {usuarios_ok} / {len(ops_usuarios)}")


def crear_indices(col_videos, col_usuarios):
    """Crea índices útiles para consultas."""
    col_videos.create_index("autor_username")
    col_videos.create_index("hashtags")
    col_videos.create_index("fecha_publicacion")
    col_usuarios.create_index("username", unique=True)
    print("Indices creados\n")


def main():
    print("=" * 60)
    print("  TikTok → MongoDB  ")
    print("=" * 60 + "\n")

    # 1. Conectar
    db, col_videos, col_usuarios = conectar_mongo()
    crear_indices(col_videos, col_usuarios)

    # 2. Leer IDs
    ids = leer_ids(ARCHIVO_IDS)
    if not ids:
        return

    # 3. Scrapear
    scrapear_videos(ids)

    # 4. Leer JSONs descargados
    videos_raw = leer_jsons_videos()
    if not videos_raw:
        print("No hay datos que cargar a MongoDB.")
        return

    # 5. Cargar a MongoDB
    print("Cargando a MongoDB...")
    upsert_a_mongo(col_videos, col_usuarios, videos_raw)

    # 6. Resumen final
    total_videos   = col_videos.count_documents({})
    total_usuarios = col_usuarios.count_documents({})
    print(f"\n{'='*60}")
    print(f"  Total en MongoDB:")
    print(f"  • Colección '{VIDEOS_COL}':   {total_videos} documentos")
    print(f"  • Colección '{USUARIOS_COL}': {total_usuarios} documentos")
    print(f"{'='*60}\n")
    print("Proceso completado!")


if __name__ == "__main__":
    main()