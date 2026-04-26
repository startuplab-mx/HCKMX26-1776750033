# Centinela Dashboard

Dashboard de monitoreo para contenido de YouTube, Telegram y TikTok.

## Resumen

- Frontend: React + TypeScript + Vite + Tailwind + Recharts
- Backend: Express + TypeScript + MongoDB (Mongoose)
- Estado actual de UI: sin mapas, enfocado en KPIs, tendencias e insights

## Stack

### Frontend

- React 18
- TypeScript
- Vite
- Tailwind CSS
- Recharts
- Axios

### Backend

- Node.js
- Express
- TypeScript
- Mongoose
- dotenv

## Estructura del Proyecto

```text
.
|-- client/
|   |-- src/
|   |   |-- components/
|   |   |-- pages/
|   |   |-- App.tsx
|   |   `-- main.tsx
|   `-- package.json
|-- server/
|   |-- src/
|   |   |-- config/mongodb.ts
|   |   |-- models/schemas.ts
|   |   |-- routes/api.ts
|   |   `-- index.ts
|   `-- package.json
|-- INTEGRACION.md
|-- SETUP.md
`-- package.json
```

## Requisitos

- Node.js 18+
- npm 9+
- MongoDB local o Atlas

## Inicio Rapido

1. Instalar dependencias en raiz y subproyectos:

```bash
npm install
npm --prefix server install
npm --prefix client install
```

2. Crear archivo de entorno en backend:

Archivo: `server/.env`

```env
MONGO_URI=mongodb+srv://<usuario>:<password>@<cluster>/<base>?retryWrites=true&w=majority
PORT=5000
```

3. Levantar frontend y backend:

```bash
npm run dev
```

4. Abrir aplicacion:

- Frontend: http://localhost:3000
- API: http://localhost:5000

## Scripts Disponibles

En raiz:

- `npm run dev`: ejecuta cliente y servidor en paralelo
- `npm run build`: compila server y client
- `npm run start`: inicia backend compilado

Backend (`server/package.json`):

- `npm --prefix server run dev`
- `npm --prefix server run build`
- `npm --prefix server run start`

Frontend (`client/package.json`):

- `npm --prefix client run dev`
- `npm --prefix client run build`
- `npm --prefix client run preview`

## API

Base URL en desarrollo: `http://localhost:5000`

- `GET /api/stats`
	Devuelve totales globales, canales y desglose por fuente.
- `GET /api/trends`
	Devuelve tendencias de los ultimos 30 dias por fecha y fuente.
- `GET /api/content/:source?limit=50&skip=0`
	Lista contenido por fuente (`youtube`, `telegram`, `tiktok`).
- `GET /api/telegram/channels?limit=50&skip=0`
	Lista canales de Telegram.
- `GET /api/search?q=texto&source=youtube`
	Busqueda por titulo y descripcion.

## Build y Produccion

Compilar todo:

```bash
npm run build
```

Iniciar backend compilado:

```bash
npm run start
```

## GitHub Checklist

- No incluir `server/.env`
- Mantener secretos solo en entorno local o CI secrets
- Usar placeholders en `server/.env.example`
- Mantener rutas relativas en docs y scripts

## Troubleshooting

### Error conectando a MongoDB

- Verifica `MONGO_URI`
- Si usas Atlas, revisa IP allowlist y credenciales
- Confirma que la base y colecciones esperadas existen

### Puerto en uso

- Cambia `PORT` en `server/.env`
- Vite puede tomar el siguiente puerto libre automaticamente

### `npm` no reconocido en Windows

Prueba primero con:

```powershell
npm.cmd run dev
```

## Documentacion Relacionada

- Setup rapido: `SETUP.md`
- Integraciones externas: `INTEGRACION.md`
