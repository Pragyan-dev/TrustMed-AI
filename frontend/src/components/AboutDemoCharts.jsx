import VitalSparkline from './VitalSparkline'
import VitalTrendChart from './VitalTrendChart'

export function AboutCareSignalCard({
    eyebrow,
    title,
    description,
    metrics = [],
    sparkline,
}) {
    return (
        <div className="pp-about-card pp-about-care-card">
            <div className="pp-about-card__eyebrow">{eyebrow}</div>
            <h2 className="pp-about-card__title">{title}</h2>
            <p className="pp-about-card__copy">{description}</p>

            <div className="pp-about-care-card__spark-shell">
                <div className="pp-about-care-card__spark-meta">
                    <div>
                        <div className="pp-about-care-card__spark-label">{sparkline.label}</div>
                        <div className="pp-about-care-card__spark-value">{sparkline.value}</div>
                    </div>
                    <span className="pp-about-chip pp-about-chip--soft">{sparkline.tag}</span>
                </div>
                <div className="pp-about-care-card__spark-chart">
                    <VitalSparkline
                        points={sparkline.points}
                        secondaryPoints={sparkline.secondaryPoints}
                        color={sparkline.color}
                        secondaryColor={sparkline.secondaryColor}
                        ariaLabel={sparkline.ariaLabel}
                    />
                </div>
                <p className="pp-about-care-card__spark-caption">{sparkline.caption}</p>
            </div>

            <div className="pp-about-metric-grid">
                {metrics.map((metric) => {
                    const Icon = metric.icon

                    return (
                        <div
                            key={metric.label}
                            className={`pp-about-metric pp-about-metric--${metric.tone || 'green'}`}
                        >
                            <div className="pp-about-metric__icon">
                                <Icon size={16} aria-hidden="true" />
                            </div>
                            <div className="pp-about-metric__value">{metric.value}</div>
                            <div className="pp-about-metric__label">{metric.label}</div>
                            <p className="pp-about-metric__note">{metric.note}</p>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}

export function AboutDemoTrendPanel({
    eyebrow,
    title,
    description,
    chart,
    notes = [],
}) {
    return (
        <div className="pp-about-trend-panel">
            <div className="pp-about-card__eyebrow">{eyebrow}</div>
            <h3 className="pp-about-card__title">{title}</h3>
            <p className="pp-about-card__copy">{description}</p>

            <div className="pp-about-trend-panel__frame">
                <VitalTrendChart
                    title={chart.title}
                    recordedAt={chart.recordedAt}
                    valueText={chart.valueText}
                    statusText={chart.statusText}
                    statusTone={chart.statusTone}
                    referenceText={chart.referenceText}
                    unit={chart.unit}
                    points={chart.points}
                    labels={chart.labels}
                    pointMeta={chart.pointMeta}
                    lowerBound={chart.lowerBound}
                    upperBound={chart.upperBound}
                    pointColor={chart.pointColor}
                    tooltipValueFormatter={chart.tooltipValueFormatter}
                />
            </div>

            <div className="pp-about-trend-notes">
                {notes.map((note) => (
                    <div key={note.label} className="pp-about-note">
                        <div className="pp-about-note__label">{note.label}</div>
                        <p className="pp-about-note__text">{note.text}</p>
                    </div>
                ))}
            </div>
        </div>
    )
}

export function AboutKnowledgeGraphCard({
    eyebrow,
    title,
    description,
    nodes = [],
    notes = [],
}) {
    const primaryNode = nodes.find(node => node.primary) || nodes[0]
    const relatedNodes = nodes.filter(node => node.id !== primaryNode?.id)

    return (
        <div className="pp-about-support-card">
            <div className="pp-about-card__eyebrow">{eyebrow}</div>
            <h3 className="pp-about-support-card__title">{title}</h3>
            <p className="pp-about-support-card__copy">{description}</p>

            <div className="pp-about-graph" aria-hidden="true">
                <svg className="pp-about-graph__lines" viewBox="0 0 100 100" preserveAspectRatio="none">
                    {primaryNode && relatedNodes.map(node => (
                        <line
                            key={node.id}
                            className="pp-about-graph__line"
                            x1={primaryNode.x}
                            y1={primaryNode.y}
                            x2={node.x}
                            y2={node.y}
                        />
                    ))}
                </svg>

                {nodes.map(node => (
                    <div
                        key={node.id}
                        className={[
                            'pp-about-graph__node',
                            `pp-about-graph__node--${node.tone || 'green'}`,
                            node.primary ? 'pp-about-graph__node--primary' : '',
                        ].filter(Boolean).join(' ')}
                        style={{ left: `${node.x}%`, top: `${node.y}%` }}
                    >
                        {node.label}
                    </div>
                ))}
            </div>

            <div className="pp-about-list">
                {notes.map(note => (
                    <div key={note} className="pp-about-list__item">
                        <span className="pp-about-list__bullet" aria-hidden="true" />
                        <span>{note}</span>
                    </div>
                ))}
            </div>
        </div>
    )
}

export function AboutPipelineCard({
    eyebrow,
    title,
    description,
    steps = [],
}) {
    return (
        <div className="pp-about-support-card">
            <div className="pp-about-card__eyebrow">{eyebrow}</div>
            <h3 className="pp-about-support-card__title">{title}</h3>
            <p className="pp-about-support-card__copy">{description}</p>

            <div className="pp-about-pipeline">
                {steps.map((step, index) => {
                    const Icon = step.icon

                    return (
                        <div key={step.title} className="pp-about-pipeline__item">
                            <div className="pp-about-pipeline__number">
                                {String(index + 1).padStart(2, '0')}
                            </div>
                            <div className="pp-about-pipeline__icon">
                                <Icon size={16} aria-hidden="true" />
                            </div>
                            <div className="pp-about-pipeline__content">
                                <div className="pp-about-pipeline__title">{step.title}</div>
                                <p className="pp-about-pipeline__copy">{step.body}</p>
                            </div>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
