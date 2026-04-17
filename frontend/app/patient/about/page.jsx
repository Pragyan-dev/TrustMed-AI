'use client'

import { Shield, Brain, Activity, Heart, Globe, Stethoscope } from 'lucide-react'
import PatientLayout from '../../../src/layouts/PatientLayout'

export default function AboutPage() {
    return (
        <div className="about-animate-container">
            <div className="pp-page-hero anim-fade-in">
                <div className="pp-hero-left">
                    <div className="pp-page-kicker">Information</div>
                    <h1 className="pp-page-title">About Synapse AI</h1>
                    <p className="pp-page-subtitle">
                        Empowering patients with clear, accessible, and AI-driven insights into their clinical care.
                    </p>
                </div>
            </div>

            <div className="pp-content-stack anim-slide-up" style={{ marginTop: '2rem' }}>
                <section className="pp-card pp-section-card">
                    <div className="pp-card__header">
                        <div className="pp-card__heading">
                            <div className="pp-card__icon pp-card__icon--green"><Shield size={18} /></div>
                            <span className="pp-card__title">Our Mission</span>
                        </div>
                    </div>
                    <div className="pp-card__body">
                        <p style={{ lineHeight: '1.6', color: '#4b5563' }}>
                            Synapse AI is designed to bridge the gap between complex clinical data and patient understanding. 
                            Our platform analyzes your medical records, vital signs, and imaging results to provide a 
                            clear, easy-to-read summary of your health journey.
                        </p>
                    </div>
                </section>

                <div className="pp-profile-grid">
                    <div className="pp-profile-panel anim-stagger-1">
                        <div className="pp-section-mini-title">Key Technology</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', marginTop: '1rem' }}>
                            <div className="tech-item">
                                <div style={{ color: '#2E7D52' }}><Brain size={24} /></div>
                                <div>
                                    <h4 style={{ margin: '0 0 0.25rem', fontSize: '0.95rem' }}>Medical Knowledge Graph</h4>
                                    <p style={{ margin: 0, fontSize: '0.85rem', color: '#636E72' }}>Connected clinical data ensuring accurate medical context for all analyses.</p>
                                </div>
                            </div>
                            <div className="tech-item">
                                <div style={{ color: '#3B82F6' }}><Activity size={24} /></div>
                                <div>
                                    <h4 style={{ margin: '0 0 0.25rem', fontSize: '0.95rem' }}>Vital Trend Analysis</h4>
                                    <p style={{ margin: 0, fontSize: '0.85rem', color: '#636E72' }}>Predictive tracking of heart rate, blood pressure, and oxygen levels.</p>
                                </div>
                            </div>
                            <div className="tech-item">
                                <div style={{ color: '#8B5CF6' }}><Globe size={24} /></div>
                                <div>
                                    <h4 style={{ margin: '0 0 0.25rem', fontSize: '0.95rem' }}>Literature Search</h4>
                                    <p style={{ margin: 0, fontSize: '0.85rem', color: '#636E72' }}>AI-powered search through peer-reviewed medical journals and guidelines.</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="pp-profile-panel anim-stagger-2">
                        <div className="pp-section-mini-title">Patient Privacy</div>
                        <p style={{ fontSize: '0.9rem', color: '#4b5563', lineHeight: '1.5' }}>
                            Your medical data is processed locally and securely. Synapse AI adheres to strict data 
                            privacy standards to ensure your protected health information (PHI) remains confidential 
                            and only accessible to you and your authorized care providers.
                        </p>
                        <div className="privacy-badge">
                            <div style={{ color: '#2E7D52' }}><Heart size={20} /></div>
                            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#2E7D52' }}>Designed with empathy for every patient.</span>
                        </div>
                    </div>
                </div>
            </div>

            <style jsx>{`
                .about-animate-container { animation: fadeIn 0.8s ease-out; }
                .anim-fade-in { animation: fadeIn 0.8s ease-out; }
                .anim-slide-up { animation: slideUp 0.8s ease-out forwards; opacity: 0; }
                .anim-stagger-1 { animation: slideUp 0.8s ease-out 0.2s forwards; opacity: 0; }
                .anim-stagger-2 { animation: slideUp 0.8s ease-out 0.4s forwards; opacity: 0; }
                
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                
                @keyframes slideUp {
                    from { opacity: 0; transform: translateY(20px); }
                    to { opacity: 1; transform: translateY(0); }
                }

                .pp-page-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 1.25rem; }
                .pp-page-kicker { display: inline-flex; align-items: center; padding: 0.3rem 0.7rem; border-radius: 999px; background: #E8F5E9; color: #2E7D52; font-size: 0.74rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.9rem; }
                .pp-page-title { margin: 0; font-size: 2.35rem; line-height: 1.05; letter-spacing: -0.03em; font-weight: 800; }
                .pp-page-subtitle { max-width: 760px; margin: 0.7rem 0 0; color: #636E72; font-size: 1.1rem; line-height: 1.7; }
                
                .pp-card { background: white; border-radius: 24px; border: 1px solid rgba(17, 24, 39, 0.06); box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04); overflow: hidden; transition: transform 0.3s ease; }
                .pp-card:hover { transform: translateY(-4px); }
                .pp-card__header { padding: 1.25rem 1.5rem; border-bottom: 1px solid rgba(46, 125, 82, 0.1); }
                .pp-card__heading { display: flex; align-items: center; gap: 0.6rem; }
                .pp-card__icon { width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
                .pp-card__icon--green { background: #E8F5E9; color: #2E7D52; }
                .pp-card__title { font-size: 1.1rem; font-weight: 700; color: #2D3436; }
                .pp-card__body { padding: 1.5rem; }
                
                .pp-profile-grid { display: grid; grid-template-columns: 1fr 1.5fr; gap: 1.5rem; margin-top: 1.5rem; }
                .pp-profile-panel { padding: 1.75rem; border-radius: 24px; background: white; border: 1px solid rgba(17, 24, 39, 0.06); box-shadow: 0 4px 20px rgba(0,0,0,0.02); }
                .pp-section-mini-title { font-size: 0.75rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em; color: #9CA3AF; margin-bottom: 1.25rem; }
                
                .tech-item { display: flex; gap: 1.25rem; transition: transform 0.2s ease; }
                .tech-item:hover { transform: translateX(8px); }
                .privacy-badge { margin-top: 1.5rem; padding: 1.25rem; background: #f0fdf4; border-radius: 16px; border: 1px dashed #2E7D52; display: flex; align-items: center; gap: 0.85rem; }
            `}</style>
        </div>
    )
}
