"""
Orquestador Principal
Cerebro: gpt-4o-mini via OpenAI API
Decide de forma inteligente cuándo y qué ejecutar consultando el estado
del sistema (Bronze vs Silver, últimos runs, errores) y coordinando
Agente 1 (ETL) y Agente 2 (NLP → Silver).
Incluye GUI con ventana de log y chat para comunicación humano-agente.
"""

import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import scrolledtext

from dotenv import load_dotenv
from pymongo import MongoClient
from openai import OpenAI

ROOT = Path(__file__).parent.parent.parent
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(ROOT / "Agentes" / "agente1"))
sys.path.insert(0, str(ROOT / "Agentes" / "agente2"))

from code_agente1 import orquestar_extraccion
from run_agente2  import run_classification

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
    "tiktok":   ["tiktok_videos", "tiktok_usuarios"]}
SILVER_COLS = {
    "youtube":  ["youtube_items"],
    "telegram": ["telegram_messages", "telegram_channels"],
    "tiktok":   ["tiktok_usuarios", "tiktok_videos"]}

SYSTEM_PROMPT = """Eres el Orquestador Principal del Pipeline de Inteligencia Centinela.

Tu misión es detectar reclutamiento criminal y contenido peligroso para niñas, niños y adolescentes (NNA) en redes sociales, coordinando dos agentes:
- Agente 1 (ETL): extrae datos crudos a Bronze (centinela en MongoDB)
- Agente 2 (NLP): clasifica registros Bronze con mDeBERTa y escribe sospechosos a Silver

Reglas estrictas:
1. SIEMPRE llama primero a revisar_estado_sistema antes de cualquier decisión.
2. Decide si correr Agente 1, Agente 2, ambos, o solo esperar, basándote en:
   - Horas desde el último ETL exitoso (si > 48h, considera correr Agente 1)
   - Registros pendientes por plataforma en Bronze sin procesar a Silver
   - Errores recientes (si hubo fallo, ajusta la estrategia)
   - Nuevos registros en la última hora (si hay actividad reciente, corre Agente 2)
3. Puedes correr Agente 2 sin correr Agente 1 si ya hay datos pendientes en Bronze.
4. Si invocas Agente 1 y retorna total_registros_nuevos = 0 Y el estado del sistema muestra total_pendientes = 0, NO invoques Agente 2. Programa espera larga (24-48h). Si total_pendientes > 0, sí puedes correr Agente 2 aunque el ETL no trajo datos nuevos.
5. Al final SIEMPRE llama a escribir_reporte con tu decisión y el tiempo de espera.
6. NO EJECUTES CÓDIGO. Usa exclusivamente tus herramientas.
7. TikTok ETL DESHABILITADO: NO invoques Agente 1 con plataforma='tiktok'. El scraper de TikTok tiene problemas técnicos temporales. Para NLP de TikTok (Agente 2), sí puedes usarlo si hay pendientes en Bronze.
8. MENSAJES DEL OPERADOR: Si recibes mensajes del operador humano al inicio del ciclo, úsalos como instrucción directa con máxima prioridad:
   - "cargué datos al bronze" / "actualicé bronze" → ejecuta revisar_estado_sistema y corre Agente 2 si hay pendientes
   - "busca más" / "extrae más" → corre Agente 1 en youtube o telegram (el que lleve más tiempo sin actualizarse)
   - "corre youtube" / "corre telegram" → ejecuta los agentes correspondientes
   - Cualquier otra instrucción: interprétala y ejecútala con tus herramientas"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "revisar_estado_sistema",
            "description": (
                "Revisa el estado actual del sistema: registros en Bronze vs Silver "
                "por plataforma (con detalle de pendientes y nuevos en la última hora), "
                "últimos runs de cada agente, errores recientes y horas transcurridas "
                "desde la última extracción."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []}}},
    {
        "type": "function",
        "function": {
            "name": "invocar_agente1",
            "description": (
                "Ejecuta el ETL para extraer datos de redes sociales a Bronze. "
                "IMPORTANTE: plataforma='tiktok' está DESHABILITADA por problemas técnicos. "
                "Usa solo 'youtube', 'telegram' o 'todos' (todos excluye TikTok internamente)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "plataforma": {
                        "type": "string",
                        "enum": ["youtube", "telegram", "todos"],
                        "description": "Plataforma a extraer. TikTok deshabilitado."}},
                "required": ["plataforma"]}}},
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
                        "description": "Plataforma a clasificar."}},
                "required": ["plataforma"]}}},
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
                        "description": "Resumen del ciclo: qué se hizo y por qué."},
                    "acciones_tomadas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de acciones ejecutadas."},
                    "proxima_revision_horas": {
                        "type": "number",
                        "description": (
                            "Horas hasta la próxima revisión. "
                            "Usa 1-4 si hay mucha actividad, 12-24 si es normal, "
                            "48-72 si el sistema está al día y tranquilo.")}},
                "required": ["resumen", "acciones_tomadas", "proxima_revision_horas"]}}}]

_TOOL_LABEL = {
    "revisar_estado_sistema": lambda a: "Consultando estado del sistema",
    "invocar_agente1":        lambda a: f"Lanzando ETL  ·  {a.get('plataforma','?').upper()}",
    "invocar_agente2":        lambda a: f"Lanzando NLP  ·  {a.get('plataforma','?').upper()}",
    "escribir_reporte":       lambda a: f"Guardando reporte  ·  próxima revisión en {a.get('proxima_revision_horas','?')}h"}


def _nuevos_1h(col, campo: str) -> int:
    try:
        hace_1h = datetime.now(timezone.utc) - timedelta(hours=1)
        return col.count_documents({campo: {"$gte": hace_1h}})
    except Exception:
        return 0


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

    detalle_plataforma = {
        "youtube": {
            "bronze":     bronze_stats.get("youtube_items", 0),
            "silver":     silver_stats.get("youtube_items", 0),
            "pendientes": pendientes.get("youtube_items", 0),
            "nuevos_1h":  _nuevos_1h(db_bronze["youtube_items"], "collected_at")},
        "telegram": {
            "bronze":     bronze_stats.get("telegram_messages", 0) + bronze_stats.get("telegram_channels", 0),
            "silver":     silver_stats.get("telegram_messages", 0) + silver_stats.get("telegram_channels", 0),
            "pendientes": pendientes.get("telegram_messages", 0) + pendientes.get("telegram_channels", 0),
            "nuevos_1h":  (_nuevos_1h(db_bronze["telegram_messages"], "collected_at") +
                           _nuevos_1h(db_bronze["telegram_channels"], "first_seen"))},
        "tiktok": {
            "bronze":     bronze_stats.get("tiktok_usuarios", 0) + bronze_stats.get("tiktok_videos", 0),
            "silver":     silver_stats.get("tiktok_usuarios", 0) + silver_stats.get("tiktok_videos", 0),
            "pendientes": pendientes.get("tiktok_usuarios", 0) + pendientes.get("tiktok_videos", 0),
            "nuevos_1h":  0}}

    ultimo_etl = kb_col.find_one(
        {"agente": "agente1_etl", "status": True},
        sort=[("fecha_inicio", -1)])
    ultimo_nlp = kb_col.find_one(
        {"agente": "agente2_nlp", "status": "completado"},
        sort=[("procesado_en", -1)])
    ultimo_error = kb_col.find_one(
        {"agente": "agente1_etl", "status": False},
        sort=[("fecha_inicio", -1)])

    ahora = datetime.now(timezone.utc)

    def _horas(doc, campo):
        if not doc or campo not in doc:
            return None
        ts = doc[campo]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return round((ahora - ts).total_seconds() / 3600, 1)

    return {
        "detalle_por_plataforma":  detalle_plataforma,
        "bronze":                  bronze_stats,
        "silver":                  silver_stats,
        "pendientes_por_procesar": pendientes,
        "total_pendientes":        sum(pendientes.values()),
        "horas_desde_ultimo_etl":  _horas(ultimo_etl, "fecha_inicio"),
        "horas_desde_ultimo_nlp":  _horas(ultimo_nlp, "procesado_en"),
        "ultimo_etl_plataforma":   ultimo_etl.get("objetivo") if ultimo_etl else None,
        "ultimo_etl_nuevos":       ultimo_etl.get("total_registros_nuevos") if ultimo_etl else None,
        "error_reciente":          bool(ultimo_error and _horas(ultimo_error, "fecha_inicio") < 6),
        "nota":                    "TikTok ETL deshabilitado temporalmente. Solo usar Agente 2 para TikTok."}


def _ejecutar_tool(nombre: str, args: dict) -> str:
    if nombre == "revisar_estado_sistema":
        resultado = _revisar_estado_sistema()

    elif nombre == "invocar_agente1":
        plataforma = args["plataforma"]
        if plataforma == "tiktok":
            resultado = {"error": "TikTok ETL deshabilitado. Usa youtube o telegram."}
        else:
            resultado = orquestar_extraccion(plataforma)
            resultado.pop("_id", None)
            resultado["fecha_inicio"] = str(resultado.get("fecha_inicio", ""))
            resultado["fecha_fin"]    = str(resultado.get("fecha_fin", ""))

    elif nombre == "invocar_agente2":
        resultado = run_classification(args["plataforma"])

    elif nombre == "escribir_reporte":
        doc = {
            "agente":             "orquestador",
            "resumen":            args["resumen"],
            "acciones_tomadas":   args["acciones_tomadas"],
            "proxima_revision_h": args["proxima_revision_horas"],
            "procesado_en":       datetime.now(timezone.utc)}
        kb_col.insert_one(doc)
        resultado = {"guardado": True, "proxima_revision_horas": args["proxima_revision_horas"]}

    else:
        resultado = {"error": f"tool '{nombre}' no reconocida"}

    return json.dumps(resultado, ensure_ascii=False, default=str)


def _ciclo_orquestador(user_msg_q: queue.Queue | None = None) -> float:
    print(f"\n{'═'*55}")
    print(f"  ORQUESTADOR  ·  {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"{'═'*55}")

    msgs_operador = []
    if user_msg_q:
        while not user_msg_q.empty():
            msgs_operador.append(user_msg_q.get_nowait())

    if msgs_operador:
        bloque = "\n".join(f"- {m}" for m in msgs_operador)
        contenido = (f"Mensajes del operador humano:\n{bloque}\n\n"
                     "Basándote en estos mensajes y en el estado actual del sistema, decide qué hacer.")
    else:
        contenido = "Revisa el estado del sistema y decide qué hacer ahora."

    messages         = [{"role": "user", "content": contenido}]
    proxima_revision = 24.0

    while True:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            tools=TOOLS,
            tool_choice="auto")

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
            label  = _TOOL_LABEL.get(nombre, lambda a: nombre)(args)
            print(f"\n  ▸ {label}")
            resultado = _ejecutar_tool(nombre, args)

            if nombre == "escribir_reporte":
                data             = json.loads(resultado)
                proxima_revision = data.get("proxima_revision_horas", 24.0)

            tool_results.append({
                "role":         "tool",
                "tool_call_id": call.id,
                "content":      resultado})

        messages.extend(tool_results)

    return proxima_revision


def iniciar_orquestador(user_msg_q: queue.Queue | None = None,
                        wake_event: threading.Event | None = None):
    print("Orquestador iniciado. Ctrl+C para detener.\n")
    while True:
        try:
            horas_espera = _ciclo_orquestador(user_msg_q)
        except Exception as e:
            print(f"\nError en ciclo del orquestador: {e}")
            horas_espera = 1.0

        segundos   = horas_espera * 3600
        siguiente  = datetime.fromtimestamp(time.time() + segundos)
        print(f"\n{'─'*55}")
        print(f"  Próxima revisión en {horas_espera:.0f}h  ·  ~{siguiente:%Y-%m-%d %H:%M:%S}")
        print(f"{'─'*55}\n")

        if wake_event:
            wake_event.wait(timeout=segundos)
            wake_event.clear()
        else:
            time.sleep(segundos)


# ── GUI ───────────────────────────────────────────────────────────────

class _GuiWriter:
    """Redirige sys.stdout al queue del GUI sin perder la salida original."""
    def __init__(self, q: queue.Queue, orig):
        self._q    = q
        self._orig = orig
        self._buf  = ""

    def write(self, text: str):
        self._orig.write(text)
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._q.put(line + "\n")

    def flush(self):
        if self._buf.strip():
            self._q.put(self._buf + "\n")
            self._buf = ""
        self._orig.flush()


class _OrchestratorGUI:
    BG      = "#0d1117"
    TEXT_BG = "#161b22"
    FG      = "#c9d1d9"
    ACCENT  = "#21262d"
    CYAN    = "#58a6ff"
    GREEN   = "#3fb950"
    YELLOW  = "#d29922"
    RED     = "#f85149"
    ORANGE  = "#e3b341"

    def __init__(self, log_q: queue.Queue, user_q: queue.Queue, wake_event: threading.Event):
        self.log_q      = log_q
        self.user_q     = user_q
        self.wake_event = wake_event

        self.root = tk.Tk()
        self.root.title("Centinela — Orquestador")
        self.root.configure(bg=self.BG)
        self.root.geometry("860x580")
        self.root.resizable(True, True)

        self._build_ui()
        self._poll_log()

    def _build_ui(self):
        hdr = tk.Frame(self.root, bg=self.ACCENT, pady=10, padx=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text="CENTINELA  ·  Orquestador Inteligente",
                 bg=self.ACCENT, fg=self.CYAN,
                 font=("Segoe UI", 13, "bold")).pack(side="left")
        self._status_lbl = tk.Label(hdr, text="iniciando...",
                                    bg=self.ACCENT, fg=self.YELLOW,
                                    font=("Segoe UI", 10))
        self._status_lbl.pack(side="right")

        log_frame = tk.Frame(self.root, bg=self.BG, padx=10, pady=8)
        log_frame.pack(fill="both", expand=True)

        self.log_area = scrolledtext.ScrolledText(
            log_frame, bg=self.TEXT_BG, fg=self.FG,
            font=("Consolas", 10), wrap=tk.WORD,
            state="disabled", relief="flat", bd=0,
            insertbackground=self.FG)
        self.log_area.pack(fill="both", expand=True)

        self.log_area.tag_configure("action",  foreground=self.CYAN)
        self.log_area.tag_configure("ok",      foreground=self.GREEN)
        self.log_area.tag_configure("warn",    foreground=self.RED)
        self.log_area.tag_configure("sep",     foreground="#444c56")
        self.log_area.tag_configure("user",    foreground=self.ORANGE)

        chat_frame = tk.Frame(self.root, bg=self.ACCENT, padx=10, pady=8)
        chat_frame.pack(fill="x")

        tk.Label(chat_frame, text="Mensaje al orquestador:",
                 bg=self.ACCENT, fg=self.FG,
                 font=("Segoe UI", 9)).pack(anchor="w")

        inp_row = tk.Frame(chat_frame, bg=self.ACCENT)
        inp_row.pack(fill="x", pady=(4, 0))

        self.chat_input = tk.Entry(
            inp_row, bg=self.TEXT_BG, fg=self.FG,
            insertbackground=self.FG,
            font=("Segoe UI", 11), relief="flat", bd=6)
        self.chat_input.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.chat_input.bind("<Return>", self._send)

        tk.Button(inp_row, text="Enviar",
                  bg=self.CYAN, fg=self.BG,
                  font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=14, pady=5,
                  cursor="hand2",
                  command=self._send).pack(side="right")

    def _send(self, _event=None):
        msg = self.chat_input.get().strip()
        if not msg:
            return
        self.chat_input.delete(0, tk.END)
        self._append(f"[Operador] {msg}\n", "user")
        self.user_q.put(msg)
        self.wake_event.set()

    def _append(self, text: str, tag: str = ""):
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, text, tag if tag else ())
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")

    def _tag_for(self, line: str) -> str:
        l = line.lower()
        if any(c in line for c in ("═", "─", "──")):
            return "sep"
        if "▸" in line or "lanzando" in l or "consultando" in l:
            return "action"
        if any(w in l for w in ("finalizado", "completado", "exitoso", "guardado")):
            return "ok"
        if any(w in l for w in ("error", "fallo", "⚠")):
            return "warn"
        return ""

    def _poll_log(self):
        while not self.log_q.empty():
            line = self.log_q.get_nowait()
            tag  = self._tag_for(line)
            self._append(line, tag)
            if "▸" in line:
                self._status_lbl.config(text=line.replace("▸", "").strip())
            elif "próxima revisión" in line.lower():
                self._status_lbl.config(text=line.strip(), fg=self.YELLOW)
            elif "finalizado" in line.lower():
                self._status_lbl.config(text="en espera", fg=self.GREEN)
        self.root.after(120, self._poll_log)

    def run(self):
        self.root.mainloop()


def iniciar_con_gui():
    log_q      = queue.Queue()
    user_q     = queue.Queue()
    wake_event = threading.Event()

    orig_stdout = sys.stdout
    sys.stdout  = _GuiWriter(log_q, orig_stdout)

    worker = threading.Thread(
        target=iniciar_orquestador,
        args=(user_q, wake_event),
        daemon=True)
    worker.start()

    gui = _OrchestratorGUI(log_q, user_q, wake_event)
    gui.run()

    sys.stdout = orig_stdout


if __name__ == "__main__":
    iniciar_con_gui()
