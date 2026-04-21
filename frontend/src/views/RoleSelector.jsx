'use client'

import Link from 'next/link'
import { useState, useEffect } from 'react'
import { Stethoscope, Heart, ArrowRight, Plus, Sun, Moon } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'

export default function RoleSelector() {
    const { theme, toggleTheme } = useTheme()
    const [displayText, setDisplayText] = useState('')
    const [isTyping, setIsTyping] = useState(true)
    const fullText = 'Breathe easier—with smart care by your side.'

    // Typing effect logic
    useEffect(() => {
        let i = 0
        const timer = setInterval(() => {
            setDisplayText(fullText.slice(0, i))
            i++
            if (i > fullText.length) {
                clearInterval(timer)
                setIsTyping(false)
            }
        }, 80)
        return () => clearInterval(timer)
    }, [])

    const handleMouseMove = (e) => {
        const card = e.currentTarget
        const rect = card.getBoundingClientRect()
        const x = e.clientX - rect.left
        const y = e.clientY - rect.top
        card.style.setProperty('--mouse-x', `${x}px`)
        card.style.setProperty('--mouse-y', `${y}px`)
    }

    return (
        <div className={`role-selector role-selector--${theme}`}>
            {/* Theme Toggle Button */}
            <button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle theme">
                {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
            </button>

            <div className="role-selector__logo">
                <Stethoscope />
            </div>
            <h1>Synapse AI</h1>
            <p className="role-selector__typing">
                {displayText}
                {isTyping && <span className="typing-cursor">|</span>}
            </p>
            <p className="role-selector__subtitle">
                Neuro-Symbolic Clinical Decision Support
            </p>

            <div className="role-selector__cards">
                <Link
                    href="/clinician"
                    className="role-card role-card--clinician"
                    onMouseMove={handleMouseMove}
                >
                    <div className="role-card__icon">
                        <Plus size={32} strokeWidth={2.5} />
                    </div>
                    <h2>Clinician Dashboard</h2>
                    <p>
                        Full clinical workspace with imaging analysis,
                        knowledge graph, drug safety, and patient records.
                    </p>
                    <div className="role-card__arrow">
                        <ArrowRight size={20} />
                    </div>
                </Link>

                <Link
                    href="/patient"
                    className="role-card role-card--patient"
                    onMouseMove={handleMouseMove}
                >
                    <div className="role-card__icon">
                        <Heart size={32} />
                    </div>
                    <h2>Patient Portal</h2>
                    <p>
                        Ask health questions in plain language.
                        Understand your conditions, medications, and care plan.
                    </p>
                    <div className="role-card__arrow">
                        <ArrowRight size={20} />
                    </div>
                </Link>
            </div>

            <p className="role-selector__footer">
                Synapse AI is for clinical decision support only.
                Always verify with qualified medical professionals.
            </p>
        </div>
    )
}
