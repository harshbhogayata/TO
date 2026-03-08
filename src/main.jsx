import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import * as Sentry from '@sentry/react'
import posthog from 'posthog-js'
import App from './App.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import { restoreSession } from './services/api.js'
import { useAuthStore } from './store/authStore.js'
import './index.css'

// Sentry (frontend error tracking)
if (import.meta.env.VITE_SENTRY_DSN) {
    Sentry.init({
        dsn: import.meta.env.VITE_SENTRY_DSN,
        integrations: [Sentry.browserTracingIntegration()],
        tracesSampleRate: import.meta.env.DEV ? 1.0 : 0.1,
        environment: import.meta.env.DEV ? 'development' : 'production',
    })
}

// PostHog (product analytics)
if (import.meta.env.VITE_POSTHOG_KEY && import.meta.env.PROD) {
    posthog.init(import.meta.env.VITE_POSTHOG_KEY, {
        api_host: import.meta.env.VITE_POSTHOG_HOST || 'https://us.i.posthog.com',
        capture_pageview: true,
        capture_pageleave: true,
        autocapture: true,
    })
}

// axe-core (accessibility auditing in development)
if (import.meta.env.DEV) {
    import('react').then((React) =>
        import('react-dom').then((ReactDOM) =>
            import('@axe-core/react').then(({ default: axe }) => {
                axe(React.default || React, ReactDOM.default || ReactDOM, 1000);
            })
        )
    );
}

const { refreshToken, setLoading } = useAuthStore.getState()
const shouldRestoreSession = Boolean(refreshToken)

if (shouldRestoreSession) {
    setLoading(true)
}

ReactDOM.createRoot(document.getElementById('root')).render(
    <StrictMode>
        <ErrorBoundary>
            <App />
        </ErrorBoundary>
    </StrictMode>,
)

if (shouldRestoreSession) {
    restoreSession().finally(() => {
        useAuthStore.getState().setLoading(false)
    })
}

// Service Worker (PWA offline support)
if ('serviceWorker' in navigator && import.meta.env.PROD) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').catch(() => {
            // SW registration failed; app still works without it.
        });
    });
}