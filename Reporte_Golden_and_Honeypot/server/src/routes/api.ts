import { Express, Request, Response } from 'express';
import mongoose from 'mongoose';

// Campos de fecha candidatos, en orden de preferencia
const DATE_FIELDS = ['etiquetado_en', 'ultima_actualizacion', 'createTimeISO', 'fecha_publicacion', 'createdAt'];

async function getDb() {
  const db = mongoose.connection.db;
  if (!db) throw new Error('DB no conectada');
  return db;
}

export const setupRoutes = (app: Express) => {
  // Estadísticas: lista todas las colecciones de golden y cuenta documentos
  app.get('/api/stats', async (_req: Request, res: Response) => {
    try {
      const db = await getDb();
      const colInfos = await db.listCollections().toArray();

      const colStats = await Promise.all(
        colInfos.map(async (c) => ({
          name: c.name,
          count: await db.collection(c.name).estimatedDocumentCount(),
        }))
      );

      colStats.sort((a, b) => b.count - a.count);

      const totalItems = colStats.reduce((sum, c) => sum + c.count, 0);

      res.json({
        totalItems,
        collections: colStats,
        // Formato compatible con el frontend (itemsBySource)
        itemsBySource: colStats.map((c) => ({
          _id: c.name,
          count: c.count,
          totalViews: 0,
          totalLikes: 0,
        })),
      });
    } catch (error) {
      res.status(500).json({ error: 'Error obteniendo estadísticas' });
    }
  });

  // Tendencias: busca el primer campo de fecha disponible en cada colección
  app.get('/api/trends', async (_req: Request, res: Response) => {
    try {
      const db = await getDb();
      const colInfos = await db.listCollections().toArray();
      const thirtyDaysAgo = new Date();
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

      const allTrends: Array<{ _id: { source: string; date: string }; count: number }> = [];

      for (const colInfo of colInfos) {
        const col = db.collection(colInfo.name);

        // Detectar qué campo de fecha tiene esta colección
        const sample = await col.findOne({});
        if (!sample) continue;

        const dateField = DATE_FIELDS.find((f) => sample[f] != null);
        if (!dateField) continue;

        const trends = await col
          .aggregate([
            {
              $addFields: {
                _parsedDate: {
                  $dateFromString: {
                    dateString: { $toString: `$${dateField}` },
                    onError: null,
                    onNull: null,
                  },
                },
              },
            },
            { $match: { _parsedDate: { $gte: thirtyDaysAgo } } },
            {
              $group: {
                _id: {
                  source: colInfo.name,
                  date: { $dateToString: { format: '%Y-%m-%d', date: '$_parsedDate' } },
                },
                count: { $sum: 1 },
                totalViews: { $sum: 0 },
                totalEngagement: { $sum: 0 },
              },
            },
            { $sort: { '_id.date': 1 } },
          ])
          .toArray();

        allTrends.push(...(trends as typeof allTrends));
      }

      res.json(allTrends);
    } catch (error) {
      res.status(500).json({ error: 'Error obteniendo tendencias' });
    }
  });

  // Documentos recientes de cualquier colección
  app.get('/api/recent', async (req: Request, res: Response) => {
    try {
      const db = await getDb();
      const limit = Number(req.query.limit) || 20;
      const colInfos = await db.listCollections().toArray();

      const allDocs: Array<Record<string, unknown>> = [];

      for (const colInfo of colInfos) {
        const col = db.collection(colInfo.name);
        const sample = await col.findOne({});
        if (!sample) continue;

        const dateField = DATE_FIELDS.find((f) => sample[f] != null);
        const sort = dateField ? { [dateField]: -1 as const } : { _id: -1 as const };

        const docs = await col.find({}).sort(sort).limit(limit).toArray();
        docs.forEach((d) => { d['_collection'] = colInfo.name; });
        allDocs.push(...docs);
      }

      // Ordenar el combinado por _id descendente (aproximación)
      allDocs.sort((a, b) => String(b['_id']).localeCompare(String(a['_id'])));

      res.json(allDocs.slice(0, limit));
    } catch (error) {
      res.status(500).json({ error: 'Error obteniendo documentos recientes' });
    }
  });
};
