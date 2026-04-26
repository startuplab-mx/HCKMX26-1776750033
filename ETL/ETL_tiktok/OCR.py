#!/usr/bin/env python3
"""
OCR.py

Pipeline completo para los IDs de NEW_IDS:
  1. Registra los IDs en el tracker del scraper (INSERT OR IGNORE)
  2. Descarga videos/slides con el scraper normal (TT_Content_Scraper)
  3. Lee los archivos descargados y aplica OCR
  4. Upsert en MongoDB: tiktok_videos_ORC + tiktok_usuarios_ORC
     (silver siempre; gold si el texto OCR supera GOLD_MIN_TEXT_LEN)
"""

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import cv2
import easyocr
from pymongo import MongoClient

# ─── path al paquete TT_Content_Scraper ───────────────────────────────────────
_PKG_PATH = Path(__file__).parent
if str(_PKG_PATH) not in sys.path:
    sys.path.insert(0, str(_PKG_PATH))

from TT_Content_Scraper.tt_content_scraper import TT_Content_Scraper  # type: ignore

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────

MONGO_URI    = "mongodb+srv://isra_db_user:Energiaoscura12w@bronze.blfvi5w.mongodb.net/?appName=Bronze"
DB_SILVER    = "silver"
DB_GOLD      = "golden"
COL_VIDEOS   = "tiktok_videos_ORC"
COL_USUARIOS = "tiktok_usuarios_ORC"

# Directorio donde el scraper guarda los archivos
DATA_DIR = Path(__file__).parent / "data"

GOLD_MIN_TEXT_LEN = 15
OCR_IDIOMAS       = ["es", "en"]
FRAMES_POR_VIDEO  = 5
SCRAPER_WAIT      = 0.5   # segundos entre requests del scraper

# ── DEFINE AQUÍ LOS NUEVOS IDs A PROCESAR ────────────────────────────────────
NEW_IDS: list[str] = [
     "7630267537321708820",
     "7632740896919784712",
     "7625074518289059090",
     "7632934605535972628",
     "7631533853231959303",
     "7617323685342366994",
     "7620333830280367378",
     "7629071316577996052",
     "7603611693582683400",
     "7589077992752598284",
     "7626090944726633736",
     "7628852724154518792",
     "7609622413801803026",
     "7628282692479618311",
     "7622055167491329281",
     "7609621228206263560",
     "7611509447612960008",
     "7609613679805402386"
]
# ─────────────────────────────────────────────────────────────────────────────

SEP = "=" * 60


# ─── OCR ──────────────────────────────────────────────────────────────────────

_reader: easyocr.Reader | None = None

def _get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        print("  Cargando modelo EasyOCR (solo la primera vez)...")
        _reader = easyocr.Reader(OCR_IDIOMAS, gpu=False)
        print("  EasyOCR listo\n")
    return _reader


def _ocr_imagen(ruta: str) -> str:
    try:
        resultado = _get_reader().readtext(ruta, detail=0, paragraph=True)
        return " | ".join(r.strip() for r in resultado if r.strip())
    except Exception as e:
        print(f"    [WARN] OCR falló en {ruta}: {e}")
        return ""


# ─── Procesadores locales ──────────────────────────────────────────────────────

def _tiempos_muestreo(total_frames: int, n: int) -> list[int]:
    if total_frames <= n:
        return list(range(total_frames))
    step = total_frames / (n - 1) if n > 1 else total_frames
    return [min(int(i * step), total_frames - 1) for i in range(n)]


def procesar_video(ruta_mp4: Path) -> dict:
    textos_frames: list[dict] = []
    texto_set: set[str] = set()
    ruta_frame = None

    try:
        cap        = cv2.VideoCapture(str(ruta_mp4))
        total      = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps        = cap.get(cv2.CAP_PROP_FPS) or 30
        posiciones = _tiempos_muestreo(total, FRAMES_POR_VIDEO)

        print(f"    [VIDEO] {total} frames → muestreo en {posiciones}")

        for pos in posiciones:
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ok, frame = cap.read()
            if not ok:
                continue

            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as ftmp:
                ruta_frame = ftmp.name
            cv2.imwrite(ruta_frame, frame)

            texto = _ocr_imagen(ruta_frame)
            seg   = round(pos / fps, 1)
            print(f"      frame {pos:>5} (~{seg}s): {texto[:60]}")

            if texto:
                textos_frames.append({"frame": pos, "seg": seg, "texto": texto})
                for linea in texto.split(" | "):
                    texto_set.add(linea.strip())

        cap.release()
    except Exception as e:
        print(f"    [ERROR] Procesando video: {e}")
    finally:
        if ruta_frame:
            Path(ruta_frame).unlink(missing_ok=True)

    texto_completo = " | ".join(t for t in texto_set if t)
    return {"tipo": "video", "frames": textos_frames, "texto_completo": texto_completo}


def procesar_slide(rutas_jpeg: list[Path]) -> dict:
    textos_imagenes: list[dict] = []
    texto_set: set[str] = set()

    print(f"    [SLIDE] {len(rutas_jpeg)} imágenes")

    for i, ruta in enumerate(rutas_jpeg):
        texto = _ocr_imagen(str(ruta))
        print(f"      imagen {i+1}/{len(rutas_jpeg)}: {texto[:60]}")
        if texto:
            textos_imagenes.append({"imagen": i, "texto": texto})
            for linea in texto.split(" | "):
                texto_set.add(linea.strip())

    texto_completo = " | ".join(t for t in texto_set if t)
    return {"tipo": "slide", "imagenes": textos_imagenes, "texto_completo": texto_completo}


# ─── Paso 1: Descarga con el scraper normal ────────────────────────────────────

def _detectar_browser() -> str | None:
    import browser_cookie3
    for nombre in ("firefox", "chrome", "edge"):
        try:
            cookies = getattr(browser_cookie3, nombre)(domain_name=".tiktok.com")
            if cookies:
                return nombre
        except Exception:
            continue
    return None


def descargar_ids(ids: list[str]) -> None:
    print("\n  [SCRAPER] Registrando IDs y descargando archivos...")

    browser = _detectar_browser()
    if browser:
        print(f"  [SCRAPER] Cookies desde {browser}")
    else:
        print("  [SCRAPER] WARN: sin cookies de navegador")

    scraper = TT_Content_Scraper(
        output_files_fp=str(DATA_DIR) + "/",
        progress_file_fn=str(DATA_DIR / "scraping_progress.db"),
        browser_name=browser,
        wait_time=SCRAPER_WAIT,
    )
    scraper.add_objects(ids, type="content")
    scraper.reset_errors_to_pending()  # reintentar los que fallaron antes

    try:
        scraper.scrape_pending(only_content=True, scrape_files=True)
    except AssertionError:
        pass  # No more pending — terminación normal del scraper
    finally:
        scraper.close()

    print("  [SCRAPER] Descarga completada\n")


# ─── Pipeline principal ────────────────────────────────────────────────────────

def main():
    if not NEW_IDS:
        print("NEW_IDS está vacío.")
        return

    print(SEP)
    print("  Descarga + OCR → MongoDB")
    print(SEP)

    # ── Fase 1: descargar ────────────────────────────────────────────────────
    descargar_ids(NEW_IDS)

    # ── Fase 2: OCR + MongoDB ────────────────────────────────────────────────
    print(SEP)
    print("  Aplicando OCR sobre archivos descargados")
    print(SEP + "\n")

    client              = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10_000)
    col_silver          = client[DB_SILVER][COL_VIDEOS]
    col_gold            = client[DB_GOLD][COL_VIDEOS]
    col_silver_usuarios = client[DB_SILVER][COL_USUARIOS]
    col_gold_usuarios   = client[DB_GOLD][COL_USUARIOS]

    meta_dir  = DATA_DIR / "content_metadata"
    files_dir = DATA_DIR / "content_files"

    total     = len(NEW_IDS)
    ok_count  = 0
    err_count = 0

    for i, video_id in enumerate(NEW_IDS, 1):
        print(f"\n[{i}/{total}] ID: {video_id}")

        # ── Metadata ──────────────────────────────────────────────────────────
        meta_path = meta_dir / f"{video_id}.json"
        if not meta_path.exists():
            print(f"  [SKIP] Sin metadata (el scraper falló para este ID)")
            err_count += 1
            continue

        with open(meta_path, encoding="utf-8") as f:
            sorted_meta = json.load(f)

        am       = sorted_meta.get("author_metadata", {})
        username = am.get("username", "tiktok")
        url_tt   = f"https://www.tiktok.com/@{username}/video/{video_id}"

        # ── Detectar tipo y aplicar OCR ───────────────────────────────────────
        mp4_path   = files_dir / f"tiktok_video_{video_id}.mp4"
        jpeg_paths = sorted(
            files_dir.glob(f"tiktok_picture_{video_id}_*.jpeg"),
            key=lambda p: int(p.stem.rsplit("_", 1)[-1]),
        )

        if mp4_path.exists():
            print(f"  @{username}  tipo=VIDEO")
            ocr_res = procesar_video(mp4_path)
        elif jpeg_paths:
            print(f"  @{username}  tipo=SLIDE ({len(jpeg_paths)} imágenes)")
            ocr_res = procesar_slide(jpeg_paths)
        else:
            print(f"  [SKIP] No hay archivo de video/slide descargado")
            err_count += 1
            continue

        texto_ocr = ocr_res.get("texto_completo", "")
        print(f"  Texto OCR: {texto_ocr[:100]}{'...' if len(texto_ocr) > 100 else ''}")

        # ── Upsert video ───────────────────────────────────────────────────────
        now = datetime.now(timezone.utc)
        doc_update = {
            **sorted_meta,
            "video_id":     str(video_id),
            "url":          url_tt,
            "fuente":       "ocr",
            "ocr": {
                "tipo":           ocr_res["tipo"],
                "texto_completo": texto_ocr,
                **({"frames":   ocr_res["frames"]}   if ocr_res["tipo"] == "video" else {}),
                **({"imagenes": ocr_res["imagenes"]} if ocr_res["tipo"] == "slide" else {}),
                "procesado_en": now,
            },
            "procesado_en": now,
        }
        filtro = {"video_id": str(video_id)}

        col_silver.update_one(filtro, {"$set": doc_update}, upsert=True)

        va_a_gold = len(texto_ocr) >= GOLD_MIN_TEXT_LEN
        if va_a_gold:
            col_gold.update_one(filtro, {"$set": doc_update}, upsert=True)

        # ── Upsert usuario ─────────────────────────────────────────────────────
        if am.get("id"):
            filtro_usuario = {"id": am["id"]}
            usuario_update = {
                "$set":      {**am, "ultima_actualizacion": now},
                "$addToSet": {"video_ids": str(video_id)},
            }
            col_silver_usuarios.update_one(filtro_usuario, usuario_update, upsert=True)
            if va_a_gold:
                col_gold_usuarios.update_one(filtro_usuario, usuario_update, upsert=True)

        destinos = "silver + gold" if va_a_gold else "silver"
        print(f"  Guardado en: {destinos} (video + usuario)")
        ok_count += 1

    print(f"\n{SEP}")
    print(f"  Procesados: {ok_count}/{total}  errores/skips: {err_count}")
    print(SEP + "\n")
    client.close()


if __name__ == "__main__":
    main()
