import { useEffect, useMemo, useRef, useState } from 'react'

const BATCH_SIZE = 5

const TIKTOK_TYPES = { VIDEOS: 'videos', USERS: 'usuarios' }
const TELEGRAM_TYPES = { MESSAGES: 'messages', CHANNELS: 'channels' }

const RISK_LABELS = [
  { value: 'narcocultura',     label: 'Narcocultura' },
  { value: 'oferta de riesgo', label: 'Oferta de riesgo' },
  { value: 'reclutamiento',    label: 'Reclutamiento' },
]

const DEMO_TIKTOK_VIDEOS = [
  {
    _id: 'demo-2',
    autor_username: 'isabelmorales3306',
    url: 'https://www.tiktok.com/@isabelmorales3306/video/7630267537321708820',
    descripcion: '',
  },
  {
    _id: 'demo-1',
    autor_username: 'user6kldybe73w',
    url: 'https://www.tiktok.com/@user6kldybe73w/video/7617323685342366994',
    descripcion: '',
  },
]

const PLATFORM_CONFIG = [
  {
    id: 'youtube',
    label: 'YouTube',
    icon: '▶',
    collectionCandidates: ['youtube_items'],
    description: 'Videos de YouTube con comentarios sospechosos.',
  },
  {
    id: 'telegram',
    label: 'Telegram',
    icon: '✈',
    collectionCandidates: ['telegram_messages', 'telegram_channels'],
    description: 'Mensajes y canales monitoreados.',
  },
  {
    id: 'tiktok',
    label: 'TikTok',
    icon: '♪',
    collectionCandidates: ['tiktok_videos', 'tiktok_usuarios', 'tiktok_users'],
    description: 'Videos y perfiles de TikTok.',
  },
]

function getCollection(database, candidates) {
  if (!database) return ''
  return candidates.find((c) => database.collections.includes(c)) || ''
}

function HomePage({ currentUser = 'Analista' }) {
  const [catalog, setCatalog]                     = useState([])
  const [catalogError, setCatalogError]           = useState('')
  const [platformCounts, setPlatformCounts]       = useState({})
  const [activePlatform, setActivePlatform]       = useState('tiktok')
  const [tiktokType, setTiktokType]               = useState(TIKTOK_TYPES.VIDEOS)
  const [telegramType, setTelegramType]           = useState(TELEGRAM_TYPES.MESSAGES)
  const [items, setItems]                         = useState([])
  const [previewError, setPreviewError]           = useState('')
  const [previewLoading, setPreviewLoading]       = useState(false)
  const [loadingMore, setLoadingMore]             = useState(false)
  const [nextSkip, setNextSkip]                   = useState(0)
  const [hasMore, setHasMore]                     = useState(true)
  const [totalMatches, setTotalMatches]           = useState(0)
  const [currentIndex, setCurrentIndex]           = useState(0)
  const [selectedLabels, setSelectedLabels]       = useState([])
  const [submittedDecisions, setSubmittedDecisions] = useState({})
  const [submitLoading, setSubmitLoading]         = useState(false)
  const [submitError, setSubmitError]             = useState('')
  const [filterValueInput, setFilterValueInput]   = useState('')
  const [appliedFilter, setAppliedFilter]         = useState({ field: '', value: '' })
  const [toast, setToast]                         = useState(null)
  const toastTimer                                = useRef(null)
  const reviewPositionByKeyRef                    = useRef({})

  function showToast(message, type = 'success') {
    if (toastTimer.current) clearTimeout(toastTimer.current)
    setToast({ message, type })
    toastTimer.current = setTimeout(() => setToast(null), 3500)
  }

  const selectedDatabase = useMemo(() => {
    if (!catalog.length) return null
    return (
      catalog.find((db) => db.name.toLowerCase() === 'silver') ||
      catalog.find((db) => db.name.toLowerCase().includes('silver')) ||
      catalog[0]
    )
  }, [catalog])

  const activeConfig = useMemo(
    () => PLATFORM_CONFIG.find((p) => p.id === activePlatform),
    [activePlatform],
  )

  const selectedCollection = useMemo(() => {
    if (!selectedDatabase || !activeConfig) return ''
    if (activePlatform === 'tiktok') {
      const col =
        tiktokType === TIKTOK_TYPES.USERS
          ? getCollection(selectedDatabase, ['tiktok_usuarios', 'tiktok_users'])
          : getCollection(selectedDatabase, ['tiktok_videos'])
      return col || getCollection(selectedDatabase, activeConfig.collectionCandidates)
    }
    if (activePlatform === 'telegram') {
      return telegramType === TELEGRAM_TYPES.CHANNELS
        ? getCollection(selectedDatabase, ['telegram_channels'])
        : getCollection(selectedDatabase, ['telegram_messages'])
    }
    return getCollection(selectedDatabase, activeConfig.collectionCandidates)
  }, [selectedDatabase, activeConfig, activePlatform, tiktokType, telegramType])

  const tiktokAvail = useMemo(() => ({
    videos:   Boolean(getCollection(selectedDatabase, ['tiktok_videos'])),
    usuarios: Boolean(getCollection(selectedDatabase, ['tiktok_usuarios', 'tiktok_users'])),
  }), [selectedDatabase])

  const telegramAvail = useMemo(() => ({
    messages: Boolean(getCollection(selectedDatabase, ['telegram_messages'])),
    channels: Boolean(getCollection(selectedDatabase, ['telegram_channels'])),
  }), [selectedDatabase])

  const reviewSessionKey = useMemo(
    () => `${activePlatform}::${selectedCollection}::${appliedFilter.field}::${appliedFilter.value}`,
    [activePlatform, selectedCollection, appliedFilter],
  )

  const normalizedItems = useMemo(() => {
    return items.map((doc, idx) => {
      const id  = doc._id || doc.id || `${activePlatform}-${idx}`
      const nlp = {
        categoria: doc.categoria_principal || '',
        score:     typeof doc.riesgo_score === 'number' ? doc.riesgo_score : null,
        nivel:     doc.nivel_riesgo || '',
      }

      if (activePlatform === 'youtube') {
        return {
          id,
          source: doc.channel_name || doc.channel_title || 'Canal YouTube',
          text:   doc.title || doc.description || doc.text || 'Sin texto disponible',
          url:    doc.url || '',
          nlp,
        }
      }

      if (activePlatform === 'telegram') {
        if (selectedCollection === 'telegram_channels') {
          return {
            id,
            source: doc.title || (doc.username ? `@${doc.username}` : 'Canal sin nombre'),
            text:   doc.about || doc.description || 'Sin descripción disponible',
            url:    doc.username ? `https://t.me/${doc.username}` : (doc.url || ''),
            nlp,
          }
        }
        return {
          id,
          source: doc.channel_name || 'Canal sin nombre',
          text:   doc.text || 'Sin texto disponible',
          url:    doc.url || '',
          nlp,
        }
      }

      if (activePlatform === 'tiktok') {
        const isUsers = selectedCollection.includes('usuario') || selectedCollection.includes('user')
        if (isUsers) {
          return {
            id,
            source: doc.username || doc.user_name || doc.author || 'Usuario TikTok',
            text:   doc.bio || doc.signature || doc.descripcion || doc.description || 'Sin bio disponible',
            url:    doc.url || doc.profile_url || '',
            nlp,
          }
        }
        return {
          id,
          source: doc.author || doc.autor_username || doc.channel_name || 'Video TikTok',
          text:   doc.descripcion || doc.description || doc.caption || doc.text || 'Sin descripción',
          url:    doc.url || '',
          nlp,
        }
      }

      return { id, source: 'Desconocido', text: 'Sin texto', url: '', nlp }
    })
  }, [items, activePlatform, selectedCollection])

  const currentItem = normalizedItems[currentIndex] || null

  const submittedEntries   = Object.entries(submittedDecisions)
  const sessionReviewed    = submittedEntries.length
  const sessionSafe        = submittedEntries.filter(([, l]) => l.includes('seguro')).length
  const sessionGolden      = sessionReviewed - sessionSafe
  const progressPercent    = totalMatches > 0 ? Math.min(100, (sessionReviewed / totalMatches) * 100) : 0

  useEffect(() => {
    reviewPositionByKeyRef.current[reviewSessionKey] = currentIndex
  }, [currentIndex, reviewSessionKey])

  useEffect(() => {
    async function loadCatalog() {
      try {
        const res     = await fetch('/api/catalog')
        const payload = await res.json()
        if (!res.ok || !payload.ok) { setCatalogError(payload.message || 'Error al cargar catálogo'); return }
        setCatalog(payload.databases || [])
      } catch (e) {
        setCatalogError(e.message || 'Error de red')
      }
    }
    loadCatalog()
  }, [])

  useEffect(() => {
    if (!selectedDatabase) { setPlatformCounts({}); return }
    async function loadCounts() {
      const entries = await Promise.all(
        PLATFORM_CONFIG.map(async (platform) => {
          const cols =
            platform.id === 'tiktok'
              ? [...new Set([
                  getCollection(selectedDatabase, ['tiktok_videos']),
                  getCollection(selectedDatabase, ['tiktok_usuarios', 'tiktok_users']),
                ].filter(Boolean))]
              : [getCollection(selectedDatabase, platform.collectionCandidates)].filter(Boolean)

          if (!cols.length) return [platform.id, 0]
          const totals = await Promise.all(
            cols.map(async (col) => {
              try {
                const res     = await fetch(`/api/catalog/${encodeURIComponent(selectedDatabase.name)}/${encodeURIComponent(col)}/preview?skip=0&limit=1`)
                const payload = await res.json()
                return (res.ok && payload.ok && Number.isInteger(payload.total)) ? payload.total : 0
              } catch { return 0 }
            }),
          )
          return [platform.id, totals.reduce((s, t) => s + t, 0)]
        }),
      )
      setPlatformCounts(Object.fromEntries(entries))
    }
    loadCounts()
  }, [selectedDatabase])

  useEffect(() => {
    if (!selectedDatabase || !selectedCollection) { setItems([]); return }
    const savedIndex = reviewPositionByKeyRef.current[reviewSessionKey] ?? 0
    setCurrentIndex(savedIndex)
    setSelectedLabels([])
    setNextSkip(0)
    setHasMore(true)
    setTotalMatches(0)
    loadBatch(0, true)
  }, [selectedDatabase, selectedCollection, appliedFilter, reviewSessionKey])

  useEffect(() => {
    setSelectedLabels([])
    setSubmittedDecisions({})
    setSubmitError('')
    setFilterValueInput('')
    setAppliedFilter({ field: '', value: '' })
  }, [activePlatform])

  useEffect(() => {
    if (!selectedCollection || previewLoading || loadingMore || !hasMore || currentItem) return
    if (currentIndex < normalizedItems.length) return
    loadBatch(nextSkip, false)
  }, [currentIndex, currentItem, hasMore, loadingMore, nextSkip, normalizedItems.length, previewLoading, selectedCollection])

  async function loadBatch(skip, replace) {
    if (replace) setPreviewLoading(true); else setLoadingMore(true)
    setPreviewError('')
    try {
      const params = new URLSearchParams({ skip: String(skip), limit: String(BATCH_SIZE) })
      if (appliedFilter.value) {
        params.set('filterField', appliedFilter.field)
        params.set('filterValue', appliedFilter.value)
      }
      const res     = await fetch(`/api/catalog/${encodeURIComponent(selectedDatabase.name)}/${encodeURIComponent(selectedCollection)}/preview?${params}`)
      const payload = await res.json()
      if (!res.ok || !payload.ok) { if (replace) setItems([]); setPreviewError(payload.message || 'Error al cargar'); return }
      const docs = payload.documents || []
      setItems((cur) => replace ? docs : [...cur, ...docs])
      setTotalMatches(Number.isInteger(payload.total) ? payload.total : docs.length)
      setHasMore(Boolean(payload.hasMore))
      setNextSkip(Number.isInteger(payload.nextSkip) ? payload.nextSkip : skip + docs.length)
    } catch (e) {
      if (replace) setItems([])
      setPreviewError(e.message || 'Error de red')
    } finally {
      if (replace) setPreviewLoading(false); else setLoadingMore(false)
    }
  }

  function handleToggleLabel(label) {
    setSelectedLabels((cur) => {
      if (label === 'seguro') return cur.includes('seguro') ? [] : ['seguro']
      const base = cur.filter((l) => l !== 'seguro')
      return base.includes(label) ? base.filter((l) => l !== label) : [...base, label]
    })
  }

  function handleSkip() {
    setSelectedLabels([])
    setSubmitError('')
    setCurrentIndex((i) => i + 1)
  }

  async function handleSendDecision() {
    if (!currentItem || selectedLabels.length === 0) return
    setSubmitLoading(true)
    setSubmitError('')
    try {
      const res     = await fetch('/api/moderation/label', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          sourceDatabase:   selectedDatabase?.name,
          sourceCollection: selectedCollection,
          labels:           selectedLabels,
          documentId:       currentItem.id,
          taggedBy:         currentUser,
        }),
      })
      const payload = await res.json()
      if (!res.ok || !payload.ok) { setSubmitError(payload.message || 'Error al enviar'); return }

      if (payload.skipped) {
        showToast('Marcado como seguro — omitido de Golden', 'info')
      } else {
        showToast(`Enviado a Golden: ${selectedLabels.join(' + ')}`, 'success')
      }

      setSubmittedDecisions((cur) => ({ ...cur, [currentItem.id]: selectedLabels }))
      setSelectedLabels([])
      setCurrentIndex((i) => i + 1)
    } catch (e) {
      setSubmitError(e.message || 'Error de red')
    } finally {
      setSubmitLoading(false)
    }
  }

  useEffect(() => {
    function onKey(e) {
      if (e.target.tagName === 'INPUT') return
      if (!currentItem) return
      if (e.key === 'ArrowRight') { handleSkip(); return }
      if (e.key === 'Enter' && !submitLoading && selectedLabels.length > 0) { handleSendDecision(); return }
      if (e.key === 's' || e.key === 'S') { handleToggleLabel('seguro'); return }
      if (e.key === '1') { handleToggleLabel('narcocultura'); return }
      if (e.key === '2') { handleToggleLabel('oferta de riesgo'); return }
      if (e.key === '3') { handleToggleLabel('reclutamiento'); return }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [currentItem, selectedLabels, submitLoading])

  const maxCount = Math.max(1, ...PLATFORM_CONFIG.map((p) => platformCounts[p.id] || 0))

  return (
    <div className="home-page">

      {/* ── TOAST ────────────────────────────────── */}
      {toast && (
        <div className={`toast toast--${toast.type}`} role="status">
          {toast.type === 'success' ? '✓' : 'ℹ'} {toast.message}
        </div>
      )}

      {/* ── SIDEBAR ──────────────────────────────── */}
      <aside className="sidebar">
        <div className="sidebar__counts">
          <h2 className="sidebar__title">Registros en Silver</h2>
          <div className="platform-bars">
            {PLATFORM_CONFIG.map((p) => {
              const count = platformCounts[p.id] || 0
              const pct   = Math.max(4, Math.round((count / maxCount) * 100))
              return (
                <div key={p.id} className="platform-bar">
                  <div className="platform-bar__meta">
                    <span>{p.label}</span>
                    <strong>{count.toLocaleString('es-MX')}</strong>
                  </div>
                  <div className="platform-bar__track">
                    <div className={`platform-bar__fill platform-bar__fill--${p.id}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <nav className="sidebar__nav">
          {PLATFORM_CONFIG.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`platform-btn platform-btn--${p.id} ${activePlatform === p.id ? 'is-active' : ''}`}
              onClick={() => setActivePlatform(p.id)}
            >
              <span className="platform-btn__icon">{p.icon}</span>
              <span className="platform-btn__label">{p.label}</span>
              <span className="platform-btn__count">{(platformCounts[p.id] || 0).toLocaleString('es-MX')}</span>
            </button>
          ))}
        </nav>

        {catalogError && <p className="error-note">{catalogError}</p>}

        <div className="sidebar__session">
          <h2 className="sidebar__title">Sesión actual</h2>
          <div className="sidebar-stats">
            <div className="sidebar-stat">
              <strong>{sessionReviewed}</strong>
              <span>Revisados</span>
            </div>
            <div className="sidebar-stat sidebar-stat--golden">
              <strong>{sessionGolden}</strong>
              <span>A Golden</span>
            </div>
            <div className="sidebar-stat sidebar-stat--safe">
              <strong>{sessionSafe}</strong>
              <span>Seguros</span>
            </div>
            <div className="sidebar-stat">
              <strong>{sessionReviewed > 0 ? `${((sessionGolden / sessionReviewed) * 100).toFixed(0)}%` : '—'}</strong>
              <span>Riesgo</span>
            </div>
          </div>
        </div>
      </aside>

      {/* ── MAIN ─────────────────────────────────── */}
      <main className="review-main">

        {/* Platform header + subtypes toggle */}
        <div className="review-header">
          <div>
            <h2 className="review-header__title">{activeConfig?.label}</h2>
            <p className="review-header__desc">{activeConfig?.description}</p>
          </div>

          {activePlatform === 'tiktok' && (
            <div className="subtype-toggle" role="group">
              <button type="button"
                className={`subtype-toggle__btn ${tiktokType === TIKTOK_TYPES.VIDEOS ? 'is-active' : ''}`}
                onClick={() => setTiktokType(TIKTOK_TYPES.VIDEOS)}
                disabled={!tiktokAvail.videos}>
                Videos
              </button>
              <button type="button"
                className={`subtype-toggle__btn ${tiktokType === TIKTOK_TYPES.USERS ? 'is-active' : ''}`}
                onClick={() => setTiktokType(TIKTOK_TYPES.USERS)}
                disabled={!tiktokAvail.usuarios}>
                Usuarios
              </button>
            </div>
          )}

          {activePlatform === 'telegram' && (
            <div className="subtype-toggle" role="group">
              <button type="button"
                className={`subtype-toggle__btn ${telegramType === TELEGRAM_TYPES.MESSAGES ? 'is-active' : ''}`}
                onClick={() => setTelegramType(TELEGRAM_TYPES.MESSAGES)}
                disabled={!telegramAvail.messages}>
                Mensajes
              </button>
              <button type="button"
                className={`subtype-toggle__btn ${telegramType === TELEGRAM_TYPES.CHANNELS ? 'is-active' : ''}`}
                onClick={() => setTelegramType(TELEGRAM_TYPES.CHANNELS)}
                disabled={!telegramAvail.channels}>
                Canales
              </button>
            </div>
          )}
        </div>

        {/* Filter bar */}
        <div className="filter-bar">
          <input
            type="text"
            className="filter-bar__input"
            placeholder="Buscar por texto, canal, usuario..."
            value={filterValueInput}
            onChange={(e) => setFilterValueInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') setAppliedFilter({ field: '', value: filterValueInput.trim() }) }}
          />
          <button type="button" className="filter-bar__btn"
            onClick={() => setAppliedFilter({ field: '', value: filterValueInput.trim() })}>
            Buscar
          </button>
          {appliedFilter.value && (
            <button type="button" className="filter-bar__btn filter-bar__btn--ghost"
              onClick={() => { setFilterValueInput(''); setAppliedFilter({ field: '', value: '' }) }}>
              × Limpiar
            </button>
          )}
        </div>

        {/* Progress + counter */}
        <div className="progress-row">
          <span className="progress-row__label">
            {totalMatches > 0
              ? `Registro ${Math.min(currentIndex + 1, totalMatches)} de ${totalMatches}`
              : previewLoading ? 'Cargando...' : 'Sin registros'}
          </span>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${progressPercent}%` }} />
          </div>
          <span className="progress-row__pct">{progressPercent.toFixed(0)}%</span>
        </div>

        {/* Error */}
        {previewError && <p className="error-note">{previewError}</p>}

        {/* Review card */}
        {selectedCollection && currentItem ? (
          <article className="review-card">

            {/* Banner IA — ancho completo */}
            {currentItem.nlp.categoria ? (
              <div className={`nlp-banner nlp-banner--${currentItem.nlp.nivel || 'medio'}`}>
                <span className="nlp-banner__dot" />
                <span className="nlp-banner__label">IA detectó</span>
                <strong className="nlp-banner__categoria">{currentItem.nlp.categoria}</strong>
                {currentItem.nlp.score !== null && (
                  <span className="nlp-banner__score">
                    {(currentItem.nlp.score * 100).toFixed(0)}%
                    {currentItem.nlp.nivel ? ` · ${currentItem.nlp.nivel.toUpperCase()}` : ''}
                  </span>
                )}
              </div>
            ) : (
              <div className="nlp-banner nlp-banner--unknown">
                <span className="nlp-banner__dot" />
                <span className="nlp-banner__label">Sin clasificación IA</span>
              </div>
            )}

            {/* Cuerpo: 2 columnas */}
            <div className="card-body">

              {/* IZQUIERDA: contenido + fuente */}
              <div className="card-content">
                <div className="review-card__source">
                  <span className="review-card__source-tag">{activeConfig?.label}</span>
                  <strong>{currentItem.source}</strong>
                </div>

                {/* Embed TikTok si hay video ID en la URL */}
                {activePlatform === 'tiktok' && (() => {
                  const videoId = currentItem.url?.match(/\/video\/(\d+)/)?.[1]
                  if (!videoId) return <p className="review-card__text">{currentItem.text}</p>
                  return (
                    <div className="platform-embed">
                      <iframe
                        key={videoId}
                        src={`https://www.tiktok.com/embed/v2/${videoId}`}
                        className="tiktok-frame"
                        allowFullScreen
                        allow="encrypted-media"
                        title="Vista previa TikTok"
                      />
                    </div>
                  )
                })()}

                {activePlatform !== 'tiktok' && (
                  <p className="review-card__text">{currentItem.text}</p>
                )}

                {/* CTA principal */}
                {currentItem.url ? (
                  <a className="source-cta" href={currentItem.url} target="_blank" rel="noopener noreferrer">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/>
                      <polyline points="15 3 21 3 21 9"/>
                      <line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                    <div className="source-cta__text">
                      <span className="source-cta__label">Ver fuente original</span>
                      <span className="source-cta__sub">Verifica el contenido antes de clasificar</span>
                    </div>
                  </a>
                ) : (
                  <div className="source-cta source-cta--disabled">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                    <div className="source-cta__text">
                      <span className="source-cta__label">Sin enlace disponible</span>
                    </div>
                  </div>
                )}
              </div>

              {/* DERECHA: clasificación + acciones */}
              <div className="card-actions">
                <p className="label-section__hint">¿Cómo clasificas este contenido?</p>
                <div className="label-grid">
                  <button type="button"
                    className={`label-card label-card--safe ${selectedLabels.includes('seguro') ? 'is-selected' : ''}`}
                    onClick={() => handleToggleLabel('seguro')}>
                    <span className="label-card__icon">✓</span>
                    <span className="label-card__name">Seguro</span>
                  </button>
                  {RISK_LABELS.map((opt) => {
                    const slug = opt.value.replace(/ /g, '-')
                    const isAiSuggested = currentItem?.nlp?.categoria?.toLowerCase().includes(opt.value.toLowerCase())
                    return (
                      <button key={opt.value} type="button"
                        className={`label-card label-card--${slug} ${selectedLabels.includes(opt.value) ? 'is-selected' : ''} ${isAiSuggested ? 'is-ai-suggested' : ''}`}
                        onClick={() => handleToggleLabel(opt.value)}>
                        {isAiSuggested && <span className="label-card__ai-badge">IA</span>}
                        <span className="label-card__icon">⚠</span>
                        <span className="label-card__name">{opt.label}</span>
                      </button>
                    )
                  })}
                </div>

                {selectedLabels.length > 0 && (
                  <p className="label-selection">
                    Clasificado como: <strong>{selectedLabels.join(' + ')}</strong>
                  </p>
                )}

                <div className="review-card__actions">
                  <button type="button" className="action-btn action-btn--skip" onClick={handleSkip}>
                    Saltar
                  </button>
                  <button type="button"
                    className={`action-btn action-btn--send ${selectedLabels.includes('seguro') ? 'action-btn--safe-mode' : ''}`}
                    onClick={handleSendDecision}
                    disabled={submitLoading || selectedLabels.length === 0}>
                    {submitLoading
                      ? 'Enviando...'
                      : selectedLabels.includes('seguro')
                        ? '✓ Marcar como seguro'
                        : 'Enviar a Golden →'}
                  </button>
                </div>

                {submitError && <p className="submit-error">{submitError}</p>}

                <div className="kbd-hints">
                  <div className="kbd-row">
                    <span className="kbd-hint"><kbd>S</kbd> Seguro</span>
                    <span className="kbd-hint"><kbd>1</kbd> Narco</span>
                    <span className="kbd-hint"><kbd>2</kbd> Oferta</span>
                  </div>
                  <div className="kbd-row">
                    <span className="kbd-hint"><kbd>3</kbd> Reclutamiento</span>
                    <span className="kbd-hint"><kbd>→</kbd> Saltar</span>
                    <span className="kbd-hint"><kbd>↵</kbd> Enviar</span>
                  </div>
                </div>
              </div>
            </div>
          </article>
        ) : (
          <div className="review-empty">
            {previewLoading || loadingMore
              ? 'Cargando registros...'
              : selectedCollection
                ? 'No hay más registros en esta sesión'
                : 'Selecciona una plataforma para comenzar'}
          </div>
        )}

      </main>
    </div>
  )
}

export default HomePage
