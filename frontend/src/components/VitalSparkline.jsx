const CHART_WIDTH = 160
const CHART_HEIGHT = 56
const CHART_PADDING = 6

function createSeries(values) {
    return values
        .map((value, index) => ({ value, index }))
        .filter(point => Number.isFinite(point.value))
}

function buildLinePath(series, minValue, maxValue) {
    if (!series.length) return ''

    const usableWidth = CHART_WIDTH - CHART_PADDING * 2
    const usableHeight = CHART_HEIGHT - CHART_PADDING * 2
    const range = maxValue - minValue || 1

    return series.map((point, pointIndex) => {
        const x = CHART_PADDING + (series.length === 1 ? usableWidth / 2 : (usableWidth * pointIndex) / (series.length - 1))
        const y = CHART_PADDING + usableHeight - ((point.value - minValue) / range) * usableHeight
        return `${pointIndex === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
    }).join(' ')
}

function finalPoint(series, minValue, maxValue) {
    if (!series.length) return null

    const usableWidth = CHART_WIDTH - CHART_PADDING * 2
    const usableHeight = CHART_HEIGHT - CHART_PADDING * 2
    const range = maxValue - minValue || 1
    const pointIndex = series.length - 1
    const point = series[pointIndex]

    return {
        x: CHART_PADDING + (series.length === 1 ? usableWidth / 2 : (usableWidth * pointIndex) / (series.length - 1)),
        y: CHART_PADDING + usableHeight - ((point.value - minValue) / range) * usableHeight,
    }
}

export default function VitalSparkline({
    points = [],
    secondaryPoints = null,
    color = '#2E7D52',
    secondaryColor = '#6B7280',
    ariaLabel,
}) {
    const primarySeries = createSeries(points)
    const secondarySeries = secondaryPoints ? createSeries(secondaryPoints) : []
    const allValues = [...primarySeries, ...secondarySeries].map(point => point.value)

    if (!allValues.length) {
        return (
            <div className="pp-sparkline pp-sparkline--empty" aria-label={ariaLabel}>
                <span>No trend data yet</span>
            </div>
        )
    }

    const minValue = Math.min(...allValues)
    const maxValue = Math.max(...allValues)
    const gridY = [CHART_PADDING + 12, CHART_HEIGHT / 2, CHART_HEIGHT - CHART_PADDING - 10]

    const primaryPath = buildLinePath(primarySeries, minValue, maxValue)
    const secondaryPath = buildLinePath(secondarySeries, minValue, maxValue)
    const primaryFinalPoint = finalPoint(primarySeries, minValue, maxValue)
    const secondaryFinalPoint = finalPoint(secondarySeries, minValue, maxValue)

    return (
        <svg
            className="pp-sparkline"
            viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
            preserveAspectRatio="none"
            role="img"
            aria-label={ariaLabel}
        >
            {gridY.map(y => (
                <line
                    key={y}
                    x1={CHART_PADDING}
                    y1={y}
                    x2={CHART_WIDTH - CHART_PADDING}
                    y2={y}
                    className="pp-sparkline__grid"
                />
            ))}
            {secondaryPath && (
                <path
                    d={secondaryPath}
                    className="pp-sparkline__line pp-sparkline__line--secondary"
                    stroke={secondaryColor}
                />
            )}
            {primaryPath && (
                <path
                    d={primaryPath}
                    className="pp-sparkline__line"
                    stroke={color}
                />
            )}
            {secondaryFinalPoint && (
                <circle
                    cx={secondaryFinalPoint.x}
                    cy={secondaryFinalPoint.y}
                    r="2.8"
                    fill={secondaryColor}
                    className="pp-sparkline__marker pp-sparkline__marker--secondary"
                />
            )}
            {primaryFinalPoint && (
                <circle
                    cx={primaryFinalPoint.x}
                    cy={primaryFinalPoint.y}
                    r="3.4"
                    fill={color}
                    className="pp-sparkline__marker"
                />
            )}
        </svg>
    )
}
