'use client'

import { useId, useState } from 'react'

const VIEWBOX_WIDTH = 860
const VIEWBOX_HEIGHT = 280
const MARGIN = {
    top: 18,
    right: 20,
    bottom: 50,
    left: 64,
}

function isFiniteNumber(value) {
    return Number.isFinite(value)
}

function parseLabelTimestamp(label) {
    if (!label) return null
    const parsed = new Date(label.replace(' ', 'T'))
    return Number.isNaN(parsed.getTime()) ? null : parsed.getTime()
}

function buildSeries(points = [], labels = []) {
    return points
        .map((value, index) => ({
            index,
            value,
            label: labels[index] || '',
            timestamp: parseLabelTimestamp(labels[index] || ''),
        }))
        .filter(point => isFiniteNumber(point.value))
        .sort((left, right) => {
            if (left.timestamp !== null && right.timestamp !== null) return left.timestamp - right.timestamp
            if (left.timestamp !== null) return -1
            if (right.timestamp !== null) return 1
            return left.index - right.index
        })
}

function computeTicks(min, max, count = 5) {
    if (!isFiniteNumber(min) || !isFiniteNumber(max)) return []
    if (min === max) {
        return Array.from({ length: count }, (_, idx) => min + idx - Math.floor(count / 2))
    }

    const step = (max - min) / (count - 1)
    return Array.from({ length: count }, (_, index) => max - step * index)
}

function formatNumericTick(value) {
    if (!isFiniteNumber(value)) return ''
    if (Math.abs(value) >= 10) return Math.round(value).toString()
    return value.toFixed(1)
}

function formatTimeLabel(value, sameDay) {
    if (!value) return ''

    const timestamp = parseLabelTimestamp(value)
    if (timestamp === null) return value
    const parsed = new Date(timestamp)

    return new Intl.DateTimeFormat(undefined, sameDay
        ? { hour: 'numeric', minute: '2-digit' }
        : { month: 'short', day: 'numeric' }
    ).format(parsed)
}

function formatDetailedTimeLabel(value, sameDay) {
    if (!value) return ''

    const timestamp = parseLabelTimestamp(value)
    if (timestamp === null) return value
    const parsed = new Date(timestamp)

    return new Intl.DateTimeFormat(undefined, sameDay
        ? { hour: 'numeric', minute: '2-digit' }
        : { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }
    ).format(parsed)
}

function formatTooltipLabel(value) {
    if (!value) return ''

    const timestamp = parseLabelTimestamp(value)
    if (timestamp === null) return value

    return new Intl.DateTimeFormat(undefined, {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
    }).format(new Date(timestamp))
}

function formatTooltipValue(value, unit) {
    if (!isFiniteNumber(value)) return 'No value'

    if (unit === '%') return `${Math.round(value)}%`
    if (unit === '°F') return `${value.toFixed(1)}°F`
    if (unit === 'mmHg' || unit === 'bpm') return `${Math.round(value)} ${unit}`
    if (Math.abs(value) >= 10) return `${Math.round(value)} ${unit}`

    return `${value.toFixed(1)} ${unit}`
}

function buildAxisLabels(series, sampleIndices, sameDay) {
    const baseLabels = sampleIndices.map(index => formatTimeLabel(series[index].label, sameDay))
    const labelCounts = baseLabels.reduce((acc, label) => {
        acc[label] = (acc[label] || 0) + 1
        return acc
    }, {})

    return sampleIndices.map((sampleIndex, idx) => (
        labelCounts[baseLabels[idx]] > 1
            ? formatDetailedTimeLabel(series[sampleIndex].label, sameDay)
            : baseLabels[idx]
    ))
}

function createSampleIndices(length) {
    if (length <= 4) return Array.from({ length }, (_, index) => index)

    const candidates = [0, Math.floor((length - 1) / 3), Math.floor(((length - 1) * 2) / 3), length - 1]
    return [...new Set(candidates)].sort((a, b) => a - b)
}

export default function VitalTrendChart({
    title,
    recordedAt,
    valueText,
    statusText,
    statusTone = 'normal',
    referenceText,
    unit,
    points = [],
    labels = [],
    lowerBound = null,
    upperBound = null,
    pointColor = '#16A34A',
    tooltipValueFormatter = null,
}) {
    const clipId = useId().replace(/:/g, '')
    const [hoveredIndex, setHoveredIndex] = useState(null)
    const series = buildSeries(points, labels)

    if (!series.length) {
        return (
            <div className="pp-trend-card">
                <div className="pp-trend-card__header">
                    <div>
                        <div className="pp-trend-card__title">{title}</div>
                        <div className="pp-trend-card__date">No trend data recorded</div>
                    </div>
                </div>
                <div className="pp-trend-card__empty">No trend data available yet.</div>
            </div>
        )
    }

    const chartWidth = VIEWBOX_WIDTH - MARGIN.left - MARGIN.right
    const chartHeight = VIEWBOX_HEIGHT - MARGIN.top - MARGIN.bottom
    const sameDay = series.every(point => {
        if (!point.label || !series[0]?.label) return false
        return point.label.slice(0, 10) === series[0].label.slice(0, 10)
    })

    const domainValues = series.map(point => point.value)
    if (isFiniteNumber(lowerBound)) domainValues.push(lowerBound)
    if (isFiniteNumber(upperBound)) domainValues.push(upperBound)

    const minValue = Math.min(...domainValues)
    const maxValue = Math.max(...domainValues)
    const padding = Math.max((maxValue - minValue) * 0.18, maxValue === minValue ? Math.abs(maxValue || 1) * 0.18 : 0.8)
    const domainMin = minValue - padding
    const domainMax = maxValue + padding
    const range = domainMax - domainMin || 1
    const ticks = computeTicks(domainMin, domainMax, 5)
    const sampleIndices = createSampleIndices(series.length)
    const axisLabels = buildAxisLabels(series, sampleIndices, sameDay)

    const xForIndex = (index) => MARGIN.left + (series.length === 1 ? chartWidth / 2 : (chartWidth * index) / (series.length - 1))
    const yForValue = (value) => MARGIN.top + chartHeight - ((value - domainMin) / range) * chartHeight
    const linePath = series.map((point, index) => {
        const x = xForIndex(index)
        const y = yForValue(point.value)
        return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
    }).join(' ')
    const hoveredPoint = hoveredIndex === null ? null : series[hoveredIndex]
    const hoveredX = hoveredPoint ? xForIndex(hoveredIndex) : null
    const hoveredY = hoveredPoint ? yForValue(hoveredPoint.value) : null
    const tooltipLeft = hoveredX === null ? null : `${(hoveredX / VIEWBOX_WIDTH) * 100}%`
    const tooltipTop = hoveredY === null ? null : `${(hoveredY / VIEWBOX_HEIGHT) * 100}%`
    const tooltipXClass = hoveredX === null
        ? ''
        : hoveredX < MARGIN.left + 96
            ? 'pp-trend-chart__tooltip--left'
            : hoveredX > VIEWBOX_WIDTH - MARGIN.right - 96
                ? 'pp-trend-chart__tooltip--right'
                : 'pp-trend-chart__tooltip--center'
    const tooltipYClass = hoveredY !== null && hoveredY < MARGIN.top + 64
        ? 'pp-trend-chart__tooltip--below'
        : 'pp-trend-chart__tooltip--above'

    const renderThreshold = (value, className) => {
        if (!isFiniteNumber(value)) return null
        const y = yForValue(value)
        return (
            <line
                x1={MARGIN.left}
                y1={y}
                x2={VIEWBOX_WIDTH - MARGIN.right}
                y2={y}
                className={className}
            />
        )
    }

    // Build area path (fill under the line)
    const areaPath = series.length > 1
        ? linePath + ` L ${xForIndex(series.length - 1).toFixed(2)} ${(MARGIN.top + chartHeight).toFixed(2)} L ${xForIndex(0).toFixed(2)} ${(MARGIN.top + chartHeight).toFixed(2)} Z`
        : null

    // Normal range band
    const normalBandY1 = isFiniteNumber(upperBound) ? yForValue(upperBound) : null
    const normalBandY2 = isFiniteNumber(lowerBound) ? yForValue(lowerBound) : null

    return (
        <div className={`pp-trend-card pp-trend-card--v2 pp-trend-card--${statusTone}`}>
            <div className="pp-trend-card__header pp-trend-card__header--v2">
                <div className="pp-trend-card__header-left">
                    <div className="pp-trend-card__title">{title}</div>
                    <div className="pp-trend-card__date">{recordedAt}</div>
                </div>
                <div className="pp-trend-card__summary pp-trend-card__summary--v2">
                    <div className="pp-trend-card__value">{valueText}</div>
                    <div className={`pp-trend-card__status pp-trend-card__status--${statusTone}`}>{statusText}</div>
                </div>
            </div>
            {referenceText && <div className="pp-trend-card__reference pp-trend-card__reference--v2">{referenceText}</div>}

            <div className="pp-trend-card__plot pp-trend-card__plot--v2" onMouseLeave={() => setHoveredIndex(null)}>
                <svg className="pp-trend-chart pp-trend-chart--v2" viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label={`${title} trend`}>
                    <defs>
                        <clipPath id={clipId}>
                            <rect
                                x={MARGIN.left}
                                y={MARGIN.top}
                                width={chartWidth}
                                height={chartHeight}
                            />
                        </clipPath>
                        <linearGradient id={`${clipId}-area`} x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor={pointColor} stopOpacity="0.18" />
                            <stop offset="100%" stopColor={pointColor} stopOpacity="0.01" />
                        </linearGradient>
                        <linearGradient id={`${clipId}-line`} x1="0" y1="0" x2="1" y2="0">
                            <stop offset="0%" stopColor={pointColor} stopOpacity="0.7" />
                            <stop offset="50%" stopColor={pointColor} stopOpacity="1" />
                            <stop offset="100%" stopColor={pointColor} stopOpacity="0.7" />
                        </linearGradient>
                    </defs>

                    {/* Horizontal grid lines — subtle */}
                    {ticks.map(tick => {
                        const y = yForValue(tick)
                        return (
                            <g key={tick}>
                                <line
                                    x1={MARGIN.left}
                                    y1={y}
                                    x2={VIEWBOX_WIDTH - MARGIN.right}
                                    y2={y}
                                    className="pp-trend-chart__grid pp-trend-chart__grid--v2"
                                />
                                <text x={MARGIN.left - 12} y={y + 4} className="pp-trend-chart__y-label pp-trend-chart__y-label--v2" textAnchor="end">
                                    {formatNumericTick(tick)}
                                </text>
                            </g>
                        )
                    })}

                    {/* X axis labels */}
                    {sampleIndices.map((sampleIndex, samplePosition) => {
                        const x = xForIndex(sampleIndex)
                        return (
                            <text key={sampleIndex} x={x} y={VIEWBOX_HEIGHT - 12} textAnchor="middle" className="pp-trend-chart__x-label pp-trend-chart__x-label--v2">
                                {axisLabels[samplePosition]}
                            </text>
                        )
                    })}

                    <g clipPath={`url(#${clipId})`}>
                        {/* Normal range band (green zone) */}
                        {normalBandY1 !== null && normalBandY2 !== null && (
                            <rect
                                x={MARGIN.left}
                                y={normalBandY1}
                                width={chartWidth}
                                height={normalBandY2 - normalBandY1}
                                fill="#22c55e"
                                opacity="0.06"
                                rx="4"
                            />
                        )}

                        {/* Threshold lines */}
                        {renderThreshold(lowerBound, 'pp-trend-chart__threshold pp-trend-chart__threshold--v2 pp-trend-chart__threshold--low')}
                        {renderThreshold(upperBound, 'pp-trend-chart__threshold pp-trend-chart__threshold--v2 pp-trend-chart__threshold--high')}

                        {/* Hover vertical line */}
                        {hoveredPoint && (
                            <line
                                x1={hoveredX}
                                y1={MARGIN.top}
                                x2={hoveredX}
                                y2={MARGIN.top + chartHeight}
                                className="pp-trend-chart__hover-line pp-trend-chart__hover-line--v2"
                            />
                        )}

                        {/* Area fill */}
                        {areaPath && (
                            <path d={areaPath} fill={`url(#${clipId}-area)`} />
                        )}

                        {/* Line */}
                        <path d={linePath} fill="none" stroke={`url(#${clipId}-line)`} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

                        {/* Points */}
                        {series.map((point, index) => {
                            const cx = xForIndex(index)
                            const cy = yForValue(point.value)
                            const isActive = hoveredIndex === index
                            return (
                                <g key={`${point.label}-${index}`}>
                                    {/* Glow ring on hover */}
                                    {isActive && (
                                        <circle cx={cx} cy={cy} r="14" fill={pointColor} opacity="0.1" />
                                    )}
                                    <circle
                                        cx={cx}
                                        cy={cy}
                                        r={isActive ? '6' : '4.5'}
                                        fill="#ffffff"
                                        stroke={pointColor}
                                        strokeWidth="2.5"
                                        className={`pp-trend-chart__point pp-trend-chart__point--v2 ${isActive ? 'pp-trend-chart__point--active' : ''}`}
                                    />
                                    <circle
                                        cx={cx}
                                        cy={cy}
                                        r="16"
                                        fill="transparent"
                                        className="pp-trend-chart__point-hitbox"
                                        onMouseEnter={() => setHoveredIndex(index)}
                                        onMouseLeave={() => setHoveredIndex(current => (current === index ? null : current))}
                                        onFocus={() => setHoveredIndex(index)}
                                        onBlur={() => setHoveredIndex(current => (current === index ? null : current))}
                                        tabIndex="0"
                                        aria-label={`${title} on ${formatTooltipLabel(point.label)}: ${typeof tooltipValueFormatter === 'function'
                                            ? tooltipValueFormatter(point.value)
                                            : formatTooltipValue(point.value, unit)}`}
                                    />
                                </g>
                            )
                        })}
                    </g>

                    <text
                        x="18"
                        y={MARGIN.top + chartHeight / 2}
                        transform={`rotate(-90 18 ${MARGIN.top + chartHeight / 2})`}
                        className="pp-trend-chart__unit pp-trend-chart__unit--v2"
                    >
                        {unit}
                    </text>
                </svg>

                {hoveredPoint && (
                    <div
                        className={`pp-trend-chart__tooltip pp-trend-chart__tooltip--v2 ${tooltipXClass} ${tooltipYClass}`}
                        style={{ left: tooltipLeft, top: tooltipTop }}
                    >
                        <div className="pp-trend-chart__tooltip-date">{formatTooltipLabel(hoveredPoint.label)}</div>
                        <div className="pp-trend-chart__tooltip-value">
                            <span className="pp-trend-chart__tooltip-swatch" style={{ backgroundColor: pointColor }} />
                            {typeof tooltipValueFormatter === 'function'
                                ? tooltipValueFormatter(hoveredPoint.value)
                                : formatTooltipValue(hoveredPoint.value, unit)}
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
