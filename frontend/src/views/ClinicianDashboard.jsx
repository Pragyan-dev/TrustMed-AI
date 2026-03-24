import Link from 'next/link'
import { useState, useRef, useEffect, useCallback } from 'react'
import {
    Send, Plus, Image as ImageIcon, X, Loader2, MessageSquare,
    Trash2, Stethoscope, FileText, Network, Shield,
    Eye, Cpu, PanelRightClose, PanelRight, Upload, Activity, BookOpen,
    SlidersHorizontal
} from 'lucide-react'
import KnowledgeGraphPanel from '../components/KnowledgeGraphPanel'
import SOAPNoteModal from '../components/SOAPNoteModal'
import PatientInfoPanel from '../components/PatientInfoPanel'
import CompoundPanelViewer from '../components/CompoundPanelViewer'
import { MarkdownWithHighlight } from '../components/MedicalTermHighlighter'
import SafeMarkdownWrapper from '../components/SafeMarkdownWrapper'
import {
    AVAILABLE_TEXT_MODELS,
    AVAILABLE_VISION_MODELS,
    DEFAULT_TEXT_MODEL,
    DEFAULT_VISION_MODEL,
} from '../lib/modelOptions'

const API_BASE = '/api'

const SAMPLE_PATIENTS = ['10002428', '10025463', '10027602', '10009049', '10007058', '10020640', '10018081', '10023239', '10035631']
const STARTER_PROMPTS = [
    'Summarize the current risks for patient 10002428.',
    'Review this chest X-ray for pneumonia and medication risks.',
    'Generate a focused assessment and next steps for today.',
]

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

const streamSseEvents = async (response, onEvent) => {
    const reader = response.body?.getReader()
    if (!reader) throw new Error('Streaming response unavailable')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            const jsonStr = line.slice(6).trim()
            if (!jsonStr) continue

            try {
                onEvent(JSON.parse(jsonStr))
            } catch {
                // Ignore malformed partial events and continue streaming.
            }
        }
    }

    const trailing = buffer.trim()
    if (trailing.startsWith('data: ')) {
        try {
            onEvent(JSON.parse(trailing.slice(6).trim()))
        } catch {
            // Ignore incomplete trailing event payloads.
        }
    }
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
    const [selectedModel, setSelectedModel] = useState(DEFAULT_TEXT_MODEL)
    const [selectedVisionModel, setSelectedVisionModel] = useState(DEFAULT_VISION_MODEL)

    // Panels
    const [rightOpen, setRightOpen] = useState(true)
    const [rightTab, setRightTab] = useState('kg')
    const [soapOpen, setSoapOpen] = useState(false)
    const [soapData, setSoapData] = useState(null)
    const [soapLoading, setSoapLoading] = useState(false)

    // Drug alerts parsed from streaming
    const [drugAlerts, setDrugAlerts] = useState([])
    const [graphContext, setGraphContext] = useState(null)

    // Term highlighter toggle
    const [highlighterOn, setHighlighterOn] = useState(false)

    // Settings drawer
    const [settingsOpen, setSettingsOpen] = useState(false)

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
        setGraphContext(null)
        setDrugAlerts([])
        setPatientData(null)
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
            setGraphContext(null)
            setPipelineSteps({})
            setSoapData(null)
            setSettingsOpen(false)
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
            setGraphContext(null)
            setPipelineSteps({})
            setSettingsOpen(false)
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
                setGraphContext(null)
            }
            fetchSessions()
        } catch (err) { console.error('Failed to delete session:', err) }
    }

    // ── Image Handling ───────────────────────────────────────────────
    const uploadImageFile = async (rawFile, { fromClipboard = false } = {}) => {
        if (!rawFile || !rawFile.type?.startsWith('image/')) return

        const clipboardFile = fromClipboard && rawFile.type
            ? new File(
                [rawFile],
                `clipboard-image-${Date.now()}.${rawFile.type.split('/')[1] || 'png'}`,
                { type: rawFile.type }
            )
            : rawFile

        setSelectedImage(clipboardFile)
        setImagePreview(URL.createObjectURL(clipboardFile))
        setUploadedImagePath(null)
        setPanelData(null)
        setIsUploading(true)
        if (fileInputRef.current) fileInputRef.current.value = ''

        const formData = new FormData()
        formData.append('file', clipboardFile)

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

    const handleImageSelect = async (e) => {
        const file = e.target.files?.[0]
        await uploadImageFile(file)
    }

    const handleComposerPaste = async (e) => {
        const items = Array.from(e.clipboardData?.items || [])
        const imageItem = items.find(item => item.type.startsWith('image/'))
        if (!imageItem) return

        const file = imageItem.getAsFile()
        if (!file) return

        e.preventDefault()
        await uploadImageFile(file, { fromClipboard: true })
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
        let resolvedImagePath = uploadedImagePath
        if (selectedImage && !resolvedImagePath && uploadPromiseRef.current) {
            resolvedImagePath = await uploadPromiseRef.current
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

        const imagePath = resolvedImagePath
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

            let assistantAdded = false

            await streamSseEvents(res, (event) => {
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
                } else if (event.type === 'graph_context') {
                    setGraphContext({
                        search_term: event.search_term || '',
                        patient_id: event.patient_id || null,
                        source: event.source || 'query',
                    })
                } else if (event.type === 'drug_alerts') {
                    setDrugAlerts(event.alerts || [])
                } else if (event.type === 'error') {
                    if (!assistantAdded) {
                        setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${event.message}` }])
                    }
                }
            })
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
                body: JSON.stringify({
                    session_id: sessionId,
                    patient_id: selectedPatient || null,
                })
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

    const applyStarterPrompt = (prompt) => {
        setInput(prompt)
        textareaRef.current?.focus()
    }

    const activePatientId = selectedPatient || patientData?.patient_id || graphContext?.patient_id || null
    const fallbackDiagnosis = patientData?.diagnoses?.[0]?.title?.trim() || ''
    const syncedGraphSearchTerm = (graphContext?.search_term || fallbackDiagnosis || '').trim()
    const graphSyncLabel = graphContext?.search_term
        ? graphContext.source === 'patient_diagnosis'
            ? `Synced from the backend patient diagnosis context${activePatientId ? ` for Patient ${activePatientId}` : ''}.`
            : graphContext.source === 'current_answer'
                ? 'Synced from the latest assistant assessment.'
                : 'Synced from the current clinical query.'
        : fallbackDiagnosis
            ? `Defaulting to the first active diagnosis for Patient ${activePatientId}.`
            : 'Select a patient or ask a question to sync the graph automatically.'
    const latestAssistantMessage = [...messages]
        .reverse()
        .find(msg => msg.role === 'assistant' && cleanContent(msg.content))?.content || ''
    const latestAssistantPreview = cleanContent(latestAssistantMessage)

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

                <div className="cd-topbar__spacer" />

                <div className="cd-topbar__view-switch" aria-label="Current application view">
                    <span className="cd-topbar__view-chip cd-topbar__view-chip--active">Clinician</span>
                    <Link
                        href="/patient"
                        className="cd-topbar__view-chip cd-topbar__view-chip--link"
                        title="Switch to patient portal"
                    >
                        Patient View
                    </Link>
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
                    onClick={() => setSettingsOpen(true)}
                    title="Open settings"
                >
                    <SlidersHorizontal size={16} />
                </button>

                <button
                    className="cd-topbar__btn"
                    onClick={() => setRightOpen(!rightOpen)}
                    title={rightOpen ? 'Collapse Panel' : 'Expand Panel'}
                >
                    {rightOpen ? <PanelRightClose size={16} /> : <PanelRight size={16} />}
                </button>
            </header>

            {settingsOpen && (
                <>
                    <div className="cd-settings-backdrop" onClick={() => setSettingsOpen(false)} />
                    <aside className="cd-settings-drawer">
                        <div className="cd-settings__header">
                            <div>
                                <div className="cd-settings__eyebrow">Workspace Controls</div>
                                <h2>Settings</h2>
                            </div>
                            <button
                                className="cd-topbar__btn"
                                onClick={() => setSettingsOpen(false)}
                                title="Close settings"
                            >
                                <X size={16} />
                            </button>
                        </div>

                        <section className="cd-settings__section">
                            <div className="cd-settings__section-title">Conversation</div>
                            <div className="cd-settings__session-card">
                                <div className="cd-settings__session-meta">
                                    <span className="cd-settings__session-label">Current Session</span>
                                    <strong>{sessionTitle || 'New Chat'}</strong>
                                </div>
                                <button className="cd-settings__new-chat" onClick={createNewSession}>
                                    <Plus size={14} />
                                    New Chat
                                </button>
                            </div>

                            <div className="cd-settings__session-list">
                                {sessions.length === 0 ? (
                                    <div className="cd-settings__empty">No saved sessions yet.</div>
                                ) : (
                                    sessions.map(s => (
                                        <div
                                            key={s.id}
                                            className={`cd-session-item ${sessionId === s.id ? 'active' : ''}`}
                                            onClick={() => loadSession(s.id)}
                                        >
                                            <MessageSquare size={14} />
                                            <span className="cd-session-item__title">{s.title || 'New Chat'}</span>
                                            <button
                                                className="cd-session-item__delete"
                                                onClick={e => deleteSession(s.id, e)}
                                                title="Delete session"
                                            >
                                                <Trash2 size={12} />
                                            </button>
                                        </div>
                                    ))
                                )}
                            </div>
                        </section>

                        <section className="cd-settings__section">
                            <div className="cd-settings__section-title">Models</div>
                            <label className="cd-settings__field">
                                <span>Text Model</span>
                                <select
                                    className="cd-settings__select"
                                    value={selectedModel}
                                    onChange={e => setSelectedModel(e.target.value)}
                                >
                                    {AVAILABLE_TEXT_MODELS.map(m => (
                                        <option key={m.id} value={m.id}>{m.label}</option>
                                    ))}
                                </select>
                            </label>

                            <label className="cd-settings__field">
                                <span>Vision Model</span>
                                <select
                                    className="cd-settings__select"
                                    value={selectedVisionModel}
                                    onChange={e => setSelectedVisionModel(e.target.value)}
                                >
                                    {AVAILABLE_VISION_MODELS.map(m => (
                                        <option key={m.id} value={m.id}>{m.label}</option>
                                    ))}
                                </select>
                            </label>
                        </section>

                        <section className="cd-settings__section">
                            <div className="cd-settings__section-title">Generation</div>
                            <label className="cd-settings__field">
                                <div className="cd-settings__field-row">
                                    <span>Temperature</span>
                                    <strong>{temperature.toFixed(1)}</strong>
                                </div>
                                <input
                                    type="range"
                                    min="0"
                                    max="1"
                                    step="0.1"
                                    value={temperature}
                                    onChange={e => setTemperature(Number(e.target.value))}
                                    className="cd-settings__slider"
                                />
                            </label>
                        </section>
                    </aside>
                </>
            )}

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

                    <div className="cd-chat-header">
                        <div className="cd-chat-header__meta">
                            <div className="cd-chat-header__eyebrow">
                                {activePatientId ? `Patient ${activePatientId}` : 'Clinical Assistant'}
                            </div>
                            <div className="cd-chat-header__title">{sessionTitle || 'New Chat'}</div>
                            <div className="cd-chat-header__subtitle">
                                {messages.length > 0
                                    ? 'Grounded clinical conversation with patient context, imaging, KG retrieval, and safety checks.'
                                    : 'Start a new conversation, upload imaging, and ask a focused clinical question.'}
                            </div>
                        </div>
                        <button className="cd-chat-new" onClick={createNewSession}>
                            <Plus size={16} />
                            New Chat
                        </button>
                    </div>

                    {/* Messages */}
                    <div className="cd-messages">
                        {messages.length === 0 ? (
                            <div className="cd-empty cd-empty--chat">
                                <div className="cd-empty__panel">
                                    <div className="cd-empty__icon">
                                        <Stethoscope size={28} />
                                    </div>
                                    <div className="cd-empty__kicker">
                                        {activePatientId ? `Patient ${activePatientId}` : 'Clinical workspace'}
                                    </div>
                                    <h3>TrustMed Clinical Assistant</h3>
                                    <p>
                                        Ground the next response with patient context, optional imaging, and one focused clinical question.
                                    </p>
                                    <div className="cd-empty__readiness">
                                        <div className={`cd-empty__readiness-card ${activePatientId ? 'is-ready' : ''}`}>
                                            <Activity size={16} />
                                            <div className="cd-empty__readiness-copy">
                                                <span className="cd-empty__readiness-label">Patient context</span>
                                                <strong>{activePatientId ? `Patient ${activePatientId} linked` : 'Select a patient'}</strong>
                                                <small>
                                                    {activePatientId
                                                        ? 'Answers will stay grounded in the linked chart and recent vitals.'
                                                        : 'Choose a patient from the sidebar to pull diagnoses, meds, and vitals into the next turn.'}
                                                </small>
                                            </div>
                                        </div>
                                        <div className={`cd-empty__readiness-card ${imagePreview || uploadedImagePath ? 'is-ready' : ''}`}>
                                            <ImageIcon size={16} />
                                            <div className="cd-empty__readiness-copy">
                                                <span className="cd-empty__readiness-label">Imaging review</span>
                                                <strong>{imagePreview || uploadedImagePath ? 'Scan attached and ready' : 'Upload imaging if needed'}</strong>
                                                <small>
                                                    {imagePreview || uploadedImagePath
                                                        ? 'The next question can use multimodal image analysis automatically.'
                                                        : 'Attach a chest X-ray or other medical image to add vision, panel detection, and graph evidence.'}
                                                </small>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="cd-empty__prompt-header">
                                        <span>Suggested launch prompts</span>
                                        <span>
                                            {activePatientId
                                                ? 'Tap a prompt to preload the composer, or type your own assessment question below.'
                                                : 'These prompts preload the composer. Link a patient first for fully grounded clinical answers.'}
                                        </span>
                                    </div>
                                    <div className="cd-empty__prompts">
                                        {STARTER_PROMPTS.map((prompt) => (
                                            <button
                                                key={prompt}
                                                type="button"
                                                className="cd-empty__prompt"
                                                onClick={() => applyStarterPrompt(prompt)}
                                            >
                                                {prompt}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        ) : (
                            messages.map((msg, i) => (
                                <div key={i} className={`cd-msg-row cd-msg-row--${msg.role}`}>
                                    <div className={`cd-msg-avatar cd-msg-avatar--${msg.role}`}>
                                        {msg.role === 'assistant' ? <Stethoscope size={15} /> : <span>You</span>}
                                    </div>
                                    <div className={`cd-msg-stack cd-msg-stack--${msg.role}`}>
                                        <div className="cd-msg-meta">
                                            <span className="cd-msg-meta__name">
                                                {msg.role === 'assistant' ? 'TrustMed AI' : 'You'}
                                            </span>
                                        </div>
                                        <div className={`cd-msg cd-msg--${msg.role}`}>
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
                                    </div>
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
                            onPaste={handleComposerPaste}
                            placeholder={selectedImage
                                ? 'Describe what you want analyzed in this image…'
                                : 'Ask a focused clinical question, or paste a medical image from your clipboard…'}
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
                        {rightTab === 'kg' && (
                            <KnowledgeGraphPanel
                                syncedSearchTerm={syncedGraphSearchTerm}
                                patientId={activePatientId}
                                syncLabel={graphSyncLabel}
                                allowManualOverride
                            />
                        )}

                        {rightTab === 'drugs' && (
                            <div>
                                <div className="cd-left__label" style={{ marginBottom: '0.75rem' }}>
                                    <Shield size={12} /> Drug Safety Alerts
                                </div>
                                <div className="cd-right__meta-card">
                                    <strong>{activePatientId ? `Patient ${activePatientId}` : 'No patient selected'}</strong>
                                    <span>
                                        {activePatientId
                                            ? 'Alerts from the latest assessment stream will appear here.'
                                            : 'Select a patient or assess a case to populate this panel.'}
                                    </span>
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
                                        <p>
                                            {activePatientId
                                                ? 'No alerts for the latest assessment yet.'
                                                : 'No patient selected yet.'}
                                        </p>
                                    </div>
                                )}
                            </div>
                        )}

                        {rightTab === 'notes' && (
                            <div>
                                <div className="cd-left__label" style={{ marginBottom: '0.75rem' }}>
                                    <FileText size={12} /> Clinical Notes
                                </div>
                                <div className="cd-right__meta-card">
                                    <strong>{activePatientId ? `Patient ${activePatientId}` : 'Session-only note'}</strong>
                                    <span>
                                        {latestAssistantPreview
                                            ? latestAssistantPreview.slice(0, 180) + (latestAssistantPreview.length > 180 ? '…' : '')
                                            : 'The latest assistant assessment will appear here before note generation.'}
                                    </span>
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
