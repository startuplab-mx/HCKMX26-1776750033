# Hackaton UI + MongoDB Atlas

Proyecto base con:
- Frontend React + Vite
- Backend Express + Mongoose
- Conexión a MongoDB Atlas

## 1) Configurar MongoDB Atlas

1. Crea un cluster en MongoDB Atlas.
2. Crea un Database User con usuario y password.
3. En Network Access agrega tu IP (o 0.0.0.0/0 solo para pruebas).
4. Copia tu connection string de Atlas.

## 2) Variables de entorno

1. Duplica el archivo .env.example como .env
2. Completa MONGODB_URI con tus credenciales reales.

Ejemplo de MONGODB_URI:
mongodb+srv://usuario:password@cluster.xxxxx.mongodb.net/mi_db?retryWrites=true&w=majority

## 3) Instalar dependencias

npm install

## 4) Ejecutar frontend + backend

npm run dev:full

Esto levanta:
- Frontend en http://localhost:5173
- API en http://localhost:5000

## 5) Verificar conexión

- Endpoint de salud: GET /api/health
- En la UI principal se muestra el estado de conexión a Atlas.

## Scripts disponibles

- npm run dev: frontend Vite
- npm run server: API backend
- npm run server:dev: API en modo watch con nodemon
- npm run dev:full: frontend + backend en paralelo
- npm run build: build de frontend
