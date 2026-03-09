import { Component } from 'react';
import * as Sentry from '@sentry/react';

/**
 * ErrorBoundary
 * Wraps the app — catches any uncaught render errors instead of
 * crashing the entire React tree. Reports to Sentry and shows a minimal recovery UI.
 */
class ErrorBoundary extends Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, info) {
        console.error('[ErrorBoundary caught]', error, info.componentStack);
        // Report to Sentry with component stack context
        Sentry.withScope((scope) => {
            scope.setExtra('componentStack', info.componentStack);
            Sentry.captureException(error);
        });
    }

    handleReset = () => {
        this.setState({ hasError: false, error: null });
        window.location.href = '/';
    };

    render() {
        if (this.state.hasError) {
            return (
                <div style={{
                    display: 'flex', flexDirection: 'column', alignItems: 'center',
                    justifyContent: 'center', width: '100%', minHeight: '100vh', minHeight: '100dvh', padding: '48px',
                    fontFamily: 'var(--font-sans, monospace)', background: '#f9f9f9'
                }}>
                    <div style={{ maxWidth: '560px', width: '100%', border: '1px solid #000', padding: '48px' }}>
                        <div style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.2em', marginBottom: '24px', opacity: 0.5 }}>
                            System — Error State
                        </div>
                        <h1 style={{ fontSize: '32px', fontFamily: 'var(--font-serif, serif)', textTransform: 'uppercase', marginBottom: '16px', lineHeight: 1 }}>
                            Something<br />Went Wrong
                        </h1>
                        <p style={{ fontSize: '12px', lineHeight: 1.6, opacity: 0.6, marginBottom: '32px' }}>
                            An unexpected error occurred in the application. The technical details have been logged.
                            {import.meta.env.DEV && this.state.error && (
                                <span style={{ display: 'block', marginTop: '12px', fontFamily: 'monospace', fontSize: '11px', background: '#f0f0f0', padding: '8px', borderLeft: '3px solid #000' }}>
                                    {this.state.error.message}
                                </span>
                            )}
                        </p>
                        <button
                            onClick={this.handleReset}
                            style={{
                                background: '#000', color: '#fff', border: 'none',
                                padding: '14px 32px', fontFamily: 'var(--font-sans, monospace)',
                                fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em',
                                cursor: 'pointer'
                            }}
                        >
                            Return to Home
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
