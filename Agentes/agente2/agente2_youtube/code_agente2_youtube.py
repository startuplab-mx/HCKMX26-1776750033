"""
Agente 2 — YouTube  (Bronze → Silver)
centinela.youtube_items → silver.youtube_items

Por cada video: clasifica sus comentarios en lotes de BATCH_SIZE.
Pasa a Silver si >= 1 comentario es sospechoso (top_label != Seguro y score >= UMBRAL).
Silver doc = copia completa del Bronze + campos NLP de enriquecimiento.
Incremental: omite _id que ya existen en Silver.
"""

import os
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
bronze_col = client["centinela"]["youtube_items"]
silver_col = client["silver"]["youtube_items"]

ETIQUETAS       = ["Reclutamiento", "Oferta de Riesgo", "Narcocultura",
                   "Contenido Inapropiado para Menores", "Seguro"]
TEMPLATE        = "Este comentario de YouTube es sobre {}."
UMBRAL          = 0.49
BATCH_SIZE      = 32
MAX_COMMENTS    = 50
MAX_TEXTO_CHARS = 500
MIN_TEXTO_CHARS = 10
WRITE_BATCH     = 100



def _nivel(score: float) -> str:
    if score >= 0.65: return "alto"
    return "medio"


def _texto_comentario(comment) -> str:
    raw = comment.get("text", "") if isinstance(comment, dict) else str(comment)
    return raw.strip()[:MAX_TEXTO_CHARS]


def _clasificar_lote(clf, textos: list[str]) -> list[dict]:
    """Llama al modelo sobre un lote. Siempre retorna lista."""
    res = clf(textos, candidate_labels=ETIQUETAS, hypothesis_template=TEMPLATE)
    return res if isinstance(res, list) else [res]


def _parsear_resultado(res: dict) -> tuple[str, float, dict]:
    top_label = res["labels"][0]
    top_score = round(res["scores"][0], 4)
    scores    = {lbl: round(sc, 4) for lbl, sc in zip(res["labels"], res["scores"])}
    return top_label, top_score, scores


def _es_sospechoso(top_label: str, top_score: float) -> bool:
    return top_label != "Seguro" and top_score >= UMBRAL


def _build_silver_doc(doc: dict, comentarios_analizados: list,
                      comentarios_sospechosos: list) -> dict:
    max_score     = max(c["top_score"] for c in comentarios_sospechosos)
    cat_principal = max(comentarios_sospechosos, key=lambda c: c["top_score"])["top_label"]
    silver        = {k: v for k, v in doc.items() if k != "_id"}
    silver.update({
        "_id_bronce":                 doc["_id"],
        "categoria_principal":        cat_principal,
        "nivel_riesgo":               _nivel(max_score),
        "riesgo_score":               round(max_score, 4),
        "comentarios_analizados_nlp": comentarios_analizados,
        "comentarios_sospechosos":    comentarios_sospechosos,
        "n_comentarios_muestra":      len(comentarios_analizados),
        "n_comentarios_sospechosos":  len(comentarios_sospechosos),
        "pct_sospechosos":            round(len(comentarios_sospechosos) / len(comentarios_analizados), 4),
        "fuente":                     "youtube",
        "coleccion_origen":           "centinela.youtube_items",
        "procesado_en":               datetime.now(timezone.utc),
    })
    return silver


def _flush(ops: list) -> None:
    if ops:
        silver_col.bulk_write(ops, ordered=False)
        ops.clear()



def _analizar_video(clf, doc: dict) -> tuple | None:
    """
    Clasifica los comentarios de un video en lotes de BATCH_SIZE.
    Retorna (UpdateOne, categoria, nivel, score, n_sosp, n_total) o None.
    """
    comentarios_raw = doc.get("comments", [])[:MAX_COMMENTS]
    textos_validos  = [t for c in comentarios_raw
                       if len(t := _texto_comentario(c)) >= MIN_TEXTO_CHARS]
    if not textos_validos:
        return None

    comentarios_analizados  = []
    comentarios_sospechosos = []

    for i in range(0, len(textos_validos), BATCH_SIZE):
        lote = textos_validos[i : i + BATCH_SIZE]
        try:
            resultados = _clasificar_lote(clf, lote)
        except Exception as e:
            print(f"    [!] Error NLP en lote {i//BATCH_SIZE + 1}: {e}")
            continue

        for texto, res in zip(lote, resultados):
            top_label, top_score, scores = _parsear_resultado(res)
            entrada = {"texto": texto, "scores": scores,
                       "top_label": top_label, "top_score": top_score}
            comentarios_analizados.append(entrada)
            if _es_sospechoso(top_label, top_score):
                comentarios_sospechosos.append(entrada)

    if not comentarios_sospechosos:
        return None

    max_score     = max(c["top_score"] for c in comentarios_sospechosos)
    cat_principal = max(comentarios_sospechosos, key=lambda c: c["top_score"])["top_label"]
    silver_doc    = _build_silver_doc(doc, comentarios_analizados, comentarios_sospechosos)
    op            = UpdateOne({"_id": doc["_id"]}, {"$set": silver_doc}, upsert=True)
    return op, cat_principal, _nivel(max_score), max_score, len(comentarios_sospechosos), len(comentarios_analizados)


def ejecutar_filtro_youtube(clf=None):
    if clf is None:
        device = 0 if torch.cuda.is_available() else -1
        print(f"\n  YouTube  ·  cargando modelo NLP  ·  device={'cuda:0' if device == 0 else 'cpu'}")
        clf = pipeline("zero-shot-classification",
                       model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
                       device=device)

    ya_en_silver = set(silver_col.distinct("_id"))
    filtro = {"comments.0": {"$exists": True},
              "_id":         {"$nin": list(ya_en_silver)}}
    total = bronze_col.count_documents(filtro)
    print(f"  YouTube  ·  {total} videos pendientes  ·  {len(ya_en_silver)} ya en Silver\n")

    if total == 0:
        print("  YouTube  ·  sin registros nuevos")
        return {"agente": "agente2_youtube", "sospechosos": 0, "total": 0}

    ops         = []
    sospechosos = 0

    for i, doc in enumerate(bronze_col.find(filtro), 1):
        try:
            result = _analizar_video(clf, doc)
        except Exception as e:
            print(f"  [!] Error en video {doc.get('_id')}: {e}")
            continue

        if result:
            op, cat, nivel, score, n_sosp, n_total = result
            ops.append(op)
            sospechosos += 1
            vid = str(doc.get("video_id", doc["_id"]))[:22]
            print(f"  [{i:>4}/{total}]  {vid:<22}  {cat:<33}  {nivel:<6}  {score:.4f}"
                  f"  ({n_sosp}/{n_total} cmts)")

        if len(ops) >= WRITE_BATCH:
            _flush(ops)

    _flush(ops)

    tasa = f"{sospechosos/total:.1%}" if total else "—"
    print(f"\n  YouTube  ·  {sospechosos}/{total} sospechosos  ·  tasa={tasa}")
    return {"agente": "agente2_youtube", "sospechosos": sospechosos, "total": total}


if __name__ == "__main__":
    ejecutar_filtro_youtube()
