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

## 1. Nombre del proyecto y descripcion

# 404 - Plataforma Centinela Multiagente

404 es una plataforma de mineria operativa para detectar contenido de riesgo en redes sociales a partir de un pipeline de agentes que:

- extrae datos desde YouTube, Telegram y TikTok,
- centraliza la ingesta en MongoDB (capa Bronze),
- clasifica contenido sospechoso con NLP zero-shot,
- promueve resultados a una capa Silver para analitica y visualizacion.

El sistema integra un orquestador inteligente que decide que agente ejecutar segun estado del sistema, volumen pendiente y actividad reciente.

---

## DEMO

Link de DEMO:

```md
## DEMO

[Ver demo en video](AQUI_PEGA_TU_LINK_DE_VIDEO)
```

---

## 2. Problema que resuelve

El problema principal es la falta de un flujo unificado, auditable y automatizable para vigilancia de contenido potencialmente peligroso en redes de alta dinamica.

La carpeta 404 resuelve ese problema con:

- una extraccion multifuente y repetible,
- un motor de priorizacion y clasificacion automatica,
- una arquitectura por capas (Bronze/Silver) que separa dato crudo de dato analizado,
- interfaces para observabilidad y consumo de resultados.

Impacto operativo esperado:

- menor tiempo de reaccion ante picos de actividad,
- mayor cobertura de fuentes en ventanas cortas,
- trazabilidad de decisiones del sistema y de cada corrida de agentes.

---

## 3. Arquitectura de alto nivel

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

## 4. Estructura funcional de la carpeta 404

```text
404/
|- Agentes/
|  |- agente1/                  # ETL wrapper
|  |- agente2/                  # NLP wrapper + subagentes por fuente
|  |- orquestador_agentes/      # Decision autonoma con GPT-4o-mini
|- Apis2BD_ETL/                 # ETL por plataforma (YouTube, Telegram, TikTok)
|- Reporte_Golden_and_Honeypot/ # Dashboard de monitoreo (TS/React/Express)
|- Silver2Gold_UI/              # UI alternativa (React + Express)
|- Bot pescador/                # Scripts de pesca (reservado)
|- demo_reset.py                # Reinicio de demo en Bronze/Silver
|- requirements.txt             # Dependencias base Python
```

---

## 5. Tecnologias y herramientas utilizadas

### Backend y pipeline

- Python 3.12+
- MongoDB (colecciones Bronze y Silver)
- PyMongo
- python-dotenv
- tqdm

### Extraccion por fuente

- YouTube Data API v3 (google-api-python-client)
- Telegram API via Telethon
- TikTok Content Scraper (pipeline local en ETL_tiktok)

### IA y NLP

- OpenAI API (modelo GPT-4o-mini para orquestacion)
- Hugging Face Transformers
- Modelo zero-shot: MoritzLaurer/mDeBERTa-v3-base-mnli-xnli
- PyTorch (CPU/GPU segun disponibilidad)

### Frontend y visualizacion

- React
- Vite
- Express
- Mongoose

---

## 6. Documentacion explicita de herramientas de IA (actualizadas)

Esta seccion documenta las herramientas de IA efectivamente integradas en el codigo de 404, su uso y el nivel de dependencia operativa.

| Herramienta IA | Modelo / Servicio | Para que se usa | Nivel de uso | Estado de actualizacion | Evidencia en codigo |
|---|---|---|---|---|---|
| OpenAI API | GPT-4o-mini | Razonamiento del orquestador: decide correr ETL, NLP, ambos o esperar; construye reporte operativo | Critico | Vigente en codigo (revision: 2026-04) | Agentes/orquestador_agentes/orquestador.py |
| Hugging Face Transformers | pipeline zero-shot-classification | Motor de inferencia NLP para clasificar riesgo en textos de YouTube, Telegram y TikTok | Critico | Vigente en codigo (revision: 2026-04) | Agentes/agente2/run_agente2.py |
| mDeBERTa multilingue | MoritzLaurer/mDeBERTa-v3-base-mnli-xnli | Modelo semantico principal para etiquetar sospecha sobre contenido multilingue | Critico | Vigente en codigo (revision: 2026-04) | Agentes/agente2/run_agente2.py |
| PyTorch | device cpu/cuda | Ejecucion del modelo NLP y seleccion de dispositivo para rendimiento | Alto | Vigente en codigo (revision: 2026-04) | Agentes/agente2/run_agente2.py |

### Escala de nivel de uso aplicada

- Critico: sin esta IA no existe la funcionalidad principal del modulo.
- Alto: mejora rendimiento o capacidad clave, aunque no define la logica de negocio por si sola.
- Medio: apoyo analitico secundario.
- Bajo: apoyo auxiliar.

### Cobertura operativa de IA por modulo

| Modulo | Uso de IA |
|---|---|
| Orquestador | IA generativa para toma de decisiones y coordinacion de herramientas |
| Agente 2 NLP | IA discriminativa zero-shot para clasificacion de riesgo |
| ETL (Agente 1 y Apis2BD_ETL) | No usa IA generativa para extraer; usa APIs y reglas de scoring |

---

## 7. Instrucciones para ejecutar el prototipo

## 7.1 Prerrequisitos

- Python 3.12 o superior
- Node.js 18 o superior
- MongoDB Atlas o local
- Credenciales API segun fuente (YouTube y Telegram)

## 7.2 Configuracion de entorno

En la raiz de 404, crear archivo .env con al menos:

```env
MONGODB_URI=mongodb+srv://usuario:password@cluster/base?retryWrites=true&w=majority
OPENAI_API_KEY=tu_openai_key
YOUTUBE_API_KEY=tu_youtube_key
TELEGRAM_API_ID=tu_telegram_api_id
TELEGRAM_API_HASH=tu_telegram_api_hash
```

## 7.3 Instalacion Python (pipeline)

Desde 404:

```bash
pip install -r requirements.txt
pip install pymongo python-dotenv openai transformers torch telethon google-api-python-client tqdm
```

Para flujo TikTok (si se activa):

```bash
pip install playwright
playwright install chromium
```

## 7.4 Ejecutar componentes principales

### Opcion A: orquestador con GUI (recomendado)

```bash
python Agentes/orquestador_agentes/orquestador.py
```

### Opcion B: ETL directo por fuentes

```bash
python Apis2BD_ETL/main.py
python Apis2BD_ETL/main.py youtube
python Apis2BD_ETL/main.py telegram
```

### Opcion C: NLP directo sobre Bronze

```bash
python Agentes/agente2/run_agente2.py todos
python Agentes/agente2/run_agente2.py youtube
python Agentes/agente2/run_agente2.py telegram
```

### Opcion D: reset rapido para demo controlada

```bash
python demo_reset.py
```

## 7.5 Ejecutar interfaz web (Silver2Gold_UI)

```bash
cd Silver2Gold_UI
npm install
npm run start
```

Esto levanta backend (Express) y frontend (Vite) en paralelo segun scripts del proyecto.

---

## 8. Estado y notas operativas

- El orquestador esta preparado para ciclos autonomos con reporte en base de conocimiento.
- El ETL de TikTok puede requerir ajustes de scraping segun cambios de plataforma.
- En reglas internas del orquestador se contempla TikTok ETL deshabilitado temporalmente para ejecucion automatica.

---

## 9. Integrantes del equipo

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

---

## 10. Documentación por módulo

| Módulo | README |
|---|---|
| Agentes (ETL, NLP, Orquestador) | [Agentes/README.md](Agentes/README.md) |
| Dashboard de monitoreo (KPIs) | [Reporte_Golden_and_Honeypot/README.md](Reporte_Golden_and_Honeypot/README.md) · [SETUP.md](Reporte_Golden_and_Honeypot/SETUP.md) · [INTEGRACION.md](Reporte_Golden_and_Honeypot/INTEGRACION.md) |
| UI de etiquetado Silver → Golden | [Silver2Gold_UI/README.md](Silver2Gold_UI/README.md) |

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=2,12,20&height=120&section=footer" width="100%"/>

</div>


