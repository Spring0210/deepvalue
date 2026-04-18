import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  message: string
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error: unknown): State {
    return {
      hasError: true,
      message: error instanceof Error ? error.message : 'An unexpected error occurred.',
    }
  }

  handleReset = () => this.setState({ hasError: false, message: '' })

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div
          className="flex flex-col items-center justify-center h-full rounded-xl p-6 text-center"
          style={{ background: '#2C2C2E', border: '1px solid rgba(255,69,58,0.3)' }}
        >
          <p className="text-sm font-semibold mb-1" style={{ color: '#FF453A' }}>Something went wrong</p>
          <p className="text-xs mb-4" style={{ color: 'rgba(235,235,245,0.4)' }}>{this.state.message}</p>
          <button
            onClick={this.handleReset}
            className="text-xs px-3 py-1.5 rounded-lg"
            style={{ background: 'rgba(10,132,255,0.15)', color: '#0A84FF', border: '1px solid rgba(10,132,255,0.25)' }}
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
