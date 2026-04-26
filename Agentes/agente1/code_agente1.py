"""
Agente 1 — ETL
Extrae datos de redes sociales y los carga a Bronze (centinela).
Expone orquestar_extraccion(objetivo) para ser invocado por el orquestador.
"""

import os
import sys
import subprocess
import datetime
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).parent.parent.parent
load_dotenv(ROOT / ".env")

MONGO_URI = os.getenv("MONGODB_URI")
client    = MongoClient(MONGO_URI)
kb_col    = client["centinela"]["knowledge_base"]

BRONCE_COLS = ["youtube_items", "telegram_messages", "telegram_channels",
               "tiktok_videos", "tiktok_usuarios"]

SCRIPTS = {
    "youtube":  str(ROOT / "Apis2BD_ETL" / "Main" / "ETL" / "ETL_youtube"  / "etl_youtube.py"),
    "telegram": str(ROOT / "Apis2BD_ETL" / "Main" / "ETL" / "ETL_telegram" / "etl_telegram.py"),
    "tiktok":   str(ROOT / "Apis2BD_ETL" / "Main" / "ETL" / "ETL_tiktok"   / "etl_tiktok.py"),
    "todos":    str(ROOT / "Apis2BD_ETL" / "main.py"),
}


def _contar_bronze() -> dict:
    db = client["centinela"]
    return {col: db[col].count_documents({}) for col in BRONCE_COLS}


def orquestar_extraccion(objetivo: str = "todos") -> dict:
    script = SCRIPTS.get(objetivo.lower())
    if not script:
        return {"reporte_de_descarga": "fallo crítico",
                "error": f"objetivo '{objetivo}' no reconocido"}

    fecha_inicio  = datetime.datetime.now()
    antes         = _contar_bronze()
    status        = False
    reporte       = "fallo crítico"
    error_msg     = ""

    print(f"\n  ── ETL · {objetivo.upper()} ── {fecha_inicio:%H:%M:%S}")

    try:
        proc = subprocess.run(
            [sys.executable, script],
            capture_output=True, text=True, check=True,
            cwd=str(ROOT)
        )
        status  = True
        reporte = "descarga exitosa"
        print(proc.stdout[-2000:] if len(proc.stdout) > 2000 else proc.stdout)
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr[-1000:]
        print(f"Error en ETL {objetivo}:\n{error_msg}")

    fecha_fin   = datetime.datetime.now()
    despues     = _contar_bronze()
    nuevos      = {col: despues[col] - antes[col] for col in BRONCE_COLS}
    total_nuevos = sum(nuevos.values())

    doc = {
        "agente":               "agente1_etl",
        "objetivo":             objetivo,
        "script_ejecutado":     script,
        "fecha_inicio":         fecha_inicio,
        "fecha_fin":            fecha_fin,
        "duracion_seg":         (fecha_fin - fecha_inicio).seconds,
        "status":               status,
        "reporte_de_descarga":  reporte,
        "registros_nuevos":     nuevos,
        "total_registros_nuevos": total_nuevos,
        "error":                error_msg,
    }
    kb_col.insert_one(doc)
    nuevos_str = "  ".join(f"{col}={v}" for col, v in nuevos.items() if v > 0) or "ninguno"
    print(f"  ETL {reporte}  ·  {total_nuevos} registros nuevos  [{nuevos_str}]\n")
    return doc


if __name__ == "__main__":
    objetivo = sys.argv[1] if len(sys.argv) > 1 else "todos"
    orquestar_extraccion(objetivo)
