# Arquitectura de Agentes — Proyecto Centinela

Sistema de detección de reclutamiento criminal y contenido peligroso para NNA (niñas, niños y adolescentes) en redes sociales.

---

## Visión General

```
Orquestador (GPT-4o-mini)
    ↓ decide inteligentemente
Agente 1 (ETL)          →  Bronze: centinela.*
    ↓
Agente 2 (mDeBERTa NLP) →  Silver: silver.*
```

El orquestador corre indefinidamente, revisa el estado del sistema y decide cuándo y qué ejecutar. No sigue un timer fijo — razona con datos reales de MongoDB.

---

## Cómo Correr

```bash
# Desde la raíz del proyecto (404/)
python Agentes/orquestador_agentes/orquestador.py
```

Para correr un agente individualmente:

```bash
# Agente 1 — ETL
python Agentes/agente1/code_agente1.py [youtube|telegram|tiktok|todos]

# Agente 2 — NLP completo
python Agentes/agente2/run_agente2.py [youtube|telegram|tiktok|todos]

# Agente 2 — sub-agente específico
python Agentes/agente2/agente2_youtube/code_agente2_youtube.py
python Agentes/agente2/agente2_telegram_channels/code_agente2_telegram_channels.py
python Agentes/agente2/agente2_telegram_messages/code_agente2_telegram_messages.py
python Agentes/agente2/agente2_tiktok_users/code_agente2_tiktok_users.py
```

---

## Dependencias

```bash
pip install openai pymongo python-dotenv transformers torch apscheduler
```

Variables requeridas en `.env`:
```
MONGODB_URI=...
OPENAI_API_KEY=...
YOUTUBE_API_KEY=...
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
```

---

## Agente 1 — ETL (Extracción → Bronze)

**Archivo:** `Agentes/agente1/code_agente1.py`
**Función pública:** `orquestar_extraccion(objetivo)` → retorna dict con reporte

### Qué hace
- Lanza el script ETL correspondiente vía subprocess
- Cuenta registros en Bronze antes y después para calcular registros nuevos
- Escribe reporte en `centinela.knowledge_base`

### Scripts ETL que invoca
| Plataforma | Script |
|---|---|
| youtube | `Apis2BD_ETL/Main/ETL/ETL_youtube/etl_youtube.py` |
| telegram | `Apis2BD_ETL/Main/ETL/ETL_telegram/etl_telegram.py` |
| tiktok | `Apis2BD_ETL/Main/ETL/ETL_tiktok/etl_tiktok.py` |
| todos | `Apis2BD_ETL/main.py` |

### Reporte que genera
```json
{
  "agente": "agente1_etl",
  "objetivo": "todos",
  "status": true,
  "reporte_de_descarga": "descarga exitosa",
  "registros_nuevos": { "youtube_items": 0, "telegram_messages": 150, ... },
  "total_registros_nuevos": 150,
  "duracion_seg": 45
}
```

---

## Agente 2 — NLP Zero-Shot (Bronze → Silver)

**Cerebro:** `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` (~558MB, se descarga automático)
**Wrapper:** `Agentes/agente2/run_agente2.py`
**Función pública:** `run_classification(plataforma)` → retorna dict con reporte

### Criterio de paso a Silver
Un registro pasa de Bronze a Silver si:
- `top_label != "Seguro"` **Y** `score >= 0.40`

### Etiquetas de clasificación
- Reclutamiento
- Oferta de Riesgo
- Narcocultura
- Contenido Inapropiado para Menores
- Seguro

### Niveles de riesgo
| Nivel | Score |
|---|---|
| `alto` | ≥ 0.65 |
| `medio` | ≥ 0.40 |

### Patrón de procesamiento
- Streaming de docs desde MongoDB (no carga todo en memoria)
- Clasificación en **lotes de 5 textos** por llamada al modelo
- `finally` garantizado: el buffer se limpia aunque haya error
- **Incremental:** obtiene `_id`s ya en Silver al inicio y los omite
- Upsert por `_id` del Bronze (sin duplicados si corre dos veces)
- Bronze es **solo lectura** — nunca se modifica

### Silver doc = Bronze completo + campos NLP
Todos los campos originales del Bronze se copian al Silver, más:

| Campo | Descripción |
|---|---|
| `_id_bronce` | Referencia explícita al doc de origen |
| `categoria_principal` | Label ganador del NLP |
| `nivel_riesgo` | alto / medio / bajo |
| `riesgo_score` | Score numérico del top label |
| `scores_zero_shot` | Dict con los 5 scores completos |
| `texto_analizado` | Texto que se pasó al modelo |
| `fuente` | youtube / telegram / tiktok |
| `coleccion_origen` | Trazabilidad exacta (ej. centinela.telegram_messages) |
| `procesado_en` | Timestamp UTC |

### Campos adicionales por plataforma

**YouTube** (`silver.youtube_items`):
- Analiza: comentarios (máx. 200 por video, en batches de 5)
- El video pasa a Silver si ≥ 1 comentario es sospechoso
- Campos extra: `comentarios_analizados_nlp`, `comentarios_sospechosos`, `n_comentarios_sospechosos`, `pct_sospechosos`

**Telegram Channels** (`silver.telegram_channels`):
- Analiza: `title + about/description` concatenados
- Campos extra: ninguno adicional

**Telegram Messages** (`silver.telegram_messages`):
- Analiza: `message_text`
- Campos extra: `contiene_url`, `contiene_telefono`, `contiene_invitacion`, `longitud_mensaje`
- Detección de invitaciones via regex: `t.me/+`, `t.me/joinchat`

**TikTok Users** (`silver.tiktok_usuarios`):
- Analiza: `username + nombre + bio` concatenados
- Campos extra: `tiene_bio`, `longitud_bio`, `contiene_url_bio`, `contiene_telefono_bio`

### Colecciones Bronze → Silver
| Bronze (centinela) | Silver |
|---|---|
| youtube_items | silver.youtube_items |
| telegram_channels | silver.telegram_channels |
| telegram_messages | silver.telegram_messages |
| tiktok_usuarios | silver.tiktok_usuarios |

---

## Orquestador — Cerebro GPT-4o-mini

**Archivo:** `Agentes/orquestador_agentes/orquestador.py`

### Cómo decide
En cada ciclo, GPT recibe el estado actual del sistema y razona:
- ¿Cuántas horas desde el último ETL exitoso? (si > 48h considera correr Agente 1)
- ¿Cuántos registros pendientes en Bronze sin procesar a Silver?
- ¿Hubo errores recientes?
- ¿Cuántos registros nuevos trajo el último ETL?

### Tools disponibles para GPT
| Tool | Qué hace |
|---|---|
| `revisar_estado_sistema()` | Stats de Bronze vs Silver, último run, errores |
| `invocar_agente1(plataforma)` | Lanza el ETL |
| `invocar_agente2(plataforma)` | Lanza clasificación NLP |
| `escribir_reporte(resumen, acciones, proxima_revision_horas)` | Loguea en MongoDB y define espera |

### Scheduling adaptativo
GPT decide cuántas horas esperar al final de cada ciclo:
- **1-4h** si hay mucha actividad o datos pendientes
- **12-24h** si es actividad normal
- **48-72h** si el sistema está al día y tranquilo

### Reglas estrictas del orquestador
1. Siempre llama `revisar_estado_sistema` antes de decidir
2. Puede correr solo Agente 2 si hay datos Bronze pendientes (sin necesidad de nuevo ETL)
3. Si Agente 1 retorna 0 nuevos registros, NO corre Agente 2 — programa espera larga
4. Siempre termina el ciclo con `escribir_reporte`

---

## Colecciones MongoDB

### centinela (Bronze)
- `youtube_items` — videos + comentarios de YouTube
- `telegram_messages` — mensajes de canales de Telegram
- `telegram_channels` — metadata de canales de Telegram
- `tiktok_videos` — videos de TikTok
- `tiktok_usuarios` — perfiles de usuarios de TikTok
- `knowledge_base` — reportes de ejecución de todos los agentes

### silver (Silver)
- `youtube_items` — videos sospechosos con análisis NLP
- `telegram_channels` — canales sospechosos
- `telegram_messages` — mensajes sospechosos
- `tiktok_usuarios` — perfiles sospechosos

---

## Estructura de Archivos

```
Agentes/
├── agente1/
│   └── code_agente1.py
├── agente2/
│   ├── run_agente2.py                          ← wrapper principal
│   ├── agente2_youtube/
│   │   └── code_agente2_youtube.py
│   ├── agente2_telegram_channels/
│   │   └── code_agente2_telegram_channels.py
│   ├── agente2_telegram_messages/
│   │   └── code_agente2_telegram_messages.py
│   └── agente2_tiktok_users/
│       └── code_agente2_tiktok_users.py
└── orquestador_agentes/
    ├── orquestador.py
    └── prompt_orquestador.md
```
