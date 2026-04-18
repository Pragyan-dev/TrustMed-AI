'use client'

import { X, Copy, Download, FileText, Stethoscope, Eye, Brain, ClipboardList, Loader2, Check } from 'lucide-react'
import { useState } from 'react'

const SECTIONS = [
    {
        key: 'subjective',
        title: 'Subjective',
        letter: 'S',
        color: '#3B82F6',
        icon: Stethoscope,
        fields: [
            { key: 'chief_complaint', label: 'Chief Complaint' },
            { key: 'history_of_present_illness', label: 'History of Present Illness' },
            { key: 'symptoms', label: 'Symptoms', isList: true },
            { key: 'relevant_history', label: 'Relevant History' },
        ]
    },
    {
        key: 'objective',
        title: 'Objective',
        letter: 'O',
        color: '#10B981',
        icon: Eye,
        fields: [
            { key: 'vitals', label: 'Vitals' },
            { key: 'physical_findings', label: 'Physical Findings' },
            { key: 'imaging_results', label: 'Imaging / Lab Results' },
            { key: 'clinical_observations', label: 'Clinical Observations' },
        ]
    },
    {
        key: 'assessment',
        title: 'Assessment',
        letter: 'A',
        color: '#F59E0B',
        icon: Brain,
        fields: [
            { key: 'primary_diagnosis', label: 'Primary Diagnosis' },
            { key: 'differential_diagnoses', label: 'Differential Diagnoses', isList: true },
            { key: 'clinical_reasoning', label: 'Clinical Reasoning' },
            { key: 'severity', label: 'Severity' },
        ]
    },
    {
        key: 'plan',
        title: 'Plan',
        letter: 'P',
        color: '#8B5CF6',
        icon: ClipboardList,
        fields: [
            { key: 'medications', label: 'Medications', isList: true },
            { key: 'lifestyle_modifications', label: 'Lifestyle Modifications', isList: true },
            { key: 'follow_up', label: 'Follow-Up' },
            { key: 'patient_education', label: 'Patient Education' },
            { key: 'referrals', label: 'Referrals' },
        ]
    },
]

function SOAPNoteModal({ isOpen, onClose, soapData, isLoading }) {
    const [copied, setCopied] = useState(false)

    if (!isOpen) return null

    const formatDate = (iso) => {
        if (!iso) return ''
        const d = new Date(iso)
        return d.toLocaleString('en-US', {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit'
        })
    }

    const generatePlainText = () => {
        if (!soapData) return ''
        let text = ''
        const meta = soapData._metadata
        if (meta) {
            text += `SOAP Note — ${meta.note_id}\n`
            text += `Generated: ${formatDate(meta.generated_at)}\n`
            text += `${'─'.repeat(50)}\n\n`
        }
        for (const section of SECTIONS) {
            const data = soapData[section.key]
            if (!data) continue
            text += `${section.title.toUpperCase()}\n${'─'.repeat(30)}\n`
            for (const field of section.fields) {
                const val = data[field.key]
                if (!val || (Array.isArray(val) && val.length === 0)) continue
                if (field.isList && Array.isArray(val)) {
                    text += `${field.label}:\n`
                    val.forEach(item => { text += `  • ${item}\n` })
                } else {
                    text += `${field.label}: ${val}\n`
                }
            }
            text += '\n'
        }
        return text.trim()
    }

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(generatePlainText())
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        } catch (err) {
            console.error('Copy failed:', err)
        }
    }

    const handleDownload = () => {
        const text = generatePlainText()
        const blob = new Blob([text], { type: 'text/plain' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        const noteId = soapData?._metadata?.note_id || 'SOAP-Note'
        a.download = `${noteId}.txt`
        a.click()
        URL.revokeObjectURL(url)
    }

    const renderFieldValue = (val, isList) => {
        if (!val) return <span className="soap-field-empty">Not discussed</span>
        if (isList && Array.isArray(val)) {
            if (val.length === 0) return <span className="soap-field-empty">None noted</span>
            return (
                <ul className="soap-field-list">
                    {val.map((item, i) => <li key={i}>{item}</li>)}
                </ul>
            )
        }
        if (typeof val === 'string' && (val === 'Not discussed' || val === 'Not provided')) {
            return <span className="soap-field-empty">{val}</span>
        }
        return <span>{val}</span>
    }

    return (
        <div className="soap-modal-overlay" onClick={onClose}>
            <div className="soap-modal" onClick={e => e.stopPropagation()}>
                {/* Header */}
                <div className="soap-modal-header">
                    <div className="soap-modal-title-row">
                        <FileText size={22} />
                        <div>
                            <h2>SOAP Note</h2>
                            {soapData?._metadata && (
                                <span className="soap-meta-text">
                                    {soapData._metadata.note_id} · {formatDate(soapData._metadata.generated_at)}
                                </span>
                            )}
                        </div>
                    </div>
                    <div className="soap-modal-actions">
                        {soapData && (
                            <>
                                <button className="soap-action-btn" onClick={handleCopy} title="Copy to clipboard">
                                    {copied ? <Check size={16} /> : <Copy size={16} />}
                                    <span>{copied ? 'Copied' : 'Copy'}</span>
                                </button>
                                <button className="soap-action-btn" onClick={handleDownload} title="Download as text">
                                    <Download size={16} />
                                    <span>Download</span>
                                </button>
                            </>
                        )}
                        <button className="soap-close-btn" onClick={onClose}>
                            <X size={18} />
                        </button>
                    </div>
                </div>

                {/* Body */}
                <div className="soap-modal-body">
                    {isLoading && (
                        <div className="soap-loading">
                            <Loader2 size={32} className="cd-spin" />
                            <p>Generating SOAP note from conversation...</p>
                            <span>Analyzing {soapData?._metadata?.message_count || 'session'} messages</span>
                        </div>
                    )}

                    {!isLoading && soapData && (
                        <div className="soap-sections">
                            {SECTIONS.map(section => {
                                const data = soapData[section.key]
                                if (!data) return null
                                const Icon = section.icon

                                return (
                                    <div key={section.key} className="soap-section">
                                        <div className="soap-section-header">
                                            <div className="soap-section-letter" style={{ background: section.color }}>
                                                {section.letter}
                                            </div>
                                            <div className="soap-section-title-wrap">
                                                <Icon size={16} style={{ color: section.color }} />
                                                <h3>{section.title}</h3>
                                            </div>
                                        </div>

                                        <div className="soap-section-content">
                                            {section.fields.map(field => {
                                                const val = data[field.key]
                                                // Skip completely empty fields
                                                // Keep fields even if they are 'Not discussed' or empty arrays
                                                // so the UI structure is consistent.
                                                if (val === undefined || val === null) {
                                                    // Default gracefully
                                                }

                                                return (
                                                    <div key={field.key} className="soap-field">
                                                        <label className="soap-field-label">{field.label}</label>
                                                        <div className="soap-field-value">
                                                            {renderFieldValue(val, field.isList)}
                                                        </div>
                                                    </div>
                                                )
                                            })}
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    )}

                    {!isLoading && !soapData && (
                        <div className="soap-loading">
                            <FileText size={32} strokeWidth={1} />
                            <p>No SOAP note data available</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}

export default SOAPNoteModal
