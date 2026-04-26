"""
Agente 2 — Telegram Messages  (Bronze → Silver)
centinela.telegram_messages → silver.telegram_messages

Clasifica el texto de cada mensaje en lotes de BATCH_SIZE.
Pasa a Silver si top_label != Seguro y score >= UMBRAL.
Silver doc = copia completa del Bronze + campos NLP de enriquecimiento.
Incremental: omite _id que ya existen en Silver.
"""

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import torch
os.environ["USE_TF"] = "0"
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from transformers import pipeline

ROOT = Path(__file__).parent.parent.parent.parent
load_dotenv(ROOT / ".env")

MONGO_URI = os.getenv("MONGODB_URI")
if not MONGO_URI:
    sys.exit("ERROR: MONGODB_URI no definida en .env")

client     = MongoClient(MONGO_URI)
bronze_col = client["centinela"]["telegram_messages"]
silver_col = client["silver"]["telegram_messages"]

ETIQUETAS       = ["Reclutamiento", "Oferta de Riesgo", "Narcocultura",
                   "Contenido Inapropiado para Menores", "Seguro"]
TEMPLATE        = "Este mensaje de Telegram es sobre {}."
UMBRAL          = 0.43
BATCH_SIZE      = 32
MAX_TEXTO_CHARS = 500
MIN_TEXTO_CHARS = 10
WRITE_BATCH     = 200

_RE_TELEFONO = re.compile(r"\+?\d[\d\s\-]{8,}\d")
_RE_URL      = re.compile(r"https?://|www\.|t\.me/|\.com|\.mx|\.io", re.I)
_RE_INVITE   = re.compile(r"t\.me/\+|t\.me/joinchat", re.I)



def _nivel(score: float) -> str:
    if score >= 0.65: return "alto"
    return "medio"


def _signals(texto: str) -> dict:
    return {
        "contiene_url":        bool(_RE_URL.search(texto)),
        "contiene_telefono":   bool(_RE_TELEFONO.search(texto)),
        "contiene_invitacion": bool(_RE_INVITE.search(texto)),
        "longitud_mensaje":    len(texto),
    }


def _clasificar_lote(clf, textos: list[str]) -> list[dict]:
    res = clf(textos, candidate_labels=ETIQUETAS, hypothesis_template=TEMPLATE)
    return res if isinstance(res, list) else [res]


def _parsear_resultado(res: dict) -> tuple[str, float, dict]:
    top_label = res["labels"][0]
    top_score = round(res["scores"][0], 4)
    scores    = {lbl: round(sc, 4) for lbl, sc in zip(res["labels"], res["scores"])}
    return top_label, top_score, scores


def _es_sospechoso(top_label: str, top_score: float) -> bool:
    return top_label != "Seguro" and top_score >= UMBRAL


def _build_op(doc: dict, texto: str, top_label: str,
              top_score: float, scores: dict) -> UpdateOne:
    silver = {k: v for k, v in doc.items() if k != "_id"}
    silver.update({
        "_id_bronce":          doc["_id"],
        "scores_zero_shot":    scores,
        "categoria_principal": top_label,
        "nivel_riesgo":        _nivel(top_score),
        "riesgo_score":        top_score,
        "texto_analizado":     texto,
        **_signals(texto),
        "fuente":              "telegram",
        "coleccion_origen":    "centinela.telegram_messages",
        "procesado_en":        datetime.now(timezone.utc),
    })
    return UpdateOne({"_id": doc["_id"]}, {"$set": silver}, upsert=True)


def _flush(ops: list) -> None:
    if ops:
        silver_col.bulk_write(ops, ordered=False)
        ops.clear()



def ejecutar_filtro_telegram_messages(clf=None):
    if clf is None:
        device = 0 if torch.cuda.is_available() else -1
        print(f"\n  Telegram Messages  ·  cargando modelo NLP  ·  device={'cuda:0' if device == 0 else 'cpu'}")
        clf = pipeline("zero-shot-classification",
                       model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
                       device=device)

    ya_en_silver = set(silver_col.distinct("_id"))
    filtro       = {"text": {"$exists": True, "$nin": ["", None]}}
    total        = max(0, bronze_col.count_documents(filtro) - len(ya_en_silver))
    print(f"  Telegram Messages  ·  {total} pendientes  ·  {len(ya_en_silver)} ya en Silver\n")

    if total == 0:
        print("  Telegram Messages  ·  sin registros nuevos")
        return {"agente": "agente2_telegram_messages", "sospechosos": 0, "total": 0}

    ops         = []
    sospechosos = 0
    buf_docs    = []
    buf_textos  = []

    def _procesar_buffer():
        nonlocal sospechosos
        resultados = _clasificar_lote(clf, buf_textos)
        for doc, texto, res in zip(buf_docs, buf_textos, resultados):
            top_label, top_score, scores = _parsear_resultado(res)
            if not _es_sospechoso(top_label, top_score):
                continue
            ops.append(_build_op(doc, texto, top_label, top_score, scores))
            sospechosos += 1
            msg_id = str(doc.get("message_id", doc["_id"]))[:22]
            print(f"  {msg_id:<22}  {top_label:<33}  {_nivel(top_score):<6}  {top_score:.4f}")

    for doc in bronze_col.find(filtro):
        if doc["_id"] in ya_en_silver:
            continue
        texto = str(doc.get("text", "")).strip()[:MAX_TEXTO_CHARS]
        if len(texto) < MIN_TEXTO_CHARS:
            continue

        buf_docs.append(doc)
        buf_textos.append(texto)

        if len(buf_docs) == BATCH_SIZE:
            try:
                _procesar_buffer()
            except Exception as e:
                print(f"  ⚠️  Error en lote: {e}")
            finally:
                buf_docs.clear()
                buf_textos.clear()

            if len(ops) >= WRITE_BATCH:
                _flush(ops)

    # Lote restante
    if buf_docs:
        try:
            _procesar_buffer()
        except Exception as e:
            print(f"  ⚠️  Error en lote final: {e}")
        finally:
            buf_docs.clear()
            buf_textos.clear()

    _flush(ops)

    tasa = f"{sospechosos/total:.1%}" if total else "—"
    print(f"\n  Telegram Messages  ·  {sospechosos}/{total} sospechosos  ·  tasa={tasa}")
    return {"agente": "agente2_telegram_messages", "sospechosos": sospechosos, "total": total}


if __name__ == "__main__":
    ejecutar_filtro_telegram_messages()
