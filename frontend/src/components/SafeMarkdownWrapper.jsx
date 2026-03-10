import { Component } from 'react'

/**
 * Catches React rendering errors in child components.
 * Shows a styled fallback instead of a blank page.
 */
class SafeMarkdownWrapper extends Component {
    constructor(props) {
        super(props)
        this.state = { hasError: false }
    }

    static getDerivedStateFromError() {
        return { hasError: true }
    }

    componentDidCatch(error, info) {
        console.warn('Markdown render error:', error, info)
    }

    render() {
        if (this.state.hasError) {
            return (
                <div style={{
                    padding: '0.5rem 0.75rem',
                    fontSize: '0.85rem',
                    color: '#555',
                    lineHeight: 1.6,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                }}>
                    {this.props.fallbackText || 'Unable to format this response.'}
                </div>
            )
        }
        return this.props.children
    }
}

export default SafeMarkdownWrapper
