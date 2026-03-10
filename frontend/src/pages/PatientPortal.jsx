import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import {
    Heart, Thermometer, Wind, Droplets, Activity,
    Pill, Stethoscope, Send, Loader2, Image as ImageIcon,
    Calendar, ClipboardList, Shield, AlertTriangle, CheckCircle2,
    Clock, FileHeart, MessageCircle, Smile
} from 'lucide-react'
import MedicalTermHighlighter, { MarkdownWithHighlight } from '../components/MedicalTermHighlighter'
import SafeMarkdownWrapper from '../components/SafeMarkdownWrapper'
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

// Strip wrapping quotes from LLM responses
const cleanContent = (text) => {
    if (!text) return ''
    let t = text.trim()
    if (t.startsWith('"') && t.endsWith('"')) t = t.slice(1, -1)
    return t
}

export default function PatientPortal() {
    const [selectedPatient, setSelectedPatient] = useState('')
    const [patientData, setPatientData] = useState(null)
    const [loading, setLoading] = useState(false)

    // Chat state
    const [chatMessages, setChatMessages] = useState([])
    const [chatInput, setChatInput] = useState('')
    const [chatLoading, setChatLoading] = useState(false)
    const [sessionId, setSessionId] = useState(null)
    const chatEndRef = useRef(null)

    // Interaction check
    const [checkingMed, setCheckingMed] = useState(null)
    const [interactionResult, setInteractionResult] = useState(null)

    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [chatMessages])

    // ── Load patient data ────────────────────────────────────────────
    const loadPatient = async (patId) => {
        if (!patId) { setPatientData(null); return }
        setLoading(true)
        try {
            const res = await fetch(`${API_BASE}/patient/${patId}`)
            if (res.ok) setPatientData(await res.json())
        } catch (err) { console.error('Failed to load patient:', err) }
        finally { setLoading(false) }
    }

    // ── Chat (with plain-language wrapper) ───────────────────────────
    const sendChat = async (e) => {
        e?.preventDefault()
        if (!chatInput.trim() || chatLoading) return

        let sid = sessionId
        if (!sid) {
            try {
                const res = await fetch(`${API_BASE}/sessions/new?source=patient`, { method: 'POST' })
                const data = await res.json()
                sid = data.id
                setSessionId(data.id)
            } catch { return }
        }

        const userMsg = chatInput
        setChatMessages(prev => [...prev, { role: 'user', content: userMsg }])
        setChatInput('')
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

        const wrappedMessage = `[PATIENT PORTAL] The patient is asking: "${userMsg}"${patientContext}\n\nPlease explain in plain language at an 8th-grade reading level. Avoid medical jargon. Be warm and reassuring. Use short sentences and bullet points. Answer specifically about this patient's data when relevant.`

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

            const reader = res.body.getReader()
            const decoder = new TextDecoder()
            let added = false

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                for (const line of decoder.decode(value, { stream: true }).split('\n')) {
                    if (!line.startsWith('data: ')) continue
                    try {
                        const event = JSON.parse(line.slice(6).trim())
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
                    } catch { /* skip */ }
                }
            }
        } catch {
            setChatMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }])
        } finally { setChatLoading(false) }
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
                })
            })
            const reader = res.body.getReader()
            const decoder = new TextDecoder()
            let result = ''
            while (true) {
                const { done, value } = await reader.read()
                if (done) break
                for (const line of decoder.decode(value, { stream: true }).split('\n')) {
                    if (!line.startsWith('data: ')) continue
                    try {
                        const event = JSON.parse(line.slice(6).trim())
                        if (event.type === 'token') result += event.content
                        else if (event.type === 'done' && event.final_response) result = event.final_response
                    } catch { /* skip */ }
                }
            }
            setInteractionResult(result || 'No significant interactions found.')
        } catch { setInteractionResult('Unable to check interactions right now.') }
        finally { setCheckingMed(null) }
    }

    // ── Parse imaging results from last assistant message ────────────
    const getImagingResults = () => {
        const lastAssistant = [...chatMessages].reverse().find(m => m.role === 'assistant')
        if (!lastAssistant) return null
        const content = lastAssistant.content.toLowerCase()
        if (!content.includes('x-ray') && !content.includes('chest') && !content.includes('scan') && !content.includes('radiograph')) return null

        const results = []
        const checks = [
            { keywords: ['no abnormal', 'normal', 'clear', 'unremarkable', 'no significant'], status: 'normal', label: 'Normal' },
            { keywords: ['opacity', 'infiltrate', 'consolidation', 'effusion', 'edema'], status: 'attention', label: 'Needs Attention' },
            { keywords: ['mass', 'nodule', 'tumor', 'pneumothorax', 'fracture'], status: 'flagged', label: 'Flagged for Review' },
        ]

        for (const check of checks) {
            if (check.keywords.some(kw => content.includes(kw))) {
                results.push({ status: check.status, label: check.label })
            }
        }
        return results.length > 0 ? results : [{ status: 'normal', label: 'Awaiting Analysis' }]
    }

    const imagingResults = getImagingResults()
    const { vitals, diagnoses, medications } = patientData || {}

    return (
        <div className="pp">
            {/* Patient selector */}
            <div className="pp-patient-bar">
                <Smile size={18} style={{ color: 'var(--pp-green)' }} />
                <label>My Account:</label>
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
                <div className="pp-empty" style={{ padding: '4rem 1rem' }}>
                    <FileHeart size={48} style={{ color: 'var(--pp-text-muted)' }} />
                    <p style={{ fontSize: '1.1rem', marginTop: '1rem' }}>
                        Welcome to your Patient Portal 👋
                    </p>
                    <p>Select your profile above to view your health information.</p>
                </div>
            ) : (
                <div className="pp-grid">

                    {/* ═══ 1. MY HEALTH SUMMARY ═══ */}
                    <div className="pp-card">
                        <div className="pp-card__header">
                            <div className="pp-card__icon pp-card__icon--green"><Stethoscope size={18} /></div>
                            <span className="pp-card__title">My Health Summary</span>
                        </div>
                        <div className="pp-card__body">
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

                    {/* ═══ 2. MY VITALS ═══ */}
                    <div className="pp-card">
                        <div className="pp-card__header">
                            <div className="pp-card__icon pp-card__icon--red"><Heart size={18} /></div>
                            <span className="pp-card__title">My Vitals</span>
                        </div>
                        <div className="pp-card__body">
                            {vitals ? (
                                <div className="pp-vitals-grid">
                                    {vitals.heart_rate != null && (
                                        <div className={`pp-vital pp-vital--${vitalStatus('heart_rate', vitals.heart_rate)}`}>
                                            <div className="pp-vital__icon"><Heart size={20} /></div>
                                            <div className="pp-vital__value">{Math.round(vitals.heart_rate)}<span className="pp-vital__unit"> bpm</span></div>
                                            <div className="pp-vital__label">Heart Rate</div>
                                        </div>
                                    )}
                                    {vitals.systolic_bp != null && (
                                        <div className={`pp-vital pp-vital--${vitalStatus('bp', null, vitals)}`}>
                                            <div className="pp-vital__icon"><Activity size={20} /></div>
                                            <div className="pp-vital__value">{Math.round(vitals.systolic_bp)}/{Math.round(vitals.diastolic_bp)}</div>
                                            <div className="pp-vital__label">Blood Pressure</div>
                                        </div>
                                    )}
                                    {vitals.o2_saturation != null && (
                                        <div className={`pp-vital pp-vital--${vitalStatus('o2_saturation', vitals.o2_saturation)}`}>
                                            <div className="pp-vital__icon"><Droplets size={20} /></div>
                                            <div className="pp-vital__value">{Math.round(vitals.o2_saturation)}<span className="pp-vital__unit">%</span></div>
                                            <div className="pp-vital__label">Oxygen Level</div>
                                        </div>
                                    )}
                                    {vitals.temperature != null && (
                                        <div className={`pp-vital pp-vital--${vitalStatus('temperature', vitals.temperature)}`}>
                                            <div className="pp-vital__icon"><Thermometer size={20} /></div>
                                            <div className="pp-vital__value">{vitals.temperature.toFixed(1)}<span className="pp-vital__unit">°F</span></div>
                                            <div className="pp-vital__label">Temperature</div>
                                        </div>
                                    )}
                                    {vitals.respiratory_rate != null && (
                                        <div className={`pp-vital pp-vital--${vitalStatus('respiratory_rate', vitals.respiratory_rate)}`}>
                                            <div className="pp-vital__icon"><Wind size={20} /></div>
                                            <div className="pp-vital__value">{Math.round(vitals.respiratory_rate)}<span className="pp-vital__unit">/min</span></div>
                                            <div className="pp-vital__label">Breathing Rate</div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="pp-empty"><p>No vitals recorded yet.</p></div>
                            )}
                        </div>
                    </div>

                    {/* ═══ 3. MY MEDICATIONS ═══ */}
                    <div className="pp-card">
                        <div className="pp-card__header">
                            <div className="pp-card__icon pp-card__icon--blue"><Pill size={18} /></div>
                            <span className="pp-card__title">My Medications</span>
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
                                        <div style={{
                                            marginTop: '0.5rem', padding: '0.75rem', borderRadius: '10px',
                                            background: 'var(--pp-blue-light)', border: '1px solid rgba(59,130,246,0.2)',
                                            fontSize: '0.85rem', lineHeight: '1.5'
                                        }}>
                                            <strong style={{ color: 'var(--pp-blue)' }}>
                                                <Shield size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
                                                Interaction Check Result:
                                            </strong>
                                            <div style={{ marginTop: '0.4rem' }}>
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
                    </div>

                    {/* ═══ 4. MY IMAGING RESULTS ═══ */}
                    <div className="pp-card">
                        <div className="pp-card__header">
                            <div className="pp-card__icon pp-card__icon--purple"><ImageIcon size={18} /></div>
                            <span className="pp-card__title">My Imaging Results</span>
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
                                            {r.status === 'normal' ? 'Your recent imaging looks good!' :
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
                    </div>

                    {/* ═══ 5. ASK A QUESTION ═══ */}
                    <div className="pp-card pp-full">
                        <div className="pp-card__header">
                            <div className="pp-card__icon pp-card__icon--green"><MessageCircle size={18} /></div>
                            <span className="pp-card__title">Ask a Question</span>
                        </div>
                        <div className="pp-card__body">
                            <div className="pp-chat">
                                <div className="pp-chat__messages">
                                    {chatMessages.length === 0 && (
                                        <div className="pp-empty">
                                            <p>👋 Hi! Ask me anything about your health, medications, or test results.</p>
                                            <p style={{ fontSize: '0.8rem' }}>I'll explain everything in simple language.</p>
                                        </div>
                                    )}
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
                                <form className="pp-chat__input-row" onSubmit={sendChat}>
                                    <input
                                        className="pp-chat__input"
                                        value={chatInput}
                                        onChange={e => setChatInput(e.target.value)}
                                        placeholder="What would you like to know? e.g. 'What is my blood pressure medication for?'"
                                        disabled={chatLoading}
                                    />
                                    <button className="pp-chat__send" type="submit" disabled={!chatInput.trim() || chatLoading}>
                                        {chatLoading ? <Loader2 size={18} className="pp-spin" /> : <Send size={18} />}
                                    </button>
                                </form>
                            </div>
                        </div>
                    </div>

                    {/* ═══ 6. MY CARE PLAN ═══ */}
                    <div className="pp-card pp-full">
                        <div className="pp-card__header">
                            <div className="pp-card__icon pp-card__icon--yellow"><ClipboardList size={18} /></div>
                            <span className="pp-card__title">My Care Plan</span>
                        </div>
                        <div className="pp-card__body">
                            <div className="pp-care-list">
                                <div className="pp-care-item">
                                    <div className="pp-care-item__icon" style={{ background: 'var(--pp-green-light)', color: 'var(--pp-green)' }}>
                                        <Calendar size={16} />
                                    </div>
                                    <div className="pp-care-item__text">
                                        <div className="pp-care-item__title">Follow-Up Appointment</div>
                                        <div className="pp-care-item__detail">
                                            Schedule a follow-up with your primary care provider within 1-2 weeks to review your progress.
                                        </div>
                                    </div>
                                </div>

                                {medications && medications.length > 0 && (
                                    <div className="pp-care-item">
                                        <div className="pp-care-item__icon" style={{ background: 'var(--pp-blue-light)', color: 'var(--pp-blue)' }}>
                                            <Clock size={16} />
                                        </div>
                                        <div className="pp-care-item__text">
                                            <div className="pp-care-item__title">Medication Schedule</div>
                                            <div className="pp-care-item__detail">
                                                Take your {medications.length} prescribed medication{medications.length > 1 ? 's' : ''} as directed.
                                                Don't skip doses — set phone reminders if needed.
                                                {medications.slice(0, 3).map(m => ` • ${m.name}`).join('')}
                                            </div>
                                        </div>
                                    </div>
                                )}

                                <div className="pp-care-item">
                                    <div className="pp-care-item__icon" style={{ background: 'var(--pp-purple-light)', color: 'var(--pp-purple)' }}>
                                        <Activity size={16} />
                                    </div>
                                    <div className="pp-care-item__text">
                                        <div className="pp-care-item__title">Monitor Your Health</div>
                                        <div className="pp-care-item__detail">
                                            Watch for changes in symptoms. If you feel worse, have trouble breathing, or develop a fever, contact your care team right away.
                                        </div>
                                    </div>
                                </div>

                                <div className="pp-care-item">
                                    <div className="pp-care-item__icon" style={{ background: 'var(--pp-yellow-light)', color: 'var(--pp-yellow)' }}>
                                        <Heart size={16} />
                                    </div>
                                    <div className="pp-care-item__text">
                                        <div className="pp-care-item__title">Wellness Tips</div>
                                        <div className="pp-care-item__detail">
                                            Stay hydrated, get adequate rest, eat balanced meals, and take short walks as tolerated. These small steps support your recovery.
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                </div>
            )}
        </div>
    )
}
