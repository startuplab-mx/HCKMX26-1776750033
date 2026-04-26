# Guía de Integración con APIs de Redes Sociales

## 1. Integración con YouTube Data API

### Requisitos:
1. Crear proyecto en Google Cloud Console
2. Activar YouTube Data API v3
3. Obtener API Key

### Implementar en el backend:

Agregar a `server/package.json`:
```json
"googleapis": "^118.0.0"
```

Crear `server/src/services/youtubeService.ts`:

```typescript
import { google } from 'googleapis';
import { ContentItem } from '../models/schemas';

const youtube = google.youtube({
  version: 'v3',
  auth: process.env.YOUTUBE_API_KEY,
});

export const searchYouTubeVideos = async (query: string) => {
  try {
    const response = await youtube.search.list({
      part: ['snippet'],
      q: query,
      type: ['video'],
      maxResults: 50,
      regionCode: 'MX', // Cambiar según necesidad
    });

    for (const item of response.data.items || []) {
      const videoId = item.id?.videoId;
      
      // Obtener estadísticas del video
      const stats = await youtube.videos.list({
        part: ['statistics', 'contentDetails'],
        id: [videoId],
      });

      const video = stats.data.items?.[0];
      
      await ContentItem.updateOne(
        { source: 'youtube', videoId },
        {
          source: 'youtube',
          title: item.snippet?.title,
          description: item.snippet?.description,
          url: `https://youtube.com/watch?v=${videoId}`,
          engagement: {
            views: Number(video?.statistics?.viewCount) || 0,
            likes: Number(video?.statistics?.likeCount) || 0,
            comments: Number(video?.statistics?.commentCount) || 0,
          },
        },
        { upsert: true }
      );
    }

    console.log('✅ Datos de YouTube sincronizados');
  } catch (error) {
    console.error('❌ Error sincronizando YouTube:', error);
  }
};
```

Agregar ruta para ejecutar sincronización:

```typescript
// En server/src/routes/api.ts
app.post('/api/admin/sync/youtube', async (req: Request, res: Response) => {
  // Verificar autenticación
  try {
    await searchYouTubeVideos('tu-keyword-aqui');
    res.json({ message: 'Sincronización iniciada' });
  } catch (error) {
    res.status(500).json({ error: 'Error en sincronización' });
  }
});
```

## 2. Integración con Bot de Telegram

### Requisitos:
1. Crear bot con @BotFather en Telegram
2. Obtener API Token

### Implementar en el backend:

Agregar a `server/package.json`:
```json
"telegraf": "^4.12.0"
```

Crear `server/src/services/telegramService.ts`:

```typescript
import { Telegraf } from 'telegraf';
import { ContentItem, TelegramChannel } from '../models/schemas';

const bot = new Telegraf(process.env.TELEGRAM_BOT_TOKEN!);

export const monitorTelegramChannel = async (channelId: string) => {
  try {
    // Este es un ejemplo básico
    // Para monitoreo real, necesitarás usar Telegram Client API
    // y tener acceso autorizado a los canales
    
    // Guardar canal
    await TelegramChannel.updateOne(
      { channel_id: channelId },
      {
        channel_id: channelId,
        name: 'Canal de Telegram',
        members: 0,
      },
      { upsert: true }
    );

    console.log('✅ Canal de Telegram registrado');
  } catch (error) {
    console.error('❌ Error con Telegram:', error);
  }
};
```

## 3. Integración con TikTok Research API

### Requisitos:
1. Aplicar para acceso a TikTok Research API
2. Obtener credentials de OAuth

### Implementar en el backend:

Agregar a `server/package.json`:
```json
"@tiktok-official/research": "^1.0.0"
```

Crear `server/src/services/tiktokService.ts`:

```typescript
import { ContentItem } from '../models/schemas';

export const searchTikTokVideos = async (keyword: string) => {
  try {
    // Implementación según documentación de TikTok Research API
    const accessToken = process.env.TIKTOK_ACCESS_TOKEN;

    const response = await fetch('https://api.tiktok.com/v1/research/video/query', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: {
          search_term: keyword,
          publish_period: 7, // últimos 7 días
        },
        data_spec: {
          fields: ['video_id', 'video_description', 'video_view_count'],
        },
      }),
    });

    const data = await response.json();

    for (const video of data.data || []) {
      await ContentItem.updateOne(
        { source: 'tiktok', videoId: video.video_id },
        {
          source: 'tiktok',
          title: video.video_description,
          engagement: {
            views: video.video_view_count,
          },
        },
        { upsert: true }
      );
    }

    console.log('✅ Datos de TikTok sincronizados');
  } catch (error) {
    console.error('❌ Error sincronizando TikTok:', error);
  }
};
```

## 4. Crear Trabajos Programados (Cron Jobs)

Agregar a `server/package.json`:
```json
"node-cron": "^3.0.2"
```

Crear `server/src/jobs/syncJobs.ts`:

```typescript
import cron from 'node-cron';
import { searchYouTubeVideos } from '../services/youtubeService';
import { searchTikTokVideos } from '../services/tiktokService';

export const startSyncJobs = () => {
  // Sincronizar YouTube cada 6 horas
  cron.schedule('0 */6 * * *', async () => {
    console.log('🔄 Sincronizando datos de YouTube...');
    await searchYouTubeVideos('tu-keyword');
  });

  // Sincronizar TikTok cada 12 horas
  cron.schedule('0 */12 * * *', async () => {
    console.log('🔄 Sincronizando datos de TikTok...');
    await searchTikTokVideos('tu-keyword');
  });

  // Sincronizar Telegram cada 30 minutos
  cron.schedule('*/30 * * * *', async () => {
    console.log('🔄 Sincronizando datos de Telegram...');
    // Llamar a función de Telegram
  });
};
```

Integrar en `server/src/index.ts`:

```typescript
import { startSyncJobs } from './jobs/syncJobs';

// ... después de conectar a MongoDB
startSyncJobs();
```

## 5. Variables de Entorno

Actualizar `server/.env`:

```env
MONGO_URI=mongodb://localhost:27017/centinela
PORT=5000

# YouTube
YOUTUBE_API_KEY=tu_api_key_aqui

# Telegram
TELEGRAM_BOT_TOKEN=tu_token_aqui

# TikTok
TIKTOK_ACCESS_TOKEN=tu_token_aqui
TIKTOK_CLIENT_ID=tu_client_id_aqui
TIKTOK_CLIENT_SECRET=tu_secret_aqui

# Opcional
LOG_LEVEL=info
```

## 6. Seguridad

### Proteger Endpoints de Admin

```typescript
const adminAuth = (req: Request, res: Response, next: Function) => {
  const token = req.headers.authorization?.split(' ')[1];
  if (token === process.env.ADMIN_TOKEN) {
    next();
  } else {
    res.status(401).json({ error: 'Unauthorized' });
  }
};

app.post('/api/admin/sync/youtube', adminAuth, async (req, res) => {
  // ...
});
```

### Rate Limiting

```typescript
import rateLimit from 'express-rate-limit';

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutos
  max: 100, // límite de 100 requests por windowMs
});

app.use('/api/', limiter);
```

## Checklist de Implementacion

- [ ] Obtener credenciales de YouTube API
- [ ] Obtener credenciales de Telegram Bot
- [ ] Solicitar acceso a TikTok Research API
- [ ] Implementar servicios de sincronización
- [ ] Crear trabajos programados (cron)
- [ ] Agregar autenticación a endpoints admin
- [ ] Configurar rate limiting
- [ ] Agregar logging
- [ ] Hacer pruebas de carga
- [ ] Configurar alertas para errores

## Recursos

- [YouTube Data API](https://developers.google.com/youtube/v3)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [TikTok Research API](https://developers.tiktok.com/doc/research-api-overview)
- [Node Cron](https://github.com/kelektiv/node-cron)
