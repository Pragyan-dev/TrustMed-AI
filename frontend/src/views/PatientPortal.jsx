import { useState, useRef, useEffect } from 'react'
import {
    Heart, Thermometer, Wind, Droplets, Activity,
    Pill, Stethoscope, Send, Loader2, Image as ImageIcon,
    ClipboardList, Shield, AlertTriangle, CheckCircle2,
    FileHeart, MessageCircle, Smile,
    Plus, Maximize2, Minimize2, X, SlidersHorizontal,
    User, TrendingUp, TrendingDown, Minus, Calendar, Beaker,
    Clock, Scan, CircleDot, Gauge, FileText, Upload, ArrowUpRight, Download
} from 'lucide-react'
import { MarkdownWithHighlight, SelectionExplainToolbar } from '../components/MedicalTermHighlighter'
import SafeMarkdownWrapper from '../components/SafeMarkdownWrapper'
import VitalTrendChart from '../components/VitalTrendChart'
import { AVAILABLE_TEXT_MODELS, DEFAULT_TEXT_MODEL } from '../lib/modelOptions'

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

const VITAL_ICONS = {
    heartRate: Heart,
    bloodPressure: Activity,
    oxygenSaturation: Droplets,
    temperature: Thermometer,
}

const VITAL_STATUS_ICON = {
    normal: Minus,
    warning: TrendingUp,
    danger: AlertTriangle,
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

function formatAttachmentDate(value) {
    if (!value) return 'Just added'

    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return value

    return new Intl.DateTimeFormat(undefined, {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
    }).format(parsed)
}

function getAttachmentSourceMeta(uploadedBy) {
    if (uploadedBy === 'patient') {
        return {
            label: 'Uploaded by you',
            tone: 'patient',
        }
    }

    return {
        label: 'Shared by care team',
        tone: 'clinician',
    }
}

function getAttachmentTypeLabel(attachment) {
    return attachment?.file_kind === 'pdf' ? 'PDF report' : 'Imaging file'
}

function getAttachmentProcessingMeta(attachment) {
    const status = attachment?.processing_status
    if (!status || attachment?.file_kind !== 'pdf') return null

    if (status === 'completed') {
        return { label: 'Parsed', tone: 'ok' }
    }
    if (status === 'completed_with_fallback') {
        return { label: 'Parsed with OCR fallback', tone: 'info' }
    }
    if (status === 'failed') {
        return { label: 'Could not parse', tone: 'error' }
    }

    return { label: 'Processing', tone: 'info' }
}

// Strip wrapping quotes from LLM responses
const cleanContent = (text) => {
    if (!text) return ''
    let t = text.trim()
    if (t.startsWith('"') && t.endsWith('"')) t = t.slice(1, -1)
    return t
}

async function readApiError(response, fallbackMessage) {
    const contentType = response.headers.get('content-type') || ''

    try {
        if (contentType.includes('application/json')) {
            const data = await response.json()
            if (typeof data?.detail === 'string' && data.detail.trim()) {
                return data.detail.trim()
            }
            if (typeof data?.message === 'string' && data.message.trim()) {
                return data.message.trim()
            }
        } else {
            const text = (await response.text()).trim()
            if (text) {
                return response.status >= 500
                    ? fallbackMessage
                    : text.slice(0, 220)
            }
        }
    } catch {
        // Fall through to fallback message.
    }

    return fallbackMessage
}

function normalizeFetchError(error, fallbackMessage) {
    const message = error instanceof Error ? error.message : ''
    if (message.includes('Failed to fetch') || message.includes('NetworkError')) {
        return 'Synapse AI could not reach the backend. Start the FastAPI server on http://localhost:8000 and try again.'
    }
    return fallbackMessage
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

function toSentenceList(value, { splitSemicolons = false, maxItems = 6 } = {}) {
    if (!value || typeof value !== 'string') return []

    const normalized = value.replace(/\s+/g, ' ').trim()
    if (!normalized) return []

    const fragments = splitSemicolons
        ? normalized.split(/\s*;\s*/)
        : normalized.split(/(?<=[.!?])\s+/)

    return fragments
        .map(fragment => fragment.trim().replace(/^[-*•\d.)\s]+/, '').trim())
        .filter(Boolean)
        .slice(0, maxItems)
}

function parseStructuredSummaryString(value) {
    if (!value || typeof value !== 'string') return []

    const trimmed = value.trim()
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
        const matches = [...trimmed.matchAll(/'[^']+'\s*:\s*'([^']+)'/g)]
        return matches.map(([, text]) => text.trim()).filter(Boolean)
    }

    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
        const matches = [...trimmed.matchAll(/'name'\s*:\s*'([^']+)'\s*,\s*'explanation'\s*:\s*'([^']+)'/g)]
        return matches
            .map(([, name, explanation]) => `${name.trim()}: ${explanation.trim()}`)
            .filter(Boolean)
    }

    return []
}

function normalizeCarePlanSteps(steps = []) {
    const baseSteps = Array.isArray(steps)
        ? steps.map(step => String(step || '').trim()).filter(Boolean)
        : []

    if (baseSteps.length !== 1) return baseSteps

    const expanded = baseSteps[0]
        .replace(/\s+and call\b/ig, '. Call')
        .replace(/\s+and keep\b/ig, '. Keep')
        .replace(/\s+and ask\b/ig, '. Ask')
        .replace(/\s+and bring\b/ig, '. Bring')
        .replace(/\s+and tell\b/ig, '. Tell')
        .split(/(?<=[.!?])\s+|;\s+/)
        .flatMap(step => step.split(/,\s+(?=(review|keep|call|ask|bring|tell|track|watch)\b)/i))
        .map(step => step.trim())
        .filter(Boolean)

    return expanded.length > 1 ? expanded : baseSteps
}

function getCareStepMeta(step, index) {
    const lower = String(step || '').toLowerCase()

    if (/(call|right away|urgent|short of breath|fever rises|breathing feels worse|worse)/.test(lower)) {
        return {
            label: 'Watch Closely',
            tone: 'alert',
        }
    }

    if (/(medication|medicine|bring your medication list|what each medicine is for)/.test(lower)) {
        return {
            label: 'Medication Check',
            tone: 'calm',
        }
    }

    if (/(follow-up|follow up|appointment|review these results|next visit)/.test(lower)) {
        return {
            label: 'Follow-Up',
            tone: 'primary',
        }
    }

    return {
        label: `Step ${index + 1}`,
        tone: 'primary',
    }
}

export default function PatientPortal() {
    const [selectedPatient, setSelectedPatient] = useState('')
    const [patientData, setPatientData] = useState(null)
    const [loading, setLoading] = useState(false)
    const [patientSummary, setPatientSummary] = useState(null)
    const [summaryLoading, setSummaryLoading] = useState(false)
    const [summaryError, setSummaryError] = useState('')
    const [loadError, setLoadError] = useState('')
    const [attachments, setAttachments] = useState([])
    const [attachmentsLoading, setAttachmentsLoading] = useState(false)
    const [attachmentsError, setAttachmentsError] = useState('')
    const [attachmentUploading, setAttachmentUploading] = useState(false)
    const [attachmentUploadError, setAttachmentUploadError] = useState('')

    // Chat state
    const [chatMessages, setChatMessages] = useState([])
    const [chatInput, setChatInput] = useState('')
    const [chatLoading, setChatLoading] = useState(false)
    const [sessionId, setSessionId] = useState(null)
    const chatEndRef = useRef(null)
    const patientChatMessagesRef = useRef(null)
    const [activeSection, setActiveSection] = useState('profile')
    const [assistantMinimized, setAssistantMinimized] = useState(false)
    const [assistantExpanded, setAssistantExpanded] = useState(false)
    const [selectedModel, setSelectedModel] = useState(DEFAULT_TEXT_MODEL)
    const [settingsOpen, setSettingsOpen] = useState(false)

    // Interaction check
    const [checkingMed, setCheckingMed] = useState(null)
    const [interactionResult, setInteractionResult] = useState(null)
    const summaryRequestRef = useRef(0)
    const attachmentInputRef = useRef(null)

    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [chatMessages])

    const loadPatientAttachments = async (patId, requestId = summaryRequestRef.current) => {
        setAttachmentsLoading(true)
        setAttachmentsError('')

        try {
            const res = await fetch(`${API_BASE}/patient/${patId}/attachments`)
            if (!res.ok) {
                throw new Error(await readApiError(
                    res,
                    'Imaging files could not be loaded right now.'
                ))
            }

            const data = await res.json()
            if (summaryRequestRef.current !== requestId) return
            setAttachments(Array.isArray(data.attachments) ? data.attachments : [])
            setAttachmentsError('')
        } catch (err) {
            console.error('Failed to load patient attachments:', err)
            if (summaryRequestRef.current === requestId) {
                setAttachments([])
                setAttachmentsError(normalizeFetchError(err, 'Imaging files could not be loaded right now.'))
            }
        } finally {
            if (summaryRequestRef.current === requestId) {
                setAttachmentsLoading(false)
            }
        }
    }

    const refreshPatientSnapshot = async (patId, requestId = summaryRequestRef.current) => {
        const res = await fetch(`${API_BASE}/patient/${patId}`)
        if (!res.ok) {
            throw new Error(await readApiError(
                res,
                'Patient data could not be loaded. Make sure the FastAPI backend is running on http://localhost:8000.'
            ))
        }

        const data = await res.json()
        if (summaryRequestRef.current !== requestId) return
        setPatientData(data)
        setLoadError('')

        setSummaryLoading(true)
        const summaryPromise = (async () => {
            try {
                const summaryRes = await fetch(`${API_BASE}/patient/${patId}/summary`, {
                    method: 'POST',
                })
                if (!summaryRes.ok) {
                    throw new Error(await readApiError(
                        summaryRes,
                        'Personalized care plan unavailable right now.'
                    ))
                }

                const summaryData = await summaryRes.json()
                if (summaryRequestRef.current !== requestId) return
                setPatientSummary(summaryData)
                setSummaryError('')
            } catch (summaryErr) {
                console.error('Failed to load patient summary:', summaryErr)
                if (summaryRequestRef.current === requestId) {
                    setPatientSummary(null)
                    setSummaryError(normalizeFetchError(summaryErr, 'Personalized care plan unavailable right now.'))
                }
            } finally {
                if (summaryRequestRef.current === requestId) {
                    setSummaryLoading(false)
                }
            }
        })()

        const attachmentsPromise = loadPatientAttachments(patId, requestId)
        await Promise.allSettled([summaryPromise, attachmentsPromise])
    }

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
        setLoadError('')
        setAttachments([])
        setAttachmentsError('')
        setAttachmentUploadError('')
        setSummaryLoading(false)
        setAttachmentsLoading(false)
        if (!patId) {
            return
        }
        setLoading(true)
        try {
            await refreshPatientSnapshot(patId, requestId)
            if (summaryRequestRef.current === requestId) {
                setLoading(false)
            }
        } catch (err) {
            console.error('Failed to load patient:', err)
            if (summaryRequestRef.current === requestId) {
                setPatientData(null)
                setPatientSummary(null)
                setAttachments([])
                setSummaryError('')
                setAttachmentsError('')
                setLoadError(normalizeFetchError(
                    err,
                    err instanceof Error && err.message
                        ? err.message
                        : 'Patient data could not be loaded.'
                ))
                setSummaryLoading(false)
                setAttachmentsLoading(false)
                setLoading(false)
            }
        }
    }

    const handlePatientAttachmentSelect = async (e) => {
        const file = e.target.files?.[0]
        e.target.value = ''

        const patientId = patientData?.patient_id || selectedPatient
        if (!file || !patientId || attachmentUploading) return

        setAttachmentUploading(true)
        setAttachmentUploadError('')

        try {
            const formData = new FormData()
            formData.append('file', file)

            const res = await fetch(`${API_BASE}/patient/${patientId}/attachments`, {
                method: 'POST',
                body: formData,
            })

            if (!res.ok) {
                throw new Error(await readApiError(
                    res,
                    'Your file could not be uploaded right now.'
                ))
            }

            await refreshPatientSnapshot(patientId)
        } catch (err) {
            console.error('Failed to upload patient attachment:', err)
            setAttachmentUploadError(normalizeFetchError(err, 'Your file could not be uploaded right now.'))
        } finally {
            setAttachmentUploading(false)
        }
    }

    // ── Chat (with plain-language wrapper) ───────────────────────────
    const submitChatMessage = async (rawMessage) => {
        if (!rawMessage.trim() || chatLoading) return

        const userMsg = rawMessage.trim()

        let sid = sessionId
        if (!sid) {
            try {
                const res = await fetch(`${API_BASE}/sessions/new?source=patient`, { method: 'POST' })
                if (!res.ok) throw new Error('Failed to create patient session')
                const data = await res.json()
                sid = data.id
                setSessionId(data.id)
            } catch {
                return
            }
        }

        setChatInput('')
        setChatMessages(prev => [...prev, { role: 'user', content: userMsg }])
        setChatLoading(true)

        try {
            const res = await fetch(`${API_BASE}/chat/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: userMsg,
                    session_id: sid,
                    patient_id: patientData?.patient_id || selectedPatient || null,
                    assistant_mode: 'patient',
                    temperature: 0.3,
                    model: selectedModel,
                })
            })
            if (!res.ok) throw new Error('Failed to send patient message')

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
            const sid = sessionId || `patient-drug-check-${patientData?.patient_id || selectedPatient || 'guest'}`
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
                    patient_id: patientData?.patient_id || selectedPatient || null,
                    assistant_mode: 'patient',
                    temperature: 0.1,
                    model: selectedModel,
                    persist: false,
                })
            })
            if (!res.ok) throw new Error('Failed to check interactions')
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
    const latestVitalSourceLabel = vitals?.source === 'report' ? 'Latest uploaded report' : 'Latest charted'
    const recentReadingLabel = vitalsHistory.some(row => row?.source === 'report')
        ? `Last ${vitalsHistory.length} chart + report readings`
        : vitalsHistory.length > 1
            ? `Last ${vitalsHistory.length} readings`
            : 'Latest reading'
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
            pointMeta: vitalsHistory.map((row, index) => ({
                ...row,
                sort_order: Number.isFinite(row?.sort_order) ? row.sort_order : index,
            })),
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
            pointMeta: vitalsHistory.map((row, index) => ({
                ...row,
                sort_order: Number.isFinite(row?.sort_order) ? row.sort_order : index,
            })),
            lowerBound: 90,
            upperBound: 140,
            referenceText: 'Trend shows systolic blood pressure. Latest reading includes diastolic pressure.',
            tooltipValueFormatter: (value) => `${Math.round(value)} mmHg systolic`,
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
            pointMeta: vitalsHistory.map((row, index) => ({
                ...row,
                sort_order: Number.isFinite(row?.sort_order) ? row.sort_order : index,
            })),
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
            pointMeta: vitalsHistory.map((row, index) => ({
                ...row,
                sort_order: Number.isFinite(row?.sort_order) ? row.sort_order : index,
            })),
            lowerBound: 97,
            upperBound: 99,
            referenceText: 'Typical oral temperature: 97.0-99.0°F',
        },
    ].filter(chart => Number.isFinite(chart.value)) : []
    const sectionTabs = [
        { key: 'profile', label: 'Health Profile', icon: Stethoscope },
        { key: 'vitals', label: 'Vitals', icon: Heart },
        { key: 'medications', label: 'Medications', icon: Pill },
        { key: 'imaging', label: 'Imaging', icon: ImageIcon },
        { key: 'carePlan', label: 'Care Plan', icon: ClipboardList },
    ]
    const assistantPrompts = [
        'Give me an overview of my health record.',
        'What are the key things in my medical history?',
        'Are there any concerning trends in my health data?',
    ]
    const activePatientId = patientData?.patient_id || selectedPatient || null
    const profileFacts = [
        { label: 'Patient ID', value: patientData?.patient_id || selectedPatient || 'Unknown' },
        { label: 'Active conditions', value: diagnoses?.length ? `${diagnoses.length}` : '0' },
        { label: 'Medications', value: medications?.length ? `${medications.length}` : '0' },
        { label: 'Latest update', value: formatRecordedAt(latestVitalsRecordedAt) },
    ]
    const carePlanVitalsPoints = toSentenceList(patientSummary?.vitals_explanation, { maxItems: 6 })
    const fallbackVitalsPoints = parseStructuredSummaryString(patientSummary?.vitals_explanation)
    const carePlanMedicationPoints = toSentenceList(patientSummary?.medications_explanation, {
        splitSemicolons: true,
        maxItems: 8,
    })
    const fallbackMedicationPoints = parseStructuredSummaryString(patientSummary?.medications_explanation)
    const carePlanSteps = normalizeCarePlanSteps(patientSummary?.next_steps)
    const carePlanHighlights = [
        {
            label: 'Focus areas',
            value: `${Math.max(carePlanVitalsPoints.length, 1)} clinical notes`,
            tone: 'emerald',
        },
        {
            label: 'Medication items',
            value: `${medications?.length || carePlanMedicationPoints.length || 0} on file`,
            tone: 'blue',
        },
        {
            label: 'Next steps',
            value: `${carePlanSteps.length || 0} recommended`,
            tone: 'amber',
        },
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
                        <div className="pp-settings">
                            <button
                                type="button"
                                className="pp-settings__button"
                                onClick={() => setSettingsOpen(prev => !prev)}
                                aria-expanded={settingsOpen}
                                aria-label="Open patient assistant settings"
                            >
                                <SlidersHorizontal size={16} />
                                Settings
                            </button>
                            {settingsOpen && (
                                <div className="pp-settings__popover">
                                    <label className="pp-settings__field">
                                        <span>Text Model</span>
                                        <select
                                            value={selectedModel}
                                            onChange={e => setSelectedModel(e.target.value)}
                                            disabled={chatLoading}
                                        >
                                            {AVAILABLE_TEXT_MODELS.map(model => (
                                                <option key={model.id} value={model.id}>{model.label}</option>
                                            ))}
                                        </select>
                                    </label>
                                </div>
                            )}
                        </div>
                        {loading && <Loader2 size={18} className="pp-spin" style={{ color: 'var(--pp-green)' }} />}
                    </div>

                    {!patientData ? (
                        <div className="pp-welcome">
                            <div className="pp-welcome__icon-ring">
                                <FileHeart size={48} />
                            </div>
                            <h2 className="pp-welcome__title">
                                {loadError ? 'Unable to load patient profile' : 'Welcome to your Patient Portal'}
                            </h2>
                            <p className="pp-welcome__desc">
                                {loadError
                                    ? loadError
                                    : 'Select a patient profile above to view your health record, vitals, medications, and personalized care plan.'}
                            </p>
                            {!loadError && (
                                <div className="pp-welcome__features">
                                    <div className="pp-welcome__feature">
                                        <Heart size={18} />
                                        <span>Vital Signs & Trends</span>
                                    </div>
                                    <div className="pp-welcome__feature">
                                        <Pill size={18} />
                                        <span>Medication Safety</span>
                                    </div>
                                    <div className="pp-welcome__feature">
                                        <ClipboardList size={18} />
                                        <span>Care Plan</span>
                                    </div>
                                    <div className="pp-welcome__feature">
                                        <MessageCircle size={18} />
                                        <span>AI Assistant</span>
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : (
                        <>
                            <div className="pp-page-hero pp-page-hero--v2">
                                <div className="pp-hero-left">
                                    <div className="pp-hero-avatar-row">
                                        <div className="pp-hero-avatar">
                                            <User size={28} />
                                        </div>
                                        <div>
                                            <div className="pp-page-kicker">Patient Portal</div>
                                            <h1 className="pp-page-title">My Health</h1>
                                        </div>
                                    </div>
                                    <p className="pp-page-subtitle">
                                        {patientSummary?.summary || 'A patient-friendly view of your current chart data and recent trends.'}
                                    </p>
                                </div>
                                <div className="pp-page-badges pp-page-badges--v2">
                                    <div className="pp-page-badge pp-page-badge--accent">
                                        <div className="pp-page-badge__icon"><User size={16} /></div>
                                        <div>
                                            <span className="pp-page-badge__label">Patient ID</span>
                                            <span className="pp-page-badge__value">{patientData?.patient_id || selectedPatient || 'Unknown'}</span>
                                        </div>
                                    </div>
                                    <div className="pp-page-badge pp-page-badge--red">
                                        <div className="pp-page-badge__icon"><AlertTriangle size={16} /></div>
                                        <div>
                                            <span className="pp-page-badge__label">Active Conditions</span>
                                            <span className="pp-page-badge__value">{diagnoses?.length || 0}</span>
                                        </div>
                                    </div>
                                    <div className="pp-page-badge pp-page-badge--blue">
                                        <div className="pp-page-badge__icon"><Pill size={16} /></div>
                                        <div>
                                            <span className="pp-page-badge__label">Medications</span>
                                            <span className="pp-page-badge__value">{medications?.length || 0}</span>
                                        </div>
                                    </div>
                                    <div className="pp-page-badge pp-page-badge--green">
                                        <div className="pp-page-badge__icon"><Calendar size={16} /></div>
                                        <div>
                                            <span className="pp-page-badge__label">Latest Update</span>
                                            <span className="pp-page-badge__value">{formatRecordedAt(latestVitalsRecordedAt)}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="pp-section-tabs pp-section-tabs--v2">
                                {sectionTabs.map(tab => {
                                    const TabIcon = tab.icon
                                    return (
                                        <button
                                            key={tab.key}
                                            className={`pp-section-tab pp-section-tab--v2 ${activeSection === tab.key ? 'pp-section-tab--active' : ''}`}
                                            onClick={() => setActiveSection(tab.key)}
                                            type="button"
                                        >
                                            <TabIcon size={15} />
                                            {tab.label}
                                        </button>
                                    )
                                })}
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
                                                    <span className="pp-vitals-meta__stamp">{latestVitalSourceLabel} {formatRecordedAt(latestVitalsRecordedAt)}</span>
                                                    <span className="pp-vitals-meta__window">{recentReadingLabel}</span>
                                                </div>

                                                {/* Quick-glance vitals summary cards */}
                                                <div className="pp-vitals-summary-grid">
                                                    {vitalsTrendCharts.map(chart => {
                                                        const VIcon = VITAL_ICONS[chart.key] || Heart
                                                        const SIcon = VITAL_STATUS_ICON[chart.statusTone] || Minus
                                                        const color = VITAL_STATUS_COLORS[chart.statusTone]
                                                        return (
                                                            <div key={chart.key} className={`pp-vital-summary pp-vital-summary--${chart.statusTone}`}>
                                                                <div className="pp-vital-summary__top">
                                                                    <div className="pp-vital-summary__icon" style={{ background: `${color}12`, color }}>
                                                                        <VIcon size={18} />
                                                                    </div>
                                                                    <div className={`pp-vital-summary__badge pp-vital-summary__badge--${chart.statusTone}`}>
                                                                        <SIcon size={10} />
                                                                        {VITAL_STATUS_LABELS[chart.statusTone]}
                                                                    </div>
                                                                </div>
                                                                <div className="pp-vital-summary__value">{chart.valueText}</div>
                                                                <div className="pp-vital-summary__label">{chart.title}</div>
                                                            </div>
                                                        )
                                                    })}
                                                    {vitals.respiratory_rate != null && (
                                                        <div className={`pp-vital-summary pp-vital-summary--${vitalStatus('respiratory_rate', vitals.respiratory_rate)}`}>
                                                            <div className="pp-vital-summary__top">
                                                                <div className="pp-vital-summary__icon" style={{ background: `${VITAL_STATUS_COLORS[vitalStatus('respiratory_rate', vitals.respiratory_rate)]}12`, color: VITAL_STATUS_COLORS[vitalStatus('respiratory_rate', vitals.respiratory_rate)] }}>
                                                                    <Wind size={18} />
                                                                </div>
                                                                <div className={`pp-vital-summary__badge pp-vital-summary__badge--${vitalStatus('respiratory_rate', vitals.respiratory_rate)}`}>
                                                                    {VITAL_STATUS_LABELS[vitalStatus('respiratory_rate', vitals.respiratory_rate)]}
                                                                </div>
                                                            </div>
                                                            <div className="pp-vital-summary__value">{Math.round(vitals.respiratory_rate)}/min</div>
                                                            <div className="pp-vital-summary__label">Respiratory Rate</div>
                                                        </div>
                                                    )}
                                                </div>

                                                {/* Detailed trend charts */}
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
                                                            pointMeta={chart.pointMeta}
                                                            lowerBound={chart.lowerBound}
                                                            upperBound={chart.upperBound}
                                                            pointColor={VITAL_STATUS_COLORS[chart.statusTone]}
                                                            tooltipValueFormatter={chart.tooltipValueFormatter}
                                                        />
                                                    ))}
                                                </div>
                                                <div className="pp-vitals-footnote">
                                                    {latestVitalsRecordedAt && (
                                                        <div className="pp-vitals-footnote__item">
                                                            <Clock size={14} />
                                                            <span>{vitalsHistory.some(row => row?.source === 'report') ? 'Trends combine chart readings and uploaded report values' : 'Trends reflect recent bedside charting'}</span>
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
                                            <>
                                                <div className="pp-med-count">
                                                    <Pill size={14} />
                                                    <span>{medications.length} active medication{medications.length !== 1 ? 's' : ''}</span>
                                                </div>
                                                <div className="pp-med-grid">
                                                    {medications.map((m, i) => (
                                                        <div key={i} className="pp-med-card">
                                                            <div className="pp-med-card__header">
                                                                <div className="pp-med-card__icon">
                                                                    <Pill size={16} />
                                                                </div>
                                                                <div className="pp-med-card__title">{m.name}</div>
                                                            </div>
                                                            <div className="pp-med-card__desc">{m.description || 'Prescribed by your care team'}</div>
                                                            <button
                                                                className="pp-med-card__check"
                                                                onClick={() => checkInteraction(m.name)}
                                                                disabled={checkingMed === m.name}
                                                            >
                                                                {checkingMed === m.name ? (
                                                                    <><Loader2 size={12} className="pp-spin" /> Checking…</>
                                                                ) : (
                                                                    <><Shield size={12} /> Safety Check</>
                                                                )}
                                                            </button>
                                                        </div>
                                                    ))}
                                                </div>
                                                {interactionResult && (
                                                    <div className="pp-inline-result pp-inline-result--v2">
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
                                            </>
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
                                        <div className="pp-imaging-workspace">
                                            <div className="pp-imaging-uploader">
                                                <div className="pp-imaging-uploader__copy">
                                                    <span className="pp-imaging-uploader__eyebrow">Imaging Library</span>
                                                    <h3>See what your care team shared and add new reports.</h3>
                                                    <p>Upload a scan image or a PDF report to keep everything in one place for your next visit.</p>
                                                </div>
                                                <button
                                                    type="button"
                                                    className="pp-imaging-uploader__button"
                                                    onClick={() => attachmentInputRef.current?.click()}
                                                    disabled={attachmentUploading || !activePatientId}
                                                >
                                                    {attachmentUploading ? (
                                                        <><Loader2 size={14} className="pp-spin" /> Uploading…</>
                                                    ) : (
                                                        <><Upload size={14} /> Upload report</>
                                                    )}
                                                </button>
                                                <input
                                                    ref={attachmentInputRef}
                                                    type="file"
                                                    accept="image/*,application/pdf"
                                                    hidden
                                                    onChange={handlePatientAttachmentSelect}
                                                />
                                            </div>

                                            {attachmentUploadError && (
                                                <div className="pp-imaging-feedback pp-imaging-feedback--error">
                                                    <AlertTriangle size={14} />
                                                    <span>{attachmentUploadError}</span>
                                                </div>
                                            )}

                                            {attachmentsError && (
                                                <div className="pp-imaging-feedback pp-imaging-feedback--error">
                                                    <AlertTriangle size={14} />
                                                    <span>{attachmentsError}</span>
                                                </div>
                                            )}

                                            {imagingResults?.length > 0 && (
                                                <>
                                                    <div className="pp-imaging-section-label">Clinical summary</div>
                                                    <div className="pp-imaging-grid">
                                                        {imagingResults.map((r, i) => {
                                                            const statusConfig = {
                                                                normal: { icon: CheckCircle2, color: '#16A34A', bg: '#F0FDF4', label: 'Normal' },
                                                                attention: { icon: AlertTriangle, color: '#D97706', bg: '#FFFBEB', label: 'Needs Review' },
                                                                abnormal: { icon: AlertTriangle, color: '#DC2626', bg: '#FEF2F2', label: 'Abnormal' },
                                                            }
                                                            const cfg = statusConfig[r.status] || statusConfig.normal
                                                            const StatusIcon = cfg.icon
                                                            return (
                                                                <div key={i} className={`pp-imaging-card pp-imaging-card--${r.status}`}>
                                                                    <div className="pp-imaging-card__icon" style={{ background: cfg.bg, color: cfg.color }}>
                                                                        <Scan size={20} />
                                                                    </div>
                                                                    <div className="pp-imaging-card__body">
                                                                        <div className="pp-imaging-card__title">{r.label}</div>
                                                                        <div className="pp-imaging-card__desc">
                                                                            {r.status === 'normal' ? 'Your recent imaging looks good.' :
                                                                                r.status === 'attention' ? 'Your doctor will discuss this finding with you.' :
                                                                                    'Your care team is reviewing this result carefully.'}
                                                                        </div>
                                                                    </div>
                                                                    <div className={`pp-imaging-card__status pp-imaging-card__status--${r.status}`}>
                                                                        <StatusIcon size={12} />
                                                                        {cfg.label}
                                                                    </div>
                                                                </div>
                                                            )
                                                        })}
                                                    </div>
                                                </>
                                            )}

                                            <div className="pp-imaging-section-label">Files in your record</div>
                                            {attachmentsLoading ? (
                                                <div className="pp-empty">
                                                    <Loader2 size={24} className="pp-spin" />
                                                    <p>Loading your imaging files…</p>
                                                </div>
                                            ) : attachments.length > 0 ? (
                                                <div className="pp-attachment-list">
                                                    {attachments.map(attachment => {
                                                        const source = getAttachmentSourceMeta(attachment.uploaded_by)
                                                        const isPdf = attachment.file_kind === 'pdf'
                                                        const processingMeta = getAttachmentProcessingMeta(attachment)

                                                        return (
                                                            <div key={attachment.id} className="pp-attachment-card">
                                                                <div className={`pp-attachment-card__preview pp-attachment-card__preview--${attachment.file_kind}`}>
                                                                    {attachment.file_kind === 'image' ? (
                                                                        <img
                                                                            src={attachment.url}
                                                                            alt={attachment.title || attachment.original_filename}
                                                                        />
                                                                    ) : (
                                                                        <FileText size={22} />
                                                                    )}
                                                                </div>
                                                                <div className="pp-attachment-card__body">
                                                                    <div className="pp-attachment-card__badges">
                                                                        <span className={`pp-attachment-card__source pp-attachment-card__source--${source.tone}`}>
                                                                            {source.label}
                                                                        </span>
                                                                        <span className="pp-attachment-card__type">
                                                                            {getAttachmentTypeLabel(attachment)}
                                                                        </span>
                                                                        {processingMeta && (
                                                                            <span className={`pp-attachment-card__type pp-attachment-card__type--${processingMeta.tone}`}>
                                                                                {processingMeta.label}
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                    <div className="pp-attachment-card__title">
                                                                        {attachment.title || attachment.original_filename}
                                                                    </div>
                                                                    <div className="pp-attachment-card__filename">
                                                                        {attachment.original_filename}
                                                                    </div>
                                                                    <div className="pp-attachment-card__meta">
                                                                        Added {formatAttachmentDate(attachment.uploaded_at)}
                                                                    </div>
                                                                    {attachment.summary_preview && (
                                                                        <div className="pp-attachment-card__meta">
                                                                            {attachment.summary_preview}
                                                                        </div>
                                                                    )}
                                                                    {attachment.extraction_error && attachment.processing_status === 'failed' && (
                                                                        <div className="pp-attachment-card__meta">
                                                                            {attachment.extraction_error}
                                                                        </div>
                                                                    )}
                                                                </div>
                                                                <div className="pp-attachment-card__actions">
                                                                    <a
                                                                        className="pp-attachment-card__action"
                                                                        href={attachment.url}
                                                                        target="_blank"
                                                                        rel="noreferrer"
                                                                    >
                                                                        <ArrowUpRight size={13} />
                                                                        {isPdf ? 'Open PDF' : 'View image'}
                                                                    </a>
                                                                    {isPdf && (
                                                                        <a
                                                                            className="pp-attachment-card__action pp-attachment-card__action--ghost"
                                                                            href={attachment.url}
                                                                            download={attachment.original_filename}
                                                                        >
                                                                            <Download size={13} />
                                                                            Download
                                                                        </a>
                                                                    )}
                                                                </div>
                                                            </div>
                                                        )
                                                    })}
                                                </div>
                                            ) : (
                                                <div className="pp-empty">
                                                    <Scan size={24} />
                                                    <p>No imaging files or reports have been added yet. Upload one here or wait for your care team to share results.</p>
                                                </div>
                                            )}
                                        </div>
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
                                            <div className="pp-care-plan pp-care-plan--v3">
                                                <div className="pp-care-hero">
                                                    <div className="pp-care-hero__summary">
                                                        <div className="pp-care-summary__icon">
                                                            <FileHeart size={20} />
                                                        </div>
                                                        <div className="pp-care-hero__copy">
                                                            <div className="pp-care-hero__eyebrow">Today&apos;s Snapshot</div>
                                                            <div className="pp-care-summary__text">{patientSummary.summary}</div>
                                                        </div>
                                                    </div>
                                                    <div className="pp-care-hero__highlights">
                                                        {carePlanHighlights.map(item => (
                                                            <div key={item.label} className={`pp-care-highlight pp-care-highlight--${item.tone}`}>
                                                                <span>{item.label}</span>
                                                                <strong>{item.value}</strong>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>

                                                <div className="pp-care-columns">
                                                    <div className="pp-care-explainer pp-care-explainer--v3">
                                                        <div className="pp-care-explainer__head">
                                                            <div className="pp-care-explainer__icon" style={{ background: '#FEF2F2', color: '#DC2626' }}>
                                                                <Heart size={16} />
                                                            </div>
                                                            <div>
                                                                <div className="pp-care-explainer__title">Vitals Overview</div>
                                                                <div className="pp-care-explainer__lede">A clearer explanation of what your recent vital signs may mean.</div>
                                                            </div>
                                                        </div>
                                                        <div className="pp-care-explainer__body">
                                                            {carePlanVitalsPoints.length > 0 || fallbackVitalsPoints.length > 0 ? (
                                                                <ul className="pp-care-bullets">
                                                                    {(carePlanVitalsPoints.length > 0 ? carePlanVitalsPoints : fallbackVitalsPoints).map((point, index) => (
                                                                        <li key={`${point}-${index}`}>{point}</li>
                                                                    ))}
                                                                </ul>
                                                            ) : (
                                                                patientSummary.vitals_explanation
                                                            )}
                                                        </div>
                                                    </div>

                                                    <div className="pp-care-explainer pp-care-explainer--v3">
                                                        <div className="pp-care-explainer__head">
                                                            <div className="pp-care-explainer__icon" style={{ background: '#EFF6FF', color: '#2563EB' }}>
                                                                <Pill size={16} />
                                                            </div>
                                                            <div>
                                                                <div className="pp-care-explainer__title">Medications Overview</div>
                                                                <div className="pp-care-explainer__lede">Your charted medicines, translated into plain language.</div>
                                                            </div>
                                                        </div>
                                                        <div className="pp-care-explainer__body">
                                                            {carePlanMedicationPoints.length > 0 || fallbackMedicationPoints.length > 0 ? (
                                                                <ul className="pp-care-bullets pp-care-bullets--dense">
                                                                    {(carePlanMedicationPoints.length > 0 ? carePlanMedicationPoints : fallbackMedicationPoints).map((point, index) => (
                                                                        <li key={`${point}-${index}`}>{point}</li>
                                                                    ))}
                                                                </ul>
                                                            ) : (
                                                                patientSummary.medications_explanation
                                                            )}
                                                        </div>
                                                    </div>
                                                </div>

                                                {carePlanSteps.length > 0 && (
                                                    <div className="pp-care-steps pp-care-steps--v3">
                                                        <div className="pp-care-steps__header">
                                                            <div>
                                                                <div className="pp-care-steps__title">Recommended Next Steps</div>
                                                                <div className="pp-care-steps__subtitle">Use these as conversation prompts for your next visit, not as stand-alone medical advice.</div>
                                                            </div>
                                                        </div>
                                                        <div className="pp-care-steps__list pp-care-steps__list--v3">
                                                            {carePlanSteps.map((step, index) => {
                                                                const meta = getCareStepMeta(step, index)
                                                                return (
                                                                    <div key={`${step}-${index}`} className={`pp-care-step pp-care-step--${meta.tone}`}>
                                                                        <div className="pp-care-step__number">{index + 1}</div>
                                                                        <div className="pp-care-step__content">
                                                                            <div className="pp-care-step__label">{meta.label}</div>
                                                                            <div className="pp-care-step__text">{step}</div>
                                                                        </div>
                                                                    </div>
                                                                )
                                                            })}
                                                        </div>
                                                    </div>
                                                )}
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
                            <div className="pp-assistant__header-copy">
                                <div className="pp-assistant__title">Synapse AI</div>
                                <div className="pp-assistant__subtitle">Ask about your health record</div>
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
                                        <p>Ask about your chart, medications, vitals, imaging, or care plan.</p>
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
                                    <div className="pp-chat__messages" ref={patientChatMessagesRef}>
                                        <SelectionExplainToolbar enabled containerRef={patientChatMessagesRef} />
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
                                placeholder={patientData ? `Ask about Patient ${activePatientId}…` : 'Select a patient profile to begin…'}
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
