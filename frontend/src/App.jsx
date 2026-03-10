import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  Send,
  Plus,
  Image as ImageIcon,
  FileText,
  Settings,
  Trash2,
  Stethoscope,
  X,
  Loader2,
  MessageSquare,
  PanelLeftClose,
  PanelLeft,
  Pencil,
  Check,
  Clock,
  Network,
  Grid2x2,
  Thermometer,
  Cpu,
  Eye
} from 'lucide-react'
import KnowledgeGraphPanel from './components/KnowledgeGraphPanel'
import CompoundPanelViewer from './components/CompoundPanelViewer'
import SOAPNoteModal from './components/SOAPNoteModal'
import PatientInfoPanel from './components/PatientInfoPanel'
import './App.css'

const API_BASE = '/api'

const AVAILABLE_MODELS = [
  { id: 'nvidia/nemotron-3-nano-30b-a3b:free', label: 'Nemotron Nano 30B (Free)' },
  { id: 'google/gemini-2.5-flash-preview', label: 'Gemini 2.5 Flash (Preview)' },
  { id: 'openai/gpt-oss-120b:free', label: 'GPT-120B (Free)' },
  { id: 'liquid/lfm-2.5-1.2b-thinking:free', label: 'Liquid FLM 2.5 (Free)' },
  { id: 'z-ai/glm-4.5-air:free', label: 'GLM 4.5 Air (Free)' },
  { id: 'qwen/qwen3-next-80b-a3b-instruct:free', label: 'Qwen 3 Next 80B (Free)' },
]

const AVAILABLE_VISION_MODELS = [
  { id: 'google/gemini-3-flash-preview', label: 'Gemini 3 Flash (Preview)' },
  { id: 'z-ai/glm-4.5-air:free', label: 'GLM 4.5 Air (Free)' },
  { id: 'google/gemini-3-pro-preview', label: 'Highest cost : Gemini 3 Pro (Preview)' },
  { id: 'meta-llama/llama-3.2-90b-vision-instruct:free', label: 'Llama 3.2 90B Vision (Free)' },
  { id: 'qwen/qwen-2-vl-7b-instruct:free', label: 'Qwen 2 VL 7B (Free)' },
]

function App() {
  // ─── State ──────────────────────────────────────────────────────
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [streamingStatus, setStreamingStatus] = useState('')
  const [selectedImage, setSelectedImage] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [uploadedImagePath, setUploadedImagePath] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [sessionTitle, setSessionTitle] = useState('New chat')
  const [sessions, setSessions] = useState([])
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [editingTitle, setEditingTitle] = useState(null)
  const [editTitleValue, setEditTitleValue] = useState('')

  // Tab & feature state
  const [activeTab, setActiveTab] = useState('chat')
  const [panelData, setPanelData] = useState(null)
  const [isDetectingPanels, setIsDetectingPanels] = useState(false)

  // Settings state
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [temperature, setTemperature] = useState(0.1)
  const [selectedModel, setSelectedModel] = useState(AVAILABLE_MODELS[0].id)
  const [selectedVisionModel, setSelectedVisionModel] = useState(AVAILABLE_VISION_MODELS[0].id)

  const messagesEndRef = useRef(null)
  const fileInputRef = useRef(null)
  const uploadPromiseRef = useRef(null)
  const textareaRef = useRef(null)

  // ─── Load sessions on mount ─────────────────────────────────────
  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`)
      const data = await res.json()
      setSessions(data.sessions || [])
    } catch (err) {
      console.error('Failed to load sessions:', err)
    }
  }, [])

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  // ─── Auto-scroll ────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ─── Auto-resize textarea ───────────────────────────────────────
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px'
    }
  }, [input])

  // ─── Session Management ─────────────────────────────────────────
  const createNewSession = async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions/new`, { method: 'POST' })
      const data = await res.json()
      setSessionId(data.id)
      setSessionTitle('New chat')
      setMessages([])
      setPanelData(null)
      removeImage()
      await fetchSessions()
    } catch (err) {
      console.error('Failed to create session:', err)
    }
  }

  const loadSession = async (sid) => {
    try {
      const res = await fetch(`${API_BASE}/sessions/${sid}`)
      const data = await res.json()
      setSessionId(data.id)
      setSessionTitle(data.title || 'Untitled')
      setMessages(data.messages || [])
      setPanelData(null)
      removeImage()
    } catch (err) {
      console.error('Failed to load session:', err)
    }
  }

  const deleteSession = async (sid, e) => {
    e.stopPropagation()
    try {
      await fetch(`${API_BASE}/clear-session?session_id=${sid}`, { method: 'POST' })
      if (sessionId === sid) {
        setSessionId(null)
        setSessionTitle('New chat')
        setMessages([])
        setPanelData(null)
      }
      await fetchSessions()
    } catch (err) {
      console.error('Failed to delete session:', err)
    }
  }

  const startRename = (sid, currentTitle, e) => {
    e.stopPropagation()
    setEditingTitle(sid)
    setEditTitleValue(currentTitle)
  }

  const finishRename = async (sid) => {
    if (!editTitleValue.trim()) {
      setEditingTitle(null)
      return
    }
    try {
      await fetch(`${API_BASE}/sessions/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sid, title: editTitleValue.trim() })
      })
      if (sessionId === sid) {
        setSessionTitle(editTitleValue.trim())
      }
      await fetchSessions()
    } catch (err) {
      console.error('Failed to rename:', err)
    }
    setEditingTitle(null)
  }

  // ─── Image Handling ─────────────────────────────────────────────
  const handleImageSelect = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setSelectedImage(file)
    setImagePreview(URL.createObjectURL(file))
    setIsUploading(true)

    const formData = new FormData()
    formData.append('file', file)

    // Store the upload promise so handleSubmit can await it
    uploadPromiseRef.current = (async () => {
      try {
        const response = await fetch(`${API_BASE}/upload-image`, {
          method: 'POST',
          body: formData
        })
        const data = await response.json()
        setUploadedImagePath(data.path)
        detectPanels(data.path)
        return data.path
      } catch (error) {
        console.error('Failed to upload image:', error)
        return null
      } finally {
        setIsUploading(false)
      }
    })()
  }

  const detectPanels = async (imagePath) => {
    setIsDetectingPanels(true)
    try {
      const res = await fetch(`${API_BASE}/detect-panels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_path: imagePath })
      })
      const data = await res.json()
      setPanelData(data)
    } catch (err) {
      console.error('Panel detection failed:', err)
      setPanelData(null)
    } finally {
      setIsDetectingPanels(false)
    }
  }

  const removeImage = () => {
    setSelectedImage(null)
    setImagePreview(null)
    setUploadedImagePath(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  // ─── Submit Message ─────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e?.preventDefault()
    if (!input.trim() && !selectedImage) return

    // Auto-create a session if none exists
    let currentSessionId = sessionId
    if (!currentSessionId) {
      try {
        const res = await fetch(`${API_BASE}/sessions/new`, { method: 'POST' })
        const data = await res.json()
        currentSessionId = data.id
        setSessionId(data.id)
      } catch (err) {
        console.error('Failed to create session:', err)
        return
      }
    }

    // Wait for image upload to finish (properly await the upload promise)
    if (selectedImage && !uploadedImagePath && uploadPromiseRef.current) {
      await uploadPromiseRef.current
    }

    const userMessage = {
      role: 'user',
      content: input || 'Analyze this medical image',
      image: imagePreview
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)
    setStreamingStatus('Connecting…')

    const imagePath = uploadedImagePath
    removeImage()

    try {
      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage.content,
          session_id: currentSessionId,
          image_path: imagePath,
          temperature: temperature,
          model: selectedModel,
          vision_model: selectedVisionModel
        })
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let assistantAdded = false

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // keep incomplete line in buffer

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const jsonStr = line.slice(6).trim()
          if (!jsonStr) continue

          try {
            const event = JSON.parse(jsonStr)

            if (event.type === 'progress') {
              setStreamingStatus(event.message)
            } else if (event.type === 'token') {
              if (!assistantAdded) {
                // Add empty assistant message to start streaming into
                setMessages(prev => [...prev, { role: 'assistant', content: '' }])
                assistantAdded = true
                setStreamingStatus('')  // hide progress, show tokens
              }
              // Append token to the last assistant message
              setMessages(prev => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                updated[updated.length - 1] = { ...last, content: last.content + event.content }
                return updated
              })
            } else if (event.type === 'replace') {
              // Safety critic override — replace entire assistant message
              setMessages(prev => {
                const updated = [...prev]
                if (!assistantAdded || updated[updated.length - 1]?.role !== 'assistant') {
                  // No assistant placeholder yet — add one instead of overwriting user message
                  updated.push({ role: 'assistant', content: event.content })
                  assistantAdded = true
                } else {
                  updated[updated.length - 1] = { role: 'assistant', content: event.content }
                }
                return updated
              })
            } else if (event.type === 'done') {
              if (event.title) setSessionTitle(event.title)
              if (event.session_id) setSessionId(event.session_id)
              // If no tokens were streamed (edge case), add the response
              if (!assistantAdded && event.final_response) {
                setMessages(prev => [...prev, { role: 'assistant', content: event.final_response }])
              }
            } else if (event.type === 'patient_context') {
              // Patient ID detected — fetch structured patient data for panel
              if (event.patient_id) {
                fetch(`${API_BASE}/patient/${event.patient_id}`)
                  .then(r => r.ok ? r.json() : null)
                  .then(data => { if (data) setPatientData(data) })
                  .catch(err => console.warn('Patient data fetch failed:', err))
              }
            } else if (event.type === 'error') {
              if (!assistantAdded) {
                setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${event.message}` }])
              }
            }
          } catch (parseErr) {
            console.warn('SSE parse error:', parseErr, jsonStr)
          }
        }
      }

      await fetchSessions()
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${error.message}. Make sure the API server is running on port 8000.`
      }])
    } finally {
      setIsLoading(false)
      setStreamingStatus('')
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  // ─── SOAP Note ──────────────────────────────────────────────────
  const [patientData, setPatientData] = useState(null)
  const [soapModalOpen, setSoapModalOpen] = useState(false)
  const [soapData, setSoapData] = useState(null)
  const [soapLoading, setSoapLoading] = useState(false)

  const generateSOAPNote = async () => {
    if (messages.length === 0 || !sessionId) return

    setSoapModalOpen(true)
    setSoapLoading(true)
    setSoapData(null)
    try {
      const response = await fetch(`${API_BASE}/soap-note`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
      })
      if (!response.ok) throw new Error('Failed to generate SOAP note')
      const data = await response.json()
      setSoapData(data)
    } catch (error) {
      console.error('Failed to generate SOAP note:', error)
    } finally {
      setSoapLoading(false)
    }
  }

  // ─── Helpers ────────────────────────────────────────────────────
  const formatTime = (timestamp) => {
    if (!timestamp) return ''
    const date = new Date(timestamp * 1000)
    const now = new Date()
    const diff = now - date
    if (diff < 86400000) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    if (diff < 604800000) {
      return date.toLocaleDateString([], { weekday: 'short' })
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
  }

  // ─── Render ─────────────────────────────────────────────────────
  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? '' : 'sidebar-collapsed'}`}>
        <div className="sidebar-header">
          <button className="new-chat-btn" onClick={createNewSession}>
            <Plus size={18} />
            <span>New chat</span>
          </button>
          <button className="toggle-sidebar-btn" onClick={() => setSidebarOpen(false)}>
            <PanelLeftClose size={18} />
          </button>
        </div>

        <div className="sidebar-content">
          <div className="brand">
            <Stethoscope size={24} className="brand-icon" />
            <span className="brand-text">TrustMed AI</span>
          </div>

          {/* Chat History */}
          <div className="history-section">
            <h3 className="section-header">Recent chats</h3>
            <div className="history-list">
              {sessions.length === 0 && (
                <p className="no-sessions">No previous chats</p>
              )}
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className={`history-item ${sessionId === s.id ? 'active' : ''}`}
                  onClick={() => loadSession(s.id)}
                >
                  {editingTitle === s.id ? (
                    <div className="rename-input-row" onClick={(e) => e.stopPropagation()}>
                      <input
                        className="rename-input"
                        value={editTitleValue}
                        onChange={(e) => setEditTitleValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') finishRename(s.id)
                          if (e.key === 'Escape') setEditingTitle(null)
                        }}
                        autoFocus
                      />
                      <button className="rename-confirm" onClick={() => finishRename(s.id)}>
                        <Check size={14} />
                      </button>
                    </div>
                  ) : (
                    <>
                      <MessageSquare size={16} className="history-icon" />
                      <div className="history-text">
                        <span className="history-title">{s.title}</span>
                        <span className="history-meta">
                          <Clock size={10} />
                          {formatTime(s.updated_at)}
                        </span>
                      </div>
                      <div className="history-actions">
                        <button onClick={(e) => startRename(s.id, s.title, e)} title="Rename">
                          <Pencil size={13} />
                        </button>
                        <button onClick={(e) => deleteSession(s.id, e)} title="Delete">
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Tools */}
          <div className="tools-section">
            <h3 className="section-header">Tools</h3>
            <button className="tool-btn" onClick={generateSOAPNote} disabled={messages.length === 0}>
              <FileText size={18} />
              <span>Generate SOAP Note</span>
            </button>
          </div>
        </div>

        <div className="sidebar-footer">
          <button className="footer-btn" onClick={() => setSettingsOpen(true)}>
            <Settings size={18} />
            <span>Settings</span>
          </button>
        </div>
      </aside>

      {/* Collapsed sidebar toggle */}
      {!sidebarOpen && (
        <button className="sidebar-open-btn" onClick={() => setSidebarOpen(true)}>
          <PanelLeft size={20} />
        </button>
      )}

      {/* Main Area */}
      <main className="chat-main">
        {/* Top bar with session title + tabs */}
        <div className="main-topbar">
          {sessionId && messages.length > 0 && (
            <div className="chat-topbar">
              <span className="topbar-title">{sessionTitle}</span>
            </div>
          )}

          {/* Tab bar */}
          <div className="tab-bar">
            <button
              className={`tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={() => setActiveTab('chat')}
            >
              <MessageSquare size={16} />
              <span>Chat</span>
            </button>
            <button
              className={`tab-btn ${activeTab === 'graph' ? 'active' : ''}`}
              onClick={() => setActiveTab('graph')}
            >
              <Network size={16} />
              <span>Knowledge Graph</span>
            </button>
            <button
              className={`tab-btn ${activeTab === 'panels' ? 'active' : ''}`}
              onClick={() => setActiveTab('panels')}
            >
              <Grid2x2 size={16} />
              <span>Image Panels</span>
              {panelData?.is_compound && (
                <span className="tab-badge">{panelData.num_panels}</span>
              )}
            </button>
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === 'chat' && (
          <>
            <div className="chat-container">
              {messages.length === 0 ? (
                <div className="welcome-screen">
                  <div className="welcome-icon">
                    <Stethoscope size={48} />
                  </div>
                  <h1>TrustMed AI</h1>
                  <p>Neuro-Symbolic Clinical Decision Support</p>
                  <div className="suggestions">
                    <button onClick={() => setInput('Analyze the chest X-ray I\'m uploading')}>
                      Analyze a chest X-ray
                    </button>
                    <button onClick={() => setInput('What are the symptoms and treatment for pneumonia?')}>
                      Pneumonia symptoms & treatment
                    </button>
                    <button onClick={() => setInput('Assess patient 10002428 for medication risks')}>
                      Assess patient risks
                    </button>
                    <button onClick={() => setInput('Compare ACE inhibitors vs ARBs for hypertension')}>
                      Compare hypertension drugs
                    </button>
                  </div>
                </div>
              ) : (
                <div className="messages-container">
                  {/* Patient Info Panel */}
                  <PatientInfoPanel
                    patientData={patientData}
                    onClose={() => setPatientData(null)}
                  />
                  {messages.map((msg, idx) => (
                    <div key={idx} className={`message ${msg.role}`}>
                      <div className="message-avatar">
                        {msg.role === 'user' ? (
                          <span className="avatar-user">P</span>
                        ) : (
                          <Stethoscope size={18} />
                        )}
                      </div>
                      <div className="message-body">
                        <span className="message-sender">
                          {msg.role === 'user' ? 'You' : 'TrustMed AI'}
                        </span>
                        {msg.image && (
                          <img src={msg.image} alt="Uploaded" className="message-image" />
                        )}
                        <div className="markdown-content">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                      </div>
                    </div>
                  ))}

                  {isLoading && streamingStatus && (
                    <div className="message assistant">
                      <div className="message-avatar">
                        <Stethoscope size={18} />
                      </div>
                      <div className="message-body">
                        <span className="message-sender">TrustMed AI</span>
                        <div className="streaming-progress">
                          <Loader2 size={16} className="spin" />
                          <span>{streamingStatus}</span>
                        </div>
                      </div>
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* Input Area */}
            <div className="input-area">
              <div className="input-container">
                {imagePreview && (
                  <div className="image-preview-container">
                    <img src={imagePreview} alt="Preview" className="image-preview" />
                    <button className="remove-image-btn" onClick={removeImage}>
                      <X size={14} />
                    </button>
                  </div>
                )}

                <div className="input-row">
                  <button
                    className="attach-btn"
                    onClick={() => fileInputRef.current?.click()}
                    title="Attach medical image"
                  >
                    <ImageIcon size={20} />
                  </button>

                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleImageSelect}
                    accept="image/*"
                    hidden
                  />

                  <textarea
                    ref={textareaRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask TrustMed AI..."
                    rows={1}
                    disabled={isLoading}
                  />

                  <button
                    className="send-btn"
                    onClick={handleSubmit}
                    disabled={isLoading || (!input.trim() && !selectedImage)}
                  >
                    <Send size={20} />
                  </button>
                </div>
              </div>

              <p className="disclaimer">
                TrustMed AI is for clinical decision support only. Always verify with qualified medical professionals.
              </p>
            </div>
          </>
        )}

        {activeTab === 'graph' && (
          <KnowledgeGraphPanel />
        )}

        {activeTab === 'panels' && (
          <CompoundPanelViewer
            panelData={panelData}
            isDetecting={isDetectingPanels}
          />
        )}
      </main>

      {/* Settings Modal */}
      {settingsOpen && (
        <div className="settings-overlay" onClick={() => setSettingsOpen(false)}>
          <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
            <div className="settings-header">
              <h2>Settings</h2>
              <button className="settings-close" onClick={() => setSettingsOpen(false)}>
                <X size={20} />
              </button>
            </div>

            <div className="settings-body">
              <div className="setting-group">
                <div className="setting-label">
                  <Thermometer size={18} />
                  <span>Model Temperature</span>
                </div>
                <p className="setting-description">
                  Controls response randomness. Lower values (0.0–0.2) are more deterministic and factual.
                  Higher values (0.5–1.0) are more creative but may hallucinate.
                </p>
                <div className="setting-control">
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={temperature}
                    onChange={(e) => setTemperature(parseFloat(e.target.value))}
                    className="temp-slider"
                  />
                  <span className="temp-value">{temperature.toFixed(2)}</span>
                </div>
                <div className="temp-labels">
                  <span>Precise</span>
                  <span>Balanced</span>
                  <span>Creative</span>
                </div>
              </div>

              <div className="setting-group">
                <div className="setting-label">
                  <Cpu size={18} />
                  <span>Synthesis Model</span>
                </div>
                <p className="setting-description">
                  The LLM used to generate the final clinical response. Free models may be slower or less accurate.
                </p>
                <select
                  className="model-select"
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                >
                  {AVAILABLE_MODELS.map((m) => (
                    <option key={m.id} value={m.id}>{m.label}</option>
                  ))}
                </select>
              </div>

              <div className="setting-group">
                <div className="setting-label">
                  <Eye size={18} />
                  <span>Vision Model</span>
                </div>
                <p className="setting-description">
                  The model used for medical image analysis (X-rays, MRIs, skin photos). Only used when an image is uploaded.
                </p>
                <select
                  className="model-select"
                  value={selectedVisionModel}
                  onChange={(e) => setSelectedVisionModel(e.target.value)}
                >
                  {AVAILABLE_VISION_MODELS.map((m) => (
                    <option key={m.id} value={m.id}>{m.label}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>
      )}
      {/* SOAP Note Modal */}
      <SOAPNoteModal
        isOpen={soapModalOpen}
        onClose={() => setSoapModalOpen(false)}
        soapData={soapData}
        isLoading={soapLoading}
      />
    </div>
  )
}

export default App
