"""
Orquestador Principal
Cerebro: gpt-4o-mini via OpenAI API
Decide de forma inteligente cuándo y qué ejecutar consultando el estado
del sistema (Bronze vs Silver, últimos runs, errores) y coordinando
Agente 1 (ETL) y Agente 2 (NLP → Silver).
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from openai import OpenAI

ROOT = Path(__file__).parent.parent.parent
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(ROOT / "Agentes" / "agente1"))
sys.path.insert(0, str(ROOT / "Agentes" / "agente2"))

from code_agente1  import orquestar_extraccion
from run_agente2   import run_classification

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_URI      = os.getenv("MONGODB_URI")
if not OPENAI_API_KEY or not MONGO_URI:
    sys.exit("ERROR: OPENAI_API_KEY o MONGODB_URI no definidos en .env")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
mongo_client  = MongoClient(MONGO_URI)
kb_col        = mongo_client["centinela"]["knowledge_base"]

BRONZE_COLS = {
    "youtube":  ["youtube_items"],
    "telegram": ["telegram_messages", "telegram_channels"],
    "tiktok":   ["tiktok_videos", "tiktok_usuarios"],
}
SILVER_COLS = {
    "youtube":  ["youtube_items"],
    "telegram": ["telegram_messages", "telegram_channels"],
    "tiktok":   ["tiktok_usuarios"],
}

SYSTEM_PROMPT = """Eres el Orquestador Principal del Pipeline de Inteligencia Centinela.

Tu misión es detectar reclutamiento criminal y contenido peligroso para niñas, niños y adolescentes (NNA) en redes sociales, coordinando dos agentes:
- Agente 1 (ETL): extrae datos crudos a Bronze (centinela en MongoDB)
- Agente 2 (NLP): clasifica registros Bronze con mDeBERTa y escribe sospechosos a Silver

Reglas estrictas:
1. SIEMPRE llama primero a revisar_estado_sistema antes de cualquier decisión.
2. Decide si correr Agente 1, Agente 2, ambos, o solo esperar, basándote en:
   - Horas desde el último ETL exitoso (si > 48h, considera correr Agente 1)
   - Registros en Bronze sin procesar a Silver (si hay muchos, corre Agente 2)
   - Errores recientes (si hubo fallo, ajusta la estrategia)
   - Tasa de datos nuevos (si hay poca actividad, espera más tiempo)
3. Puedes correr Agente 2 sin correr Agente 1 si ya hay datos pendientes en Bronze.
4. Si invocas Agente 1 y retorna total_registros_nuevos = 0 Y el estado del sistema muestra total_pendientes = 0, NO invoques Agente 2 — no hay nada que clasificar. Programa espera larga (24-48h). Si total_pendientes > 0, sí puedes correr Agente 2 aunque el ETL no trajo datos nuevos.
5. Al final SIEMPRE llama a escribir_reporte con tu decisión y el tiempo de espera.
6. NO EJECUTES CÓDIGO. Usa exclusivamente tus herramientas."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "revisar_estado_sistema",
            "description": (
                "Revisa el estado actual del sistema: registros en Bronze vs Silver "
                "por plataforma, últimos runs de cada agente, errores recientes y "
                "horas transcurridas desde la última extracción."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "invocar_agente1",
            "description": "Ejecuta el ETL para extraer datos de redes sociales a Bronze.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plataforma": {
                        "type": "string",
                        "enum": ["youtube", "telegram", "tiktok", "todos"],
                        "description": "Plataforma a extraer.",
                    }
                },
                "required": ["plataforma"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "invocar_agente2",
            "description": "Clasifica registros Bronze con NLP y escribe sospechosos a Silver.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plataforma": {
                        "type": "string",
                        "enum": ["youtube", "telegram", "tiktok", "todos"],
                        "description": "Plataforma a clasificar.",
                    }
                },
                "required": ["plataforma"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escribir_reporte",
            "description": "Guarda el reporte del ciclo en MongoDB y define cuántas horas esperar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "resumen": {
                        "type": "string",
                        "description": "Resumen del ciclo: qué se hizo y por qué.",
                    },
                    "acciones_tomadas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de acciones ejecutadas.",
                    },
                    "proxima_revision_horas": {
                        "type": "number",
                        "description": (
                            "Horas hasta la próxima revisión. "
                            "Usa 1-4 si hay mucha actividad, 12-24 si es normal, "
                            "48-72 si el sistema está al día y tranquilo."
                        ),
                    },
                },
                "required": ["resumen", "acciones_tomadas", "proxima_revision_horas"],
            },
        },
    },
]

_TOOL_LABEL = {
    "revisar_estado_sistema": lambda a: "Consultando estado del sistema",
    "invocar_agente1":        lambda a: f"Lanzando ETL  ·  {a.get('plataforma','?').upper()}",
    "invocar_agente2":        lambda a: f"Lanzando NLP  ·  {a.get('plataforma','?').upper()}",
    "escribir_reporte":       lambda a: f"Guardando reporte  ·  próxima revisión en {a.get('proxima_revision_horas','?')}h",
}


def _revisar_estado_sistema() -> dict:
    db_bronze = mongo_client["centinela"]
    db_silver = mongo_client["silver"]

    bronze_stats = {}
    silver_stats = {}
    pendientes   = {}

    for plataforma, cols in BRONZE_COLS.items():
        for col in cols:
            n_bronze = db_bronze[col].count_documents({})
            n_silver = db_silver[col].count_documents({}) if col in SILVER_COLS.get(plataforma, []) else None
            bronze_stats[col] = n_bronze
            if n_silver is not None:
                silver_stats[col] = n_silver
                pendientes[col]   = max(0, n_bronze - n_silver)

    ultimo_etl = kb_col.find_one(
        {"agente": "agente1_etl", "status": True},
        sort=[("fecha_inicio", -1)]
    )
    ultimo_nlp = kb_col.find_one(
        {"agente": "agente2_nlp", "status": "completado"},
        sort=[("procesado_en", -1)]
    )
    ultimo_error = kb_col.find_one(
        {"agente": "agente1_etl", "status": False},
        sort=[("fecha_inicio", -1)]
    )

    ahora = datetime.now(timezone.utc)

    def _horas(doc, campo):
        if not doc or campo not in doc:
            return None
        ts = doc[campo]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return round((ahora - ts).total_seconds() / 3600, 1)

    return {
        "bronze":                  bronze_stats,
        "silver":                  silver_stats,
        "pendientes_por_procesar": pendientes,
        "total_pendientes":        sum(pendientes.values()),
        "horas_desde_ultimo_etl":  _horas(ultimo_etl, "fecha_inicio"),
        "horas_desde_ultimo_nlp":  _horas(ultimo_nlp, "procesado_en"),
        "ultimo_etl_plataforma":   ultimo_etl.get("objetivo") if ultimo_etl else None,
        "ultimo_etl_nuevos":       ultimo_etl.get("total_registros_nuevos") if ultimo_etl else None,
        "error_reciente":          bool(ultimo_error and _horas(ultimo_error, "fecha_inicio") < 6),
    }


def _ejecutar_tool(nombre: str, args: dict) -> str:
    if nombre == "revisar_estado_sistema":
        resultado = _revisar_estado_sistema()

    elif nombre == "invocar_agente1":
        resultado = orquestar_extraccion(args["plataforma"])
        resultado.pop("_id", None)
        resultado["fecha_inicio"] = str(resultado.get("fecha_inicio", ""))
        resultado["fecha_fin"]    = str(resultado.get("fecha_fin", ""))

    elif nombre == "invocar_agente2":
        resultado = run_classification(args["plataforma"])

    elif nombre == "escribir_reporte":
        doc = {
            "agente":              "orquestador",
            "resumen":             args["resumen"],
            "acciones_tomadas":    args["acciones_tomadas"],
            "proxima_revision_h":  args["proxima_revision_horas"],
            "procesado_en":        datetime.now(timezone.utc),
        }
        kb_col.insert_one(doc)
        resultado = {"guardado": True, "proxima_revision_horas": args["proxima_revision_horas"]}

    else:
        resultado = {"error": f"tool '{nombre}' no reconocida"}

    return json.dumps(resultado, ensure_ascii=False, default=str)


def _ciclo_orquestador() -> float:
    """Ejecuta un ciclo completo de razonamiento. Retorna horas hasta el próximo ciclo."""
    print(f"\n{'═'*55}")
    print(f"  ORQUESTADOR  ·  {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"{'═'*55}")

    messages = [
        {"role": "user", "content": "Revisa el estado del sistema y decide qué hacer ahora."}
    ]
    proxima_revision = 24.0

    while True:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        messages.append(msg)

        if response.choices[0].finish_reason == "stop":
            if msg.content:
                print(f"\n  Decisión GPT:\n  {msg.content}")
            break

        if not msg.tool_calls:
            break

        tool_results = []
        for call in msg.tool_calls:
            nombre = call.function.name
            args   = json.loads(call.function.arguments)
            label = _TOOL_LABEL.get(nombre, lambda a: nombre)(args)
            print(f"\n  ▸ {label}")
            resultado = _ejecutar_tool(nombre, args)

            if nombre == "escribir_reporte":
                data = json.loads(resultado)
                proxima_revision = data.get("proxima_revision_horas", 24.0)

            tool_results.append({
                "role":         "tool",
                "tool_call_id": call.id,
                "content":      resultado,
            })

        messages.extend(tool_results)

    return proxima_revision


def iniciar_orquestador():
    print("Orquestador iniciado. Ctrl+C para detener.\n")
    while True:
        try:
            horas_espera = _ciclo_orquestador()
        except Exception as e:
            print(f"\nError en ciclo del orquestador: {e}")
            horas_espera = 1.0

        segundos = horas_espera * 3600
        siguiente = datetime.fromtimestamp(time.time() + segundos)
        print(f"\n{'─'*55}")
        print(f"  Próxima revisión en {horas_espera:.0f}h  ·  ~{siguiente:%Y-%m-%d %H:%M:%S}")
        print(f"{'─'*55}\n")
        time.sleep(segundos)


if __name__ == "__main__":
    iniciar_orquestador()
