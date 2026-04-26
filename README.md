<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=2,12,20&height=240&section=header&text=404%20%7C%20Chimalli&fontSize=46&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=Plataforma+de+Inteligencia+Operativa+contra+Reclutamiento+Criminal+en+Redes+Sociales&descAlignY=58&descSize=15" width="100%"/>

[![Typing SVG](https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=19&duration=2800&pause=900&color=1F8BFF&center=true&vCenter=true&random=false&width=980&lines=Vigilancia+aut%C3%B3noma+en+YouTube%2C+Telegram+y+TikTok;Bot+infiltrado+en+canales+y+perfiles+sospechosos+en+tiempo+real;Clasificaci%C3%B3n+de+riesgo+zero-shot+multiling%C3%BCe+con+mDeBERTa;Validaci%C3%B3n+humana+guiada+para+decisi%C3%B3n+operativa)](https://git.io/typing-svg)

<br/>

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-18+-339933?style=for-the-badge&logo=node.js&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas%20%7C%20Local-47A248?style=for-the-badge&logo=mongodb&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-111111?style=for-the-badge&logo=openai&logoColor=white)
![HuggingFace](https://img.shields.io/badge/Hugging%20Face-mDeBERTa%20Zero--Shot-FFB000?style=for-the-badge)
![Transformers](https://img.shields.io/badge/Transformers-NLP-FFD21E?style=for-the-badge)

</div>

---

## ¿Qué es Chimalli?

El crimen organizado recluta en redes sociales. Lo hace en público, con códigos, en canales de Telegram, en videos de TikTok, en comentarios de YouTube. Y lo hace en tiempo real.

**Chimalli** es una plataforma de inteligencia operativa que detecta, clasifica y documenta ese reclutamiento de forma automática. Extrae publicaciones, mensajes, videos y perfiles con indicadores de narcocultura, oferta criminal y reclutamiento activo. No es solo un monitor pasivo: su orquestador despliega un bot que se infiltra en canales y perfiles sospechosos para capturar contenido en tiempo real, antes de que desaparezca.

El pipeline completo va de la extracción automática a la decisión humana informada, con trazabilidad total en cada paso.

---

## Demo

> [Ver demo en video](AQUI_PEGA_TU_LINK_DE_VIDEO)

> [📁 Carpeta del proyecto (Drive)](https://drive.google.com/drive/folders/1it1OJgNVbram578OwhpguPdqRCIaHNTk?usp=sharing)

---

## Capacidades del sistema

| Capacidad | Detalle |
|---|---|
| Vigilancia continua | Recolección automática de publicaciones, mensajes y perfiles desde YouTube, Telegram y TikTok |
| Infiltración en tiempo real | Bot pescador que monitorea activamente canales y perfiles sospechosos |
| Clasificación inteligente | NLP zero-shot multilingüe (mDeBERTa) que identifica narcocultura, oferta criminal y reclutamiento |
| Orquestación autónoma | GPT-4o-mini decide qué ejecutar según el estado del sistema y el volumen pendiente |
| Validación humana guiada | Interfaz de revisión con preview del contenido original y clasificación asistida por IA |
| Trazabilidad completa | Arquitectura Bronze / Silver / Gold con historial auditado de cada decisión |

---

## Arquitectura

```mermaid
flowchart TD
    OP([Operador]) --> O

    O[Orquestador\nGPT-4o-mini\nDecide qué ejecutar y cuándo] --> A1
    O --> A2

    A1[Agente 1 — ETL\nDescarga publicaciones\ny mensajes sospechosos] --> YT[YouTube ETL]
    A1 --> TG[Telegram ETL]

    BP([Bot Pescador\nVigilancia en tiempo real\nindependiente]) --> BR

    YT --> BR[(Bronze\ncentinela\nDato crudo)]
    TG --> BR

    BR --> A2[Agente 2 — NLP\nmDeBERTa zero-shot\nNarcocultura · Oferta · Reclutamiento]

    A2 -->|solo sospechosos| SL[(Silver\nDato clasificado)]

    SL --> UI[Silver2Gold UI\nValidación humana\nguiada por IA]
    SL --> DS[Dashboard KPIs\nReporte Golden]

    UI -->|confirmados| GD[(Gold\nObjetivos confirmados)]
    GD --> DM([Demo Monitor\nVigilancia continua\nsobre Golden])
```

**Flujo:** Extracción / Infiltración → Bronze → Clasificación NLP → Silver → Validación humana → Gold → Monitoreo continuo

---

## Estructura del proyecto

```text
404/
├── Agentes/
│   ├── agente1/                  # Wrapper ETL: lanza los scripts de extracción
│   ├── agente2/                  # Wrapper NLP: clasifica contenido desde Bronze
│   └── orquestador_agentes/      # Cerebro del sistema: decide qué ejecutar y cuándo
├── Apis2BD_ETL/                  # Scripts ETL por plataforma (YouTube, Telegram, TikTok)
├── Bot pescador/                 # Bot de infiltración: monitorea canales sospechosos en tiempo real
├── Silver2Gold_UI/               # Interfaz de validación humana (React + Express)
├── Reporte_Golden_and_Honeypot/  # Dashboard de KPIs y monitoreo (TS/React/Express)
├── demo_reset.py                 # Reinicia datos Bronze/Silver para demo controlada
└── requirements.txt              # Dependencias Python del pipeline
```

---

## Instalación paso a paso

### Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/AlegreVentura/404.git
cd 404
```

### Paso 2 — Crear el archivo de variables de entorno

Crear un archivo `.env` en la raíz del proyecto (`404/`) con las siguientes claves:

```env
# Base de datos
MONGODB_URI=mongodb+srv://usuario:password@cluster/base?retryWrites=true&w=majority

# IA
OPENAI_API_KEY=tu_openai_key

# APIs de extracción
YOUTUBE_API_KEY=tu_youtube_key
TELEGRAM_API_ID=tu_telegram_api_id
TELEGRAM_API_HASH=tu_telegram_api_hash
```

> Necesitas una cuenta en [MongoDB Atlas](https://www.mongodb.com/cloud/atlas), [OpenAI](https://platform.openai.com/) y acceso a las APIs de YouTube y Telegram.

### Paso 3 — Instalar dependencias Python

```bash
pip install -r requirements.txt
```

Si vas a usar el flujo de TikTok:

```bash
pip install playwright && playwright install chromium
```

### Paso 4 — Ejecutar el pipeline

**Opción A — Orquestador completo (recomendado)**
> El sistema decide de forma autónoma si extraer, clasificar o ambos.

```bash
python Agentes/orquestador_agentes/orquestador.py
```

**Opción B — Solo extracción ETL (carga datos a Bronze)**
> Para poblar la base de datos sin clasificar aún.

```bash
python Apis2BD_ETL/main.py          # todas las fuentes
python Apis2BD_ETL/main.py youtube  # solo YouTube
python Apis2BD_ETL/main.py telegram # solo Telegram
```

**Opción C — Solo clasificación NLP (Bronze → Silver)**
> Para clasificar datos que ya están en Bronze.

```bash
python Agentes/agente2/run_agente2.py todos
python Agentes/agente2/run_agente2.py youtube
python Agentes/agente2/run_agente2.py telegram
```

**Opción D — Reset para demo**
> Restablece Bronze y Silver a un estado controlado para presentación.

```bash
python demo_reset.py
```

### Paso 5 — Levantar la interfaz de validación (Silver2Gold_UI)

```bash
cd Silver2Gold_UI
npm install
npm run start
```

Esto levanta en paralelo:
- **Frontend** (React + Vite) → `http://localhost:5173`
- **Backend** (Express + Mongoose) → `http://localhost:5000`

---

## Módulos con IA

| Módulo | Tecnología |
|---|---|
| Orquestador | GPT-4o-mini — razonamiento autónomo para coordinación de tareas |
| Agente 2 NLP | mDeBERTa multilingüe — clasificación zero-shot de contenido en riesgo |
| ETL | Sin IA generativa — extracción por APIs + scoring por léxico de riesgo |

<details>
<summary>Ver detalle técnico de modelos</summary>

| Herramienta | Modelo | Uso | Archivo |
|---|---|---|---|
| OpenAI API | GPT-4o-mini | Decide correr ETL, NLP, ambos o esperar según estado del sistema | orquestador_agentes/orquestador.py |
| Hugging Face | zero-shot-classification | Motor de inferencia NLP sobre textos de las tres plataformas | agente2/run_agente2.py |
| mDeBERTa | MoritzLaurer/mDeBERTa-v3-base-mnli-xnli | Clasificación semántica multilingüe de contenido sospechoso | agente2/run_agente2.py |
| PyTorch | cpu / cuda | Ejecución del modelo con selección automática de dispositivo | agente2/run_agente2.py |

</details>

---

## Tecnologías

| Capa | Herramientas |
|---|---|
| Pipeline / Backend | Python 3.12+, MongoDB, PyMongo, python-dotenv, tqdm |
| Extracción | YouTube Data API v3, Telegram via Telethon, TikTok Scraper |
| Modelos | OpenAI GPT-4o-mini, mDeBERTa-v3-base-mnli-xnli, PyTorch |
| Frontend | React, Vite, Express, Mongoose |

---

## Estado operativo

- El orquestador soporta ciclos autónomos con reporte en base de conocimiento.
- El ETL de TikTok puede requerir ajustes de scraping ante cambios de plataforma.
- TikTok ETL está deshabilitado temporalmente en la ejecución automática del orquestador.

---

## Documentación por módulo

| Módulo | README |
|---|---|
| Agentes (ETL, NLP, Orquestador) | [Agentes/README.md](Agentes/README.md) |
| Dashboard de KPIs | [Reporte_Golden_and_Honeypot/README.md](Reporte_Golden_and_Honeypot/README.md) |
| UI de validación Silver → Gold | [Silver2Gold_UI/README.md](Silver2Gold_UI/README.md) |

---

## Uso de IA en el desarrollo

Durante el desarrollo se utilizaron **ChatGPT** y **Gemini** como asistentes de programación para acelerar la escritura y depuración de código. La arquitectura, las decisiones técnicas, la integración de fuentes y la lógica de negocio son trabajo propio del equipo.

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
