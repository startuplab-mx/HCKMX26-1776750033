<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=2,12,20&height=240&section=header&text=404%20%7C%20Plataforma%20Centinela&fontSize=46&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=Pipeline%20Multiagente%20de%20Monitoreo%20y%20Deteccion%20de%20Riesgo%20en%20Redes%20Sociales&descAlignY=58&descSize=15" width="100%"/>

[![Typing SVG](https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=19&duration=2800&pause=900&color=1F8BFF&center=true&vCenter=true&random=false&width=980&lines=Extraccion+continua+de+YouTube%2C+Telegram+y+TikTok;Orquestacion+autonoma+con+LLM+y+agentes+especializados;Clasificacion+NLP+zero-shot+multilingue+con+mDeBERTa;Pipeline+Bronze+to+Silver+para+analitica+y+visualizacion)](https://git.io/typing-svg)

<br/>

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-18+-339933?style=for-the-badge&logo=node.js&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas%20%7C%20Local-47A248?style=for-the-badge&logo=mongodb&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-111111?style=for-the-badge&logo=openai&logoColor=white)
![HuggingFace](https://img.shields.io/badge/Hugging%20Face-mDeBERTa%20Zero--Shot-FFB000?style=for-the-badge)
![Transformers](https://img.shields.io/badge/Transformers-NLP-FFD21E?style=for-the-badge)

</div>

---

## Descripcion

**404 - Plataforma Centinela Multiagente** es un sistema de mineria operativa para detectar contenido de riesgo en redes sociales. Implementa un pipeline de agentes que extrae datos de YouTube, Telegram y TikTok, los centraliza en MongoDB (capa Bronze), clasifica contenido sospechoso con NLP zero-shot y promueve resultados a una capa Silver para analitica y validacion humana.

Un orquestador inteligente decide que agente ejecutar segun el estado del sistema, el volumen pendiente y la actividad reciente.

---

## Demo

> [Ver demo en video](AQUI_PEGA_TU_LINK_DE_VIDEO)

---

## Problema que resuelve

La falta de un flujo unificado, auditable y automatizable para vigilar contenido potencialmente peligroso en redes de alta dinamica genera puntos ciegos operativos y tiempos de reaccion elevados.

**404 resuelve esto con:**

- Extraccion multifuente y repetible desde tres plataformas
- Motor de priorizacion y clasificacion automatica
- Arquitectura por capas (Bronze / Silver) que separa dato crudo de dato analizado
- Interfaces para observabilidad y consumo de resultados

**Impacto esperado:** menor tiempo de reaccion ante picos de actividad, mayor cobertura de fuentes en ventanas cortas y trazabilidad completa de decisiones del sistema.

---

## Arquitectura

```mermaid
flowchart LR
    A[Orquestador LLM\nAgentes/orquestador_agentes/orquestador.py] --> B[Agente 1 ETL]
    A --> C[Agente 2 NLP]

    B --> B1[YouTube ETL]
    B --> B2[Telegram ETL]
    B --> B3[TikTok ETL]

    B1 --> D[(MongoDB Bronze\ncentinela)]
    B2 --> D
    B3 --> D

    C --> D
    C --> E[(MongoDB Silver\nsilver)]

    E --> F[Silver2Gold_UI\nReact + Express]
    E --> G[Reporte_Golden_and_Honeypot\nDashboard KPIs]
```

---

## Estructura del proyecto

```text
404/
├── Agentes/
│   ├── agente1/                  # ETL wrapper
│   ├── agente2/                  # NLP wrapper + subagentes por fuente
│   └── orquestador_agentes/      # Decision autonoma con GPT-4o-mini
├── Apis2BD_ETL/                  # ETL por plataforma (YouTube, Telegram, TikTok)
├── Reporte_Golden_and_Honeypot/  # Dashboard de monitoreo (TS/React/Express)
├── Silver2Gold_UI/               # UI de validacion humana (React + Express)
├── Bot pescador/                 # Scripts de pesca (reservado)
├── demo_reset.py                 # Reinicio de demo en Bronze/Silver
└── requirements.txt              # Dependencias Python
```

---

## Tecnologias

| Capa | Herramientas |
|---|---|
| Pipeline / Backend | Python 3.12+, MongoDB, PyMongo, python-dotenv, tqdm |
| Extraccion | YouTube Data API v3, Telegram via Telethon, TikTok Scraper |
| Modelos | OpenAI GPT-4o-mini, mDeBERTa-v3-base-mnli-xnli (zero-shot), PyTorch |
| Frontend | React, Vite, Express, Mongoose |

---

## Modulos con IA integrada

| Modulo | Tecnologia principal |
|---|---|
| Orquestador | GPT-4o-mini como motor de razonamiento para coordinacion autonoma de tareas |
| Agente 2 NLP | Clasificacion semantica zero-shot con mDeBERTa multilingue |
| ETL (Agente 1 y Apis2BD_ETL) | Extraccion directa via APIs publicas + scoring por lexico de riesgo |

<details>
<summary>Ver detalle de herramientas IA integradas</summary>

| Herramienta | Modelo | Uso | Modulo |
|---|---|---|---|
| OpenAI API | GPT-4o-mini | Razonamiento del orquestador: decide correr ETL, NLP, ambos o esperar | orquestador_agentes/orquestador.py |
| Hugging Face | zero-shot-classification | Motor de inferencia NLP para clasificar riesgo en textos | agente2/run_agente2.py |
| mDeBERTa | MoritzLaurer/mDeBERTa-v3-base-mnli-xnli | Clasificacion semantica multilingue de contenido sospechoso | agente2/run_agente2.py |
| PyTorch | cpu / cuda | Ejecucion del modelo NLP con seleccion automatica de dispositivo | agente2/run_agente2.py |

</details>

---

## Instalacion y ejecucion

### Prerrequisitos

- Python 3.12+
- Node.js 18+
- MongoDB Atlas o local
- Credenciales API: YouTube, Telegram y OpenAI

### Variables de entorno

Crear `.env` en la raiz de `404/`:

```env
MONGODB_URI=mongodb+srv://usuario:password@cluster/base?retryWrites=true&w=majority
OPENAI_API_KEY=tu_openai_key
YOUTUBE_API_KEY=tu_youtube_key
TELEGRAM_API_ID=tu_telegram_api_id
TELEGRAM_API_HASH=tu_telegram_api_hash
```

### Dependencias Python

```bash
pip install -r requirements.txt
pip install pymongo python-dotenv openai transformers torch telethon google-api-python-client tqdm
```

Para el flujo TikTok:

```bash
pip install playwright && playwright install chromium
```

### Opciones de ejecucion

```bash
# Opcion A — Orquestador completo (recomendado)
python Agentes/orquestador_agentes/orquestador.py

# Opcion B — ETL directo por fuente
python Apis2BD_ETL/main.py
python Apis2BD_ETL/main.py youtube
python Apis2BD_ETL/main.py telegram

# Opcion C — NLP directo sobre Bronze
python Agentes/agente2/run_agente2.py todos
python Agentes/agente2/run_agente2.py youtube

# Opcion D — Reset rapido para demo
python demo_reset.py
```

### Interfaz web (Silver2Gold_UI)

```bash
cd Silver2Gold_UI
npm install
npm run start
```

Levanta el backend (Express, puerto 5000) y el frontend (Vite, puerto 5173) en paralelo.

---

## Estado operativo

- El orquestador soporta ciclos autonomos con reporte en base de conocimiento.
- El ETL de TikTok puede requerir ajustes de scraping ante cambios de plataforma.
- TikTok ETL esta deshabilitado temporalmente en ejecucion automatica del orquestador.

---

## Documentacion por modulo

| Modulo | Enlace |
|---|---|
| Agentes (ETL, NLP, Orquestador) | [Agentes/README.md](Agentes/README.md) |
| Dashboard de monitoreo (KPIs) | [Reporte_Golden_and_Honeypot/README.md](Reporte_Golden_and_Honeypot/README.md) |
| UI de etiquetado Silver → Golden | [Silver2Gold_UI/README.md](Silver2Gold_UI/README.md) |

---

## Uso de IA en el desarrollo

Durante el desarrollo se utilizaron **ChatGPT** y **Gemini** como asistentes de programacion para acelerar la escritura y depuracion de codigo. La arquitectura, las decisiones tecnicas, la integracion de fuentes y la logica de negocio son trabajo propio del equipo.

---

## Equipo

<table>
    <tr>
        <td align="center" width="20%">
            <img src="assets/equipo/melisa.jpg" alt="Arano Bejarano Melisa Asharet" width="180"/><br/>
            <strong>Arano Bejarano Melisa Asharet</strong>
        </td>
        <td align="center" width="20%">
            <img src="assets/equipo/roberto.jpeg" alt="Alegre Ventura Roberto Jhoshua" width="180"/><br/>
            <strong>Alegre Ventura Roberto Jhoshua</strong>
        </td>
        <td align="center" width="20%">
            <img src="assets/equipo/bruno.jpeg" alt="Fonseca González Bruno" width="180"/><br/>
            <strong>Fonseca González Bruno</strong>
        </td>
        <td align="center" width="20%">
            <img src="assets/equipo/israel.jpeg" alt="Martínez Jiménez Israel" width="180"/><br/>
            <strong>Martínez Jiménez Israel</strong>
        </td>
        <td align="center" width="20%">
            <img src="assets/equipo/emil.jpeg" alt="Sánchez Olsen Emil Ehécatl" width="180"/><br/>
            <strong>Sánchez Olsen Emil Ehécatl</strong>
        </td>
    </tr>
</table>

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=2,12,20&height=120&section=footer" width="100%"/>

</div>
