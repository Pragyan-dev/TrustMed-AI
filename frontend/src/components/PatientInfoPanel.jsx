import { X, Heart, Thermometer, Wind, Droplets, Activity, Pill, Stethoscope, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'

const VITAL_CONFIG = [
    {
        key: 'temperature', label: 'Temp', unit: '°F', icon: Thermometer, color: '#F59E0B',
        normal: [97, 99.5], format: v => v?.toFixed(1)
    },
    {
        key: 'heart_rate', label: 'HR', unit: 'bpm', icon: Heart, color: '#EF4444',
        normal: [60, 100], format: v => Math.round(v)
    },
    {
        key: 'respiratory_rate', label: 'RR', unit: '/min', icon: Wind, color: '#3B82F6',
        normal: [12, 20], format: v => Math.round(v)
    },
    {
        key: 'o2_saturation', label: 'SpO₂', unit: '%', icon: Droplets, color: '#10B981',
        normal: [95, 100], format: v => Math.round(v)
    },
]

function PatientInfoPanel({ patientData, onClose }) {
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

    return (
        <div className={`patient-info-panel ${collapsed ? 'collapsed' : ''}`}>
            <div className="patient-info-header" onClick={() => setCollapsed(!collapsed)}>
                <div className="patient-info-title">
                    <Activity size={16} />
                    <span>Patient {patient_id}</span>
                    <span className="patient-badge">MIMIC-IV</span>
                </div>
                <div className="patient-info-actions">
                    {collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
                    <button className="patient-close-btn" onClick={(e) => { e.stopPropagation(); onClose(); }}>
                        <X size={14} />
                    </button>
                </div>
            </div>

            {!collapsed && (
                <div className="patient-info-body">
                    {/* Vitals Row */}
                    {vitals && (
                        <div className="patient-section">
                            <div className="patient-section-label">
                                <Stethoscope size={12} />
                                <span>Vitals</span>
                                {vitals.recorded_at && (
                                    <span className="patient-timestamp">{vitals.recorded_at}</span>
                                )}
                            </div>
                            <div className="vitals-grid">
                                {VITAL_CONFIG.map(vc => {
                                    const val = vitals[vc.key]
                                    if (val == null) return null
                                    const status = getVitalStatus(val, vc.normal)
                                    const Icon = vc.icon
                                    return (
                                        <div key={vc.key} className={`vital-card vital-${status}`}>
                                            <div className="vital-icon" style={{ color: vc.color }}>
                                                <Icon size={14} />
                                            </div>
                                            <div className="vital-value">{vc.format(val)}</div>
                                            <div className="vital-meta">
                                                <span className="vital-unit">{vc.unit}</span>
                                                <span className="vital-label">{vc.label}</span>
                                            </div>
                                        </div>
                                    )
                                })}
                                {/* Blood Pressure */}
                                {vitals.systolic_bp != null && (
                                    <div className={`vital-card vital-${bpStatus()}`}>
                                        <div className="vital-icon" style={{ color: '#8B5CF6' }}>
                                            <Activity size={14} />
                                        </div>
                                        <div className="vital-value">
                                            {Math.round(vitals.systolic_bp)}/{Math.round(vitals.diastolic_bp)}
                                        </div>
                                        <div className="vital-meta">
                                            <span className="vital-unit">mmHg</span>
                                            <span className="vital-label">BP</span>
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
                </div>
            )}
        </div>
    )
}

export default PatientInfoPanel
