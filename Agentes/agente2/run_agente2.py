"""
Agente 2 — Wrapper principal
Expone run_classification(plataforma) para ser invocado por el orquestador.
Carga el modelo NLP una sola vez y lo comparte entre los 5 sub-agentes,
que se ejecutan en paralelo con ThreadPoolExecutor para solapar I/O de
MongoDB y preprocesamiento CPU mientras la GPU atiende los lotes.
"""

import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import torch
import os
os.environ["USE_TF"] = "0"
from transformers import pipeline

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(Path(__file__).parent / "agente2_youtube"))
sys.path.insert(0, str(Path(__file__).parent / "agente2_telegram_channels"))
sys.path.insert(0, str(Path(__file__).parent / "agente2_telegram_messages"))
sys.path.insert(0, str(Path(__file__).parent / "agente2_tiktok_users"))
sys.path.insert(0, str(Path(__file__).parent / "agente2_tiktok_videos"))

from code_agente2_youtube            import ejecutar_filtro_youtube
from code_agente2_telegram_channels  import ejecutar_filtro_telegram_channels
from code_agente2_telegram_messages  import ejecutar_filtro_telegram_messages
from code_agente2_tiktok_users       import ejecutar_filtro_tiktok_users
from code_agente2_tiktok_videos      import ejecutar_filtro_tiktok_videos


class _SafeCLF:
    """Wrapper thread-safe sobre HuggingFace pipeline de zero-shot classification.
    Un único modelo en GPU compartido entre threads; el Lock serializa la inferencia
    mientras el I/O de MongoDB y el preprocesamiento CPU corren en paralelo."""
    def __init__(self, *args, **kwargs):
        self._clf  = pipeline(*args, **kwargs)
        self._lock = threading.Lock()

    def __call__(self, *args, **kwargs):
        with self._lock:
            return self._clf(*args, **kwargs)


MAPA = {
    "youtube":  [ejecutar_filtro_youtube],
    "telegram": [ejecutar_filtro_telegram_channels, ejecutar_filtro_telegram_messages],
    "tiktok":   [ejecutar_filtro_tiktok_users, ejecutar_filtro_tiktok_videos],
    "todos":    [ejecutar_filtro_youtube,
                 ejecutar_filtro_telegram_channels,
                 ejecutar_filtro_telegram_messages,
                 ejecutar_filtro_tiktok_users,
                 ejecutar_filtro_tiktok_videos]}


def run_classification(plataforma: str = "todos") -> dict:
    funciones = MAPA.get(plataforma.lower())
    if not funciones:
        return {"status": "error", "error": f"plataforma '{plataforma}' no reconocida"}

    print(f"\n  ── NLP · {plataforma.upper()} ────────────────────────────────────")

    device = 0 if torch.cuda.is_available() else -1
    print(f"  Cargando modelo NLP compartido  ·  device={'cuda:0' if device == 0 else 'cpu'}")
    clf = _SafeCLF("zero-shot-classification",
                   model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
                   device=device)

    resultados = []
    total_sosp = 0
    total_docs = 0
    errores    = []

    with ThreadPoolExecutor(max_workers=len(funciones)) as pool:
        futuros = {pool.submit(fn, clf): fn for fn in funciones}
        for futuro in as_completed(futuros):
            fn = futuros[futuro]
            try:
                rep = futuro.result()
                resultados.append(rep)
                total_sosp += rep.get("sospechosos", 0)
                total_docs += rep.get("total", 0)
            except Exception as e:
                errores.append(f"{fn.__name__}: {e}")
                print(f"  Error en {fn.__name__}: {e}")

    reporte = {
        "agente":                "agente2_nlp",
        "plataforma":            plataforma,
        "sub_agentes":           resultados,
        "total_docs_analizados": total_docs,
        "total_sospechosos":     total_sosp,
        "tasa_sospecha":         round(total_sosp / total_docs, 4) if total_docs else 0,
        "errores":               errores,
        "status":                "completado" if not errores else "completado_con_errores"}

    tasa = f"{reporte['tasa_sospecha']:.1%}" if total_docs else "—"
    print(f"\n  NLP finalizado  ·  {total_sosp}/{total_docs} sospechosos → Silver  ·  tasa={tasa}\n")
    return reporte


if __name__ == "__main__":
    plataforma = sys.argv[1] if len(sys.argv) > 1 else "todos"
    run_classification(plataforma)
