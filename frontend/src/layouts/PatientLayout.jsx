'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Stethoscope, MessageSquare, Info, Sun, Moon } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'

export default function PatientLayout({ children }) {
    const pathname = usePathname()
    const { theme, toggleTheme } = useTheme()

    return (
        <div className={`patient-layout patient-layout--${theme}`}>
            {/* Top navbar */}
            <header className="pt-navbar">
                <Link href="/" className="pt-navbar__brand">
                    <div className="pt-navbar__logo">
                        <Stethoscope />
                    </div>
                    <div className="pt-navbar__title">
                        Synapse <span>AI</span>
                    </div>
                </Link>

                <nav className="pt-navbar__links">
                    <div className="pt-view-switch" aria-label="Current application view">
                        <button className="pt-theme-toggle" onClick={toggleTheme} aria-label="Toggle theme">
                            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
                        </button>
                        <div className="pt-navbar__divider" style={{ width: '1px', height: '20px', background: 'rgba(0,0,0,0.1)', margin: '0 8px' }} />
                        <Link
                            href="/clinician"
                            className="pt-view-chip pt-view-chip--link"
                            title="Switch to clinician dashboard"
                        >
                            Clinician View
                        </Link>
                        <span className="pt-view-chip pt-view-chip--active">Patient View</span>
                    </div>

                    <Link
                        href="/patient"
                        className={`pt-nav-link ${pathname === '/patient' ? 'active' : ''}`}
                    >
                        <MessageSquare size={16} />
                        Chat
                    </Link>
                    <Link
                        href="/patient/about"
                        className={`pt-nav-link ${pathname === '/patient/about' ? 'active' : ''}`}
                    >
                        <Info size={16} />
                        About
                    </Link>
                </nav>
            </header>

            {/* Centered content */}
            <div className="pt-main">
                {children}
            </div>
        </div>
    )
}
