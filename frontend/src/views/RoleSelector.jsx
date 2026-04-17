import Link from 'next/link'
import { Stethoscope, Heart, ArrowRight } from 'lucide-react'

export default function RoleSelector() {
    return (
        <div className="role-selector">
            <div className="role-selector__logo">
                <Stethoscope />
            </div>
            <h1>Synapse AI</h1>
            <p className="role-selector__subtitle">
                Neuro-Symbolic Clinical Decision Support
            </p>

            <div className="role-selector__cards">
                <Link href="/clinician" className="role-card role-card--clinician">
                    <div className="role-card__icon">
                        <Stethoscope size={32} />
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

                <Link href="/patient" className="role-card role-card--patient">
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
