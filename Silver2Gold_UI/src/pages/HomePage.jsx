import { useEffect, useMemo, useRef, useState } from 'react'

const BATCH_SIZE = 5

const LABEL_OPTIONS = [
  { value: 'seguro', label: 'Seguro', tone: 'safe' },
  { value: 'narcocultura', label: 'Narcocultura', tone: 'risk' },
  { value: 'oferta de riesgo', label: 'Oferta de riesgo', tone: 'risk' },
  { value: 'reclutamiento', label: 'Reclutamiento', tone: 'risk' },
]

const PLATFORM_CONFIG = [
  {
    id: 'youtube',
    label: 'YouTube',
    collectionCandidates: ['youtube_items'],
    description: 'Videos y metadatos disponibles para análisis.',
    filters: [
      { value: 'channel_id', label: 'Channel ID' },
      { value: 'title', label: 'Título' },
      { value: 'channel_name', label: 'Canal' },
      { value: 'description', label: 'Descripción' },
      { value: 'text', label: 'Texto' },
    ],
  },
  {
    id: 'telegram',
    label: 'Telegram',
    collectionCandidates: [
      'telegram_messages',
      'telegram_channels', // antes usado en Silver
    ],
    description: 'Mensajes y actividad de canales monitoreados.',
    filters: [
      { value: 'channel_name', label: 'Canal / Grupo' },
      { value: 'group_name', label: 'Nombre de grupo' },
      { value: 'chat_title', label: 'Título del chat' },
      { value: 'text', label: 'Texto' },
    ],
  },
  {
    id: 'tiktok',
    label: 'TikTok',
    collectionCandidates: [
      'tiktok_videos',
      'tiktok_usuarios',
      // rollback opcional: 'tiktok_videos_ORC',
      // rollback opcional: 'tiktok_usuarios_ORC',
    ],
    description: 'Videos y metadatos disponibles para análisis.',
    filters: [
      { value: 'author', label: 'Autor' },
      { value: 'channel_name', label: 'Canal' },
      { value: 'description', label: 'Descripción' },
      { value: 'caption', label: 'Caption' },
      { value: 'text', label: 'Texto' },
    ],
  },
]

function getAvailableCollectionForPlatform(platform, database) {
  if (!database) {
    return ''
  }

  const candidates = platform.collectionCandidates || []
  return candidates.find((collectionName) => database.collections.includes(collectionName)) || ''
}

function HomePage({ currentUser = 'Asharet' }) {
  const [catalog, setCatalog] = useState([])
  const [catalogError, setCatalogError] = useState('')
  const [platformCounts, setPlatformCounts] = useState({})
  const [platformCountsLoading, setPlatformCountsLoading] = useState(false)
  const [platformCountsError, setPlatformCountsError] = useState('')
  const [activePlatform, setActivePlatform] = useState('telegram')
  const [items, setItems] = useState([])
  const [previewError, setPreviewError] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [nextSkip, setNextSkip] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [totalMatches, setTotalMatches] = useState(0)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [selectedLabels, setSelectedLabels] = useState([])
  const [submittedDecisions, setSubmittedDecisions] = useState({})
  const [submitLoading, setSubmitLoading] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [submitMessage, setSubmitMessage] = useState('')
  const [filterField, setFilterField] = useState('')
  const [filterValueInput, setFilterValueInput] = useState('')
  const [appliedFilter, setAppliedFilter] = useState({ field: '', value: '' })
  const reviewPositionByKeyRef = useRef({})

  const selectedDatabase = useMemo(() => {
    if (catalog.length === 0) {
      return null
    }

    return (
      catalog.find((database) => database.name.toLowerCase().includes('silver')) ||
      catalog.find((database) => database.name.toLowerCase() === 'silver') ||
      catalog.find((database) => database.name.toLowerCase() === 'centinela') || // antes: base principal
      catalog[0]
    )
  }, [catalog])

  const activeConfig = useMemo(
    () => PLATFORM_CONFIG.find((platform) => platform.id === activePlatform),
    [activePlatform],
  )

  const selectedCollection = useMemo(() => {
    if (!selectedDatabase || !activeConfig) {
      return ''
    }

    return getAvailableCollectionForPlatform(activeConfig, selectedDatabase)
  }, [selectedDatabase, activeConfig])

  const activeFilters = useMemo(() => activeConfig?.filters || [], [activeConfig])

  const platformChartData = useMemo(
    () =>
      PLATFORM_CONFIG.map((platform) => ({
        ...platform,
        count: Number.isFinite(platformCounts[platform.id])
          ? platformCounts[platform.id]
          : 0,
        available:
          Boolean(getAvailableCollectionForPlatform(platform, selectedDatabase)) || false,
      })),
    [platformCounts, selectedDatabase],
  )

  const maxPlatformCount = useMemo(
    () => Math.max(1, ...platformChartData.map((platform) => platform.count)),
    [platformChartData],
  )

  const reviewSessionKey = useMemo(
    () =>
      `${activePlatform}::${selectedCollection || 'no-collection'}::${
        appliedFilter.field || 'no-field'
      }::${appliedFilter.value || 'no-value'}`,
    [activePlatform, appliedFilter.field, appliedFilter.value, selectedCollection],
  )

  const appliedFilterLabel = useMemo(() => {
    if (!appliedFilter.field) {
      return ''
    }

    return (
      activeFilters.find((filter) => filter.value === appliedFilter.field)?.label ||
      appliedFilter.field
    )
  }, [activeFilters, appliedFilter.field])

  const normalizedItems = useMemo(() => {
    const documents = items || []

    return documents.map((document, index) => {
      const fallbackId = `${activePlatform}-${index}`
      const id = document._id || document.id || fallbackId

      if (activePlatform === 'telegram') {
        return {
          id,
          source: document.channel_name || 'Canal sin nombre',
          text: document.text || 'Sin texto disponible',
          url: document.url || '',
        }
      }

      if (activePlatform === 'youtube') {
        return {
          id,
          source: document.channel_name || document.channel_title || 'Canal YouTube',
          text:
            document.text ||
            document.description ||
            document.title ||
            'Sin texto disponible',
          url: document.url || '',
        }
      }

      return {
        id,
        source: document.channel_name || document.author || 'Descripción del TikTok',
         text:
          document.descripcion || document.description || document.text || document.caption || 'Sin texto disponible',
        url: document.url || '',
      }
    })
  }, [activePlatform, items])

  const currentItem = normalizedItems[currentIndex] || null
  const submittedEntries = Object.entries(submittedDecisions)

  const sessionReviewedCount = submittedEntries.length
  const sessionSafeCount = submittedEntries.filter(([, labels]) =>
    Array.isArray(labels) && labels.includes('seguro'),
  ).length
  const sessionGoldenCount = sessionReviewedCount - sessionSafeCount
  const progressPercent =
    totalMatches > 0 ? Math.min(100, (sessionReviewedCount / totalMatches) * 100) : 0

  useEffect(() => {
    reviewPositionByKeyRef.current[reviewSessionKey] = currentIndex
  }, [currentIndex, reviewSessionKey])

  useEffect(() => {
    async function loadCatalog() {
      try {
        const response = await fetch('/api/catalog')
        const payload = await response.json()

        if (!response.ok || !payload.ok) {
          setCatalogError(payload.message || 'No se pudo cargar el catálogo')
          return
        }

        setCatalog(payload.databases || [])
      } catch (error) {
        setCatalogError(
          error instanceof Error ? error.message : 'No se pudo cargar el catálogo',
        )
      }
    }

    loadCatalog()
  }, [])

  useEffect(() => {
    let cancelled = false

    async function loadPlatformCounts() {
      if (!selectedDatabase) {
        setPlatformCounts({})
        setPlatformCountsLoading(false)
        setPlatformCountsError('')
        return
      }

      setPlatformCountsLoading(true)
      setPlatformCountsError('')

      try {
        const entries = await Promise.all(
          PLATFORM_CONFIG.map(async (platform) => {
            const availableCollection = getAvailableCollectionForPlatform(
              platform,
              selectedDatabase,
            )
            if (!availableCollection) {
              return [platform.id, 0]
            }

            const response = await fetch(
              `/api/catalog/${encodeURIComponent(selectedDatabase.name)}/${encodeURIComponent(
                availableCollection,
              )}/preview?skip=0&limit=1`,
            )
            const payload = await response.json()

            if (!response.ok || !payload.ok) {
              return [platform.id, 0]
            }

            const total = Number.isInteger(payload.total) ? payload.total : 0
            return [platform.id, total]
          }),
        )

        if (!cancelled) {
          setPlatformCounts(Object.fromEntries(entries))
        }
      } catch (error) {
        if (!cancelled) {
          setPlatformCountsError(
            error instanceof Error
              ? error.message
              : 'No se pudieron cargar los conteos por red',
          )
        }
      } finally {
        if (!cancelled) {
          setPlatformCountsLoading(false)
        }
      }
    }

    loadPlatformCounts()

    return () => {
      cancelled = true
    }
  }, [selectedDatabase])

  useEffect(() => {
    if (!selectedDatabase || !selectedCollection) {
      setItems([])
      setPreviewLoading(false)
      return
    }

    async function loadPreviewBatch(startSkip, replaceItems) {
      if (replaceItems) {
        setPreviewLoading(true)
      } else {
        setLoadingMore(true)
      }

      setPreviewError('')

      try {
        const params = new URLSearchParams({
          skip: String(startSkip),
          limit: String(BATCH_SIZE),
        })

        if (appliedFilter.value) {
          params.set('filterField', appliedFilter.field)
          params.set('filterValue', appliedFilter.value)
        }

        const response = await fetch(
          `/api/catalog/${encodeURIComponent(selectedDatabase.name)}/${encodeURIComponent(
            selectedCollection,
          )}/preview?${params.toString()}`,
        )
        const payload = await response.json()

        if (!response.ok || !payload.ok) {
          if (replaceItems) {
            setItems([])
          }
          setPreviewError(payload.message || 'No se pudo cargar la vista previa')
          return
        }

        const docs = payload.documents || []
        setItems((current) => (replaceItems ? docs : [...current, ...docs]))
        setTotalMatches(Number.isInteger(payload.total) ? payload.total : docs.length)
        setHasMore(Boolean(payload.hasMore))
        setNextSkip(
          Number.isInteger(payload.nextSkip)
            ? payload.nextSkip
            : startSkip + docs.length,
        )
      } catch (error) {
        if (replaceItems) {
          setItems([])
        }
        setPreviewError(
          error instanceof Error ? error.message : 'No se pudo cargar la vista previa',
        )
      } finally {
        if (replaceItems) {
          setPreviewLoading(false)
        } else {
          setLoadingMore(false)
        }
      }
    }

    const savedIndex = reviewPositionByKeyRef.current[reviewSessionKey] ?? 0
    setCurrentIndex(savedIndex)
    setSelectedLabels([])
    setNextSkip(0)
    setHasMore(true)
    setTotalMatches(0)
    loadPreviewBatch(0, true)
  }, [selectedDatabase, selectedCollection, appliedFilter, reviewSessionKey])

  useEffect(() => {
    setSelectedLabels([])
    setSubmittedDecisions({})
    setSubmitError('')
    setSubmitMessage('')
    const defaultFilterField = activeConfig?.filters?.[0]?.value || ''
    setFilterField(defaultFilterField)
    setFilterValueInput('')
    setAppliedFilter({ field: '', value: '' })
  }, [activeConfig, activePlatform])

  useEffect(() => {
    if (
      !selectedCollection ||
      previewLoading ||
      loadingMore ||
      !hasMore ||
      currentItem ||
      currentIndex < normalizedItems.length
    ) {
      return
    }

    async function loadMoreBatch() {
      setLoadingMore(true)
      setPreviewError('')

      try {
        const params = new URLSearchParams({
          skip: String(nextSkip),
          limit: String(BATCH_SIZE),
        })

        if (appliedFilter.value) {
          params.set('filterField', appliedFilter.field)
          params.set('filterValue', appliedFilter.value)
        }

        const response = await fetch(
          `/api/catalog/${encodeURIComponent(selectedDatabase.name)}/${encodeURIComponent(
            selectedCollection,
          )}/preview?${params.toString()}`,
        )
        const payload = await response.json()

        if (!response.ok || !payload.ok) {
          setPreviewError(payload.message || 'No se pudo cargar más mensajes')
          return
        }

        const docs = payload.documents || []
        setItems((current) => [...current, ...docs])
        setTotalMatches(Number.isInteger(payload.total) ? payload.total : docs.length)
        setHasMore(Boolean(payload.hasMore))
        setNextSkip(
          Number.isInteger(payload.nextSkip)
            ? payload.nextSkip
            : nextSkip + docs.length,
        )
      } catch (error) {
        setPreviewError(
          error instanceof Error ? error.message : 'No se pudo cargar más mensajes',
        )
      } finally {
        setLoadingMore(false)
      }
    }

    loadMoreBatch()
  }, [
    currentIndex,
    currentItem,
    hasMore,
    loadingMore,
    nextSkip,
    normalizedItems.length,
    previewLoading,
    appliedFilter,
    selectedCollection,
    selectedDatabase,
  ])

  function handleApplyFilter() {
    const normalizedValue = filterValueInput.trim()
    if (!normalizedValue || !filterField) {
      setAppliedFilter({ field: '', value: '' })
      return
    }

    setAppliedFilter({
      field: filterField,
      value: normalizedValue,
    })
  }

  function handleClearFilter() {
    setFilterValueInput('')
    setAppliedFilter({ field: '', value: '' })
  }

  function handleToggleLabel(label) {
    setSelectedLabels((current) => {
      if (label === 'seguro') {
        return current.includes('seguro') ? [] : ['seguro']
      }

      const base = current.filter((item) => item !== 'seguro')
      if (base.includes(label)) {
        return base.filter((item) => item !== label)
      }

      return [...base, label]
    })
  }

  async function handleSendDecision() {
    if (!currentItem || selectedLabels.length === 0) {
      return
    }

    setSubmitLoading(true)
    setSubmitError('')
    setSubmitMessage('')

    try {
      const response = await fetch('/api/moderation/label', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          sourceDatabase: selectedDatabase?.name,
          sourceCollection: selectedCollection,
          labels: selectedLabels,
          documentId: currentItem.id,
          platform: activePlatform,
          taggedBy: currentUser,
        }),
      })

      const payload = await response.json()

      if (!response.ok || !payload.ok) {
        setSubmitError(payload.message || 'No se pudo enviar la clasificación')
        return
      }

      if (payload.copied) {
        setSubmitMessage('')
      } else if (payload.skipped) {
        setSubmitMessage('')
      }

      setSubmittedDecisions((current) => ({
        ...current,
        [currentItem.id]: selectedLabels,
      }))
      setSelectedLabels([])
      setCurrentIndex((value) => value + 1)
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : 'No se pudo enviar la clasificación',
      )
    } finally {
      setSubmitLoading(false)
    }
  }

  return (
    <section className="home-page home-page--dashboard">
      <aside className="catalog-sidebar">
        <div className="catalog-sidebar__top">
          <h2>Registros por red social</h2>
          <p>Distribución actual de registros disponibles en Silver.</p>

          {platformCountsLoading ? (
            <p className="catalog-sidebar__loading">Cargando gráfica...</p>
          ) : null}

          {platformCountsError ? (
            <div className="mongo-status mongo-status--error">{platformCountsError}</div>
          ) : (
            <div className="platform-chart" aria-label="Gráfica de barras por red social">
              {platformChartData.map((platform) => {
                const widthPercent = Math.max(
                  4,
                  Math.round((platform.count / maxPlatformCount) * 100),
                )

                return (
                  <article key={platform.id} className="platform-chart__row">
                    <div className="platform-chart__meta">
                      <span className="platform-chart__name">{platform.label}</span>
                      <strong className="platform-chart__value">
                        {platform.count.toLocaleString('es-MX')}
                      </strong>
                    </div>
                    <div className="platform-chart__track" aria-hidden="true">
                      <div
                        className={`platform-chart__fill platform-chart__fill--${platform.id} ${
                          platform.available ? '' : 'is-unavailable'
                        }`}
                        style={{ width: `${widthPercent}%` }}
                      />
                    </div>
                  </article>
                )
              })}
            </div>
          )}
        </div>

        {catalogError ? (
          <div className="mongo-status mongo-status--error">{catalogError}</div>
        ) : null}

        <nav className="catalog-nav" aria-label="Redes sociales">
          <ul className="social-nav">
            {PLATFORM_CONFIG.map((platform) => {
              const isActive = platform.id === activePlatform
              const available = Boolean(
                getAvailableCollectionForPlatform(platform, selectedDatabase),
              )

              return (
                <li key={platform.id}>
                  <button
                    type="button"
                    className={`social-nav__button platform--${platform.id} ${isActive ? 'is-active' : ''}`}
                    onClick={() => setActivePlatform(platform.id)}
                  >
                    <span>{platform.label}</span>
                    <small>{available ? 'Disponible' : 'Próximamente'}</small>
                  </button>
                </li>
              )
            })}
          </ul>
        </nav>
      </aside>

      <main className="catalog-main">
        <header className="catalog-main__hero">
          <p className="catalog-main__eyebrow">Red social activa</p>
          <h3>{activeConfig?.label || 'Red social'}</h3>
          <p>{activeConfig?.description}</p>
        </header>

        <section className="catalog-filters">
          <div className="catalog-filters__header">
            <h4>Filtros</h4>
            {appliedFilter.value ? (
              <span>
                Filtrando por {appliedFilterLabel}: "{appliedFilter.value}"
              </span>
            ) : (
              <span>Sin filtro activo</span>
            )}
          </div>

          <p className="catalog-filters__session">Etiquetado por: {currentUser}</p>

          <div className="catalog-filters__controls">
            <select
              value={filterField}
              onChange={(event) => setFilterField(event.target.value)}
              disabled={activeFilters.length === 0}
            >
              {activeFilters.map((filter) => (
                <option key={filter.value} value={filter.value}>
                  {filter.label}
                </option>
              ))}
            </select>

            <input
              type="text"
              value={filterValueInput}
              onChange={(event) => setFilterValueInput(event.target.value)}
              placeholder="Escribe para filtrar..."
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  handleApplyFilter()
                }
              }}
            />

            <button type="button" className="filter-button" onClick={handleApplyFilter}>
              Aplicar
            </button>
            <button
              type="button"
              className="filter-button filter-button--ghost"
              onClick={handleClearFilter}
            >
              Limpiar
            </button>
          </div>
        </section>

        <section className="session-metrics" aria-label="Resumen de sesión">
          <article className="session-metric">
            <p>
              Revisados
              <br />
              en sesión
            </p>
            <strong>{sessionReviewedCount}</strong>
          </article>
          <article className="session-metric">
            <p>
              Etiquetados
              <br />
              de riesgo
            </p>
            <strong>{sessionGoldenCount}</strong>
          </article>
          <article className="session-metric">
            <p>
              Seguros
              <br />
              en sesión
            </p>
            <strong>{sessionSafeCount}</strong>
          </article>
          <article className="session-metric">
            <p>
              Enviados a
              <br />
              Golden
            </p>
            <strong>{sessionGoldenCount}</strong>
          </article>
        </section>

        <section className="preview-panel">
          <div className="preview-panel__header">
            <h4>Mensajes para clasificar</h4>
            <span>
              {selectedCollection
                ? previewLoading
                  ? 'Cargando...'
                  : totalMatches > 0
                    ? `${Math.min(currentIndex + 1, totalMatches)} de ${totalMatches}`
                    : '0 de 0'
                : 'Sin fuente disponible'}
            </span>
          </div>

          <div className="session-progress">
            <div className="session-progress__labels">
              <span>Progreso de sesión</span>
              <strong>{progressPercent.toFixed(0)}%</strong>
            </div>
            <div className="session-progress__track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Number(progressPercent.toFixed(0))}>
              <div
                className="session-progress__fill"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          {previewError ? (
            <div className="mongo-status mongo-status--error">{previewError}</div>
          ) : null}

          {selectedCollection && currentItem ? (
            <div className="preview-documents">
              <article key={currentItem.id} className="message-card">
                <header className="message-card__header">
                  <strong>{currentItem.source}</strong>
                </header>

                <p className="message-card__text">{currentItem.text}</p>

                {currentItem.url ? (
                  <a
                    className="message-card__link"
                    href={currentItem.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {currentItem.url}
                  </a>
                ) : null}

                <div className="message-card__actions">
                  {LABEL_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={`tag-button ${
                        selectedLabels.includes(option.value)
                          ? option.tone === 'safe'
                            ? 'is-active-safe'
                            : 'is-active-risk'
                          : ''
                      }`}
                      onClick={() => handleToggleLabel(option.value)}
                    >
                      {option.label}
                    </button>
                  ))}

                  {selectedLabels.length > 0 ? (
                    <button
                      type="button"
                      className="send-button"
                      onClick={handleSendDecision}
                      disabled={submitLoading}
                    >
                      {submitLoading ? 'Enviando...' : 'Enviar'}
                    </button>
                  ) : null}
                </div>

                <p className="tag-state">
                  {selectedLabels.length > 0
                    ? `Selección actual: ${selectedLabels.join(', ')}`
                    : 'Selecciona una o más etiquetas para habilitar Enviar'}
                </p>

                <p className="tag-state">
                  Seguro es exclusivo. Narcocultura, oferta de riesgo y reclutamiento
                  pueden combinarse.
                </p>

                {submitError ? <p className="submit-feedback is-error">{submitError}</p> : null}
                {submitMessage ? (
                  <p className="submit-feedback is-success">{submitMessage}</p>
                ) : null}
              </article>
            </div>
          ) : (
            <div className="preview-empty">
              {selectedCollection
                ? previewLoading || loadingMore
                  ? 'Cargando documentos...'
                  : normalizedItems.length === 0
                    ? 'No hay documentos para mostrar'
                    : 'No hay más mensajes disponibles por ahora'
                : 'TikTok estará disponible cuando exista tiktok_videos o tiktok_usuarios'}
            </div>
          )}

          {Object.keys(submittedDecisions).length > 0 ? (
            <p className="tag-state">
              Mensajes enviados en esta sesión: {Object.keys(submittedDecisions).length}
            </p>
          ) : null}
        </section>
      </main>
    </section>
  )
}

export default HomePage
