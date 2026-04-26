import 'dotenv/config'
import cors from 'cors'
import express from 'express'
import mongoose from 'mongoose'
import { connectToDatabase, getDbConnectionState } from './db.js'

const app = express()
const port = Number(process.env.PORT || 5000)
let startupDbMessage = null

const DEFAULT_FILTER_FIELDS = [
  'channel_id',
  'channel_name',
  'channel_title',
  'title',
  'text',
  'description',
  'descripcion',
  'author',
  'group_name',
  'chat_title',
  'caption',
  'url',
]

const FILTER_FIELDS_BY_COLLECTION = {
  youtube_items: [
    'channel_id',
    'channel_name',
    'channel_title',
    'title',
    'description',
    'text',
    'url',
  ],
  telegram_messages: ['channel_name', 'group_name', 'chat_title', 'text', 'url'],
  tiktok_videos: [
    'author',
    'autor_username',
    'author_username',
    'channel_name',
    'description',
    'descripcion',
    'caption',
    'text',
    'url',
  ],
}

const DEDUPE_FIELDS_BY_COLLECTION = {
  youtube_items: ['video_id', 'id', 'url', 'channel_id', 'title'],
  telegram_messages: ['message_id', 'id', 'url', 'channel_id', 'chat_id', 'group_id'],
  tiktok_videos: [
    'video_id',
    'aweme_id',
    'id',
    'url',
    'author',
    'autor_username',
    'author_username',
    'username',
    'user_name',
  ],
  tiktok_users: [
    'uid',
    'user_id',
    'id',
    'username',
    'user_name',
    'author',
    'autor_username',
    'author_username',
  ],
  tiktok_usuarios: [
    'uid',
    'user_id',
    'id',
    'username',
    'user_name',
    'author',
    'author_username',
  ],
  telegram_channels: ['channel_id', 'chat_id', 'group_id', 'peer_id', 'username', 'chat_username', 'group_name', 'channel_name'],
}

const SAFE_LABEL = 'seguro'
const RISK_LABELS = ['narcocultura', 'oferta de riesgo', 'reclutamiento']
const ALLOWED_LABELS = [SAFE_LABEL, ...RISK_LABELS]

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function collectCandidateValues(document, fields) {
  const values = new Set()

  fields.forEach((field) => {
    const rawValue = document?.[field]
    if (typeof rawValue === 'string') {
      const normalized = rawValue.trim()
      if (normalized) {
        values.add(normalized)
      }
      return
    }

    if (typeof rawValue === 'number') {
      values.add(rawValue)
    }
  })

  return [...values]
}

function buildLookupQuery(targetFields, candidateValues) {
  if (candidateValues.length === 0 || targetFields.length === 0) {
    return null
  }

  const orConditions = []

  candidateValues.forEach((value) => {
    targetFields.forEach((field) => {
      if (typeof value === 'string') {
        orConditions.push({
          [field]: {
            $regex: `^${escapeRegex(value)}$`,
            $options: 'i',
          },
        })
      } else {
        orConditions.push({ [field]: value })
      }
    })
  })

  return orConditions.length > 0 ? { $or: orConditions } : null
}

function normalizeFieldValue(value) {
  if (typeof value === 'string') {
    const normalized = value.trim()
    return normalized || null
  }

  if (typeof value === 'number') {
    return value
  }

  return null
}

function buildDedupQuery(document, dedupeFields) {
  const conditions = []

  if (document?._id !== undefined && document?._id !== null) {
    conditions.push({ _id: document._id })
  }

  dedupeFields.forEach((field) => {
    const normalizedValue = normalizeFieldValue(document?.[field])
    if (normalizedValue === null) {
      return
    }

    if (typeof normalizedValue === 'string') {
      conditions.push({
        [field]: {
          $regex: `^${escapeRegex(normalizedValue)}$`,
          $options: 'i',
        },
      })
      return
    }

    conditions.push({ [field]: normalizedValue })
  })

  return conditions.length > 0 ? { $or: conditions } : null
}

async function upsertDocumentWithDedup({
  targetCollection,
  collectionName,
  document,
}) {
  if (!document || typeof document !== 'object') {
    return { copied: false, merged: false }
  }

  const dedupeFields = DEDUPE_FIELDS_BY_COLLECTION[collectionName] || []
  const dedupeQuery = buildDedupQuery(document, dedupeFields)

  let targetId = document._id
  let merged = false

  if (dedupeQuery) {
    const existing = await targetCollection.findOne(dedupeQuery, {
      projection: { _id: 1 },
    })

    if (existing?._id !== undefined && existing?._id !== null) {
      targetId = existing._id
      merged = String(existing._id) !== String(document._id)
    }
  }

  if (targetId === undefined || targetId === null) {
    return { copied: false, merged: false }
  }

  const replacement = {
    ...document,
    _id: targetId,
  }

  await targetCollection.replaceOne({ _id: targetId }, replacement, { upsert: true })

  return { copied: true, merged }
}

async function upsertDocumentsWithDedup(targetCollection, collectionName, documents) {
  const uniqueById = new Map()

  documents.forEach((document) => {
    if (document?._id !== undefined && document?._id !== null) {
      uniqueById.set(String(document._id), document)
    }
  })

  const uniqueDocuments = [...uniqueById.values()]
  if (uniqueDocuments.length === 0) {
    return { attempted: 0, copied: 0, merged: 0 }
  }

  let copied = 0
  let merged = 0

  for (const document of uniqueDocuments) {
    const result = await upsertDocumentWithDedup({
      targetCollection,
      collectionName,
      document,
    })

    if (result.copied) {
      copied += 1
    }

    if (result.merged) {
      merged += 1
    }
  }

  return {
    attempted: uniqueDocuments.length,
    copied,
    merged,
  }
}

async function copyRelatedDocumentsToGolden({
  sourceCollection,
  sourceDoc,
  sourceDb,
  goldenDb,
  labels,
  moderationMeta,
}) {
  const relatedResults = []

  if (sourceCollection === 'tiktok_videos') {
    const candidateValues = collectCandidateValues(sourceDoc, [
      'autor_username',
      'author',
      'author_username',
      'username',
      'user_name',
      'channel_name',
      'creator_username',
      'owner_username',
    ])

    const query = buildLookupQuery(
      [
        'autor_username',
        'author',
        'author_username',
        'username',
        'user_name',
        'channel_name',
        'creator_username',
        'owner_username',
      ],
      candidateValues,
    )

    if (query) {
      const [usersFromTiktokUsers, usersFromTiktokUsuarios] = await Promise.all([
        sourceDb.collection('tiktok_users').find(query).limit(250).toArray(),
        sourceDb.collection('tiktok_usuarios').find(query).limit(250).toArray(),
      ])

      const uniqueRelatedDocs = [
        ...new Map(
          [...usersFromTiktokUsers, ...usersFromTiktokUsuarios].map((document) => [
            String(document._id),
            document,
          ]),
        ).values(),
      ]

      const taggedDocs = uniqueRelatedDocs.map((document) => ({
        ...document,
        etiqueta: labels,
        etiquetado_por: moderationMeta.taggedBy,
        etiquetado_en: moderationMeta.taggedAt,
        moderation: moderationMeta,
      }))

      const copyStats = await upsertDocumentsWithDedup(
        goldenDb.collection('tiktok_users'),
        'tiktok_users',
        taggedDocs,
      )

      relatedResults.push({
        collection: 'tiktok_users',
        criteriaValues: candidateValues.length,
        matched: uniqueRelatedDocs.length,
        copied: copyStats.copied,
        merged: copyStats.merged,
      })
    }
  }

  if (sourceCollection === 'telegram_messages') {
    const candidateValues = collectCandidateValues(sourceDoc, [
      'group_name',
      'channel_name',
      'chat_title',
      'username',
      'chat_username',
      'channel_id',
      'chat_id',
      'group_id',
      'peer_id',
    ])

    const query = buildLookupQuery(
      [
        'group_name',
        'channel_name',
        'chat_title',
        'username',
        'chat_username',
        'channel_id',
        'chat_id',
        'group_id',
        'peer_id',
        'title',
        'name',
      ],
      candidateValues,
    )

    if (query) {
      const relatedDocs = await sourceDb
        .collection('telegram_channels')
        .find(query)
        .limit(250)
        .toArray()

      const taggedDocs = relatedDocs.map((document) => ({
        ...document,
        etiqueta: labels,
        etiquetado_por: moderationMeta.taggedBy,
        etiquetado_en: moderationMeta.taggedAt,
        moderation: moderationMeta,
      }))

      const copyStats = await upsertDocumentsWithDedup(
        goldenDb.collection('telegram_channels'),
        'telegram_channels',
        taggedDocs,
      )

      relatedResults.push({
        collection: 'telegram_channels',
        criteriaValues: candidateValues.length,
        matched: relatedDocs.length,
        copied: copyStats.copied,
        merged: copyStats.merged,
      })
    }
  }

  return relatedResults
}

app.use(cors())
app.use(express.json())

app.get('/', (_req, res) => {
  res.json({
    ok: true,
    message: 'API is running',
    endpoints: ['/api/health', '/api/sample'],
  })
})

app.get('/api/health', async (_req, res) => {
  if (!process.env.MONGODB_URI) {
    return res.status(503).json({
      ok: false,
      message: 'Set MONGODB_URI in .env to connect MongoDB Atlas',
      dbState: getDbConnectionState(),
    })
  }

  try {
    const db = mongoose.connection.db
    if (!db) {
      return res.status(503).json({
        ok: false,
        message: 'MongoDB is not connected yet',
        dbState: getDbConnectionState(),
      })
    }

    await db.admin().ping()

    return res.json({
      ok: true,
      message: 'API and MongoDB Atlas connection are healthy',
      dbState: getDbConnectionState(),
    })
  } catch (error) {
    return res.status(500).json({
      ok: false,
      message: 'MongoDB ping failed',
      dbState: getDbConnectionState(),
      error: error instanceof Error ? error.message : 'Unknown error',
    })
  }
})

app.get('/api/sample', (_req, res) => {
  res.json({
    ok: true,
    data: [
      { id: 1, label: 'Mongo Atlas connected endpoint' },
      { id: 2, label: 'Ready for your collections and queries' },
    ],
  })
})

app.get('/api/catalog', async (_req, res) => {
  try {
    const client = mongoose.connection.getClient()
    const adminDb = client.db().admin()

    if (!mongoose.connection.db) {
      return res.status(503).json({
        ok: false,
        message: 'MongoDB is not connected yet',
      })
    }

    const databases = await adminDb.listDatabases()
    const visibleDatabases = databases.databases.filter(
      (database) => !['admin', 'local', 'config'].includes(database.name),
    )

    const catalog = await Promise.all(
      visibleDatabases.map(async (database) => {
        const collections = await client
          .db(database.name)
          .listCollections({}, { nameOnly: true })
          .toArray()

        return {
          name: database.name,
          sizeOnDisk: database.sizeOnDisk,
          empty: database.empty,
          collections: collections.map((collection) => collection.name).sort(),
        }
      }),
    )

    return res.json({
      ok: true,
      databases: catalog.sort((left, right) => left.name.localeCompare(right.name)),
    })
  } catch (error) {
    return res.status(500).json({
      ok: false,
      message: 'Failed to load database catalog',
      error: error instanceof Error ? error.message : 'Unknown error',
    })
  }
})

app.get('/api/catalog/:database/:collection/preview', async (req, res) => {
  try {
    const { database, collection } = req.params
    const skip = Math.max(0, Number.parseInt(req.query.skip ?? '0', 10) || 0)
    const limit = Math.min(
      25,
      Math.max(1, Number.parseInt(req.query.limit ?? '5', 10) || 5),
    )
    const filterField =
      typeof req.query.filterField === 'string' ? req.query.filterField.trim() : ''
    const filterValue =
      typeof req.query.filterValue === 'string' ? req.query.filterValue.trim() : ''
    const client = mongoose.connection.getClient()

    if (!mongoose.connection.db) {
      return res.status(503).json({
        ok: false,
        message: 'MongoDB is not connected yet',
      })
    }

    const allowedFields =
      FILTER_FIELDS_BY_COLLECTION[collection] || DEFAULT_FILTER_FIELDS

    if (filterField && !allowedFields.includes(filterField)) {
      return res.status(400).json({
        ok: false,
        message: `Invalid filter field: ${filterField}`,
      })
    }

    let query = {}
    if (filterValue) {
      const fieldsToSearch = filterField ? [filterField] : allowedFields
      const escapedValue = escapeRegex(filterValue)
      query = {
        $or: fieldsToSearch.map((field) => ({
          [field]: { $regex: escapedValue, $options: 'i' },
        })),
      }
    }

    const mongoCollection = client.db(database).collection(collection)

    const totalMatching = await mongoCollection.countDocuments(query)

    const documents = await mongoCollection
      .find(query)
      .skip(skip)
      .limit(limit)
      .toArray()

    const nextSkip = skip + documents.length
    const hasMore = nextSkip < totalMatching

    return res.json({
      ok: true,
      database,
      collection,
      total: totalMatching,
      skip,
      limit,
      hasMore,
      nextSkip,
      filter: {
        field: filterField || null,
        value: filterValue || null,
      },
      documents: JSON.parse(JSON.stringify(documents)),
    })
  } catch (error) {
    return res.status(500).json({
      ok: false,
      message: 'Failed to load collection preview',
      error: error instanceof Error ? error.message : 'Unknown error',
    })
  }
})

app.post('/api/moderation/label', async (req, res) => {
  try {
    const {
      sourceDatabase,
      sourceCollection,
      decision,
      labels,
      documentId,
      taggedBy,
    } = req.body

    if (!mongoose.connection.db) {
      return res.status(503).json({
        ok: false,
        message: 'MongoDB is not connected yet',
      })
    }

    if (!sourceDatabase || !sourceCollection || !documentId) {
      return res.status(400).json({
        ok: false,
        message: 'sourceDatabase, sourceCollection and documentId are required',
      })
    }

    const incomingLabels = Array.isArray(labels)
      ? labels
      : typeof decision === 'string'
        ? [decision]
        : []

    const normalizedLabels = [
      ...new Set(
        incomingLabels
          .map((label) =>
            typeof label === 'string' ? label.trim().toLowerCase() : '',
          )
          .filter(Boolean),
      ),
    ]

    if (normalizedLabels.length === 0) {
      return res.status(400).json({
        ok: false,
        message:
          'labels is required and must include seguro, narcocultura, oferta de riesgo or reclutamiento',
      })
    }

    const invalidLabels = normalizedLabels.filter(
      (label) => !ALLOWED_LABELS.includes(label),
    )

    if (invalidLabels.length > 0) {
      return res.status(400).json({
        ok: false,
        message: `Invalid labels: ${invalidLabels.join(', ')}`,
      })
    }

    if (normalizedLabels.includes(SAFE_LABEL) && normalizedLabels.length > 1) {
      return res.status(400).json({
        ok: false,
        message: 'seguro cannot be combined with other labels',
      })
    }

    const normalizedTaggedBy =
      typeof taggedBy === 'string' && taggedBy.trim()
        ? taggedBy.trim()
        : 'usuario-sin-perfil'
    const taggedAt = new Date().toISOString()
    const moderationMeta = {
      taggedBy: normalizedTaggedBy,
      taggedAt,
      labels: normalizedLabels,
      sourceDatabase,
      sourceCollection,
    }

    if (normalizedLabels.includes(SAFE_LABEL)) {
      return res.json({
        ok: true,
        skipped: true,
        labels: normalizedLabels,
        taggedBy: normalizedTaggedBy,
        taggedAt,
        message: 'Seguro: no se copia a Golden',
      })
    }

    const client = mongoose.connection.getClient()
    const sourceDb = client.db(sourceDatabase)
    const sourceColl = sourceDb.collection(sourceCollection)
    const goldenDbName = process.env.GOLDEN_DATABASE || 'golden'
    const goldenDb = client.db(goldenDbName)
    const goldenColl = goldenDb.collection(sourceCollection)

    let sourceDoc = await sourceColl.findOne({ _id: documentId })

    if (!sourceDoc && mongoose.isValidObjectId(documentId)) {
      sourceDoc = await sourceColl.findOne({
        _id: new mongoose.Types.ObjectId(String(documentId)),
      })
    }

    if (!sourceDoc) {
      return res.status(404).json({
        ok: false,
        message: 'No se encontro el documento en la fuente',
      })
    }

    const sourceDocWithLabel = {
      ...sourceDoc,
      etiqueta: normalizedLabels,
      etiquetado_por: normalizedTaggedBy,
      etiquetado_en: taggedAt,
      moderation: moderationMeta,
    }

    const mainCopyResult = await upsertDocumentWithDedup({
      targetCollection: goldenColl,
      collectionName: sourceCollection,
      document: sourceDocWithLabel,
    })

    const relatedCopies = await copyRelatedDocumentsToGolden({
      sourceCollection,
      sourceDoc,
      sourceDb,
      goldenDb,
      labels: normalizedLabels,
      moderationMeta,
    })

    return res.json({
      ok: true,
      copied: true,
      targetDatabase: goldenDbName,
      targetCollection: sourceCollection,
      documentId: sourceDoc._id,
      labels: normalizedLabels,
      taggedBy: normalizedTaggedBy,
      taggedAt,
      mergedMain: mainCopyResult.merged,
      relatedCopies,
    })
  } catch (error) {
    return res.status(500).json({
      ok: false,
      message: 'Failed to process moderation decision',
      error: error instanceof Error ? error.message : 'Unknown error',
    })
  }
})

async function startServer() {
  try {
    const dbResult = await connectToDatabase()
    if (!dbResult.connected) {
      startupDbMessage = dbResult.reason
      console.warn(`MongoDB not connected: ${dbResult.reason}`)
    }

    app.listen(port, () => {
      console.log(`API listening on http://localhost:${port}`)
      if (startupDbMessage) {
        console.log('Create a .env file from .env.example and set MONGODB_URI')
      }
    })
  } catch (error) {
    console.error('Failed to start API server:', error)
    process.exit(1)
  }
}

startServer()
