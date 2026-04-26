import 'dotenv/config'
import mongoose from 'mongoose'
import ExcelJS from 'exceljs'
import path from 'path'
import fs from 'fs'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// ── Config ─────────────────────────────────────────────────────────────────
const GOLDEN_DB   = process.env.GOLDEN_DATABASE || 'golden'
const EXPORTS_DIR = path.resolve(__dirname, '../exports_golden')
const OUTPUT_FILE = path.join(EXPORTS_DIR, `golden_export_${timestamp()}.xlsx`)

const LABEL_COLORS = {
  narcocultura:       { bg: 'FFFF4444', font: 'FFFFFFFF' },
  'oferta de riesgo': { bg: 'FFFF8C00', font: 'FFFFFFFF' },
  reclutamiento:      { bg: 'FFFFC107', font: 'FF1A1A1A' },
}

const HEADER_BG   = 'FF1A2535'
const HEADER_FONT = 'FFFFFFFF'
const ALT_ROW_BG  = 'FFF4F6F9'

// ── Normalizers ────────────────────────────────────────────────────────────
const NORMALIZERS = {
  youtube_items(doc) {
    return {
      plataforma: 'YouTube',
      fuente:     doc.channel_name || doc.channel_title || '',
      texto:      doc.title || doc.description || doc.text || '',
      url:        doc.url || '',
    }
  },
  telegram_messages(doc) {
    return {
      plataforma: 'Telegram',
      fuente:     doc.channel_name || doc.group_name || doc.chat_title || '',
      texto:      doc.text || '',
      url:        doc.url || '',
    }
  },
  telegram_channels(doc) {
    return {
      plataforma: 'Telegram Canales',
      fuente:     doc.title || (doc.username ? `@${doc.username}` : ''),
      texto:      doc.about || doc.description || '',
      url:        doc.username ? `https://t.me/${doc.username}` : (doc.url || ''),
    }
  },
  tiktok_videos(doc) {
    return {
      plataforma: 'TikTok Videos',
      fuente:     doc.author || doc.autor_username || doc.author_username || '',
      texto:      doc.descripcion || doc.description || doc.caption || doc.text || '',
      url:        doc.url || '',
    }
  },
  tiktok_users(doc) {
    return {
      plataforma: 'TikTok Usuarios',
      fuente:     doc.username || doc.user_name || doc.author || '',
      texto:      doc.bio || doc.signature || doc.descripcion || doc.description || '',
      url:        doc.url || doc.profile_url || '',
    }
  },
  tiktok_usuarios(doc) {
    return {
      plataforma: 'TikTok Usuarios',
      fuente:     doc.username || doc.user_name || doc.author || '',
      texto:      doc.bio || doc.signature || doc.descripcion || doc.description || '',
      url:        doc.url || doc.profile_url || '',
    }
  },
}

function normalizeDoc(collectionName, doc) {
  const fn = NORMALIZERS[collectionName]
  if (fn) return fn(doc)
  return {
    plataforma: collectionName,
    fuente:     doc.channel_name || doc.author || doc.username || '',
    texto:      doc.text || doc.description || doc.title || '',
    url:        doc.url || '',
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────
function timestamp() {
  return new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
}

function labelsText(doc) {
  const v = doc.etiqueta || doc.labels || doc.label
  if (Array.isArray(v)) return v.join(', ')
  return typeof v === 'string' ? v : ''
}

function primaryLabel(doc) {
  const v = doc.etiqueta || doc.labels || doc.label
  const arr = Array.isArray(v) ? v : (typeof v === 'string' ? [v] : [])
  return arr.find((l) => LABEL_COLORS[l]) || arr[0] || ''
}

function scoreText(doc) {
  if (typeof doc.riesgo_score === 'number') return `${(doc.riesgo_score * 100).toFixed(0)}%`
  return ''
}

function cell(fg, bold = false) {
  return { font: { color: { argb: fg }, bold }, alignment: { vertical: 'middle', wrapText: true } }
}

// ── Sheet builder ──────────────────────────────────────────────────────────
function applyHeader(sheet) {
  const cols = [
    { header: 'Plataforma',   key: 'plataforma',   width: 18 },
    { header: 'Fuente',       key: 'fuente',        width: 28 },
    { header: 'Texto',        key: 'texto',         width: 55 },
    { header: 'URL',          key: 'url',           width: 48 },
    { header: 'Etiquetas',    key: 'etiquetas',     width: 30 },
    { header: 'Score IA',     key: 'score',         width: 12 },
    { header: 'Nivel Riesgo', key: 'nivel',         width: 16 },
    { header: 'Etiquetado por', key: 'taggedBy',    width: 20 },
    { header: 'Fecha',        key: 'taggedAt',      width: 22 },
  ]
  sheet.columns = cols

  const headerRow = sheet.getRow(1)
  headerRow.height = 30
  headerRow.eachCell((c) => {
    c.fill   = { type: 'pattern', pattern: 'solid', fgColor: { argb: HEADER_BG } }
    c.font   = { color: { argb: HEADER_FONT }, bold: true, size: 11 }
    c.alignment = { vertical: 'middle', horizontal: 'center', wrapText: false }
    c.border = {
      bottom: { style: 'medium', color: { argb: 'FF4A90D9' } },
    }
  })
}

function addDocRow(sheet, rowIdx, collectionName, doc) {
  const norm  = normalizeDoc(collectionName, doc)
  const label = primaryLabel(doc)
  const color = LABEL_COLORS[label]

  const row = sheet.addRow({
    plataforma: norm.plataforma,
    fuente:     norm.fuente,
    texto:      norm.texto,
    url:        norm.url,
    etiquetas:  labelsText(doc),
    score:      scoreText(doc),
    nivel:      doc.nivel_riesgo || '',
    taggedBy:   doc.etiquetado_por || doc.moderation?.taggedBy || '',
    taggedAt:   doc.etiquetado_en  || doc.moderation?.taggedAt || '',
  })

  row.height = 42

  // Alternate row background
  const rowBg = rowIdx % 2 === 0 ? ALT_ROW_BG : 'FFFFFFFF'

  row.eachCell((c, colNum) => {
    c.alignment = { vertical: 'middle', wrapText: true }
    c.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: rowBg } }
    c.font = { size: 10 }
  })

  // URL as hyperlink
  if (norm.url) {
    const urlCell = row.getCell('url')
    urlCell.value = { text: norm.url, hyperlink: norm.url }
    urlCell.font = { size: 10, color: { argb: 'FF1565C0' }, underline: true }
  }

  // Color label cell
  if (color) {
    const labelCell = row.getCell('etiquetas')
    labelCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: color.bg } }
    labelCell.font = { size: 10, color: { argb: color.font }, bold: true }
    labelCell.alignment = { vertical: 'middle', horizontal: 'center', wrapText: false }
  }

  return row
}

// ── Summary sheet ──────────────────────────────────────────────────────────
function buildSummarySheet(wb, stats, totalDocs) {
  const sheet = wb.addWorksheet('Resumen', { properties: { tabColor: { argb: 'FF1A2535' } } })

  sheet.columns = [
    { key: 'a', width: 28 },
    { key: 'b', width: 20 },
  ]

  function titleRow(text) {
    const r = sheet.addRow([text, ''])
    sheet.mergeCells(`A${r.number}:B${r.number}`)
    r.getCell('A').fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: HEADER_BG } }
    r.getCell('A').font = { color: { argb: HEADER_FONT }, bold: true, size: 13 }
    r.getCell('A').alignment = { horizontal: 'center', vertical: 'middle' }
    r.height = 28
    return r
  }

  function dataRow(label, value, bgArgb = 'FFFFFFFF') {
    const r = sheet.addRow([label, value])
    ;['A', 'B'].forEach((col) => {
      r.getCell(col).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: bgArgb } }
      r.getCell(col).font = { size: 11 }
      r.getCell(col).alignment = { vertical: 'middle' }
    })
    r.getCell('B').alignment = { vertical: 'middle', horizontal: 'right' }
    r.height = 22
    return r
  }

  titleRow('Exportación Golden — Centinela')
  dataRow('Fecha de exportación', new Date().toLocaleString('es-MX'), ALT_ROW_BG)
  dataRow('Total documentos exportados', totalDocs, ALT_ROW_BG)

  sheet.addRow([])

  titleRow('Registros por plataforma')
  Object.entries(stats.byCollection).forEach(([col, count], i) => {
    dataRow(col, count, i % 2 === 0 ? ALT_ROW_BG : 'FFFFFFFF')
  })

  sheet.addRow([])

  titleRow('Registros por etiqueta')
  Object.entries(stats.byLabel).forEach(([label, count], i) => {
    const color = LABEL_COLORS[label]
    const r = dataRow(label, count, color?.bg || (i % 2 === 0 ? ALT_ROW_BG : 'FFFFFFFF'))
    if (color) {
      ;['A', 'B'].forEach((col) => {
        r.getCell(col).font = { size: 11, color: { argb: color.font }, bold: true }
      })
    }
  })
}

// ── Main ───────────────────────────────────────────────────────────────────
async function main() {
  fs.mkdirSync(EXPORTS_DIR, { recursive: true })
  console.log('Conectando a MongoDB...')
  await mongoose.connect(process.env.MONGODB_URI)
  const client = mongoose.connection.getClient()
  const goldenDb = client.db(GOLDEN_DB)

  const collectionList = await goldenDb.listCollections().toArray()
  const collectionNames = collectionList.map((c) => c.name).sort()

  if (collectionNames.length === 0) {
    console.log(`No se encontraron colecciones en la base de datos "${GOLDEN_DB}".`)
    await mongoose.disconnect()
    return
  }

  console.log(`Colecciones encontradas: ${collectionNames.join(', ')}`)

  // Collect all data first so summary can be built before writing
  const allData = []
  const stats   = { byCollection: {}, byLabel: {} }
  let totalDocs = 0

  for (const colName of collectionNames) {
    const docs = await goldenDb.collection(colName).find({}).toArray()
    if (docs.length === 0) continue

    console.log(`  ${colName}: ${docs.length} documentos`)
    stats.byCollection[colName] = docs.length
    totalDocs += docs.length

    docs.forEach((doc) => {
      const labels = Array.isArray(doc.etiqueta) ? doc.etiqueta : (doc.etiqueta ? [doc.etiqueta] : [])
      labels.forEach((l) => { stats.byLabel[l] = (stats.byLabel[l] || 0) + 1 })
    })

    allData.push({ colName, docs })
  }

  // Build workbook — summary sheet first, then data sheets
  const wb = new ExcelJS.Workbook()
  wb.creator  = 'Centinela / Silver2Gold'
  wb.created  = new Date()
  wb.modified = new Date()

  buildSummarySheet(wb, stats, totalDocs)

  for (const { colName, docs } of allData) {
    const sheetName = colName.slice(0, 31)
    const sheet = wb.addWorksheet(sheetName, {
      views: [{ state: 'frozen', ySplit: 1 }],
    })
    applyHeader(sheet)
    docs.forEach((doc, idx) => addDocRow(sheet, idx, colName, doc))
    sheet.autoFilter = { from: 'A1', to: `I${docs.length + 1}` }
  }

  await wb.xlsx.writeFile(OUTPUT_FILE)
  console.log(`\nExportación lista: ${OUTPUT_FILE}`)
  console.log(`Total documentos: ${totalDocs}`)
  await mongoose.disconnect()
}

main().catch((err) => {
  console.error('Error durante la exportación:', err.message)
  process.exit(1)
})
