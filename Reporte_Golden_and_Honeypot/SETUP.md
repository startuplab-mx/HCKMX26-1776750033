# Guia de Configuracion Rapida

## 1. Requisitos

- Node.js 18+
- npm 9+
- Acceso a MongoDB (local o Atlas)

## 2. Instalar dependencias

Desde la raiz del proyecto:

```bash
npm install
npm --prefix server install
npm --prefix client install
```

## 3. Configurar entorno

Crear `server/.env` a partir de `server/.env.example`.

Ejemplo:

```env
MONGO_URI=mongodb://localhost:27017/centinela
PORT=5000
```

Si usas Atlas:

```env
MONGO_URI=mongodb+srv://<usuario>:<password>@<cluster>/<base>?retryWrites=true&w=majority
PORT=5000
```

## 4. Ejecutar en desarrollo

```bash
npm run dev
```

Servicios:

- Backend: http://localhost:5000
- Frontend: http://localhost:3000 (o puerto libre siguiente)

## 5. Verificacion rapida

1. Abrir el frontend en el navegador.
2. Confirmar que se muestran KPIs y grafica de tendencias.
3. Probar endpoint de salud funcional:

```bash
curl http://localhost:5000/api/stats
```

## 6. Endpoints principales

- `GET /api/stats`
- `GET /api/trends`
- `GET /api/content/:source?limit=50&skip=0`
- `GET /api/telegram/channels?limit=50&skip=0`
- `GET /api/search?q=termino&source=youtube`

## 7. Build de produccion

```bash
npm run build
npm --prefix server start
```

## 8. Problemas comunes

### MongoDB connection failed

- Verifica credenciales y base en `MONGO_URI`.
- Si usas Atlas, revisa whitelist de IP y usuario.

### Puerto ocupado

- Cambia `PORT` en `server/.env`.
- Vite cambiara de puerto automaticamente si el 3000 esta ocupado.

### Dependencias rotas

```bash
npm --prefix server install
npm --prefix client install
```

## 9. Recomendacion para GitHub

- No subir `server/.env`.
- Mantener solo placeholders en `server/.env.example`.
- Evitar rutas de sistema en docs y scripts.
