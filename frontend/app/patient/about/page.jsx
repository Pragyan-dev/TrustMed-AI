'use client'

import {
    Activity,
    Brain,
    CheckCircle2,
    ClipboardList,
    Droplets,
    FileHeart,
    Heart,
    MessageCircle,
    Shield,
    Stethoscope,
} from 'lucide-react'
import {
    AboutCareSignalCard,
    AboutDemoTrendPanel,
    AboutKnowledgeGraphCard,
    AboutPipelineCard,
} from '../../../src/components/AboutDemoCharts'

const HERO_FEATURES = [
    {
        title: 'Translate the chart',
        description: 'Synapse turns dense clinical details into a calmer summary patients can scan before a visit.',
        icon: Stethoscope,
        tone: 'green',
    },
    {
        title: 'Watch the trend',
        description: 'Range bands and clearer labels make it easier to tell what is improving, stable, or needs a question.',
        icon: Brain,
        tone: 'blue',
    },
    {
        title: 'Prepare the follow-up',
        description: 'The patient view is designed to support better conversations with the care team, not replace them.',
        icon: MessageCircle,
        tone: 'purple',
    },
]

const HERO_METRICS = [
    {
        label: 'Improving signals',
        value: '2',
        note: 'Oxygen and pulse readings are settling toward the goal range.',
        icon: Activity,
        tone: 'green',
    },
    {
        label: 'Follow-up prompts',
        value: '1',
        note: 'Medication timing is worth confirming at the next check-in.',
        icon: Shield,
        tone: 'blue',
    },
    {
        label: 'Context layers',
        value: '4',
        note: 'Vitals, notes, medications, and prior results stay connected.',
        icon: FileHeart,
        tone: 'purple',
    },
]

const HERO_SPARKLINE = {
    label: 'Example recovery signal',
    value: 'Stabilizing over 24h',
    tag: 'Illustrative example',
    points: [82, 83, 85, 87, 89, 92, 94],
    secondaryPoints: [84, 84, 85, 85, 86, 86, 87],
    color: '#2E7D52',
    secondaryColor: '#94A3B8',
    ariaLabel: 'Illustrative recovery signal trend',
    caption: 'The solid line shows a steadier recent pattern, while the dotted line represents the earlier baseline.',
}

const DEMO_TREND_LABELS = [
    '2026-04-22 07:00',
    '2026-04-22 10:00',
    '2026-04-22 13:00',
    '2026-04-22 16:00',
    '2026-04-22 19:00',
    '2026-04-22 22:00',
    '2026-04-23 01:00',
]

const DEMO_TREND = {
    title: 'Oxygen Saturation',
    recordedAt: 'Example data · Last 24 hours',
    valueText: '96%',
    statusText: 'Back in range',
    statusTone: 'normal',
    referenceText: 'Illustrative example only: the shaded band represents the typical target range for this demo view.',
    unit: '%',
    points: [92, 91, 92, 93, 94, 95, 96],
    labels: DEMO_TREND_LABELS,
    pointMeta: DEMO_TREND_LABELS.map((_, index) => ({ source: 'chart', sort_order: index })),
    lowerBound: 95,
    upperBound: 100,
    pointColor: '#16A34A',
}

const TREND_NOTES = [
    {
        label: 'Range awareness',
        text: 'Patients can see when a value moves into the safer band instead of decoding every number in isolation.',
    },
    {
        label: 'Trend over snapshot',
        text: 'The design emphasizes direction of change, which usually matters more than a single reading on its own.',
    },
    {
        label: 'Plain-language cue',
        text: 'Status labels like “Back in range” make the takeaway readable at a glance before a follow-up conversation.',
    },
]

const KNOWLEDGE_GRAPH_NODES = [
    { id: 'vitals', label: 'Vitals', x: 20, y: 28, tone: 'red' },
    { id: 'history', label: 'Prior Results', x: 22, y: 76, tone: 'green' },
    { id: 'summary', label: 'Patient Summary', x: 50, y: 50, tone: 'accent', primary: true },
    { id: 'guidance', label: 'Care Guidance', x: 78, y: 24, tone: 'blue' },
    { id: 'meds', label: 'Medications', x: 78, y: 76, tone: 'purple' },
]

const KNOWLEDGE_GRAPH_NOTES = [
    'Related details stay connected before Synapse writes a patient-friendly explanation.',
    'The visual model is meant to preserve context across symptoms, medications, and prior findings.',
]

const PIPELINE_STEPS = [
    {
        title: 'Collect the record',
        body: 'Bring together bedside vitals, medications, imaging context, and prior chart notes.',
        icon: FileHeart,
    },
    {
        title: 'Detect the signal',
        body: 'Spot movement, compare against a healthy range, and highlight what changed recently.',
        icon: Activity,
    },
    {
        title: 'Translate the meaning',
        body: 'Convert clinical jargon into patient language without stripping away the important nuance.',
        icon: Brain,
    },
    {
        title: 'Support next steps',
        body: 'Surface calmer summaries and follow-up prompts patients can bring back to their care team.',
        icon: ClipboardList,
    },
]

const TRUST_PILLARS = [
    {
        tag: 'Privacy',
        title: 'Protected by design',
        description: 'This page uses illustrative demo visuals. In the patient experience, protected information is meant to stay scoped to you and authorized care contexts.',
        icon: Shield,
        tone: 'green',
    },
    {
        tag: 'Clarity',
        title: 'Readable under stress',
        description: 'Large labels, calmer color decisions, and explicit ranges reduce the cognitive load of reading a medical chart during a difficult moment.',
        icon: CheckCircle2,
        tone: 'blue',
    },
    {
        tag: 'Empathy',
        title: 'Built for real questions',
        description: 'The goal is to help patients understand what is stable, what changed, and what they should ask next, without escalating fear.',
        icon: Heart,
        tone: 'purple',
    },
]

export default function AboutPage() {
    return (
        <div className="pp-about pp-content-stack">
            <section className="pp-about-hero pp-about__band">
                <div className="pp-about-hero__content">
                    <div className="pp-about-hero__copy">
                        <div className="pp-page-kicker">About Synapse AI</div>
                        <h1 className="pp-page-title">Clinical context, explained in patient language.</h1>
                        <p className="pp-page-subtitle">
                            Synapse is designed to turn chart details, vital trends, and medical context into a calmer,
                            clearer experience for patients who need to understand what their care team is seeing.
                        </p>

                        <div className="pp-about-chip-row">
                            <span className="pp-about-chip pp-about-chip--accent">Patient-facing explainer</span>
                            <span className="pp-about-chip">No live patient record on this page</span>
                        </div>

                        <div className="pp-about-feature-list">
                            {HERO_FEATURES.map((feature) => {
                                const Icon = feature.icon

                                return (
                                    <div key={feature.title} className="pp-about-feature">
                                        <div className={`pp-about-feature__icon pp-about-feature__icon--${feature.tone}`}>
                                            <Icon size={18} aria-hidden="true" />
                                        </div>
                                        <div>
                                            <div className="pp-about-feature__title">{feature.title}</div>
                                            <p className="pp-about-feature__copy">{feature.description}</p>
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    </div>

                    <AboutCareSignalCard
                        eyebrow="Illustrative example data"
                        title="Care Signal Overview"
                        description="A sample patient-facing summary showing how Synapse can compress multiple clinical cues into one readable visual card."
                        metrics={HERO_METRICS}
                        sparkline={HERO_SPARKLINE}
                    />
                </div>
            </section>

            <section className="pp-card pp-section-card pp-about-section pp-about__band pp-about__band--delay-1">
                <div className="pp-card__header">
                    <div className="pp-card__heading">
                        <div className="pp-card__icon pp-card__icon--blue">
                            <Droplets size={18} />
                        </div>
                        <span className="pp-card__title">How the visuals work</span>
                    </div>
                </div>

                <div className="pp-card__body">
                    <div className="pp-about-section__intro">
                        <p>
                            These example visuals show the style of guidance Synapse aims to provide: clearer trend
                            reading, more connected clinical context, and patient-friendly explanations that support a
                            follow-up conversation with the care team.
                        </p>
                    </div>

                    <div className="pp-about-analytics-grid">
                        <AboutDemoTrendPanel
                            eyebrow="Illustrative example data"
                            title="Trend cards show movement, not just numbers"
                            description="This sample oxygen trend highlights a value returning into range so patients can understand the direction of change before they interpret the details."
                            chart={DEMO_TREND}
                            notes={TREND_NOTES}
                        />

                        <div className="pp-about-support-stack">
                            <AboutKnowledgeGraphCard
                                eyebrow="Connected context"
                                title="A lightweight knowledge graph keeps details related"
                                description="Instead of treating each chart element as an isolated note, Synapse can connect readings, treatments, and care guidance into one explainable picture."
                                nodes={KNOWLEDGE_GRAPH_NODES}
                                notes={KNOWLEDGE_GRAPH_NOTES}
                            />

                            <AboutPipelineCard
                                eyebrow="Four-step flow"
                                title="How Synapse turns records into guidance"
                                description="The interface is built around a simple flow patients can understand without seeing the underlying model complexity."
                                steps={PIPELINE_STEPS}
                            />
                        </div>
                    </div>
                </div>
            </section>

            <section className="pp-card pp-section-card pp-about-section pp-about__band pp-about__band--delay-2">
                <div className="pp-card__header">
                    <div className="pp-card__heading">
                        <div className="pp-card__icon pp-card__icon--green">
                            <Shield size={18} />
                        </div>
                        <span className="pp-card__title">Trust, safety, and empathy</span>
                    </div>
                </div>

                <div className="pp-card__body">
                    <div className="pp-about-section__intro">
                        <p>
                            The patient experience should feel supportive, not theatrical. The visual system aims to
                            reduce confusion while keeping privacy, readability, and emotional tone front and center.
                        </p>
                    </div>

                    <div className="pp-about-trust-grid">
                        {TRUST_PILLARS.map((pillar) => {
                            const Icon = pillar.icon

                            return (
                                <div key={pillar.title} className={`pp-about-trust-card pp-about-trust-card--${pillar.tone}`}>
                                    <div className="pp-about-trust-card__tag">{pillar.tag}</div>
                                    <div className="pp-about-trust-card__icon">
                                        <Icon size={18} aria-hidden="true" />
                                    </div>
                                    <h3 className="pp-about-trust-card__title">{pillar.title}</h3>
                                    <p className="pp-about-trust-card__copy">{pillar.description}</p>
                                </div>
                            )
                        })}
                    </div>

                    <p className="pp-about-trust-footnote">
                        This About page intentionally uses example-only visuals. Live patient information remains in the
                        main patient portal workflow.
                    </p>
                </div>
            </section>
        </div>
    )
}
