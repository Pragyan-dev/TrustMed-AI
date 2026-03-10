import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import {
    Send, Plus, Image as ImageIcon, X, Loader2, MessageSquare,
    Trash2, Settings, Stethoscope, FileText, Network, Shield,
    Eye, Cpu, PanelRightClose, PanelRight, Upload, Activity, BookOpen,
    History, ChevronDown
} from 'lucide-react'
import KnowledgeGraphPanel from '../components/KnowledgeGraphPanel'
import SOAPNoteModal from '../components/SOAPNoteModal'
import PatientInfoPanel from '../components/PatientInfoPanel'
import CompoundPanelViewer from '../components/CompoundPanelViewer'
import MedicalTermHighlighter, { MarkdownWithHighlight } from '../components/MedicalTermHighlighter'
import SafeMarkdownWrapper from '../components/SafeMarkdownWrapper'
import '../clinician.css'

const API_BASE = '/api'

const AVAILABLE_MODELS = [
    { id: 'vertex/medgemma-27b-it', label: 'MedGemma 27B (Vertex AI)' },
    { id: 'nvidia/llama-nemotron-embed-vl-1b-v2:free', label: 'Nemotron Embed VL 1B' },
    { id: 'sourceful/riverflow-v2-pro', label: 'Riverflow V2 Pro' },
    { id: 'nvidia/nemotron-3-nano-30b-a3b:free', label: 'Nemotron 30B' },
    { id: 'qwen/qwen3-vl-235b-a22b-thinking', label: 'Qwen 3 VL 235B' },
    { id: 'google/gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro' },
]

const AVAILABLE_VISION_MODELS = [
    { id: 'vertex/medgemma-27b-it', label: 'MedGemma 27B (Vertex AI)' },
    { id: 'google/gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro' },
    { id: 'google/gemini-3-flash-preview', label: 'Gemini 3 Flash' },
    { id: 'z-ai/glm-4.5-air:free', label: 'GLM 4.5 Air' },
    { id: 'meta-llama/llama-3.2-90b-vision-instruct:free', label: 'Llama 90B Vision' },
]

const SAMPLE_PATIENTS = ['10002428', '10025463', '10027602', '10009049', '10007058', '10020640', '10018081', '10023239', '10035631']

// Pipeline step config
const PIPELINE_STEPS = [
    { key: 'vision', label: 'Vision', icon: Eye },
    { key: 'kg', label: 'KG Query', icon: Network },
    { key: 'drugs', label: 'Drug Check', icon: Shield },
    { key: 'safety', label: 'Safety', icon: Cpu },
]

// Strip wrapping quotes from LLM responses
const cleanContent = (text) => {
    if (!text) return ''
    let t = text.trim()
    if (t.startsWith('"') && t.endsWith('"')) t = t.slice(1, -1)
    return t
}

export default function ClinicianDashboard() {
    // ── State ──────────────────────────────────────────────────────
    const [messages, setMessages] = useState([])
    const [input, setInput] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [streamingStatus, setStreamingStatus] = useState('')
    const [pipelineSteps, setPipelineSteps] = useState({})

    // Image
    const [selectedImage, setSelectedImage] = useState(null)
    const [imagePreview, setImagePreview] = useState(null)
    const [uploadedImagePath, setUploadedImagePath] = useState(null)
    const [isUploading, setIsUploading] = useState(false)
    const [panelData, setPanelData] = useState(null)

    // Session
    const [sessionId, setSessionId] = useState(null)
    const [sessionTitle, setSessionTitle] = useState('New Chat')
    const [sessions, setSessions] = useState([])

    // Patient
    const [selectedPatient, setSelectedPatient] = useState('')
    const [patientData, setPatientData] = useState(null)

    // Settings
    const [temperature, setTemperature] = useState(0.1)
    const [selectedModel, setSelectedModel] = useState(AVAILABLE_MODELS[0].id)
    const [selectedVisionModel, setSelectedVisionModel] = useState(AVAILABLE_VISION_MODELS[0].id)

    // Panels
    const [rightOpen, setRightOpen] = useState(true)
    const [rightTab, setRightTab] = useState('kg')
    const [soapOpen, setSoapOpen] = useState(false)
    const [soapData, setSoapData] = useState(null)
    const [soapLoading, setSoapLoading] = useState(false)

    // Drug alerts parsed from streaming
    const [drugAlerts, setDrugAlerts] = useState([])

    // Term highlighter toggle
    const [highlighterOn, setHighlighterOn] = useState(false)

    // Sessions dropdown
    const [sessionsOpen, setSessionsOpen] = useState(false)

    const messagesEndRef = useRef(null)
    const fileInputRef = useRef(null)
    const uploadPromiseRef = useRef(null)
    const textareaRef = useRef(null)

    // ── Load sessions ────────────────────────────────────────────────
    const fetchSessions = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/sessions?source=clinician`)
            const data = await res.json()
            setSessions(data.sessions || [])
        } catch (err) { console.error('Failed to load sessions:', err) }
    }, [])

    useEffect(() => { fetchSessions() }, [fetchSessions])

    // Auto-scroll
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto'
            textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + 'px'
        }
    }, [input])

    // ── Patient Loading ──────────────────────────────────────────────
    const loadPatient = async (patId) => {
        if (!patId) { setPatientData(null); return }
        try {
            const res = await fetch(`${API_BASE}/patient/${patId}`)
            if (res.ok) {
                const data = await res.json()
                setPatientData(data)
            }
        } catch (err) { console.error('Failed to load patient:', err) }
    }

    // ── Session Management ───────────────────────────────────────────
    const createNewSession = async () => {
        try {
            const res = await fetch(`${API_BASE}/sessions/new?source=clinician`, { method: 'POST' })
            const data = await res.json()
            setSessionId(data.id)
            setSessionTitle('New Chat')
            setMessages([])
            setDrugAlerts([])
            setPipelineSteps({})
            fetchSessions()
        } catch (err) { console.error('Failed to create session:', err) }
    }

    const loadSession = async (sid) => {
        try {
            const res = await fetch(`${API_BASE}/sessions/${sid}`)
            const data = await res.json()
            setSessionId(sid)
            setSessionTitle(data.title || 'Chat')
            setMessages(data.messages || data.history || [])
            setDrugAlerts([])
            setPipelineSteps({})
        } catch (err) { console.error('Failed to load session:', err) }
    }

    const deleteSession = async (sid, e) => {
        e?.stopPropagation()
        try {
            await fetch(`${API_BASE}/sessions/${sid}`, { method: 'DELETE' })
            if (sessionId === sid) {
                setSessionId(null)
                setMessages([])
                setSessionTitle('New Chat')
            }
            fetchSessions()
        } catch (err) { console.error('Failed to delete session:', err) }
    }

    // ── Image Handling ───────────────────────────────────────────────
    const handleImageSelect = async (e) => {
        const file = e.target.files?.[0]
        if (!file) return

        setSelectedImage(file)
        setImagePreview(URL.createObjectURL(file))
        setIsUploading(true)

        const formData = new FormData()
        formData.append('file', file)

        uploadPromiseRef.current = (async () => {
            try {
                const response = await fetch(`${API_BASE}/upload-image`, {
                    method: 'POST', body: formData
                })
                const data = await response.json()
                setUploadedImagePath(data.path)
                // Detect compound panels
                try {
                    const panelRes = await fetch(`${API_BASE}/detect-panels`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ image_path: data.path })
                    })
                    const pData = await panelRes.json()
                    setPanelData(pData)
                } catch { setPanelData(null) }
                return data.path
            } catch (error) {
                console.error('Upload failed:', error)
                return null
            } finally { setIsUploading(false) }
        })()
    }

    const removeImage = () => {
        setSelectedImage(null)
        setImagePreview(null)
        setUploadedImagePath(null)
        setPanelData(null)
        if (fileInputRef.current) fileInputRef.current.value = ''
    }

    // ── Pipeline Step Tracker ────────────────────────────────────────
    const updatePipeline = (statusMsg) => {
        if (!statusMsg) return
        const msg = statusMsg.toLowerCase()
        setPipelineSteps(prev => {
            const next = { ...prev }
            if (msg.includes('vision') || msg.includes('image') || msg.includes('analyzing scan')) {
                next.vision = 'active'
            }
            if (msg.includes('knowledge graph') || msg.includes('kg') || msg.includes('graph query') || msg.includes('cypher')) {
                if (next.vision === 'active') next.vision = 'done'
                next.kg = 'active'
            }
            if (msg.includes('drug') || msg.includes('medication') || msg.includes('interaction')) {
                if (next.kg === 'active') next.kg = 'done'
                next.drugs = 'active'
            }
            if (msg.includes('safety') || msg.includes('critic') || msg.includes('verif')) {
                if (next.drugs === 'active') next.drugs = 'done'
                next.safety = 'active'
            }
            if (msg.includes('complet') || msg.includes('done') || msg.includes('final')) {
                Object.keys(next).forEach(k => { if (next[k] === 'active') next[k] = 'done' })
            }
            return next
        })
    }

    // ── Submit Message ───────────────────────────────────────────────
    const handleSubmit = async (e) => {
        e?.preventDefault()
        if (!input.trim() && !selectedImage) return

        let currentSessionId = sessionId
        if (!currentSessionId) {
            try {
                const res = await fetch(`${API_BASE}/sessions/new?source=clinician`, { method: 'POST' })
                const data = await res.json()
                currentSessionId = data.id
                setSessionId(data.id)
            } catch (err) { console.error('Failed to create session:', err); return }
        }

        // Wait for upload
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
        setPipelineSteps({})
        setDrugAlerts([])

        const imagePath = uploadedImagePath
        removeImage()

        let apiMessage = userMessage.content
        if (selectedPatient) {
            apiMessage += `\n\n[System Note: Contextualize response for Patient ${selectedPatient}]`
        }

        try {
            const res = await fetch(`${API_BASE}/chat/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: apiMessage,
                    session_id: currentSessionId,
                    image_path: imagePath || null,
                    temperature,
                    model: selectedModel,
                    vision_model: selectedVisionModel,
                })
            })

            const reader = res.body.getReader()
            const decoder = new TextDecoder()
            let assistantAdded = false

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                const chunk = decoder.decode(value, { stream: true })
                for (const line of chunk.split('\n')) {
                    if (!line.startsWith('data: ')) continue
                    const jsonStr = line.slice(6).trim()
                    if (!jsonStr) continue

                    try {
                        const event = JSON.parse(jsonStr)

                        if (event.type === 'progress') {
                            setStreamingStatus(event.message)
                            updatePipeline(event.message)
                        } else if (event.type === 'token') {
                            if (!assistantAdded) {
                                setMessages(prev => [...prev, { role: 'assistant', content: '' }])
                                assistantAdded = true
                                setStreamingStatus('')
                            }
                            setMessages(prev => {
                                const updated = [...prev]
                                const last = updated[updated.length - 1]
                                updated[updated.length - 1] = { ...last, content: last.content + event.content }
                                return updated
                            })
                        } else if (event.type === 'replace') {
                            setMessages(prev => {
                                const updated = [...prev]
                                if (!assistantAdded || updated[updated.length - 1]?.role !== 'assistant') {
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
                            if (!assistantAdded && event.final_response) {
                                setMessages(prev => [...prev, { role: 'assistant', content: event.final_response }])
                            }
                            // Mark all pipeline steps done
                            setPipelineSteps(prev => {
                                const next = { ...prev }
                                Object.keys(next).forEach(k => { next[k] = 'done' })
                                return next
                            })
                            fetchSessions()
                        } else if (event.type === 'patient_context') {
                            if (event.patient_id) {
                                setSelectedPatient(event.patient_id)
                                loadPatient(event.patient_id)
                            }
                        } else if (event.type === 'drug_alerts') {
                            setDrugAlerts(event.alerts || [])
                        } else if (event.type === 'error') {
                            if (!assistantAdded) {
                                setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${event.message}` }])
                            }
                        }
                    } catch { /* skip parse errors */ }
                }
            }
        } catch (err) {
            console.error('Chat error:', err)
            setMessages(prev => [...prev, { role: 'assistant', content: `Connection error: ${err.message}` }])
        } finally {
            setIsLoading(false)
            setStreamingStatus('')
        }
    }

    // ── SOAP Note ────────────────────────────────────────────────────
    const generateSOAP = async () => {
        if (!sessionId || messages.length === 0) return
        setSoapLoading(true)
        setSoapOpen(true)
        try {
            const res = await fetch(`${API_BASE}/soap-note`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId })
            })
            const data = await res.json()
            setSoapData(data)
        } catch (err) {
            console.error('SOAP generation failed:', err)
        } finally { setSoapLoading(false) }
    }

    // ── Key handler ──────────────────────────────────────────────────
    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSubmit()
        }
    }

    // ── Render ───────────────────────────────────────────────────────
    return (
        <div className="cd">
            {/* ═══ TOP BAR ═══ */}
            <header className="cd-topbar">
                <div className="cd-topbar__brand">
                    <div className="cd-topbar__logo"><Stethoscope /></div>
                    <div className="cd-topbar__name">TrustMed <span>AI</span></div>
                </div>

                <div className="cd-topbar__divider" />

                {/* Model selector */}
                <select
                    className="cd-topbar__select"
                    value={selectedModel}
                    onChange={e => setSelectedModel(e.target.value)}
                    title="Synthesis Model"
                >
                    {AVAILABLE_MODELS.map(m => (
                        <option key={m.id} value={m.id}>{m.label}</option>
                    ))}
                </select>

                <select
                    className="cd-topbar__select"
                    value={selectedVisionModel}
                    onChange={e => setSelectedVisionModel(e.target.value)}
                    title="Vision Model"
                >
                    {AVAILABLE_VISION_MODELS.map(m => (
                        <option key={m.id} value={m.id}>{m.label}</option>
                    ))}
                </select>

                <div className="cd-topbar__spacer" />

                {/* Session dropdown trigger */}
                <div className="cd-topbar__session-wrap">
                    <button
                        className={`cd-topbar__session-btn ${sessionsOpen ? 'active' : ''}`}
                        onClick={() => setSessionsOpen(!sessionsOpen)}
                        title="Chat History"
                    >
                        <History size={14} />
                        <span className="cd-topbar__session-title">{sessionTitle}</span>
                        <ChevronDown size={12} className={`cd-topbar__chevron ${sessionsOpen ? 'open' : ''}`} />
                    </button>

                    <button className="cd-topbar__btn" onClick={() => { createNewSession(); setSessionsOpen(false); }} title="New Chat">
                        <Plus size={16} />
                    </button>

                    {/* Sessions dropdown */}
                    {sessionsOpen && (
                        <>
                            <div className="cd-sessions-overlay" onClick={() => setSessionsOpen(false)} />
                            <div className="cd-sessions-dropdown">
                                <div className="cd-sessions-dropdown__header">
                                    <span>Chat History</span>
                                    <span className="cd-sessions-dropdown__count">{sessions.length}</span>
                                </div>
                                <div className="cd-sessions-dropdown__list">
                                    {sessions.length === 0 ? (
                                        <div className="cd-sessions-dropdown__empty">No sessions yet</div>
                                    ) : (
                                        sessions.map(s => (
                                            <div
                                                key={s.id}
                                                className={`cd-session-item ${sessionId === s.id ? 'active' : ''}`}
                                                onClick={() => { loadSession(s.id); setSessionsOpen(false); }}
                                            >
                                                <MessageSquare size={14} />
                                                <span className="cd-session-item__title">{s.title || 'New Chat'}</span>
                                                <button
                                                    className="cd-session-item__delete"
                                                    onClick={e => deleteSession(s.id, e)}
                                                >
                                                    <Trash2 size={12} />
                                                </button>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </div>
                        </>
                    )}
                </div>

                <button
                    className={`mth-toggle ${highlighterOn ? 'active' : ''}`}
                    onClick={() => setHighlighterOn(!highlighterOn)}
                    title="Toggle term explanations"
                >
                    <BookOpen size={14} />
                    Explain
                </button>

                <button
                    className="cd-topbar__btn"
                    onClick={() => setRightOpen(!rightOpen)}
                    title={rightOpen ? 'Collapse Panel' : 'Expand Panel'}
                >
                    {rightOpen ? <PanelRightClose size={16} /> : <PanelRight size={16} />}
                </button>
            </header>

            {/* ═══ BODY (3-column) ═══ */}
            <div className="cd-body">

                {/* ─── LEFT SIDEBAR ─── */}
                <aside className="cd-left">
                    {/* Patient selector */}
                    <div className="cd-left__section">
                        <div className="cd-left__label">
                            <Activity size={12} /> Patient
                        </div>
                        <select
                            className="cd-patient-select"
                            value={selectedPatient}
                            onChange={e => {
                                setSelectedPatient(e.target.value)
                                loadPatient(e.target.value)
                            }}
                        >
                            <option value="">Select Patient…</option>
                            {SAMPLE_PATIENTS.map(p => (
                                <option key={p} value={p}>Patient {p}</option>
                            ))}
                        </select>

                        {/* Inline vitals */}
                        {patientData && (
                            <div style={{ marginTop: '0.75rem' }}>
                                <PatientInfoPanel
                                    patientData={patientData}
                                    onClose={() => setPatientData(null)}
                                />
                            </div>
                        )}
                    </div>

                    {/* System status */}
                    <div className="cd-left__section">
                        <div className="cd-left__label">
                            <Shield size={12} /> System Status
                        </div>
                        <div className="cd-status-list">
                            <div className="cd-status-item">
                                <span className="cd-status-dot cd-status-dot--ok" />
                                Knowledge Graph
                            </div>
                            <div className="cd-status-item">
                                <span className="cd-status-dot cd-status-dot--ok" />
                                Vector Store (4,199 images)
                            </div>
                            <div className="cd-status-item">
                                <span className="cd-status-dot cd-status-dot--ok" />
                                MIMIC-IV Linked
                            </div>
                            <div className="cd-status-item">
                                <span className="cd-status-dot cd-status-dot--ok" />
                                Drug Safety Engine
                            </div>
                        </div>
                    </div>

                    {/* Image upload */}
                    <div className="cd-left__section">
                        <div className="cd-left__label">
                            <ImageIcon size={12} /> Medical Imaging
                        </div>
                        {imagePreview ? (
                            <div className="cd-upload-preview">
                                <img src={imagePreview} alt="Upload" />
                                <button className="cd-upload-preview__remove" onClick={removeImage}>
                                    <X size={14} />
                                </button>
                                {isUploading && (
                                    <div style={{
                                        position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.6)',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        borderRadius: '10px'
                                    }}>
                                        <Loader2 size={24} className="cd-spin" style={{ color: '#64ffda' }} />
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="cd-upload-area">
                                <input
                                    type="file"
                                    accept="image/*"
                                    onChange={handleImageSelect}
                                    ref={fileInputRef}
                                />
                                <Upload size={24} />
                                <p>Drop or click to upload scan</p>
                            </div>
                        )}

                        {panelData?.is_compound && (
                            <div style={{ marginTop: '0.5rem' }}>
                                <CompoundPanelViewer panelData={panelData} />
                            </div>
                        )}
                    </div>


                </aside>

                {/* ─── CENTER (Chat) ─── */}
                <div className="cd-center">
                    {/* Pipeline badges */}
                    <div className="cd-pipeline">
                        {PIPELINE_STEPS.map(step => {
                            const status = pipelineSteps[step.key]
                            const Icon = step.icon
                            return (
                                <div
                                    key={step.key}
                                    className={`cd-badge ${status ? `cd-badge--${status}` : ''}`}
                                >
                                    <span className="cd-badge__dot" />
                                    <Icon size={12} />
                                    {step.label}
                                </div>
                            )
                        })}

                        {streamingStatus && (
                            <div className="cd-streaming">
                                <span className="cd-streaming__dot" />
                                {streamingStatus}
                            </div>
                        )}
                    </div>

                    {/* Messages */}
                    <div className="cd-messages">
                        {messages.length === 0 ? (
                            <div className="cd-empty">
                                <div className="cd-empty__icon">
                                    <Stethoscope size={28} />
                                </div>
                                <h3>Clinical Decision Support</h3>
                                <p>
                                    Select a patient, upload imaging, or ask a clinical question to begin analysis.
                                </p>
                            </div>
                        ) : (
                            messages.map((msg, i) => (
                                <div key={i} className={`cd-msg cd-msg--${msg.role}`}>
                                    {msg.image && (
                                        <img
                                            src={msg.image.startsWith('blob:') || msg.image.startsWith('http') ? msg.image : `${API_BASE}${msg.image}`}
                                            alt="Attached"
                                            className="cd-msg__image"
                                        />
                                    )}
                                    {msg.role === 'assistant' ? (
                                        <SafeMarkdownWrapper fallbackText={cleanContent(msg.content)}>
                                            <MarkdownWithHighlight enabled={highlighterOn}>
                                                {cleanContent(msg.content)}
                                            </MarkdownWithHighlight>
                                        </SafeMarkdownWrapper>
                                    ) : (
                                        msg.content
                                    )}
                                </div>
                            ))
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    {/* Input bar */}
                    <div className="cd-input-bar">
                        <button
                            className="cd-input-btn cd-img-btn"
                            onClick={() => fileInputRef.current?.click()}
                            title="Attach Image"
                        >
                            <ImageIcon size={18} />
                        </button>
                        <textarea
                            ref={textareaRef}
                            value={input}
                            onChange={e => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Assess patient 10002428 for this chest X-ray…"
                            rows={1}
                            disabled={isLoading}
                        />
                        <button
                            className="cd-input-btn cd-send-btn"
                            onClick={handleSubmit}
                            disabled={(!input.trim() && !selectedImage) || isLoading}
                        >
                            {isLoading ? <Loader2 size={18} className="cd-spin" /> : <Send size={18} />}
                        </button>
                    </div>
                </div>

                {/* ─── RIGHT PANEL ─── */}
                <aside className={`cd-right ${rightOpen ? '' : 'collapsed'}`}>
                    <div className="cd-right__tabs">
                        <button
                            className={`cd-right__tab ${rightTab === 'kg' ? 'active' : ''}`}
                            onClick={() => setRightTab('kg')}
                        >
                            <Network size={14} /> Graph
                        </button>
                        <button
                            className={`cd-right__tab ${rightTab === 'drugs' ? 'active' : ''}`}
                            onClick={() => setRightTab('drugs')}
                        >
                            <Shield size={14} /> Drugs
                        </button>
                        <button
                            className={`cd-right__tab ${rightTab === 'notes' ? 'active' : ''}`}
                            onClick={() => setRightTab('notes')}
                        >
                            <FileText size={14} /> Notes
                        </button>
                    </div>

                    <div className="cd-right__content">
                        {rightTab === 'kg' && <KnowledgeGraphPanel />}

                        {rightTab === 'drugs' && (
                            <div>
                                <div className="cd-left__label" style={{ marginBottom: '0.75rem' }}>
                                    <Shield size={12} /> Drug Safety Alerts
                                </div>
                                {drugAlerts.length > 0 ? (
                                    drugAlerts.map((alert, i) => (
                                        <div
                                            key={i}
                                            className={`cd-drug-alert ${alert.includes('🔴') ? 'cd-drug-alert--danger' : 'cd-drug-alert--warning'
                                                }`}
                                        >
                                            {alert}
                                        </div>
                                    ))
                                ) : (
                                    <div className="cd-empty" style={{ height: 'auto', padding: '2rem 1rem' }}>
                                        <Shield size={24} />
                                        <p>Drug safety alerts will appear here after patient assessment.</p>
                                    </div>
                                )}
                            </div>
                        )}

                        {rightTab === 'notes' && (
                            <div>
                                <div className="cd-left__label" style={{ marginBottom: '0.75rem' }}>
                                    <FileText size={12} /> Clinical Notes
                                </div>
                                <button
                                    className="cd-soap-btn"
                                    onClick={generateSOAP}
                                    disabled={!sessionId || messages.length === 0}
                                >
                                    <FileText size={16} />
                                    Generate SOAP Note
                                </button>
                                {!sessionId && (
                                    <p style={{ fontSize: '0.8rem', color: 'var(--cd-text-muted)', marginTop: '0.5rem', textAlign: 'center' }}>
                                        Start a conversation to enable SOAP note generation.
                                    </p>
                                )}
                            </div>
                        )}
                    </div>
                </aside>
            </div>

            {/* SOAP Modal */}
            <SOAPNoteModal
                isOpen={soapOpen}
                onClose={() => setSoapOpen(false)}
                soapData={soapData}
                isLoading={soapLoading}
            />
        </div>
    )
}
