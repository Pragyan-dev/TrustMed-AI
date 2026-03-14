import { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import {
  Search, Network, Loader2, X, Pill, Activity, Shield,
  AlertTriangle, ChevronRight, RefreshCw, Link2, Maximize2, Minimize2
} from 'lucide-react'

const API_BASE = '/api'

// Node colors matching the backend
const NODE_COLORS = {
  Disease: '#FF4B4B',
  Symptom: '#FFA500',
  Precaution: '#636EFA',
  Drug: '#00CC96',
  Condition: '#E879F9',
  Patient: '#555555',
}

const LEGEND_ITEMS = [
  { label: 'Disease', color: '#FF4B4B', icon: '🦠' },
  { label: 'Symptom', color: '#FFA500', icon: '⚠️' },
  { label: 'Drug', color: '#00CC96', icon: '💊' },
  { label: 'Precaution', color: '#636EFA', icon: '🛡️' },
]

const QUALIFIER_PATTERN = /\b(organism unspecified|unspecified|not otherwise specified|nos|without mention of complication|site not specified|unknown etiology)\b/gi

const prettifyGraphTerm = (term) => {
  return term
    .split(' ')
    .filter(Boolean)
    .map((word) => {
      if (word.length <= 4 && word === word.toUpperCase()) return word
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    })
    .join(' ')
}

const normalizeGraphTerm = (term) => {
  if (!term) return ''

  let cleaned = String(term)
    .replace(/\((?:[^)(]+)\)/g, ' ')
    .replace(/[_/]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  const commaParts = cleaned.split(',').map(part => part.trim()).filter(Boolean)
  if (commaParts.length > 1) {
    const qualifierTail = commaParts.slice(1).join(' ')
    if (QUALIFIER_PATTERN.test(qualifierTail)) {
      cleaned = commaParts[0]
    }
    QUALIFIER_PATTERN.lastIndex = 0
  }

  cleaned = cleaned
    .replace(QUALIFIER_PATTERN, ' ')
    .replace(/\s*,\s*/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  if (!cleaned) return ''
  return prettifyGraphTerm(cleaned)
}

const extractGraphTerms = (rawContext) => {
  if (!rawContext) return []

  const rawParts = String(rawContext)
    .split(/\n|;|•|\. (?=[A-Za-z])/g)
    .map(part => part.trim())
    .filter(Boolean)

  const sourceParts = rawParts.length > 0 ? rawParts : [rawContext]
  const seen = new Set()
  const normalized = []

  for (const part of sourceParts) {
    const cleaned = normalizeGraphTerm(part)
    if (!cleaned) continue
    const key = cleaned.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    normalized.push(cleaned)
  }

  return normalized
}

function KnowledgeGraphPanel({
  syncedSearchTerm = '',
  patientId = null,
  syncLabel = '',
  allowManualOverride = true,
}) {
  const [searchInput, setSearchInput] = useState('')
  const [manualSearchTerm, setManualSearchTerm] = useState('')
  const [manualOverride, setManualOverride] = useState(false)
  const [activeSyncedTerm, setActiveSyncedTerm] = useState('')
  const [graphData, setGraphData] = useState({ nodes: [], links: [] })
  const [stats, setStats] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)
  const [error, setError] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const [hoveredNode, setHoveredNode] = useState(null)
  const graphRef = useRef()
  const canvasWrapRef = useRef()
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 })
  const syncedTerms = useMemo(() => extractGraphTerms(syncedSearchTerm), [syncedSearchTerm])

  // Observe the actual canvas area so the graph uses the full remaining space.
  useEffect(() => {
    if (!canvasWrapRef.current) return
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDimensions({
          width: Math.max(entry.contentRect.width, 260),
          height: Math.max(entry.contentRect.height, 320)
        })
      }
    })
    observer.observe(canvasWrapRef.current)
    return () => observer.disconnect()
  }, [])

  const fetchGraph = useCallback(async (term, activePatientId = patientId) => {
    if (!term || term.trim().length < 2) return

    setIsLoading(true)
    setError(null)
    setSelectedNode(null)

    try {
      const params = new URLSearchParams({ search_term: term.trim() })
      if (activePatientId) {
        params.set('patient_id', activePatientId)
      }
      const res = await fetch(`${API_BASE}/graph?${params.toString()}`)
      if (!res.ok) throw new Error('Failed to fetch graph data')
      const data = await res.json()

      if (data.nodes.length === 0) {
        setError(`No results found for "${term}"`)
        setGraphData({ nodes: [], links: [] })
        setStats(null)
        return
      }

      // Convert edges to links
      const links = data.edges.map((e, i) => ({
        id: `edge_${i}`,
        source: e.source,
        target: e.target,
        color: e.color || '#888',
        label: e.label || '',
        dashes: e.dashes || false,
        width: e.width || 1,
      }))

      // Enrich nodes
      const nodes = data.nodes.map((n) => ({
        ...n,
        val: n.size || 20,
        nodeColor: n.color || NODE_COLORS[n.type] || '#888',
      }))

      setGraphData({ nodes, links })
      setStats(data.stats || null)

      // Zoom to fit
      setTimeout(() => {
        graphRef.current?.zoomToFit(400, 60)
      }, 600)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }, [patientId])

  useEffect(() => {
    setManualOverride(false)
    setManualSearchTerm('')
    setSearchInput('')
    setActiveSyncedTerm(syncedTerms[0] || '')
  }, [patientId, syncedTerms])

  useEffect(() => {
    if (!syncedTerms.length) {
      setActiveSyncedTerm('')
      return
    }

    setActiveSyncedTerm(prev => (
      prev && syncedTerms.includes(prev) ? prev : syncedTerms[0]
    ))
  }, [syncedTerms])

  useEffect(() => {
    const activeTerm = (manualOverride ? manualSearchTerm : activeSyncedTerm || '').trim()
    if (activeTerm.length < 2) {
      setGraphData({ nodes: [], links: [] })
      setStats(null)
      setError(null)
      setSelectedNode(null)
      return
    }
    fetchGraph(activeTerm, patientId)
  }, [fetchGraph, manualOverride, manualSearchTerm, activeSyncedTerm, patientId])

  // Configure d3 forces for better node spacing
  useEffect(() => {
    if (graphRef.current) {
      graphRef.current.d3Force('charge')?.strength(-200)
      graphRef.current.d3Force('link')?.distance(80)
    }
  }, [graphData])

  useEffect(() => {
    if (!isExpanded) return undefined

    const previousOverflow = document.body.style.overflow
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setIsExpanded(false)
      }
    }

    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', handleEscape)

    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', handleEscape)
    }
  }, [isExpanded])

  const handleSearch = (e) => {
    e.preventDefault()
    const nextTerm = normalizeGraphTerm(searchInput.trim()) || searchInput.trim()
    if (!allowManualOverride || nextTerm.length < 2) return
    setManualSearchTerm(nextTerm)
    setManualOverride(true)
    setSearchInput(nextTerm)
  }

  const resetToSyncedContext = () => {
    setManualOverride(false)
    setManualSearchTerm('')
    setSearchInput('')
  }

  // Custom node rendering
  const nodeCanvasObject = useCallback((node, ctx, globalScale) => {
    // Guard: skip if node hasn't been positioned by the simulation yet
    if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return

    const label = node.label || ''
    const nodeRadius = Math.sqrt(node.val) * 1.5
    const isSelected = selectedNode?.id === node.id
    const isHovered = hoveredNode === node.id
    const isDiseaseNode = node.type === 'Disease'

    // Glow effect for disease node
    if (isDiseaseNode) {
      const gradient = ctx.createRadialGradient(node.x, node.y, nodeRadius, node.x, node.y, nodeRadius * 2.5)
      gradient.addColorStop(0, 'rgba(255, 75, 75, 0.3)')
      gradient.addColorStop(1, 'rgba(255, 75, 75, 0)')
      ctx.beginPath()
      ctx.arc(node.x, node.y, nodeRadius * 2.5, 0, 2 * Math.PI)
      ctx.fillStyle = gradient
      ctx.fill()
    }

    // Node circle
    ctx.beginPath()
    ctx.arc(node.x, node.y, nodeRadius, 0, 2 * Math.PI)
    ctx.fillStyle = node.nodeColor
    ctx.fill()

    // Selection / hover ring
    if (isSelected || isHovered) {
      ctx.strokeStyle = isSelected ? '#fff' : 'rgba(255,255,255,0.5)'
      ctx.lineWidth = (isSelected ? 3 : 2) / globalScale
      ctx.stroke()
    }

    // Label
    const fontSize = isDiseaseNode
      ? Math.max(14 / globalScale, 5)
      : Math.max(11 / globalScale, 3)

    ctx.font = `${isDiseaseNode ? 'bold ' : ''}${fontSize}px 'Inter', 'Segoe UI', sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'

    if (globalScale > 0.4) {
      const displayLabel = isDiseaseNode ? label.toUpperCase() : label
      const textWidth = ctx.measureText(displayLabel).width
      const pad = 3 / globalScale
      const textY = node.y + nodeRadius + fontSize / 2 + 4 / globalScale

      // Text background
      ctx.fillStyle = 'rgba(255, 255, 255, 0.92)'
      ctx.beginPath()
      const bgRadius = 3 / globalScale
      const bgX = node.x - textWidth / 2 - pad
      const bgY = textY - fontSize / 2 - pad
      const bgW = textWidth + pad * 2
      const bgH = fontSize + pad * 2
      ctx.roundRect(bgX, bgY, bgW, bgH, bgRadius)
      ctx.fill()

      // Text
      ctx.fillStyle = isDiseaseNode ? '#1a1a1a' : '#4a4a4a'
      ctx.fillText(displayLabel, node.x, textY)
    }
  }, [selectedNode, hoveredNode])

  // Custom link rendering — no labels on canvas to keep it clean
  const linkCanvasObject = useCallback((link, ctx) => {
    const start = link.source
    const end = link.target
    if (!Number.isFinite(start.x) || !Number.isFinite(end.x)) return

    ctx.beginPath()
    ctx.strokeStyle = link.color || '#555'
    ctx.lineWidth = link.width || 1

    if (link.dashes) {
      ctx.setLineDash([4, 4])
    } else {
      ctx.setLineDash([])
    }

    ctx.moveTo(start.x, start.y)
    ctx.lineTo(end.x, end.y)
    ctx.stroke()
    ctx.setLineDash([])
  }, [])

  const handleNodeClick = useCallback((node) => {
    setSelectedNode(prev => prev?.id === node.id ? null : node)
  }, [])

  const hasData = graphData.nodes.length > 0
  const activeContextTerm = (manualOverride ? manualSearchTerm : activeSyncedTerm || '').trim()
  const contextLabel = manualOverride ? 'Manual Override' : 'Synced Context'
  const contextDescription = manualOverride
    ? 'Using a manual graph search. Reset to resume automatic sync.'
    : (syncLabel || 'Auto-synced to the active patient and latest clinical context.')
  const visibleContextTerms = manualOverride
    ? [manualSearchTerm].filter(Boolean)
    : syncedTerms

  const handleSyncedTermSelect = (term) => {
    if (manualOverride) return
    setActiveSyncedTerm(term)
  }

  // Get edges connected to selected node
  const getNodeEdges = (nodeId) => {
    return graphData.links.filter(l =>
      (l.source?.id || l.source) === nodeId ||
      (l.target?.id || l.target) === nodeId
    )
  }

  return (
    <>
      {isExpanded && (
        <div
          className="graph-panel-backdrop"
          onClick={() => setIsExpanded(false)}
          aria-hidden="true"
        />
      )}
      <div className={`graph-panel ${isExpanded ? 'graph-panel--expanded' : ''}`}>
      <div className="graph-sync-bar">
        <div className="graph-sync-top">
          <div className="graph-sync-pill">
            <Link2 size={12} />
            <span>{contextLabel}</span>
          </div>
          {visibleContextTerms.length > 1 && !manualOverride && (
            <div className="graph-sync-count">{visibleContextTerms.length} linked contexts</div>
          )}
          <button
            type="button"
            className="graph-expand-btn"
            onClick={() => setIsExpanded(prev => !prev)}
            title={isExpanded ? 'Close enlarged view' : 'Open enlarged view'}
          >
            {isExpanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            <span>{isExpanded ? 'Close view' : 'Enlarge view'}</span>
          </button>
          {allowManualOverride && manualOverride && (
            <button type="button" className="graph-sync-reset" onClick={resetToSyncedContext}>
              <RefreshCw size={14} />
              Reset
            </button>
          )}
        </div>

        {visibleContextTerms.length > 0 ? (
          <div className="graph-context-chips">
            {visibleContextTerms.map((term) => (
              <button
                key={term}
                type="button"
                className={`graph-context-chip ${activeContextTerm === term ? 'active' : ''}`}
                onClick={() => handleSyncedTermSelect(term)}
                disabled={manualOverride}
                title={term}
              >
                {term}
              </button>
            ))}
          </div>
        ) : (
          <div className="graph-sync-empty">No synced context yet.</div>
        )}

        <div className="graph-sync-desc">
          {contextDescription}
          {patientId && !manualOverride ? ` Patient ${patientId} is included in the graph query.` : ''}
        </div>
      </div>

      {/* Search bar */}
      <form className="graph-search" onSubmit={handleSearch}>
        <div className="graph-search-input-wrap">
          <Search size={18} className="graph-search-icon" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder={activeContextTerm ? `Override "${activeContextTerm}"` : 'Override graph focus'}
            className="graph-search-input"
          />
        </div>
        <button
          type="submit"
          className="graph-search-btn"
          disabled={!allowManualOverride || isLoading || searchInput.trim().length < 2}
        >
          {isLoading && manualOverride ? <Loader2 size={16} className="spin" /> : 'Apply'}
        </button>
      </form>

      {/* Stats bar */}
      {stats && hasData && (
        <div className="graph-stats-bar">
          <div className="graph-stat">
            <Activity size={14} />
            <span>{stats.symptoms} symptoms</span>
          </div>
          <div className="graph-stat">
            <Pill size={14} />
            <span>{stats.drugs} drugs</span>
          </div>
          <div className="graph-stat">
            <Shield size={14} />
            <span>{stats.precautions} precautions</span>
          </div>
          {stats.interactions > 0 && (
            <div className="graph-stat graph-stat-warn">
              <AlertTriangle size={14} />
              <span>{stats.interactions} interactions</span>
            </div>
          )}
          {stats.contraindications > 0 && (
            <div className="graph-stat graph-stat-danger">
              <AlertTriangle size={14} />
              <span>{stats.contraindications} contraindicated</span>
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && <div className="graph-error">{error}</div>}

      {/* Empty state */}
      {!hasData && !isLoading && !error && (
        <div className="graph-empty">
          <Network size={64} strokeWidth={1} />
          <h3>Knowledge Graph</h3>
          <p>
            {activeContextTerm
              ? `No graph data is available for "${activeContextTerm}" yet.`
              : 'Select a patient or ask a question to sync the graph automatically.'}
          </p>
        </div>
      )}

      {/* Graph + optional detail sidebar */}
      {hasData && (
        <div className={`graph-content-area ${isExpanded ? 'graph-content-area--expanded' : ''}`}>
          <div className="graph-canvas-wrap" ref={canvasWrapRef}>
            <ForceGraph2D
              ref={graphRef}
              graphData={graphData}
              width={dimensions.width}
              height={dimensions.height}
              nodeCanvasObject={nodeCanvasObject}
              nodePointerAreaPaint={(node, color, ctx) => {
                if (!Number.isFinite(node.x)) return
                const r = Math.sqrt(node.val) * 1.5 + 4
                ctx.beginPath()
                ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
                ctx.fillStyle = color
                ctx.fill()
              }}
              linkCanvasObject={linkCanvasObject}
              onNodeHover={(node) => setHoveredNode(node?.id || null)}
              onNodeClick={handleNodeClick}
              backgroundColor="transparent"
              cooldownTicks={100}
              d3AlphaDecay={0.03}
              d3VelocityDecay={0.3}
            />
          </div>

          {/* Detail sidebar */}
          {selectedNode && (
            <div className="graph-detail-sidebar">
              <div className="graph-detail-header">
                <div className="graph-detail-type-badge" style={{ background: selectedNode.color }}>
                  {selectedNode.type}
                </div>
                <button className="graph-detail-close" onClick={() => setSelectedNode(null)}>
                  <X size={16} />
                </button>
              </div>

              <h3 className="graph-detail-name">{selectedNode.label}</h3>

              {selectedNode.title && (
                <p className="graph-detail-desc">{selectedNode.title}</p>
              )}

              {selectedNode.cui && (
                <div className="graph-detail-meta">
                  <span className="graph-detail-meta-label">CUI:</span>
                  <span>{selectedNode.cui}</span>
                </div>
              )}

              {selectedNode.drug_class && (
                <div className="graph-detail-meta">
                  <span className="graph-detail-meta-label">Class:</span>
                  <span>{selectedNode.drug_class}</span>
                </div>
              )}

              {selectedNode.dosage && (
                <div className="graph-detail-meta">
                  <span className="graph-detail-meta-label">Dosage:</span>
                  <span>{selectedNode.dosage}</span>
                </div>
              )}

              {selectedNode.line && (
                <div className="graph-detail-meta">
                  <span className="graph-detail-meta-label">Line:</span>
                  <span className={`graph-line-badge ${selectedNode.line === 'first_line' ? 'first' : 'second'}`}>
                    {selectedNode.line === 'first_line' ? '1st Line' : '2nd Line'}
                  </span>
                </div>
              )}

              {selectedNode.severity && (
                <div className="graph-detail-meta">
                  <span className="graph-detail-meta-label">Severity:</span>
                  <span>{selectedNode.severity}/7</span>
                </div>
              )}

              {/* Connected nodes */}
              <div className="graph-detail-connections">
                <h4>Connections</h4>
                {getNodeEdges(selectedNode.id).map((edge, i) => {
                  const otherId = (edge.source?.id || edge.source) === selectedNode.id
                    ? (edge.target?.id || edge.target)
                    : (edge.source?.id || edge.source)
                  const otherNode = graphData.nodes.find(n => n.id === otherId)
                  if (!otherNode) return null
                  return (
                    <div
                      key={i}
                      className="graph-detail-connection"
                      onClick={() => setSelectedNode(otherNode)}
                    >
                      <span className="graph-conn-dot" style={{ background: otherNode.color }} />
                      <span className="graph-conn-name">{otherNode.label}</span>
                      <span className="graph-conn-rel">{edge.label}</span>
                      <ChevronRight size={12} className="graph-conn-arrow" />
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Legend */}
      {hasData && (
        <div className="graph-legend">
          {LEGEND_ITEMS.map((item) => (
            <div key={item.label} className="legend-item">
              <span className="legend-dot" style={{ backgroundColor: item.color }} />
              <span>{item.label}</span>
            </div>
          ))}
        </div>
      )}
      </div>
    </>
  )
}

export default KnowledgeGraphPanel
