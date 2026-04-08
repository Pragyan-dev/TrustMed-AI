import { X, Heart, Thermometer, Wind, Droplets, Activity, Pill, Stethoscope, ChevronDown, ChevronUp, TrendingUp, TrendingDown, Minus, Image as ImageIcon, FileText, ArrowUpRight, Loader2, AlertCircle } from 'lucide-react'
import { useState } from 'react'

const VITAL_CONFIG = [
    {
        key: 'temperature', label: 'Temperature', unit: '°F', icon: Thermometer, color: '#F59E0B',
        colorBg: 'rgba(245, 158, 11, 0.08)', normal: [97, 99.5], format: v => v?.toFixed(1),
        range: [95, 104]
    },
    {
        key: 'heart_rate', label: 'Heart Rate', unit: 'bpm', icon: Heart, color: '#EF4444',
        colorBg: 'rgba(239, 68, 68, 0.08)', normal: [60, 100], format: v => Math.round(v),
        range: [40, 160], pulse: true
    },
    {
        key: 'respiratory_rate', label: 'Resp. Rate', unit: 'breaths/min', icon: Wind, color: '#3B82F6',
        colorBg: 'rgba(59, 130, 246, 0.08)', normal: [12, 20], format: v => Math.round(v),
        range: [8, 35]
    },
    {
        key: 'o2_saturation', label: 'SpO₂', unit: '%', icon: Droplets, color: '#10B981',
        colorBg: 'rgba(16, 185, 129, 0.08)', normal: [95, 100], format: v => Math.round(v),
        range: [80, 100]
    },
]

function VitalGauge({ value, min, max, normalMin, normalMax, color, status }) {
    const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100))
    const normalStartPct = ((normalMin - min) / (max - min)) * 100
    const normalEndPct = ((normalMax - min) / (max - min)) * 100

    return (
        <div className="vital-gauge">
            <div className="vital-gauge-track">
                <div
                    className="vital-gauge-normal"
                    style={{ left: `${normalStartPct}%`, width: `${normalEndPct - normalStartPct}%` }}
                />
                <div
                    className={`vital-gauge-indicator vital-gauge-${status}`}
                    style={{ left: `${pct}%`, background: status === 'normal' ? color : undefined }}
                />
            </div>
        </div>
    )
}

function StatusIcon({ status }) {
    if (status === 'high') return <TrendingUp size={10} />
    if (status === 'low') return <TrendingDown size={10} />
    return <Minus size={10} />
}

function formatAttachmentDate(value) {
    if (!value) return 'Just added'

    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return value

    return new Intl.DateTimeFormat(undefined, {
        month: 'short',
        day: 'numeric',
    }).format(parsed)
}

function getAttachmentSourceLabel(uploadedBy) {
    return uploadedBy === 'patient' ? 'Patient upload' : 'Care team'
}

function getAttachmentTypeLabel(fileKind) {
    return fileKind === 'pdf' ? 'PDF report' : 'Imaging file'
}

function PatientInfoPanel({ patientData, attachments = [], attachmentsLoading = false, attachmentsError = '', onClose }) {
    const [collapsed, setCollapsed] = useState(false)

    if (!patientData) return null

    const { vitals, diagnoses, medications, patient_id } = patientData

    const getVitalStatus = (value, normal) => {
        if (value == null || !normal) return 'normal'
        if (value < normal[0]) return 'low'
        if (value > normal[1]) return 'high'
        return 'normal'
    }

    const bpStatus = () => {
        if (!vitals) return 'normal'
        const sys = vitals.systolic_bp
        if (sys == null) return 'normal'
        if (sys >= 140) return 'high'
        if (sys < 90) return 'low'
        return 'normal'
    }

    const statusLabel = (status) => {
        if (status === 'high') return 'HIGH'
        if (status === 'low') return 'LOW'
        return 'Normal'
    }

    return (
        <div className={`patient-info-panel ${collapsed ? 'collapsed' : ''}`}>
            <div className="patient-info-header">
                <div className="patient-info-title">
                    <Activity size={16} />
                    <span>Patient {patient_id}</span>
                    <span className="patient-badge">MIMIC-IV</span>
                </div>
                <div className="patient-info-actions">
                    <button
                        type="button"
                        className="patient-info-action patient-toggle-btn"
                        onClick={() => setCollapsed(!collapsed)}
                        aria-label={collapsed ? 'Expand patient information' : 'Collapse patient information'}
                        title={collapsed ? 'Expand patient information' : 'Collapse patient information'}
                    >
                        {collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
                    </button>
                    <button
                        type="button"
                        className="patient-info-action patient-close-btn"
                        onClick={onClose}
                        aria-label="Close patient information"
                        title="Close patient information"
                    >
                        <X size={14} />
                    </button>
                </div>
            </div>

            {!collapsed && (
                <div className="patient-info-body">
                    {/* Vitals */}
                    {vitals && (
                        <div className="patient-section">
                            <div className="patient-section-label">
                                <Stethoscope size={12} />
                                <span>Vitals</span>
                                {vitals.recorded_at && (
                                    <span className="patient-timestamp">{vitals.recorded_at}</span>
                                )}
                            </div>
                            <div className="vitals-grid-v2">
                                {VITAL_CONFIG.map(vc => {
                                    const val = vitals[vc.key]
                                    if (val == null) return null
                                    const status = getVitalStatus(val, vc.normal)
                                    const Icon = vc.icon
                                    return (
                                        <div key={vc.key} className={`vital-card-v2 vital-${status}`}>
                                            <div className="vital-card-top">
                                                <div className="vital-icon-v2" style={{ background: vc.colorBg, color: vc.color }}>
                                                    <Icon size={16} />
                                                </div>
                                                <div className={`vital-status-badge vital-status-${status}`}>
                                                    <StatusIcon status={status} />
                                                    <span>{statusLabel(status)}</span>
                                                </div>
                                            </div>
                                            <div className="vital-card-body">
                                                <div className={`vital-value-v2 ${vc.pulse && status === 'normal' ? 'vital-pulse' : ''}`}>
                                                    {vc.format(val)}
                                                </div>
                                                <div className="vital-unit-v2">{vc.unit}</div>
                                            </div>
                                            <div className="vital-card-footer">
                                                <span className="vital-label-v2">{vc.label}</span>
                                                <VitalGauge
                                                    value={val}
                                                    min={vc.range[0]}
                                                    max={vc.range[1]}
                                                    normalMin={vc.normal[0]}
                                                    normalMax={vc.normal[1]}
                                                    color={vc.color}
                                                    status={status}
                                                />
                                                <span className="vital-range-label">
                                                    {vc.normal[0]}–{vc.normal[1]}
                                                </span>
                                            </div>
                                        </div>
                                    )
                                })}
                                {/* Blood Pressure */}
                                {vitals.systolic_bp != null && (
                                    <div className={`vital-card-v2 vital-bp vital-${bpStatus()}`}>
                                        <div className="vital-card-top">
                                            <div className="vital-icon-v2" style={{ background: 'rgba(139, 92, 246, 0.08)', color: '#8B5CF6' }}>
                                                <Activity size={16} />
                                            </div>
                                            <div className={`vital-status-badge vital-status-${bpStatus()}`}>
                                                <StatusIcon status={bpStatus()} />
                                                <span>{statusLabel(bpStatus())}</span>
                                            </div>
                                        </div>
                                        <div className="vital-card-body">
                                            <div className="vital-value-v2 vital-bp-value">
                                                <span className="bp-systolic">{Math.round(vitals.systolic_bp)}</span>
                                                <span className="bp-slash">/</span>
                                                <span className="bp-diastolic">{Math.round(vitals.diastolic_bp)}</span>
                                            </div>
                                            <div className="vital-unit-v2">mmHg</div>
                                        </div>
                                        <div className="vital-card-footer">
                                            <span className="vital-label-v2">Blood Pressure</span>
                                            <VitalGauge
                                                value={vitals.systolic_bp}
                                                min={70}
                                                max={200}
                                                normalMin={90}
                                                normalMax={140}
                                                color="#8B5CF6"
                                                status={bpStatus()}
                                            />
                                            <span className="vital-range-label">90–140 sys</span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Diagnoses */}
                    {diagnoses && diagnoses.length > 0 && (
                        <div className="patient-section">
                            <div className="patient-section-label">
                                <Stethoscope size={12} />
                                <span>Diagnoses ({diagnoses.length})</span>
                            </div>
                            <div className="patient-tag-list">
                                {diagnoses.map((d, i) => (
                                    <span key={i} className="patient-tag diagnosis-tag" title={`ICD: ${d.icd_code}`}>
                                        {d.title}
                                        <span className="tag-code">{d.icd_code}</span>
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Medications */}
                    {medications && medications.length > 0 && (
                        <div className="patient-section">
                            <div className="patient-section-label">
                                <Pill size={12} />
                                <span>Medications ({medications.length})</span>
                            </div>
                            <div className="patient-tag-list">
                                {medications.map((m, i) => (
                                    <span key={i} className="patient-tag med-tag" title={m.description || m.name}>
                                        {m.name}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="patient-section">
                        <div className="patient-section-label">
                            <ImageIcon size={12} />
                            <span>Imaging & Reports ({attachments.length})</span>
                        </div>

                        {attachmentsLoading ? (
                            <div className="patient-attachments__state">
                                <Loader2 size={12} className="cd-spin" />
                                <span>Loading patient files…</span>
                            </div>
                        ) : attachmentsError ? (
                            <div className="patient-attachments__state patient-attachments__state--error">
                                <AlertCircle size={12} />
                                <span>{attachmentsError}</span>
                            </div>
                        ) : attachments.length > 0 ? (
                            <div className="patient-attachment-list">
                                {attachments.map(attachment => (
                                    <div key={attachment.id} className="patient-attachment-row">
                                        <div className={`patient-attachment-row__preview patient-attachment-row__preview--${attachment.file_kind}`}>
                                            {attachment.file_kind === 'image' ? (
                                                <img
                                                    src={attachment.url}
                                                    alt={attachment.title || attachment.original_filename}
                                                />
                                            ) : (
                                                <FileText size={15} />
                                            )}
                                        </div>
                                        <div className="patient-attachment-row__body">
                                            <div className="patient-attachment-row__title">
                                                {attachment.title || attachment.original_filename}
                                            </div>
                                            <div className="patient-attachment-row__meta">
                                                <span>{getAttachmentSourceLabel(attachment.uploaded_by)}</span>
                                                <span>{getAttachmentTypeLabel(attachment.file_kind)}</span>
                                                <span>{formatAttachmentDate(attachment.uploaded_at)}</span>
                                            </div>
                                        </div>
                                        <a
                                            className="patient-attachment-row__link"
                                            href={attachment.url}
                                            target="_blank"
                                            rel="noreferrer"
                                        >
                                            Open
                                            <ArrowUpRight size={12} />
                                        </a>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="patient-attachments__state">
                                <span>No patient-linked imaging or reports yet.</span>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}

export default PatientInfoPanel
