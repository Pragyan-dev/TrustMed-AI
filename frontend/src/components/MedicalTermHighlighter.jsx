import { useState, useRef, useEffect, useCallback } from 'react'
import { BookOpen, X, Loader2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

const API_BASE = '/api'

// ── Client-side explanation cache (shared across all instances) ─────────
const _explanationCache = {}

// ── Known medical terms + Latin/Greek root patterns ────────────────────
const MEDICAL_TERMS = new Set([
    // Conditions
    'pneumonia', 'sepsis', 'tachycardia', 'bradycardia', 'hypertension',
    'hypotension', 'atrial fibrillation', 'arrhythmia', 'edema', 'effusion',
    'embolism', 'thrombosis', 'stenosis', 'ischemia', 'infarction',
    'cardiomyopathy', 'anemia', 'leukocytosis', 'thrombocytopenia',
    'hypoxia', 'hypoxemia', 'acidosis', 'alkalosis', 'dyspnea', 'apnea',
    'cyanosis', 'hepatitis', 'cirrhosis', 'nephropathy', 'neuropathy',
    'encephalopathy', 'meningitis', 'cellulitis', 'osteomyelitis',
    'endocarditis', 'pericarditis', 'pleurisy', 'bronchitis',
    'gastroenteritis', 'pancreatitis', 'cholecystitis', 'diverticulitis',
    'appendicitis', 'peritonitis', 'abscess', 'fibrosis', 'necrosis',
    'hemorrhage', 'hematoma', 'contusion', 'laceration', 'fracture',
    'dislocation', 'subluxation', 'scoliosis', 'lordosis', 'kyphosis',
    'atherosclerosis', 'aneurysm', 'varicose', 'lymphedema',
    'hypoglycemia', 'hyperglycemia', 'ketoacidosis', 'hypothyroidism',
    'hyperthyroidism', 'osteoporosis', 'osteoarthritis', 'rheumatoid',
    'lupus', 'sarcoidosis', 'amyloidosis', 'vasculitis',
    'pneumothorax', 'hemothorax', 'atelectasis', 'consolidation',
    'infiltrate', 'opacity', 'cardiomegaly', 'hepatomegaly',
    'splenomegaly', 'lymphadenopathy', 'ascites',
    'copd', 'asthma', 'emphysema',
    'hypercholesterolemia', 'dyslipidemia', 'hyperkalemia', 'hyponatremia',
    // Diagnostic
    'electrocardiogram', 'echocardiogram', 'angiography', 'biopsy',
    'spirometry', 'endoscopy', 'colonoscopy', 'bronchoscopy',
    'laparoscopy', 'thoracentesis', 'paracentesis', 'lumbar puncture',
    'ct scan', 'mri', 'ultrasound', 'radiograph',
    // Medications / treatments
    'anticoagulant', 'antibiotic', 'analgesic', 'antipyretic',
    'bronchodilator', 'diuretic', 'vasopressor', 'vasodilator',
    'corticosteroid', 'immunosuppressant', 'chemotherapy',
    'thrombolytic', 'antiarrhythmic', 'antiemetic', 'antihypertensive',
    'metformin', 'insulin', 'heparin', 'warfarin', 'aspirin',
    'amoxicillin', 'ciprofloxacin', 'metoprolol', 'lisinopril',
    'amlodipine', 'furosemide', 'omeprazole', 'prednisone',
    'albuterol', 'sumatriptan', 'gabapentin', 'sertraline',
    // Labs / vitals
    'hemoglobin', 'hematocrit', 'platelets', 'creatinine',
    'troponin', 'procalcitonin', 'lactate', 'albumin', 'bilirubin',
    'electrolytes', 'systolic', 'diastolic', 'tachypnea',
    'spo2', 'o2 saturation', 'bmi', 'gfr', 'lvad', 'ef', 'bnp', 'cbc', 'bmp',
    'intubation', 'extubation', 'ventilator', 'vasopressor', 'inotrope',
    'ejection fraction', 'd-dimer', 'lactic acid',
    // Anatomy
    'pleural', 'pericardial', 'peritoneal', 'mesenteric',
    'pulmonary', 'hepatic', 'renal', 'cerebral', 'cervical',
    'thoracic', 'lumbar', 'sacral', 'femoral', 'radial',
])

// Regex for Latin/Greek medical suffixes / technical-looking terms not in the list
const MEDICAL_PATTERN = /\b[A-Za-z]*(?:itis|osis|emia|uria|pathy|ectomy|otomy|ostomy|plasty|scopy|graphy|algia|dynia|megaly|penia|cytosis|trophy|plasia|genesis|lysis|stasis|philia|sclerosis|oma|plegia|paresis|asthenia|ology|scopic|genic|lytic|ectasia|ectasis|pnea|dipsia|phagia|stenotic|stolic|dystolic)\b/gi

/**
 * MedicalTermHighlighter
 *
 * Wraps text content and makes detected medical terms clickable.
 * On click, fetches a plain-English explanation from /api/explain-term.
 *
 * Props:
 *   text      – raw text to process
 *   enabled   – whether highlighting is active (default: true)
 *   children  – alternative: pass ReactMarkdown output (will process text nodes)
 */
export default function MedicalTermHighlighter({ text, enabled = true, children }) {
    const [activeTerm, setActiveTerm] = useState(null)
    const [explanation, setExplanation] = useState('')
    const [loading, setLoading] = useState(false)
    const [popoverPos, setPopoverPos] = useState({ top: 0, left: 0 })
    const popoverRef = useRef(null)

    // Close on outside click
    useEffect(() => {
        if (!activeTerm) return
        const handler = (e) => {
            if (popoverRef.current && !popoverRef.current.contains(e.target)) {
                setActiveTerm(null)
            }
        }
        document.addEventListener('mousedown', handler)
        return () => document.removeEventListener('mousedown', handler)
    }, [activeTerm])

    const fetchExplanation = useCallback(async (term, rect) => {
        const cacheKey = term.toLowerCase().trim()

        // Position popover
        setPopoverPos({
            top: rect.bottom + window.scrollY + 6,
            left: Math.min(rect.left + window.scrollX, window.innerWidth - 320),
        })
        setActiveTerm(term)

        if (_explanationCache[cacheKey]) {
            setExplanation(_explanationCache[cacheKey])
            setLoading(false)
            return
        }

        setLoading(true)
        setExplanation(null) // Clear previous

        try {
            const res = await fetch(`${API_BASE}/explain-term?term=${encodeURIComponent(term)}`)
            if (!res.ok) throw new Error('Explain request failed')
            const data = await res.json()

            const result = {
                text: data.explanation ?? '',
                note: data.clinician_note,
                source: data.source || 'Library'
            }

            _explanationCache[cacheKey] = result
            setExplanation(result)
        } catch {
            setExplanation({ text: 'Unable to load explanation right now.', source: 'Error' })
        } finally {
            setLoading(false)
        }
    }, [])

    const handleTermActivate = (e, term) => {
        e.preventDefault()
        e.stopPropagation()
        const rect = (e.currentTarget || e.target).getBoundingClientRect()
        if (activeTerm === term) {
            setActiveTerm(null)
        } else {
            fetchExplanation(term, rect)
        }
    }

    // ── Highlight terms in a string ──────────────────────────────────
    const highlightText = (str) => {
        if (!enabled || !str || typeof str !== 'string') return str

        // Collect all matches: known terms + regex pattern
        const matches = []

        // Check known terms (case-insensitive)
        for (const term of MEDICAL_TERMS) {
            const regex = new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'gi')
            let match
            while ((match = regex.exec(str)) !== null) {
                matches.push({ start: match.index, end: match.index + match[0].length, term: match[0] })
            }
        }

        // Check regex pattern for terms not already matched
        let regexMatch
        MEDICAL_PATTERN.lastIndex = 0
        while ((regexMatch = MEDICAL_PATTERN.exec(str)) !== null) {
            const overlap = matches.some(m =>
                (regexMatch.index >= m.start && regexMatch.index < m.end) ||
                (m.start >= regexMatch.index && m.start < regexMatch.index + regexMatch[0].length)
            )
            if (!overlap && regexMatch[0].length > 4) {
                matches.push({ start: regexMatch.index, end: regexMatch.index + regexMatch[0].length, term: regexMatch[0] })
            }
        }

        if (matches.length === 0) return str

        // Sort by position, remove overlaps
        matches.sort((a, b) => a.start - b.start)
        const deduped = [matches[0]]
        for (let i = 1; i < matches.length; i++) {
            if (matches[i].start >= deduped[deduped.length - 1].end) {
                deduped.push(matches[i])
            }
        }

        // Build JSX
        const parts = []
        let cursor = 0
        for (const m of deduped) {
            if (m.start > cursor) {
                parts.push(str.slice(cursor, m.start))
            }
            parts.push(
                <span
                    key={`${m.start}-${m.term}`}
                    className="mth-term"
                    onClick={(e) => handleTermActivate(e, m.term)}
                    onContextMenu={(e) => handleTermActivate(e, m.term)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            handleTermActivate(e, m.term)
                        }
                    }}
                    role="button"
                    tabIndex={0}
                    title="Right-click for medical dictionary explanation"
                >
                    {m.term}
                </span>
            )
            cursor = m.end
        }
        if (cursor < str.length) {
            parts.push(str.slice(cursor))
        }

        return parts
    }

    // ── Process React children recursively ───────────────────────────
    const processNode = (node) => {
        if (!enabled) return node
        if (typeof node === 'string') return highlightText(node)
        if (Array.isArray(node)) return node.map((child, i) => <span key={i}>{processNode(child)}</span>)
        if (node?.props?.children) {
            const Tag = node.type || 'span'
            // Don't recurse into code blocks
            if (Tag === 'code' || Tag === 'pre') return node
            return <Tag {...node.props}>{processNode(node.props.children)}</Tag>
        }
        return node
    }

    const content = children ? processNode(children) : highlightText(text || '')

    return (
        <span className="mth-wrapper">
            {content}

            {/* Popover */}
            {activeTerm && (
                <span
                    ref={popoverRef}
                    className="mth-popover"
                    style={{ top: popoverPos.top, left: popoverPos.left }}
                >
                    <span className="mth-popover__header">
                        <BookOpen size={14} />
                        <span className="mth-popover__term">{activeTerm}</span>
                        <span className="mth-popover__source">{explanation?.source || '...'}</span>
                        <button type="button" className="mth-popover__close" onClick={() => setActiveTerm(null)}>
                            <X size={12} />
                        </button>
                    </span>
                    <span className="mth-popover__body">
                        {loading ? (
                            <span className="mth-popover__loading">
                                <Loader2 size={16} className="mth-spin" />
                                <span>Querying dictionary…</span>
                            </span>
                        ) : (
                            <>
                                <span className="mth-popover__text">{explanation?.text}</span>
                                {explanation?.note && (
                                    <span className="mth-popover__note">
                                        <strong>Clinician Note:</strong> {explanation.note}
                                    </span>
                                )}
                            </>
                        )}
                    </span>
                </span>
            )}
        </span>
    )
}

/**
 * Floating “Explain” for any selected text inside a message (2–200 chars).
 * Use when auto-highlight misses a term or for multi-word phrases.
 */
export function SelectionExplainToolbar({ enabled, containerRef }) {
    const [buttonPos, setButtonPos] = useState(null)
    const [selectedText, setSelectedText] = useState('')
    const [activeTerm, setActiveTerm] = useState(null)
    const [explanation, setExplanation] = useState('')
    const [loading, setLoading] = useState(false)
    const [popoverPos, setPopoverPos] = useState({ top: 0, left: 0 })
    const popoverRef = useRef(null)

    useEffect(() => {
        if (!enabled) {
            setButtonPos(null)
            setSelectedText('')
            return
        }
        const onMouseUp = () => {
            requestAnimationFrame(() => {
                const sel = window.getSelection()
                if (!sel || sel.rangeCount === 0 || sel.isCollapsed) {
                    setButtonPos(null)
                    return
                }
                const root = containerRef?.current
                if (!root) return
                const range = sel.getRangeAt(0)
                let anchor = range.commonAncestorContainer
                if (anchor.nodeType === Node.TEXT_NODE) anchor = anchor.parentElement
                if (!anchor || !root.contains(anchor)) {
                    setButtonPos(null)
                    return
                }
                if (anchor.closest('input, textarea, [contenteditable="true"]')) {
                    setButtonPos(null)
                    return
                }
                const text = sel.toString().replace(/\s+/g, ' ').trim()
                if (text.length < 2 || text.length > 200) {
                    setButtonPos(null)
                    return
                }
                const rect = range.getBoundingClientRect()
                setSelectedText(text)
                setButtonPos({
                    top: rect.bottom + window.scrollY + 6,
                    left: Math.min(rect.left + window.scrollX, window.innerWidth - 140),
                })
            })
        }
        document.addEventListener('mouseup', onMouseUp)
        return () => document.removeEventListener('mouseup', onMouseUp)
    }, [enabled, containerRef])

    useEffect(() => {
        if (!activeTerm) return
        const handler = (e) => {
            if (popoverRef.current && !popoverRef.current.contains(e.target)) {
                setActiveTerm(null)
            }
        }
        document.addEventListener('mousedown', handler)
        return () => document.removeEventListener('mousedown', handler)
    }, [activeTerm])

    const openSelectionExplain = useCallback(async () => {
        const term = selectedText.trim().slice(0, 200)
        if (term.length < 2 || !buttonPos) return
        setPopoverPos({
            top: buttonPos.top + 4,
            left: Math.min(buttonPos.left, window.innerWidth - 320),
        })
        setActiveTerm(term)
        setButtonPos(null)
        window.getSelection()?.removeAllRanges()

        const cacheKey = term.toLowerCase()
        if (_explanationCache[cacheKey]) {
            setExplanation(_explanationCache[cacheKey])
            setLoading(false)
            return
        }
        setLoading(true)
        setExplanation(null)
        try {
            const res = await fetch(`${API_BASE}/explain-term?term=${encodeURIComponent(term)}`)
            if (!res.ok) throw new Error('Explain request failed')
            const data = await res.json()

            const result = {
                text: data.explanation ?? '',
                note: data.clinician_note,
                source: data.source || 'Library'
            }

            _explanationCache[cacheKey] = result
            setExplanation(result)
        } catch {
            setExplanation({ text: 'Unable to load explanation right now.', source: 'Error' })
        } finally {
            setLoading(false)
        }
    }, [selectedText, buttonPos])

    if (!enabled) return null

    return (
        <>
            {buttonPos && (
                <button
                    type="button"
                    className="mth-selection-btn"
                    style={{ top: buttonPos.top, left: buttonPos.left }}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={(e) => {
                        e.stopPropagation()
                        openSelectionExplain()
                    }}
                >
                    <BookOpen size={14} />
                    Explain
                </button>
            )}
            {activeTerm && (
                <span
                    ref={popoverRef}
                    className="mth-popover"
                    style={{ top: popoverPos.top, left: popoverPos.left }}
                >
                    <span className="mth-popover__header">
                        <BookOpen size={14} />
                        <span className="mth-popover__term">{activeTerm}</span>
                        <span className="mth-popover__source">{explanation?.source || '...'}</span>
                        <button type="button" className="mth-popover__close" onClick={() => setActiveTerm(null)}>
                            <X size={12} />
                        </button>
                    </span>
                    <span className="mth-popover__body">
                        {loading ? (
                            <span className="mth-popover__loading">
                                <Loader2 size={16} className="mth-spin" />
                                <span>Querying library…</span>
                            </span>
                        ) : (
                            <>
                                <span className="mth-popover__text">{explanation?.text}</span>
                                {explanation?.note && (
                                    <span className="mth-popover__note">
                                        <strong>Clinician Note:</strong> {explanation.note}
                                    </span>
                                )}
                            </>
                        )}
                    </span>
                </span>
            )}
        </>
    )
}

/**
 * Helper component that correctly integrates MedicalTermHighlighter with ReactMarkdown.
 * It applies the highlighter to the rendered HTML elements (like paragraphs and lists)
 * rather than modifying the raw markdown string before parsing.
 */
export function MarkdownWithHighlight({ children, enabled = true }) {
    return (
        <ReactMarkdown
            components={{
                p: ({ node: _node, ...props }) => <p {...props}><MedicalTermHighlighter enabled={enabled}>{props.children}</MedicalTermHighlighter></p>,
                li: ({ node: _node, ...props }) => <li {...props}><MedicalTermHighlighter enabled={enabled}>{props.children}</MedicalTermHighlighter></li>,
                td: ({ node: _node, ...props }) => <td {...props}><MedicalTermHighlighter enabled={enabled}>{props.children}</MedicalTermHighlighter></td>,
                th: ({ node: _node, ...props }) => <th {...props}><MedicalTermHighlighter enabled={enabled}>{props.children}</MedicalTermHighlighter></th>,
                span: ({ node: _node, ...props }) => <span {...props}><MedicalTermHighlighter enabled={enabled}>{props.children}</MedicalTermHighlighter></span>,
                strong: ({ node: _node, ...props }) => <strong {...props}><MedicalTermHighlighter enabled={enabled}>{props.children}</MedicalTermHighlighter></strong>,
                em: ({ node: _node, ...props }) => <em {...props}><MedicalTermHighlighter enabled={enabled}>{props.children}</MedicalTermHighlighter></em>,
                h1: ({ node: _node, ...props }) => <h1 {...props}><MedicalTermHighlighter enabled={enabled}>{props.children}</MedicalTermHighlighter></h1>,
                h2: ({ node: _node, ...props }) => <h2 {...props}><MedicalTermHighlighter enabled={enabled}>{props.children}</MedicalTermHighlighter></h2>,
                h3: ({ node: _node, ...props }) => <h3 {...props}><MedicalTermHighlighter enabled={enabled}>{props.children}</MedicalTermHighlighter></h3>,
                h4: ({ node: _node, ...props }) => <h4 {...props}><MedicalTermHighlighter enabled={enabled}>{props.children}</MedicalTermHighlighter></h4>,
                blockquote: ({ node: _node, ...props }) => <blockquote {...props}><MedicalTermHighlighter enabled={enabled}>{props.children}</MedicalTermHighlighter></blockquote>,
            }}
        >
            {children}
        </ReactMarkdown>
    )
}
