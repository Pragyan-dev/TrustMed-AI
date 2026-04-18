'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Stethoscope, MessageSquare, Info } from 'lucide-react'

export default function PatientLayout({ children }) {
    const pathname = usePathname()

    return (
        <div className="patient-layout">
            {/* Top navbar */}
            <header className="pt-navbar">
                <Link href="/patient" className="pt-navbar__brand">
                    <div className="pt-navbar__logo">
                        <Stethoscope />
                    </div>
                    <div className="pt-navbar__title">
                        Synapse <span>AI</span>
                    </div>
                </Link>

                <nav className="pt-navbar__links">
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

                    <div className="pt-view-switch" aria-label="Current application view">
                        <Link
                            href="/clinician"
                            className="pt-view-chip pt-view-chip--link"
                            title="Switch to clinician dashboard"
                        >
                            Clinician
                        </Link>
                        <span className="pt-view-chip pt-view-chip--active">Patient View</span>
                    </div>
                </nav>
            </header>

            {/* Centered content */}
            <div className="pt-main">
                {children}
            </div>
        </div>
    )
}
