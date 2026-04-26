#!/usr/bin/env python3
"""
Exporta tiktok_usuarios_ORC (silver y gold) a CSV y JSON en esta carpeta.

  python reportes/export_ocr_usuarios.py [--db silver|gold|ambas]

Por defecto exporta ambas bases.
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

MONGO_URI   = os.getenv("MONGODB_URI")
COL_NAME    = "tiktok_usuarios_ORC"
REPORTES    = Path(__file__).parent

CAMPOS_CSV = [
    "db",
    "id",
    "username",
    "name",
    "signature",
    "create_time",
    "verified",
    "private_account",
    "video_ids_count",
    "video_ids",
    "ultima_actualizacion",
]


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def fetch_usuarios(client: MongoClient, db_name: str) -> list[dict]:
    col  = client[db_name][COL_NAME]
    docs = list(col.find({}, {"_id": 0}))
    for d in docs:
        d["db"] = db_name
    return docs


def doc_to_row(doc: dict) -> dict:
    video_ids = doc.get("video_ids", [])
    return {
        "db":                   doc.get("db", ""),
        "id":                   doc.get("id", ""),
        "username":             doc.get("username", ""),
        "name":                 doc.get("name", ""),
        "signature":            doc.get("signature", ""),
        "create_time":          doc.get("create_time", ""),
        "verified":             doc.get("verified", ""),
        "private_account":      doc.get("private_account", ""),
        "video_ids_count":      len(video_ids),
        "video_ids":            "|".join(str(v) for v in video_ids),
        "ultima_actualizacion": str(doc.get("ultima_actualizacion", "")),
    }


def export(dbs: list[str]) -> None:
    if not MONGO_URI:
        sys.exit("[ERROR] MONGODB_URI no configurada en .env")

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10_000)
    ts     = _ts()

    for db_name in dbs:
        docs = fetch_usuarios(client, db_name)
        print(f"[{db_name}] {len(docs)} usuarios encontrados")

        if not docs:
            print(f"  (sin datos)\n")
            continue

        # ── JSON ─────────────────────────────────────────────────────────────
        json_path = REPORTES / f"usuarios_ocr_{db_name}_{ts}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2, default=str)
        print(f"  JSON → {json_path.name}")

        # ── CSV ──────────────────────────────────────────────────────────────
        csv_path = REPORTES / f"usuarios_ocr_{db_name}_{ts}.csv"
        rows     = [doc_to_row(d) for d in docs]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CAMPOS_CSV)
            writer.writeheader()
            writer.writerows(rows)
        print(f"  CSV  → {csv_path.name}\n")

    client.close()
    print("Exportación completada.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", choices=["silver", "gold", "ambas"], default="ambas")
    args = parser.parse_args()

    dbs = ["silver", "golden"] if args.db == "ambas" else \
          ["golden"] if args.db == "gold" else ["silver"]

    export(dbs)


if __name__ == "__main__":
    main()
