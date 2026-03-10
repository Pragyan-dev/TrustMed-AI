import { Outlet, Link, useNavigate } from 'react-router-dom'
import { Stethoscope, MessageSquare, Info, LogOut } from 'lucide-react'

export default function PatientLayout() {
    const navigate = useNavigate()

    return (
        <div className="patient-layout">
            {/* Top navbar */}
            <header className="pt-navbar">
                <Link to="/patient" className="pt-navbar__brand">
                    <div className="pt-navbar__logo">
                        <Stethoscope />
                    </div>
                    <div className="pt-navbar__title">
                        TrustMed <span>AI</span>
                    </div>
                </Link>

                <nav className="pt-navbar__links">
                    <Link to="/patient" className="pt-nav-link active">
                        <MessageSquare size={16} />
                        Chat
                    </Link>
                    <Link to="/patient" className="pt-nav-link">
                        <Info size={16} />
                        About
                    </Link>
                    <button
                        className="pt-nav-link"
                        onClick={() => navigate('/')}
                    >
                        <LogOut size={16} />
                        Switch Role
                    </button>
                </nav>
            </header>

            {/* Centered content */}
            <div className="pt-main">
                <Outlet />
            </div>
        </div>
    )
}
