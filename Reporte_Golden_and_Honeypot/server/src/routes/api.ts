import { Express, Request, Response } from 'express';
import mongoose from 'mongoose';
import { ContentItem, TelegramChannel } from '../models/schemas';

type SourceName = 'youtube' | 'telegram' | 'tiktok';

interface SourceStats {
  _id: SourceName;
  count: number;
  totalViews: number;
  totalLikes: number;
}

interface TrendPoint {
  _id: {
    source: SourceName;
    date: string;
  };
  count: number;
  totalViews: number;
  totalEngagement: number;
}

const getLegacyStats = async (): Promise<{ totalItems: number; totalChannels: number; itemsBySource: SourceStats[] } | null> => {
  const db = mongoose.connection.db;
  if (!db) return null;

  const hasYoutube = await db.listCollections({ name: 'youtube_items' }).hasNext();
  if (!hasYoutube) return null;

  const [youtubeCount, telegramCount, tiktokCount, totalChannels] = await Promise.all([
    db.collection('youtube_items').countDocuments(),
    db.collection('telegram_messages').countDocuments(),
    db.collection('tiktok_videos').countDocuments(),
    db.collection('telegram_channels').countDocuments(),
  ]);

  const [youtubeAgg, telegramAgg, tiktokAgg] = await Promise.all([
    db.collection('youtube_items')
      .aggregate([{ $group: { _id: null, totalViews: { $sum: { $ifNull: ['$view_count', 0] } }, totalLikes: { $sum: { $ifNull: ['$like_count', 0] } } } }])
      .toArray(),
    db.collection('telegram_messages')
      .aggregate([{ $group: { _id: null, totalViews: { $sum: { $ifNull: ['$views', 0] } } } }])
      .toArray(),
    db.collection('tiktok_videos')
      .aggregate([{ $group: { _id: null, totalViews: { $sum: { $ifNull: ['$stats.vistas', 0] } }, totalLikes: { $sum: { $ifNull: ['$stats.likes', 0] } } } }])
      .toArray(),
  ]);

  const itemsBySource: SourceStats[] = [
    {
      _id: 'youtube',
      count: youtubeCount,
      totalViews: Number(youtubeAgg[0]?.totalViews || 0),
      totalLikes: Number(youtubeAgg[0]?.totalLikes || 0),
    },
    {
      _id: 'telegram',
      count: telegramCount,
      totalViews: Number(telegramAgg[0]?.totalViews || 0),
      totalLikes: 0,
    },
    {
      _id: 'tiktok',
      count: tiktokCount,
      totalViews: Number(tiktokAgg[0]?.totalViews || 0),
      totalLikes: Number(tiktokAgg[0]?.totalLikes || 0),
    },
  ];

  return {
    totalItems: youtubeCount + telegramCount + tiktokCount,
    totalChannels,
    itemsBySource,
  };
};

const getLegacyTrends = async (fromDate: Date): Promise<TrendPoint[] | null> => {
  const db = mongoose.connection.db;
  if (!db) return null;

  const hasYoutube = await db.listCollections({ name: 'youtube_items' }).hasNext();
  if (!hasYoutube) return null;

  const [youtube, telegram, tiktok] = await Promise.all([
    db.collection('youtube_items')
      .aggregate<TrendPoint>([
        { $addFields: { parsedDate: { $dateFromString: { dateString: '$published_at', onError: null, onNull: null } } } },
        { $match: { parsedDate: { $gte: fromDate } } },
        {
          $group: {
            _id: {
              source: 'youtube',
              date: { $dateToString: { format: '%Y-%m-%d', date: '$parsedDate' } },
            },
            count: { $sum: 1 },
            totalViews: { $sum: { $ifNull: ['$view_count', 0] } },
            totalEngagement: { $sum: { $add: [{ $ifNull: ['$like_count', 0] }, { $ifNull: ['$comment_count', 0] }] } },
          },
        },
      ])
      .toArray(),
    db.collection('telegram_messages')
      .aggregate<TrendPoint>([
        { $addFields: { parsedDate: { $dateFromString: { dateString: '$date', onError: null, onNull: null } } } },
        { $match: { parsedDate: { $gte: fromDate } } },
        {
          $group: {
            _id: {
              source: 'telegram',
              date: { $dateToString: { format: '%Y-%m-%d', date: '$parsedDate' } },
            },
            count: { $sum: 1 },
            totalViews: { $sum: { $ifNull: ['$views', 0] } },
            totalEngagement: { $sum: { $ifNull: ['$forwards', 0] } },
          },
        },
      ])
      .toArray(),
    db.collection('tiktok_videos')
      .aggregate<TrendPoint>([
        { $addFields: { parsedDate: { $dateFromString: { dateString: '$fecha_publicacion', onError: null, onNull: null } } } },
        { $match: { parsedDate: { $gte: fromDate } } },
        {
          $group: {
            _id: {
              source: 'tiktok',
              date: { $dateToString: { format: '%Y-%m-%d', date: '$parsedDate' } },
            },
            count: { $sum: 1 },
            totalViews: { $sum: { $ifNull: ['$stats.vistas', 0] } },
            totalEngagement: {
              $sum: {
                $add: [
                  { $ifNull: ['$stats.likes', 0] },
                  { $ifNull: ['$stats.comentarios', 0] },
                  { $ifNull: ['$stats.compartidos', 0] },
                ],
              },
            },
          },
        },
      ])
      .toArray(),
  ]);

  return [...youtube, ...telegram, ...tiktok].sort((a, b) => a._id.date.localeCompare(b._id.date));
};

export const setupRoutes = (app: Express) => {
  // Obtener estadísticas generales
  app.get('/api/stats', async (req: Request, res: Response) => {
    try {
      const totalItems = await ContentItem.countDocuments();
      const itemsBySource = await ContentItem.aggregate([
        {
          $group: {
            _id: '$source',
            count: { $sum: 1 },
            totalViews: { $sum: '$engagement.views' },
            totalLikes: { $sum: '$engagement.likes' },
          },
        },
      ]);

      const totalChannels = await TelegramChannel.countDocuments();

      // Fallback para la base "centinela" con colecciones legadas separadas por fuente.
      if (totalItems === 0 && totalChannels === 0) {
        const legacy = await getLegacyStats();
        if (legacy) {
          res.json(legacy);
          return;
        }
      }

      res.json({
        totalItems,
        totalChannels,
        itemsBySource,
      });
    } catch (error) {
      res.status(500).json({ error: 'Error obteniendo estadísticas' });
    }
  });

  // Obtener contenido por fuente
  app.get('/api/content/:source', async (req: Request, res: Response) => {
    try {
      const { source } = req.params;
      const { limit = 50, skip = 0 } = req.query;

      const items = await ContentItem.find({ source })
        .limit(Number(limit))
        .skip(Number(skip))
        .sort({ createdAt: -1 });

      const total = await ContentItem.countDocuments({ source });

      res.json({
        items,
        total,
        page: Math.floor(Number(skip) / Number(limit)) + 1,
        pages: Math.ceil(total / Number(limit)),
      });
    } catch (error) {
      res.status(500).json({ error: 'Error obteniendo contenido' });
    }
  });

  // Obtener tendencias (últimos 30 días)
  app.get('/api/trends', async (req: Request, res: Response) => {
    try {
      const thirtyDaysAgo = new Date();
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

      const trends = await ContentItem.aggregate([
        {
          $match: {
            createdAt: { $gte: thirtyDaysAgo },
          },
        },
        {
          $group: {
            _id: {
              source: '$source',
              date: {
                $dateToString: {
                  format: '%Y-%m-%d',
                  date: '$createdAt',
                },
              },
            },
            count: { $sum: 1 },
            totalViews: { $sum: '$engagement.views' },
            totalEngagement: {
              $sum: {
                $add: [
                  { $ifNull: ['$engagement.likes', 0] },
                  { $ifNull: ['$engagement.comments', 0] },
                  { $ifNull: ['$engagement.shares', 0] },
                ],
              },
            },
          },
        },
        {
          $sort: { '_id.date': 1 },
        },
      ]);

      if (trends.length === 0) {
        const legacy = await getLegacyTrends(thirtyDaysAgo);
        if (legacy) {
          res.json(legacy);
          return;
        }
      }

      res.json(trends);
    } catch (error) {
      res.status(500).json({ error: 'Error obteniendo tendencias' });
    }
  });

  // Obtener canales de Telegram
  app.get('/api/telegram/channels', async (req: Request, res: Response) => {
    try {
      const { limit = 50, skip = 0 } = req.query;

      const channels = await TelegramChannel.find()
        .limit(Number(limit))
        .skip(Number(skip))
        .sort({ members: -1 });

      const total = await TelegramChannel.countDocuments();

      res.json({
        channels,
        total,
        page: Math.floor(Number(skip) / Number(limit)) + 1,
      });
    } catch (error) {
      res.status(500).json({ error: 'Error obteniendo canales' });
    }
  });

  // Buscar contenido por palabras clave
  app.get('/api/search', async (req: Request, res: Response) => {
    try {
      const { q, source } = req.query;

      const query: any = {
        $or: [
          { title: { $regex: q, $options: 'i' } },
          { description: { $regex: q, $options: 'i' } },
        ],
      };

      if (source) {
        query.source = source;
      }

      const results = await ContentItem.find(query).limit(100);

      res.json(results);
    } catch (error) {
      res.status(500).json({ error: 'Error en búsqueda' });
    }
  });
};
