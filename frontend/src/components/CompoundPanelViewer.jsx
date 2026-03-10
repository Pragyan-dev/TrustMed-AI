import { useState } from 'react'
import { Grid2x2, ImageIcon, X, ZoomIn, Loader2 } from 'lucide-react'

const API_BASE = '/api'

function CompoundPanelViewer({ panelData, isDetecting }) {
  const [selectedPanel, setSelectedPanel] = useState(null)

  // No data yet
  if (!panelData && !isDetecting) {
    return (
      <div className="panel-viewer">
        <div className="panel-empty">
          <ImageIcon size={64} strokeWidth={1} />
          <h3>Image Panel Viewer</h3>
          <p>Upload a medical image in the Chat tab to automatically detect compound figures. If the image contains multiple panels (A, B, C...), they will be split and displayed here.</p>
        </div>
      </div>
    )
  }

  // Loading
  if (isDetecting) {
    return (
      <div className="panel-viewer">
        <div className="panel-empty">
          <Loader2 size={48} className="spin" />
          <h3>Detecting Panels...</h3>
          <p>Analyzing image for compound figure structure</p>
        </div>
      </div>
    )
  }

  // Not compound
  if (!panelData.is_compound) {
    return (
      <div className="panel-viewer">
        <div className="panel-empty">
          <ImageIcon size={64} strokeWidth={1} />
          <h3>Single Panel Image</h3>
          <p>This image was not detected as a compound figure. No subfigures to display.</p>
          <div className="panel-info-chip">
            Confidence: {((1 - panelData.confidence) * 100).toFixed(0)}% single image
          </div>
        </div>
      </div>
    )
  }

  // Compound figure detected — show panels
  return (
    <div className="panel-viewer">
      {/* Header info */}
      <div className="panel-header">
        <div className="panel-header-left">
          <Grid2x2 size={20} />
          <h3>Compound Figure Detected</h3>
        </div>
        <div className="panel-header-chips">
          <span className="panel-info-chip">{panelData.num_panels} panels</span>
          <span className="panel-info-chip">Layout: {panelData.layout}</span>
          <span className="panel-info-chip">Confidence: {(panelData.confidence * 100).toFixed(0)}%</span>
          {panelData.grid_structure && (
            <span className="panel-info-chip">
              Grid: {panelData.grid_structure[0]}×{panelData.grid_structure[1]}
            </span>
          )}
        </div>
      </div>

      {/* Panel grid */}
      <div className="panel-grid" style={{
        gridTemplateColumns: panelData.grid_structure
          ? `repeat(${panelData.grid_structure[1]}, 1fr)`
          : `repeat(${Math.min(panelData.num_panels, 3)}, 1fr)`
      }}>
        {panelData.panels.map((panel) => (
          <div
            key={panel.panel_id}
            className="panel-card"
            onClick={() => setSelectedPanel(panel)}
          >
            <div className="panel-card-image-wrap">
              <img
                src={`${API_BASE}${panel.image_url}`}
                alt={`Panel ${panel.label}`}
                className="panel-card-image"
              />
              <div className="panel-card-zoom">
                <ZoomIn size={16} />
              </div>
            </div>
            <div className="panel-card-info">
              <span className="panel-label-badge">{panel.label}</span>
              <span className="panel-card-meta">
                {panel.bbox.width}×{panel.bbox.height}px
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Full-size modal */}
      {selectedPanel && (
        <div className="panel-modal-overlay" onClick={() => setSelectedPanel(null)}>
          <div className="panel-modal" onClick={(e) => e.stopPropagation()}>
            <div className="panel-modal-header">
              <span className="panel-label-badge">{selectedPanel.label}</span>
              <span className="panel-card-meta">
                {selectedPanel.bbox.width}×{selectedPanel.bbox.height}px |
                Position: ({selectedPanel.grid_position[0]}, {selectedPanel.grid_position[1]})
              </span>
              <button className="panel-modal-close" onClick={() => setSelectedPanel(null)}>
                <X size={18} />
              </button>
            </div>
            <img
              src={`${API_BASE}${selectedPanel.image_url}`}
              alt={`Panel ${selectedPanel.label} (full)`}
              className="panel-modal-image"
            />
          </div>
        </div>
      )}
    </div>
  )
}

export default CompoundPanelViewer
