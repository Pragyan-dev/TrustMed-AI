import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import {
  Search, Network, Loader2, X, Pill, Activity, Shield,
  AlertTriangle, RefreshCw, Link2, Maximize2, Minimize2, ChevronRight
} from 'lucide-react'
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from 'd3-force'
import { drag } from 'd3-drag'
import { select } from 'd3-selection'

const API_BASE = '/api'

const NODE_COLORS = {
  Disease: '#FF4B4B',
  Symptom: '#FFA500',
  Precaution: '#636EFA',
  Drug: '#00CC96',
  Condition: '#E879F9',
  Patient: '#555555',
}

const NODE_RADII = {
  Disease: 22,
  Drug: 15,
  Symptom: 11,
  Precaution: 10,
  Condition: 12,
  Patient: 16,
}

const LEGEND_ITEMS = [
  { label: 'Disease', color: '#FF4B4B' },
  { label: 'Symptom', color: '#FFA500' },
  { label: 'Drug', color: '#00CC96' },
  { label: 'Precaution', color: '#636EFA' },
]

const normalizeGraphTerm = (term) => {
  if (!term) return ''
  return String(term)
    .replace(/\[(?:system\s+)?Note:\s*[^\]]+\]/gi, ' ')
    .replace(/\[.*?\]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .split(' ')
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ')
}

const extractGraphTerms = (rawContext) => {
  if (!rawContext) return []
  const seen = new Set()
  return String(rawContext)
    .split(/\n|;|•|\. (?=[A-Za-z])/g)
    .map((p) => normalizeGraphTerm(p.trim()))
    .filter((t) => t.length >= 2 && !seen.has(t.toLowerCase()) && seen.add(t.toLowerCase()))
}

// ─── Pure D3 Canvas Force Graph ───────────────────────────────────────────────

function ForceGraphCanvas({ nodes: rawNodes, edges: rawEdges, width, height, onNodeClick, selectedNodeId }) {
  const canvasRef = useRef(null)
  const simRef = useRef(null)
  const nodesRef = useRef([])
  const linksRef = useRef([])
  const selectedIdRef = useRef(selectedNodeId)
  const animFrameRef = useRef(null)

  // Keep selectedIdRef in sync without restarting simulation
  useEffect(() => {
    selectedIdRef.current = selectedNodeId
    drawFrame()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNodeId])

  const drawFrame = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1
    const w = canvas.width / dpr
    const h = canvas.height / dpr

    ctx.save()
    ctx.scale(dpr, dpr)
    ctx.clearRect(0, 0, w, h)

    // Draw edges
    linksRef.current.forEach((link) => {
      const s = link.source
      const t = link.target
      if (!Number.isFinite(s.x) || !Number.isFinite(t.x)) return

      ctx.beginPath()
      ctx.strokeStyle = link.color || '#555'
      ctx.lineWidth = link.width || 1
      if (link.dashes) ctx.setLineDash([5, 5])
      else ctx.setLineDash([])
      ctx.moveTo(s.x, s.y)
      ctx.lineTo(t.x, t.y)
      ctx.stroke()
      ctx.setLineDash([])
    })

    // Draw nodes
    nodesRef.current.forEach((node) => {
      if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return
      const r = NODE_RADII[node.type] || 12
      const isSelected = selectedIdRef.current === node.id
      const color = NODE_COLORS[node.type] || '#888'
      const isDisease = node.type === 'Disease'

      // Glow for disease
      if (isDisease) {
        const grad = ctx.createRadialGradient(node.x, node.y, r, node.x, node.y, r * 2.5)
        grad.addColorStop(0, 'rgba(255,75,75,0.3)')
        grad.addColorStop(1, 'rgba(255,75,75,0)')
        ctx.beginPath()
        ctx.arc(node.x, node.y, r * 2.5, 0, 2 * Math.PI)
        ctx.fillStyle = grad
        ctx.fill()
      }

      // Circle
      ctx.beginPath()
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
      ctx.fillStyle = color
      ctx.fill()

      // Selection ring
      if (isSelected) {
        ctx.strokeStyle = '#ffffff'
        ctx.lineWidth = 2.5
        ctx.stroke()
      }

      // Label
      const fontSize = isDisease ? 11 : 9
      ctx.font = `${isDisease ? 'bold ' : ''}${fontSize}px Inter, sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      const label = node.label || ''
      const textY = node.y + r + 3
      const tw = ctx.measureText(label).width
      const pad = 2

      ctx.fillStyle = 'rgba(18,18,18,0.80)'
      ctx.beginPath()
      ctx.roundRect(node.x - tw / 2 - pad, textY - pad, tw + pad * 2, fontSize + pad * 2, 3)
      ctx.fill()

      ctx.fillStyle = isDisease ? '#ffffff' : '#dddddd'
      ctx.fillText(label, node.x, textY)
    })

    ctx.restore()
  }, [])

  useEffect(() => {
    if (!canvasRef.current || rawNodes.length === 0) return

    const canvas = canvasRef.current
    const dpr = window.devicePixelRatio || 1
    canvas.width = width * dpr
    canvas.height = height * dpr

    // Clone for D3 mutation
    const nodes = rawNodes.map((n) => ({ ...n }))
    const links = rawEdges.map((e) => ({
      ...e,
      source: e.source,
      target: e.target,
    }))

    nodesRef.current = nodes
    linksRef.current = links

    // Stop old simulation
    if (simRef.current) simRef.current.stop()

    const sim = forceSimulation(nodes)
      .force('link', forceLink(links).id((d) => d.id).distance(90).strength(0.7))
      .force('charge', forceManyBody().strength(-260))
      .force('center', forceCenter(width / 2, height / 2))
      .force('collide', forceCollide().radius((d) => (NODE_RADII[d.type] || 12) + 8))
      .alphaDecay(0.025)

    sim.on('tick', () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
      animFrameRef.current = requestAnimationFrame(drawFrame)
    })

    simRef.current = sim

    // ── Drag support ──
    const canvasSel = select(canvas)

    let dragSubject = null

    const findNode = (event) => {
      const rect = canvas.getBoundingClientRect()
      const scaleX = width / rect.width
      const scaleY = height / rect.height
      const mx = (event.clientX - rect.left) * scaleX
      const my = (event.clientY - rect.top) * scaleY
      return nodes.find((n) => {
        const r = (NODE_RADII[n.type] || 12) + 4
        return Math.hypot(n.x - mx, n.y - my) < r
      })
    }

    const dragHandler = drag()
      .on('start', function (event) {
        dragSubject = findNode(event.sourceEvent || event)
        if (!dragSubject) return
        if (!event.active) sim.alphaTarget(0.3).restart()
        dragSubject.fx = dragSubject.x
        dragSubject.fy = dragSubject.y
      })
      .on('drag', function (event) {
        if (!dragSubject) return
        const rect = canvas.getBoundingClientRect()
        const scaleX = width / rect.width
        const scaleY = height / rect.height
        const sourceEvent = event.sourceEvent || event
        dragSubject.fx = (sourceEvent.clientX - rect.left) * scaleX
        dragSubject.fy = (sourceEvent.clientY - rect.top) * scaleY
      })
      .on('end', function (event) {
        if (!dragSubject) return
        if (!event.active) sim.alphaTarget(0)
        dragSubject.fx = null
        dragSubject.fy = null
        dragSubject = null
      })

    canvasSel.call(dragHandler)

    // Click to select node
    const handleClick = (event) => {
      const node = findNode(event)
      onNodeClick(node || null)
    }
    canvas.addEventListener('click', handleClick)

    return () => {
      sim.stop()
      canvas.removeEventListener('click', handleClick)
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawNodes, rawEdges, width, height])

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: '100%',
        height: '100%',
        display: 'block',
        cursor: 'grab',
        borderRadius: '8px',
      }}
    />
  )
}

// ─── Main Panel ───────────────────────────────────────────────────────────────

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
  const [rawNodes, setRawNodes] = useState([])
  const [rawEdges, setRawEdges] = useState([])
  const [stats, setStats] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)
  const [error, setError] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const canvasWrapRef = useRef()
  const [dimensions, setDimensions] = useState({ width: 600, height: 400 })

  const syncedTerms = useMemo(() => extractGraphTerms(syncedSearchTerm), [syncedSearchTerm])

  // Observe container size
  useEffect(() => {
    if (!canvasWrapRef.current) return
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDimensions({
          width: Math.max(entry.contentRect.width || 300, 260),
          height: Math.max(entry.contentRect.height || 300, 240),
        })
      }
    })
    observer.observe(canvasWrapRef.current)
    return () => observer.disconnect()
  }, [])

  const fetchGraph = useCallback(async (term) => {
    if (!term || term.trim().length < 2) return

    setIsLoading(true)
    setError(null)
    setSelectedNode(null)

    try {
      const params = new URLSearchParams({ search_term: term.trim() })
      if (patientId) params.set('patient_id', patientId)

      const res = await fetch(`${API_BASE}/graph?${params}`)
      if (!res.ok) throw new Error(`Server error ${res.status}`)

      const data = await res.json()

      if (data.error) {
        setError(data.error)
        setRawNodes([])
        setRawEdges([])
        setStats(null)
        return
      }

      if (!data.nodes || data.nodes.length === 0) {
        setError(`No graph data found for "${term}"`)
        setRawNodes([])
        setRawEdges([])
        setStats(null)
        return
      }

      setRawNodes(data.nodes)
      setRawEdges(data.edges || [])
      setStats(data.stats || null)
    } catch (err) {
      setError(err.message)
      setRawNodes([])
      setRawEdges([])
    } finally {
      setIsLoading(false)
    }
  }, [patientId])

  // Reset on patient change
  useEffect(() => {
    setManualOverride(false)
    setManualSearchTerm('')
    setSearchInput('')
    setActiveSyncedTerm(syncedTerms[0] || '')
  }, [patientId, syncedTerms])

  useEffect(() => {
    if (!syncedTerms.length) { setActiveSyncedTerm(''); return }
    setActiveSyncedTerm((prev) => (prev && syncedTerms.includes(prev) ? prev : syncedTerms[0]))
  }, [syncedTerms])

  // Auto-fetch
  useEffect(() => {
    const term = (manualOverride ? manualSearchTerm : activeSyncedTerm || '').trim()
    if (term.length < 2) { setRawNodes([]); setRawEdges([]); setStats(null); setError(null); return }
    fetchGraph(term)
  }, [fetchGraph, manualOverride, manualSearchTerm, activeSyncedTerm])

  // Expanded keyboard & scroll lock
  useEffect(() => {
    if (!isExpanded) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const esc = (e) => { if (e.key === 'Escape') setIsExpanded(false) }
    window.addEventListener('keydown', esc)
    return () => { document.body.style.overflow = prev; window.removeEventListener('keydown', esc) }
  }, [isExpanded])

  const handleSearch = (e) => {
    e.preventDefault()
    const next = normalizeGraphTerm(searchInput.trim()) || searchInput.trim()
    if (!allowManualOverride || next.length < 2) return
    setManualSearchTerm(next)
    setManualOverride(true)
    setSearchInput(next)
  }

  const resetToSyncedContext = () => {
    setManualOverride(false)
    setManualSearchTerm('')
    setSearchInput('')
  }

  const getNodeEdges = (nodeId) =>
    rawEdges.filter(
      (l) => l.source === nodeId || l.target === nodeId
    )

  const hasData = rawNodes.length > 0
  const activeContextTerm = (manualOverride ? manualSearchTerm : activeSyncedTerm || '').trim()
  const contextLabel = manualOverride ? 'Manual Override' : 'Synced Context'
  const contextDescription = manualOverride
    ? 'Using a manual graph search. Reset to resume automatic sync.'
    : syncLabel || 'Auto-synced to the active patient and latest clinical context.'
  const visibleContextTerms = manualOverride ? [manualSearchTerm].filter(Boolean) : syncedTerms

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

        {/* Sync bar */}
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
              onClick={() => setIsExpanded((p) => !p)}
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
                  onClick={() => !manualOverride && setActiveSyncedTerm(term)}
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

        {/* Search */}
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

        {/* Loading state */}
        {isLoading && (
          <div className="graph-empty" style={{ opacity: 0.8 }}>
            <Loader2 size={32} className="spin" style={{ marginBottom: '0.5rem', color: '#636EFA' }} />
            <p>Loading graph for &ldquo;{activeContextTerm}&rdquo;…</p>
          </div>
        )}

        {/* Stats bar */}
        {stats && hasData && !isLoading && (
          <div className="graph-stats-bar">
            <div className="graph-stat"><Activity size={14} /><span>{stats.symptoms} symptoms</span></div>
            <div className="graph-stat"><Pill size={14} /><span>{stats.drugs} drugs</span></div>
            <div className="graph-stat"><Shield size={14} /><span>{stats.precautions} precautions</span></div>
            {stats.interactions > 0 && (
              <div className="graph-stat graph-stat-warn">
                <AlertTriangle size={14} /><span>{stats.interactions} interactions</span>
              </div>
            )}
            {stats.contraindications > 0 && (
              <div className="graph-stat graph-stat-danger">
                <AlertTriangle size={14} /><span>{stats.contraindications} contraindicated</span>
              </div>
            )}
          </div>
        )}

        {/* Error */}
        {error && !isLoading && <div className="graph-error">{error}</div>}

        {/* Empty state */}
        {!hasData && !isLoading && !error && (
          <div className="graph-empty">
            <Network size={64} strokeWidth={1} />
            <h3>Knowledge Graph</h3>
            <p>
              {activeContextTerm
                ? `No graph data available for "${activeContextTerm}" yet.`
                : 'Select a patient or ask a question to sync the graph automatically.'}
            </p>
          </div>
        )}

        {/* Graph canvas + sidebar */}
        {hasData && !isLoading && (
          <div className={`graph-content-area ${isExpanded ? 'graph-content-area--expanded' : ''}`}>
            <div
              className="graph-canvas-wrap"
              ref={canvasWrapRef}
              style={{ flex: 1, minHeight: 0, position: 'relative' }}
            >
              <ForceGraphCanvas
                nodes={rawNodes}
                edges={rawEdges}
                width={dimensions.width}
                height={dimensions.height}
                onNodeClick={(node) => setSelectedNode((prev) => prev?.id === node?.id ? null : node)}
                selectedNodeId={selectedNode?.id || null}
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

                {selectedNode.title && <p className="graph-detail-desc">{selectedNode.title}</p>}

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

                <div className="graph-detail-connections">
                  <h4>Connections</h4>
                  {getNodeEdges(selectedNode.id).map((edge, i) => {
                    const otherId = edge.source === selectedNode.id ? edge.target : edge.source
                    const other = rawNodes.find((n) => n.id === otherId)
                    if (!other) return null
                    return (
                      <div key={i} className="graph-detail-connection" onClick={() => setSelectedNode(other)}>
                        <span className="graph-conn-dot" style={{ background: other.color }} />
                        <span className="graph-conn-name">{other.label}</span>
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
        {hasData && !isLoading && (
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
