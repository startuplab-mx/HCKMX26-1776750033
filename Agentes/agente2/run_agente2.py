"""
Agente 2 — Wrapper principal
Expone run_classification(plataforma) para ser invocado por el orquestador.
Coordina los 4 sub-agentes NLP según la plataforma solicitada.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(Path(__file__).parent / "agente2_youtube"))
sys.path.insert(0, str(Path(__file__).parent / "agente2_telegram_channels"))
sys.path.insert(0, str(Path(__file__).parent / "agente2_telegram_messages"))
sys.path.insert(0, str(Path(__file__).parent / "agente2_tiktok_users"))

from code_agente2_youtube            import ejecutar_filtro_youtube
from code_agente2_telegram_channels  import ejecutar_filtro_telegram_channels
from code_agente2_telegram_messages  import ejecutar_filtro_telegram_messages
from code_agente2_tiktok_users       import ejecutar_filtro_tiktok_users

MAPA = {
    "youtube":  [ejecutar_filtro_youtube],
    "telegram": [ejecutar_filtro_telegram_channels, ejecutar_filtro_telegram_messages],
    "tiktok":   [ejecutar_filtro_tiktok_users],
    "todos":    [ejecutar_filtro_youtube,
                 ejecutar_filtro_telegram_channels,
                 ejecutar_filtro_telegram_messages,
                 ejecutar_filtro_tiktok_users],
}


def run_classification(plataforma: str = "todos") -> dict:
    funciones = MAPA.get(plataforma.lower())
    if not funciones:
        return {"status": "error", "error": f"plataforma '{plataforma}' no reconocida"}

    print(f"\n  ── NLP · {plataforma.upper()} ────────────────────────────────────")

    resultados   = []
    total_sosp   = 0
    total_docs   = 0
    errores      = []

    for fn in funciones:
        try:
            rep = fn()
            resultados.append(rep)
            total_sosp += rep.get("sospechosos", 0)
            total_docs += rep.get("total", 0)
        except Exception as e:
            errores.append(f"{fn.__name__}: {e}")
            print(f"  Error en {fn.__name__}: {e}")

    reporte = {
        "agente":              "agente2_nlp",
        "plataforma":          plataforma,
        "sub_agentes":         resultados,
        "total_docs_analizados": total_docs,
        "total_sospechosos":   total_sosp,
        "tasa_sospecha":       round(total_sosp / total_docs, 4) if total_docs else 0,
        "errores":             errores,
        "status":              "completado" if not errores else "completado_con_errores",
    }

    tasa = f"{reporte['tasa_sospecha']:.1%}" if total_docs else "—"
    print(f"\n  NLP finalizado  ·  {total_sosp}/{total_docs} sospechosos → Silver  ·  tasa={tasa}\n")
    return reporte


if __name__ == "__main__":
    plataforma = sys.argv[1] if len(sys.argv) > 1 else "todos"
    run_classification(plataforma)
