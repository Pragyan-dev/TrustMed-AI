import { useState, useRef, useEffect } from 'react'
import {
    Heart, Thermometer, Wind, Droplets, Activity,
    Pill, Stethoscope, Send, Loader2, Image as ImageIcon,
    ClipboardList, Shield, AlertTriangle, CheckCircle2,
    FileHeart, MessageCircle, Smile,
    Plus, Maximize2, Minimize2, X
} from 'lucide-react'
import { MarkdownWithHighlight } from '../components/MedicalTermHighlighter'
import SafeMarkdownWrapper from '../components/SafeMarkdownWrapper'
import VitalTrendChart from '../components/VitalTrendChart'
import '../patient-portal.css'

const API_BASE = '/api'
const SAMPLE_PATIENTS = ['10002428', '10025463', '10027602', '10009049', '10007058', '10020640', '10018081', '10023239', '10035631']

// ── ICD title → friendly name mapping ──────────────────────────────────
const FRIENDLY_NAMES = {
    'pneumonia': { name: 'Lung Infection (Pneumonia)', severity: 'high', desc: 'An infection that causes inflammation in your lungs.' },
    'sepsis': { name: 'Blood Infection (Sepsis)', severity: 'high', desc: 'A serious response to infection in your body.' },
    'heart failure': { name: 'Heart Condition', severity: 'high', desc: 'Your heart needs extra support to pump blood effectively.' },
    'atrial fibrillation': { name: 'Irregular Heartbeat', severity: 'moderate', desc: 'Your heart rhythm is irregular, which your care team is monitoring.' },
    'hypertension': { name: 'High Blood Pressure', severity: 'moderate', desc: 'Your blood pressure is higher than the target range.' },
    'diabetes': { name: 'Blood Sugar Condition', severity: 'moderate', desc: 'Your body needs help managing blood sugar levels.' },
    'copd': { name: 'Breathing Condition (COPD)', severity: 'moderate', desc: 'A condition that makes it harder to breathe, managed with inhalers.' },
    'asthma': { name: 'Asthma', severity: 'low', desc: 'A breathing condition well-controlled with medication.' },
    'anemia': { name: 'Low Iron / Anemia', severity: 'low', desc: 'Your blood has fewer red blood cells than normal.' },
    'uti': { name: 'Urinary Tract Infection', severity: 'low', desc: 'An infection in your urinary system being treated with antibiotics.' },
    'kidney': { name: 'Kidney Condition', severity: 'moderate', desc: 'Your kidneys need extra monitoring to work properly.' },
    'liver': { name: 'Liver Condition', severity: 'moderate', desc: 'Your liver function is being monitored by your care team.' },
}

function friendlyDiagnosis(title) {
    const lower = title.toLowerCase()
    for (const [key, val] of Object.entries(FRIENDLY_NAMES)) {
        if (lower.includes(key)) return val
    }
    // Default: clean up title
    return { name: title, severity: 'low', desc: 'Your care team is monitoring this condition.' }
}

// ── Vital status logic ─────────────────────────────────────────────────
function vitalStatus(key, value, vitals) {
    if (value == null) return 'normal'
    switch (key) {
        case 'heart_rate': return value < 60 || value > 100 ? (value < 50 || value > 120 ? 'danger' : 'warning') : 'normal'
        case 'o2_saturation': return value < 90 ? 'danger' : value < 95 ? 'warning' : 'normal'
        case 'temperature': return value < 96 || value > 100.4 ? 'danger' : (value < 97 || value > 99) ? 'warning' : 'normal'
        case 'respiratory_rate': return value < 12 || value > 20 ? (value < 8 || value > 30 ? 'danger' : 'warning') : 'normal'
        case 'bp': {
            const sys = vitals?.systolic_bp
            if (sys == null) return 'normal'
            return sys >= 180 ? 'danger' : sys >= 140 ? 'warning' : sys < 90 ? 'warning' : 'normal'
        }
        default: return 'normal'
    }
}

const VITAL_STATUS_LABELS = {
    normal: 'In range',
    warning: 'Watch',
    danger: 'Attention',
}

const VITAL_STATUS_COLORS = {
    normal: '#16A34A',
    warning: '#D97706',
    danger: '#DC2626',
}

function formatRecordedAt(value) {
    if (!value) return 'Latest reading'

    const parsed = new Date(value.replace(' ', 'T'))
    if (Number.isNaN(parsed.getTime())) return value

    return new Intl.DateTimeFormat(undefined, {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
    }).format(parsed)
}

function formatMetricValue(value, decimals = 0) {
    if (!Number.isFinite(value)) return null
    return decimals > 0 ? value.toFixed(decimals) : Math.round(value).toString()
}

function buildRangeLabel(values, formatter, prefix = 'Range') {
    const validValues = values.filter(Number.isFinite)
    if (!validValues.length) return 'No trend data yet'
    if (validValues.length === 1) return 'Single recent reading'

    const minValue = Math.min(...validValues)
    const maxValue = Math.max(...validValues)
    return `${prefix} ${formatter(minValue)}-${formatter(maxValue)}`
}

function formatTrendDate(value) {
    if (!value) return 'Latest reading'

    const parsed = new Date(value.replace(' ', 'T'))
    if (Number.isNaN(parsed.getTime())) return value

    return new Intl.DateTimeFormat(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
    }).format(parsed)
}

// Strip wrapping quotes from LLM responses
const cleanContent = (text) => {
    if (!text) return ''
    let t = text.trim()
    if (t.startsWith('"') && t.endsWith('"')) t = t.slice(1, -1)
    return t
}

const PATIENT_ASSISTANT_SCOPE_REPLY = 'I can only help with your health record, medications, vitals, imaging, lab results, and care plan. Ask me about your visit or chart data.'

const OFF_TOPIC_PATTERNS = [
    /\b(write|generate|create|make|build)\s+(a\s+)?(python|javascript|java|c\+\+|c#|html|css|sql|code|program|script)\b/i,
    /\b(python|javascript|typescript|java|c\+\+|rust|golang|node\.?js|react)\b/i,
    /\b(prime numbers?|leetcode|binary tree|algorithm|sort an array)\b/i,
    /\b(recipe|weather|movie|song|poem|essay|resume|cover letter|crypto|stock market)\b/i,
    /\btranslate\b/i,
]

const MEDICAL_SCOPE_PATTERNS = [
    /\b(health|visit|record|chart|doctor|care team|medical|diagnosis|diagnoses|condition|symptom|symptoms|medication|medications|medicine|drug|drugs|dose|side effect|interaction|allergy|vitals?|blood pressure|heart rate|pulse|oxygen|spo2|temperature|fever|breathing|respiratory|lab|labs|test result|results|imaging|x-ray|ct|mri|scan|ultrasound|report|care plan|follow-up|treatment|infection|pain|cough|glucose|cholesterol)\b/i,
]

function shouldBlockOffTopicPatientQuestion(text) {
    if (!text) return false
    const normalized = text.trim()
    if (!normalized) return false

    const looksMedical = MEDICAL_SCOPE_PATTERNS.some(pattern => pattern.test(normalized))
    if (looksMedical) return false

    return OFF_TOPIC_PATTERNS.some(pattern => pattern.test(normalized))
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

export default function PatientPortal() {
    const [selectedPatient, setSelectedPatient] = useState('')
    const [patientData, setPatientData] = useState(null)
    const [loading, setLoading] = useState(false)
    const [patientSummary, setPatientSummary] = useState(null)
    const [summaryLoading, setSummaryLoading] = useState(false)
    const [summaryError, setSummaryError] = useState('')

    // Chat state
    const [chatMessages, setChatMessages] = useState([])
    const [chatInput, setChatInput] = useState('')
    const [chatLoading, setChatLoading] = useState(false)
    const [sessionId, setSessionId] = useState(null)
    const chatEndRef = useRef(null)
    const [activeSection, setActiveSection] = useState('profile')
    const [assistantMinimized, setAssistantMinimized] = useState(false)
    const [assistantExpanded, setAssistantExpanded] = useState(false)

    // Interaction check
    const [checkingMed, setCheckingMed] = useState(null)
    const [interactionResult, setInteractionResult] = useState(null)
    const summaryRequestRef = useRef(0)

    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [chatMessages])

    // ── Load patient data ────────────────────────────────────────────
    const loadPatient = async (patId) => {
        const requestId = ++summaryRequestRef.current
        setChatMessages([])
        setChatInput('')
        setSessionId(null)
        setActiveSection('profile')
        setInteractionResult(null)
        setPatientData(null)
        setPatientSummary(null)
        setSummaryError('')
        setSummaryLoading(false)
        if (!patId) {
            return
        }
        setLoading(true)
        try {
            const res = await fetch(`${API_BASE}/patient/${patId}`)
            if (!res.ok) throw new Error('Failed to load patient data')

            const data = await res.json()
            if (summaryRequestRef.current !== requestId) return
            setPatientData(data)
            setLoading(false)

            setSummaryLoading(true)
            try {
                const summaryRes = await fetch(`${API_BASE}/patient/${patId}/summary`, {
                    method: 'POST',
                })
                if (!summaryRes.ok) throw new Error('Failed to load patient summary')

                const summaryData = await summaryRes.json()
                if (summaryRequestRef.current !== requestId) return
                setPatientSummary(summaryData)
                setSummaryError('')
            } catch (summaryErr) {
                console.error('Failed to load patient summary:', summaryErr)
                if (summaryRequestRef.current === requestId) {
                    setPatientSummary(null)
                    setSummaryError('Personalized care plan unavailable right now.')
                }
            } finally {
                if (summaryRequestRef.current === requestId) {
                    setSummaryLoading(false)
                }
            }
        } catch (err) {
            console.error('Failed to load patient:', err)
            if (summaryRequestRef.current === requestId) {
                setPatientData(null)
                setPatientSummary(null)
                setSummaryError('')
                setSummaryLoading(false)
                setLoading(false)
            }
        }
    }

    // ── Chat (with plain-language wrapper) ───────────────────────────
    const submitChatMessage = async (rawMessage) => {
        if (!rawMessage.trim() || chatLoading) return

        const userMsg = rawMessage.trim()
        setChatInput('')

        if (shouldBlockOffTopicPatientQuestion(userMsg)) {
            setChatMessages(prev => [
                ...prev,
                { role: 'user', content: userMsg },
                { role: 'assistant', content: PATIENT_ASSISTANT_SCOPE_REPLY },
            ])
            return
        }

        let sid = sessionId
        if (!sid) {
            try {
                const res = await fetch(`${API_BASE}/sessions/new?source=patient`, { method: 'POST' })
                const data = await res.json()
                sid = data.id
                setSessionId(data.id)
            } catch { return }
        }

        setChatMessages(prev => [...prev, { role: 'user', content: userMsg }])
        setChatLoading(true)

        // Wrap with plain-language system prompt + patient context
        let patientContext = ''
        if (patientData) {
            const parts = [`Patient ${patientData.patient_id || selectedPatient}`]
            if (patientData.vitals) {
                const v = patientData.vitals
                const vitals = []
                if (v.heart_rate != null) vitals.push(`HR ${Math.round(v.heart_rate)} bpm`)
                if (v.temperature != null) vitals.push(`Temp ${v.temperature.toFixed(1)}°F`)
                if (v.respiratory_rate != null) vitals.push(`RR ${Math.round(v.respiratory_rate)}/min`)
                if (v.o2_saturation != null) vitals.push(`SpO₂ ${Math.round(v.o2_saturation)}%`)
                if (v.systolic_bp != null) vitals.push(`BP ${Math.round(v.systolic_bp)}/${Math.round(v.diastolic_bp)} mmHg`)
                if (vitals.length) parts.push(`Vitals: ${vitals.join(', ')}`)
            }
            if (patientData.diagnoses?.length) {
                parts.push(`Diagnoses: ${patientData.diagnoses.map(d => d.title).join(', ')}`)
            }
            if (patientData.medications?.length) {
                parts.push(`Current Medications: ${patientData.medications.map(m => m.name).join(', ')}`)
            }
            patientContext = `\n\nPatient clinical context:\n${parts.join('\n')}`
        }

        const wrappedMessage = `[PATIENT PORTAL] You are TrustMed AI's patient visit assistant. You may only answer questions about this patient's visit, chart, diagnoses, medications, vitals, lab results, imaging, symptoms, or care plan.${patientContext}

If the patient asks for anything outside that scope, do not answer the request. Respond exactly with:
"${PATIENT_ASSISTANT_SCOPE_REPLY}"

Patient question: "${userMsg}"

Explain in plain language at an 8th-grade reading level. Avoid medical jargon. Be warm, direct, and concise. Use short sentences and bullet points when helpful. Answer specifically about this patient's data when relevant.`

        try {
            const res = await fetch(`${API_BASE}/chat/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: wrappedMessage,
                    session_id: sid,
                    temperature: 0.3,
                })
            })

            let added = false

            await streamSseEvents(res, (event) => {
                if (event.type === 'token') {
                    if (!added) {
                        setChatMessages(prev => [...prev, { role: 'assistant', content: '' }])
                        added = true
                    }
                    setChatMessages(prev => {
                        const u = [...prev]
                        const l = u[u.length - 1]
                        u[u.length - 1] = { ...l, content: l.content + event.content }
                        return u
                    })
                } else if (event.type === 'done' && !added && event.final_response) {
                    setChatMessages(prev => [...prev, { role: 'assistant', content: event.final_response }])
                }
            })
        } catch {
            setChatMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }])
        } finally { setChatLoading(false) }
    }

    const sendChat = async (e) => {
        e?.preventDefault()
        await submitChatMessage(chatInput)
    }

    // ── Check drug interactions via chat ─────────────────────────────
    const checkInteraction = async (medName) => {
        setCheckingMed(medName)
        setInteractionResult(null)
        try {
            let sid = sessionId
            if (!sid) {
                const res = await fetch(`${API_BASE}/sessions/new?source=patient`, { method: 'POST' })
                const data = await res.json()
                sid = data.id
                setSessionId(data.id)
            }
            const otherMeds = patientData?.medications
                ?.filter(m => m.name !== medName)
                ?.map(m => m.name)
                ?.join(', ') || 'unknown'
            const res = await fetch(`${API_BASE}/chat/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: `Check drug interactions for ${medName}. The patient's other current medications are: ${otherMeds}. List any interactions in plain language. Be brief.`,
                    session_id: sid,
                    temperature: 0.1,
                    persist: false,
                })
            })
            let result = ''
            await streamSseEvents(res, (event) => {
                if (event.type === 'token') result += event.content
                else if (event.type === 'done' && event.final_response) result = event.final_response
            })
            setInteractionResult(result || 'No significant interactions found.')
        } catch { setInteractionResult('Unable to check interactions right now.') }
        finally { setCheckingMed(null) }
    }

    const imagingResults = Array.isArray(patientData?.imaging_results) ? patientData.imaging_results : null
    const { vitals, diagnoses, medications } = patientData || {}
    const vitalsHistory = Array.isArray(patientData?.vitals_history) && patientData.vitals_history.length
        ? patientData.vitals_history
        : vitals ? [vitals] : []
    const latestVitalsRecordedAt = vitals?.recorded_at || vitalsHistory[vitalsHistory.length - 1]?.recorded_at || null
    const recentReadingLabel = vitalsHistory.length > 1 ? `Last ${vitalsHistory.length} readings` : 'Latest reading'
    const vitalsTrendCharts = vitals ? [
        {
            key: 'heartRate',
            title: 'Heart Rate',
            value: vitals.heart_rate,
            valueText: Number.isFinite(vitals.heart_rate) ? `${Math.round(vitals.heart_rate)} bpm` : null,
            statusTone: vitalStatus('heart_rate', vitals.heart_rate),
            unit: 'bpm',
            points: vitalsHistory.map(row => row.heart_rate),
            labels: vitalsHistory.map(row => row.recorded_at),
            lowerBound: 60,
            upperBound: 100,
            referenceText: 'Typical resting range: 60-100 bpm',
        },
        {
            key: 'bloodPressure',
            title: 'Blood Pressure',
            value: vitals.systolic_bp,
            valueText: Number.isFinite(vitals.systolic_bp)
                ? Number.isFinite(vitals.diastolic_bp)
                    ? `${Math.round(vitals.systolic_bp)}/${Math.round(vitals.diastolic_bp)} mmHg`
                    : `${Math.round(vitals.systolic_bp)} mmHg`
                : null,
            statusTone: vitalStatus('bp', null, vitals),
            unit: 'mmHg',
            points: vitalsHistory.map(row => row.systolic_bp),
            labels: vitalsHistory.map(row => row.recorded_at),
            lowerBound: 90,
            upperBound: 140,
            referenceText: 'Target systolic range: 90-140 mmHg',
        },
        {
            key: 'oxygenSaturation',
            title: 'Oxygen Saturation',
            value: vitals.o2_saturation,
            valueText: Number.isFinite(vitals.o2_saturation) ? `${Math.round(vitals.o2_saturation)}%` : null,
            statusTone: vitalStatus('o2_saturation', vitals.o2_saturation),
            unit: '%',
            points: vitalsHistory.map(row => row.o2_saturation),
            labels: vitalsHistory.map(row => row.recorded_at),
            lowerBound: 95,
            referenceText: 'Goal oxygen saturation: at least 95%',
        },
        {
            key: 'temperature',
            title: 'Temperature',
            value: vitals.temperature,
            valueText: Number.isFinite(vitals.temperature) ? `${vitals.temperature.toFixed(1)}°F` : null,
            statusTone: vitalStatus('temperature', vitals.temperature),
            unit: '°F',
            points: vitalsHistory.map(row => row.temperature),
            labels: vitalsHistory.map(row => row.recorded_at),
            lowerBound: 97,
            upperBound: 99,
            referenceText: 'Typical oral temperature: 97.0-99.0°F',
        },
    ].filter(chart => Number.isFinite(chart.value)) : []
    const sectionTabs = [
        { key: 'profile', label: 'Health Profile' },
        { key: 'vitals', label: 'Vitals' },
        { key: 'medications', label: 'Medications' },
        { key: 'imaging', label: 'Imaging' },
        { key: 'carePlan', label: 'Care Plan' },
    ]
    const assistantPrompts = [
        'Give me an overview of my health record.',
        'What are the key things in my medical history?',
        'Are there any concerning trends in my health data?',
    ]
    const profileFacts = [
        { label: 'Patient ID', value: patientData?.patient_id || selectedPatient || 'Unknown' },
        { label: 'Active conditions', value: diagnoses?.length ? `${diagnoses.length}` : '0' },
        { label: 'Medications', value: medications?.length ? `${medications.length}` : '0' },
        { label: 'Latest update', value: formatRecordedAt(latestVitalsRecordedAt) },
    ]
    const askAboutSection = (question) => submitChatMessage(question)

    return (
        <div className="pp">
            <div className={`pp-shell ${assistantMinimized ? 'pp-shell--assistant-hidden' : ''}`}>
                <div className="pp-main">
                    <div className="pp-patient-bar">
                        <Smile size={18} style={{ color: 'var(--pp-green)' }} />
                        <label>Patient Profile</label>
                        <select
                            value={selectedPatient}
                            onChange={e => { setSelectedPatient(e.target.value); loadPatient(e.target.value) }}
                        >
                            <option value="">Select your profile…</option>
                            {SAMPLE_PATIENTS.map(p => <option key={p} value={p}>Patient {p}</option>)}
                        </select>
                        {loading && <Loader2 size={18} className="pp-spin" style={{ color: 'var(--pp-green)' }} />}
                    </div>

                    {!patientData ? (
                        <div className="pp-empty pp-empty--hero">
                            <FileHeart size={52} style={{ color: 'var(--pp-text-muted)' }} />
                            <p style={{ fontSize: '1.1rem', marginTop: '1rem' }}>
                                Welcome to your Patient Portal
                            </p>
                            <p>Select a patient profile to load the health record, vitals, medications, and care plan.</p>
                        </div>
                    ) : (
                        <>
                            <div className="pp-page-hero">
                                <div>
                                    <div className="pp-page-kicker">Patient panel</div>
                                    <h1 className="pp-page-title">My Health</h1>
                                    <p className="pp-page-subtitle">
                                        {patientSummary?.summary || 'A patient-friendly view of your current chart data and recent trends.'}
                                    </p>
                                </div>
                                <div className="pp-page-badges">
                                    {profileFacts.map(item => (
                                        <div key={item.label} className="pp-page-badge">
                                            <span className="pp-page-badge__label">{item.label}</span>
                                            <span className="pp-page-badge__value">{item.value}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div className="pp-section-tabs">
                                {sectionTabs.map(tab => (
                                    <button
                                        key={tab.key}
                                        className={`pp-section-tab ${activeSection === tab.key ? 'pp-section-tab--active' : ''}`}
                                        onClick={() => setActiveSection(tab.key)}
                                        type="button"
                                    >
                                        {tab.label}
                                    </button>
                                ))}
                            </div>

                            <div className="pp-content-stack">
                                {activeSection === 'profile' && (
                                <section className="pp-card pp-section-card">
                                    <div className="pp-card__header pp-card__header--split">
                                        <div className="pp-card__heading">
                                            <div className="pp-card__icon pp-card__icon--green"><Stethoscope size={18} /></div>
                                            <span className="pp-card__title">Health Profile</span>
                                        </div>
                                        <button
                                            className="pp-card__ask"
                                            type="button"
                                            onClick={() => askAboutSection('Give me an overview of my health record and what my main conditions mean.')}
                                        >
                                            <MessageCircle size={14} />
                                            Ask
                                        </button>
                                    </div>
                                    <div className="pp-card__body">
                                        <div className="pp-profile-summary">
                                            <div className="pp-profile-intro">
                                                <div className="pp-profile-avatar">{(patientData.patient_id || 'P').slice(0, 1)}</div>
                                                <div>
                                                    <div className="pp-profile-title">Patient {patientData.patient_id || selectedPatient}</div>
                                                    <div className="pp-profile-subtitle">Current record summary and active health concerns.</div>
                                                </div>
                                            </div>
                                            <div className="pp-profile-callout">
                                                {patientSummary?.summary || 'Your health profile summarizes the conditions, medications, and recent trends available in your current chart.'}
                                            </div>
                                        </div>

                                        <div className="pp-profile-grid">
                                            <div className="pp-profile-panel">
                                                <div className="pp-section-mini-title">Profile snapshot</div>
                                                <div className="pp-profile-facts">
                                                    {profileFacts.map(item => (
                                                        <div key={item.label} className="pp-profile-fact">
                                                            <span className="pp-profile-fact__label">{item.label}</span>
                                                            <span className="pp-profile-fact__value">{item.value}</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                            <div className="pp-profile-panel">
                                                <div className="pp-section-mini-title">Active conditions</div>
                                                {diagnoses && diagnoses.length > 0 ? (
                                                    <div className="pp-diagnosis-list">
                                                        {diagnoses.map((d, i) => {
                                                            const friendly = friendlyDiagnosis(d.title)
                                                            return (
                                                                <div key={i} className="pp-diagnosis">
                                                                    <span className={`pp-diagnosis__badge pp-diagnosis__badge--${friendly.severity}`}>
                                                                        {friendly.severity}
                                                                    </span>
                                                                    <div>
                                                                        <div className="pp-diagnosis__name">{friendly.name}</div>
                                                                        <div className="pp-diagnosis__desc">{friendly.desc}</div>
                                                                    </div>
                                                                </div>
                                                            )
                                                        })}
                                                    </div>
                                                ) : (
                                                    <div className="pp-empty">
                                                        <CheckCircle2 size={24} />
                                                        <p>No active conditions on file.</p>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </section>
                                )}

                                {activeSection === 'vitals' && (
                                <section className="pp-card pp-section-card">
                                    <div className="pp-card__header pp-card__header--split">
                                        <div className="pp-card__heading">
                                            <div className="pp-card__icon pp-card__icon--red"><Heart size={18} /></div>
                                            <span className="pp-card__title">Vitals</span>
                                        </div>
                                        <button
                                            className="pp-card__ask"
                                            type="button"
                                            onClick={() => askAboutSection('Are there any concerning trends in my vital signs?')}
                                        >
                                            <MessageCircle size={14} />
                                            Ask
                                        </button>
                                    </div>
                                    <div className="pp-card__body">
                                        {vitals ? (
                                            <>
                                                <div className="pp-vitals-meta">
                                                    <span className="pp-vitals-meta__stamp">Latest charted {formatRecordedAt(latestVitalsRecordedAt)}</span>
                                                    <span className="pp-vitals-meta__window">{recentReadingLabel}</span>
                                                </div>
                                                <div className="pp-vitals-trends">
                                                    {vitalsTrendCharts.map(chart => (
                                                        <VitalTrendChart
                                                            key={chart.key}
                                                            title={chart.title}
                                                            recordedAt={formatTrendDate(latestVitalsRecordedAt)}
                                                            valueText={chart.valueText}
                                                            statusText={VITAL_STATUS_LABELS[chart.statusTone]}
                                                            statusTone={chart.statusTone}
                                                            referenceText={chart.referenceText}
                                                            unit={chart.unit}
                                                            points={chart.points}
                                                            labels={chart.labels}
                                                            lowerBound={chart.lowerBound}
                                                            upperBound={chart.upperBound}
                                                            pointColor={VITAL_STATUS_COLORS[chart.statusTone]}
                                                        />
                                                    ))}
                                                </div>
                                                <div className="pp-vitals-footnote">
                                                    {vitals.respiratory_rate != null && (
                                                        <div className={`pp-vitals-footnote__item pp-vitals-footnote__item--${vitalStatus('respiratory_rate', vitals.respiratory_rate)}`}>
                                                            <Wind size={14} />
                                                            <span>Breathing rate {Math.round(vitals.respiratory_rate)}/min</span>
                                                        </div>
                                                    )}
                                                    {latestVitalsRecordedAt && (
                                                        <div className="pp-vitals-footnote__item">
                                                            <Heart size={14} />
                                                            <span>Trends reflect recent bedside charting</span>
                                                        </div>
                                                    )}
                                                </div>
                                            </>
                                        ) : (
                                                <div className="pp-empty"><p>No vitals recorded yet.</p></div>
                                            )}
                                    </div>
                                </section>
                                )}

                                {activeSection === 'medications' && (
                                <section className="pp-card pp-section-card">
                                    <div className="pp-card__header pp-card__header--split">
                                        <div className="pp-card__heading">
                                            <div className="pp-card__icon pp-card__icon--blue"><Pill size={18} /></div>
                                            <span className="pp-card__title">Medications</span>
                                        </div>
                                        <button
                                            className="pp-card__ask"
                                            type="button"
                                            onClick={() => askAboutSection('What should I know about my current medications and how they work together?')}
                                        >
                                            <MessageCircle size={14} />
                                            Ask
                                        </button>
                                    </div>
                                    <div className="pp-card__body">
                                        {medications && medications.length > 0 ? (
                                            <div className="pp-med-list">
                                                {medications.map((m, i) => (
                                                    <div key={i} className="pp-med">
                                                        <div className="pp-med__pill"><Pill size={16} /></div>
                                                        <div className="pp-med__info">
                                                            <div className="pp-med__name">{m.name}</div>
                                                            <div className="pp-med__desc">{m.description || 'Prescribed by your care team'}</div>
                                                        </div>
                                                        <button
                                                            className="pp-med__check-btn"
                                                            onClick={() => checkInteraction(m.name)}
                                                            disabled={checkingMed === m.name}
                                                        >
                                                            {checkingMed === m.name ? (
                                                                <><Loader2 size={12} className="pp-spin" /> Checking…</>
                                                            ) : (
                                                                <><Shield size={12} /> Check</>
                                                            )}
                                                        </button>
                                                    </div>
                                                ))}
                                                {interactionResult && (
                                                    <div className="pp-inline-result">
                                                        <strong className="pp-inline-result__title">
                                                            <Shield size={14} />
                                                            Interaction Check Result
                                                        </strong>
                                                        <div className="pp-inline-result__body">
                                                            <SafeMarkdownWrapper fallbackText={cleanContent(interactionResult)}>
                                                                <MarkdownWithHighlight>{cleanContent(interactionResult)}</MarkdownWithHighlight>
                                                            </SafeMarkdownWrapper>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        ) : (
                                            <div className="pp-empty"><p>No medications on file.</p></div>
                                        )}
                                    </div>
                                </section>
                                )}

                                {activeSection === 'imaging' && (
                                <section className="pp-card pp-section-card">
                                    <div className="pp-card__header pp-card__header--split">
                                        <div className="pp-card__heading">
                                            <div className="pp-card__icon pp-card__icon--purple"><ImageIcon size={18} /></div>
                                            <span className="pp-card__title">Imaging Results</span>
                                        </div>
                                        <button
                                            className="pp-card__ask"
                                            type="button"
                                            onClick={() => askAboutSection('Summarize my imaging results in simple language.')}
                                        >
                                            <MessageCircle size={14} />
                                            Ask
                                        </button>
                                    </div>
                                    <div className="pp-card__body">
                                        {imagingResults ? (
                                            imagingResults.map((r, i) => (
                                                <div key={i} className="pp-imaging-result">
                                                    <span className={`pp-imaging-badge pp-imaging-badge--${r.status}`}>
                                                        {r.status === 'normal' ? <CheckCircle2 size={12} /> : r.status === 'attention' ? <AlertTriangle size={12} /> : <AlertTriangle size={12} />}
                                                        {' '}{r.label}
                                                    </span>
                                                    <span className="pp-imaging-text">
                                                        {r.status === 'normal' ? 'Your recent imaging looks good.' :
                                                            r.status === 'attention' ? 'Your doctor will discuss this finding with you.' :
                                                                'Your care team is reviewing this result carefully.'}
                                                    </span>
                                                </div>
                                            ))
                                        ) : (
                                            <div className="pp-empty">
                                                <ImageIcon size={24} />
                                                <p>No imaging results yet. Results will appear here after your scans are reviewed.</p>
                                            </div>
                                        )}
                                    </div>
                                </section>
                                )}

                                {activeSection === 'carePlan' && (
                                <section className="pp-card pp-section-card">
                                    <div className="pp-card__header pp-card__header--split">
                                        <div className="pp-card__heading">
                                            <div className="pp-card__icon pp-card__icon--yellow"><ClipboardList size={18} /></div>
                                            <span className="pp-card__title">Care Plan</span>
                                        </div>
                                        <button
                                            className="pp-card__ask"
                                            type="button"
                                            onClick={() => askAboutSection('What are the most important next steps in my care plan?')}
                                        >
                                            <MessageCircle size={14} />
                                            Ask
                                        </button>
                                    </div>
                                    <div className="pp-card__body">
                                        <div className="pp-care-meta">
                                            <span className="pp-care-tag">Generated from your current chart data</span>
                                            <span className="pp-care-disclaimer">For understanding only, not medical advice.</span>
                                        </div>

                                        {summaryLoading ? (
                                            <div className="pp-empty">
                                                <Loader2 size={24} className="pp-spin" />
                                                <p>Building your personalized care plan…</p>
                                            </div>
                                        ) : summaryError ? (
                                            <div className="pp-care-unavailable">
                                                <AlertTriangle size={18} />
                                                <div>
                                                    <strong>Personalized care plan unavailable</strong>
                                                    <p>{summaryError}</p>
                                                </div>
                                            </div>
                                        ) : patientSummary ? (
                                            <div className="pp-care-plan">
                                                <div className="pp-care-summary">{patientSummary.summary}</div>

                                                <div className="pp-care-explainers">
                                                    <div className="pp-care-explainer">
                                                        <div className="pp-care-explainer__title">Vitals</div>
                                                        <div className="pp-care-explainer__body">{patientSummary.vitals_explanation}</div>
                                                    </div>
                                                    <div className="pp-care-explainer">
                                                        <div className="pp-care-explainer__title">Medications</div>
                                                        <div className="pp-care-explainer__body">{patientSummary.medications_explanation}</div>
                                                    </div>
                                                </div>

                                                <div className="pp-care-list">
                                                    {patientSummary.next_steps?.map((step, index) => (
                                                        <div key={`${step}-${index}`} className="pp-care-item">
                                                            <div className="pp-care-item__icon" style={{ background: 'var(--pp-green-light)', color: 'var(--pp-green)' }}>
                                                                <CheckCircle2 size={16} />
                                                            </div>
                                                            <div className="pp-care-item__text">
                                                                <div className="pp-care-item__title">Next Step {index + 1}</div>
                                                                <div className="pp-care-item__detail">{step}</div>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="pp-care-unavailable">
                                                <AlertTriangle size={18} />
                                                <div>
                                                    <strong>Personalized care plan unavailable</strong>
                                                    <p>We could not generate a patient-specific care plan right now.</p>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </section>
                                )}
                            </div>
                        </>
                    )}
                </div>

                {!assistantMinimized && (
                <aside className={`pp-assistant-shell ${assistantExpanded ? 'pp-assistant-shell--expanded' : ''}`}>
                    <div className={`pp-assistant ${assistantExpanded ? 'pp-assistant--expanded' : ''}`}>
                        <div className="pp-assistant__header">
                            <div className="pp-assistant__badge"><Stethoscope size={24} strokeWidth={2.2} /></div>
                            <div>
                                <div className="pp-assistant__title">TrustMed AI</div>
                                <div className="pp-assistant__subtitle">Ask anything about your visit</div>
                            </div>
                            <div className="pp-assistant__controls">
                                <button
                                    type="button"
                                    className="pp-assistant__control-btn"
                                    onClick={() => setAssistantExpanded(prev => !prev)}
                                    aria-label={assistantExpanded ? 'Restore assistant panel' : 'Expand assistant panel'}
                                >
                                    {assistantExpanded ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
                                </button>
                                <button
                                    type="button"
                                    className="pp-assistant__control-btn"
                                    onClick={() => setAssistantMinimized(true)}
                                    aria-label="Minimize assistant panel"
                                >
                                    <X size={18} />
                                </button>
                            </div>
                        </div>

                        <div className="pp-assistant__body">
                            {chatMessages.length === 0 ? (
                                <div className="pp-assistant__empty">
                                    <div className="pp-assistant__hero">
                                        <div className="pp-assistant__hero-icon"><Stethoscope size={42} strokeWidth={2.15} /></div>
                                        <div className="pp-assistant__hero-title">Your visit assistant</div>
                                        <div className="pp-assistant__hero-pill">Patient Record</div>
                                        <p>Ask me anything about your health.</p>
                                    </div>
                                    <div className="pp-assistant__suggestions">
                                        {assistantPrompts.map(prompt => (
                                            <button
                                                key={prompt}
                                                type="button"
                                                className="pp-assistant__suggestion"
                                                onClick={() => askAboutSection(prompt)}
                                                disabled={!patientData || chatLoading}
                                            >
                                                {prompt}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            ) : (
                                <div className="pp-chat pp-chat--sidebar">
                                    <div className="pp-chat__messages">
                                        {chatMessages.map((m, i) => (
                                            <div key={i} className={`pp-chat__msg pp-chat__msg--${m.role}`}>
                                                {m.role === 'assistant' ? (
                                                    <SafeMarkdownWrapper fallbackText={cleanContent(m.content)}>
                                                        <MarkdownWithHighlight>{cleanContent(m.content)}</MarkdownWithHighlight>
                                                    </SafeMarkdownWrapper>
                                                ) : m.content}
                                            </div>
                                        ))}
                                        {chatLoading && !chatMessages.some((m, i) => i === chatMessages.length - 1 && m.role === 'assistant') && (
                                            <div className="pp-chat__typing">
                                                <div className="pp-chat__dot" />
                                                <div className="pp-chat__dot" />
                                                <div className="pp-chat__dot" />
                                            </div>
                                        )}
                                        <div ref={chatEndRef} />
                                    </div>
                                </div>
                            )}
                        </div>

                        <form className="pp-assistant__composer" onSubmit={sendChat}>
                            <button
                                type="button"
                                className="pp-assistant__plus-btn"
                                onClick={() => askAboutSection('Give me an overview of my health record.')}
                                disabled={!patientData || chatLoading}
                                aria-label="Use a suggested patient-record question"
                            >
                                <Plus size={24} />
                            </button>
                            <input
                                className="pp-chat__input"
                                value={chatInput}
                                onChange={e => setChatInput(e.target.value)}
                                placeholder={patientData ? 'Ask about your visit…' : 'Select a patient profile to begin…'}
                                disabled={chatLoading || !patientData}
                            />
                            <button className="pp-chat__send pp-chat__send--label" type="submit" disabled={!chatInput.trim() || chatLoading || !patientData}>
                                {chatLoading ? <Loader2 size={18} className="pp-spin" /> : <Send size={18} />}
                                <span>Send</span>
                            </button>
                        </form>
                    </div>
                </aside>
                )}

                {assistantMinimized && (
                    <button
                        type="button"
                        className="pp-assistant-launcher"
                        onClick={() => setAssistantMinimized(false)}
                        aria-label="Open visit assistant"
                    >
                        <span className="pp-assistant-launcher__dot" />
                        <span className="pp-assistant-launcher__icon">
                            <Stethoscope size={30} strokeWidth={2.15} />
                        </span>
                    </button>
                )}
            </div>
        </div>
    )
}
