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
7. TikTok ETL DESHABILITADO: NO invoques Agente 1 con plataforma='tiktok'. La recolección de TikTok debe hacerse de forma manual por el operador y cargarse directamente a Bronze. Para NLP de TikTok (Agente 2), sí puedes usarlo si hay pendientes en Bronze.
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
        "nota":                    "TikTok ETL deshabilitado. Recolección manual por operador → Bronze. Agente 2 disponible si hay pendientes."}


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
    # Paleta principal
    NAVY     = "#0a2240"
    NAVY2    = "#0d2d55"
    NAVYLT   = "#163660"
    WHITE    = "#ffffff"
    OFFWHITE = "#f4f7fb"
    TEXT     = "#1a2744"
    BLUE     = "#1e5fa8"
    BLUELIT  = "#2e7dd1"
    GREEN    = "#0a7c3e"
    RED      = "#b92d2d"
    ORANGE   = "#c25c10"
    GRAY     = "#7a8fa6"
    GOLD     = "#8a6d00"
    SEPLINE  = "#d5e1ef"

    # Dot animation states
    _DOT_IDLE   = ("#4a9eff", 800)   # color, delay ms
    _DOT_ACTIVE = ("#00e676", 180)

    def __init__(self, log_q: queue.Queue, user_q: queue.Queue, wake_event: threading.Event):
        self.log_q       = log_q
        self.user_q      = user_q
        self.wake_event  = wake_event
        self._active     = False
        self._pulse_r    = 5
        self._pulse_dir  = -1
        self._spin_angle = 0

        self.root = tk.Tk()
        self.root.title("Centinela — Orquestador Inteligente")
        self.root.configure(bg=self.NAVY)
        self.root.geometry("920x640")
        self.root.minsize(700, 480)
        self.root.resizable(True, True)

        # icono de ventana (canvas pequeño como ícono)
        try:
            ico = tk.PhotoImage(width=16, height=16)
            ico.put(self.NAVY, to=(0, 0, 15, 15))
            self.root.iconphoto(True, ico)
        except Exception:
            pass

        self._build_ui()
        self._animate_dot()
        self._poll_log()

    # ── construcción UI ───────────────────────────────────────────────

    def _build_ui(self):
        # ── HEADER ──
        hdr = tk.Frame(self.root, bg=self.NAVY, pady=0)
        hdr.pack(fill="x")

        # barra de color superior fina
        tk.Frame(hdr, bg=self.BLUELIT, height=3).pack(fill="x")

        inner_hdr = tk.Frame(hdr, bg=self.NAVY, padx=18, pady=12)
        inner_hdr.pack(fill="x")

        # logo / título
        left = tk.Frame(inner_hdr, bg=self.NAVY)
        left.pack(side="left")

        tk.Label(left, text="CENTINELA",
                 bg=self.NAVY, fg=self.WHITE,
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Label(left, text="  ·  Orquestador Inteligente",
                 bg=self.NAVY, fg=self.BLUELIT,
                 font=("Segoe UI", 12)).pack(side="left")

        # status (dot + texto) a la derecha
        right = tk.Frame(inner_hdr, bg=self.NAVY)
        right.pack(side="right")

        self._dot_cv = tk.Canvas(right, width=14, height=14,
                                 bg=self.NAVY, highlightthickness=0)
        self._dot_cv.pack(side="left", padx=(0, 7))
        self._dot_oval = self._dot_cv.create_oval(2, 2, 12, 12,
                                                  fill="#4a9eff", outline="")

        self._status_var = tk.StringVar(value="iniciando…")
        self._status_lbl = tk.Label(right, textvariable=self._status_var,
                                    bg=self.NAVY, fg=self.BLUELIT,
                                    font=("Segoe UI", 10))
        self._status_lbl.pack(side="left")

        # separador decorativo
        tk.Frame(self.root, bg=self.NAVYLT, height=1).pack(fill="x")

        # ── LOG AREA (fondo blanco) ──
        log_outer = tk.Frame(self.root, bg=self.WHITE, padx=0, pady=0)
        log_outer.pack(fill="both", expand=True)

        # barra lateral izquierda de color
        tk.Frame(log_outer, bg=self.NAVY2, width=5).pack(side="left", fill="y")

        log_inner = tk.Frame(log_outer, bg=self.WHITE, padx=12, pady=10)
        log_inner.pack(fill="both", expand=True)

        self.log_area = scrolledtext.ScrolledText(
            log_inner, bg=self.WHITE, fg=self.TEXT,
            font=("Consolas", 10), wrap=tk.WORD,
            state="disabled", relief="flat", bd=0,
            selectbackground=self.BLUELIT, selectforeground=self.WHITE,
            spacing3=2)
        self.log_area.pack(fill="both", expand=True)

        # tags de color sobre fondo blanco
        self.log_area.tag_configure("ts",     foreground=self.GRAY,
                                              font=("Consolas", 9))
        self.log_area.tag_configure("sep",    foreground=self.SEPLINE,
                                              font=("Consolas", 9))
        self.log_area.tag_configure("action", foreground=self.NAVY,
                                              font=("Consolas", 10, "bold"))
        self.log_area.tag_configure("ok",     foreground=self.GREEN,
                                              font=("Consolas", 10, "bold"))
        self.log_area.tag_configure("warn",   foreground=self.RED)
        self.log_area.tag_configure("info",   foreground=self.BLUE)
        self.log_area.tag_configure("user",   foreground=self.ORANGE,
                                              font=("Consolas", 10, "bold italic"))
        self.log_area.tag_configure("data",   foreground="#555e6a")

        # ── separador antes del chat ──
        tk.Frame(self.root, bg=self.NAVYLT, height=1).pack(fill="x")

        # ── CHAT FOOTER ──
        footer = tk.Frame(self.root, bg=self.NAVY2, padx=16, pady=12)
        footer.pack(fill="x")

        lbl_row = tk.Frame(footer, bg=self.NAVY2)
        lbl_row.pack(fill="x", pady=(0, 6))

        tk.Label(lbl_row, text="Mensaje al orquestador",
                 bg=self.NAVY2, fg=self.BLUELIT,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(lbl_row,
                 text="  (el agente entiende instrucciones en lenguaje natural)",
                 bg=self.NAVY2, fg=self.GRAY,
                 font=("Segoe UI", 8)).pack(side="left")

        inp_row = tk.Frame(footer, bg=self.NAVY2)
        inp_row.pack(fill="x")

        # campo de texto con borde simulado
        entry_wrap = tk.Frame(inp_row, bg=self.BLUELIT, padx=1, pady=1)
        entry_wrap.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.chat_input = tk.Entry(
            entry_wrap, bg=self.WHITE, fg=self.TEXT,
            insertbackground=self.NAVY,
            font=("Segoe UI", 11), relief="flat", bd=8)
        self.chat_input.pack(fill="x")
        self.chat_input.bind("<Return>", self._send)
        self.chat_input.bind("<FocusIn>",  lambda e: entry_wrap.config(bg=self.BLUELIT))
        self.chat_input.bind("<FocusOut>", lambda e: entry_wrap.config(bg=self.NAVYLT))

        self._send_btn = tk.Button(
            inp_row, text="Enviar  →",
            bg=self.BLUELIT, fg=self.WHITE,
            activebackground=self.BLUE, activeforeground=self.WHITE,
            font=("Segoe UI", 10, "bold"),
            relief="flat", padx=18, pady=8,
            cursor="hand2",
            command=self._send)
        self._send_btn.pack(side="right")
        self._send_btn.bind("<Enter>", lambda e: self._send_btn.config(bg=self.BLUE))
        self._send_btn.bind("<Leave>", lambda e: self._send_btn.config(bg=self.BLUELIT))

        # pie
        tk.Frame(self.root, bg=self.NAVY, height=4).pack(fill="x")

    # ── lógica de animación ───────────────────────────────────────────

    def _animate_dot(self):
        color, delay = self._DOT_ACTIVE if self._active else self._DOT_IDLE
        self._pulse_r += self._pulse_dir
        if self._pulse_r <= 3:
            self._pulse_dir = 1
        elif self._pulse_r >= 6:
            self._pulse_dir = -1
        r = self._pulse_r
        cx = 7
        self._dot_cv.coords(self._dot_oval, cx - r, cx - r, cx + r, cx + r)
        self._dot_cv.itemconfig(self._dot_oval, fill=color)
        self.root.after(delay, self._animate_dot)

    def _set_active(self, active: bool, status_text: str = ""):
        self._active = active
        if status_text:
            self._status_var.set(status_text)
        color = self.GREEN if active else self.BLUELIT
        self._status_lbl.config(fg=color)

    # ── envío de mensajes ─────────────────────────────────────────────

    def _send(self, _event=None):
        msg = self.chat_input.get().strip()
        if not msg:
            return
        self.chat_input.delete(0, tk.END)
        ts = datetime.now().strftime("%H:%M:%S")
        self._append(f"{ts}  ", "ts")
        self._append(f"[Tú] {msg}\n", "user")
        self.user_q.put(msg)
        self.wake_event.set()
        self._set_active(True, "procesando mensaje…")

    # ── log ───────────────────────────────────────────────────────────

    def _append(self, text: str, tag: str = ""):
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, text, (tag,) if tag else ())
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")

    def _tag_for(self, line: str) -> str:
        lo = line.lower().strip()
        if any(c in line for c in ("═══", "───")):
            return "sep"
        if "▸" in line:
            return "action"
        if any(w in lo for w in ("finalizado", "completado", "exitoso", "guardado")):
            return "ok"
        if any(w in lo for w in ("error", "fallo")):
            return "warn"
        if any(w in lo for w in ("orquestador ·", "nlp ·", "etl ·")):
            return "info"
        if any(w in lo for w in ("sospechosos", "confirmados", "recolectados", "pendientes")):
            return "data"
        return ""

    def _poll_log(self):
        while not self.log_q.empty():
            line = self.log_q.get_nowait()
            tag  = self._tag_for(line)
            ts   = datetime.now().strftime("%H:%M:%S")

            # no agregar timestamp a separadores o líneas vacías
            if tag not in ("sep", "") or "═" in line or "─" in line:
                self._append(f"{ts}  ", "ts")
            else:
                self._append(f"{ts}  ", "ts")

            self._append(line if line.endswith("\n") else line + "\n", tag)

            # actualizar status bar
            if "▸" in line:
                label = line.replace("▸", "").strip()
                self._set_active(True, label)
            elif "próxima revisión" in line.lower():
                h = line.strip()
                self._set_active(False, h)
            elif "finalizado" in line.lower():
                self._set_active(False, "en espera")
            elif "listo" in line.lower() and "esperando" in line.lower():
                self._set_active(False, "listo · esperando instrucción")
            elif "iniciando" in line.lower() or "cargando" in line.lower():
                self._set_active(True, "cargando…")

        self.root.after(100, self._poll_log)

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
