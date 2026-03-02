import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import * as Sentry from '@sentry/react'
import posthog from 'posthog-js'
import App from './App.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import { restoreSession } from './services/api.js'
import './index.css'

// ─── Sentry (frontend error tracking) ────────────────────────────────────────
if (import.meta.env.VITE_SENTRY_DSN) {
    Sentry.init({
        dsn: import.meta.env.VITE_SENTRY_DSN,
        integrations: [Sentry.browserTracingIntegration()],
        tracesSampleRate: import.meta.env.DEV ? 1.0 : 0.1,
        environment: import.meta.env.DEV ? 'development' : 'production',
    })
}

// ─── PostHog (product analytics) ─────────────────────────────────────────────
if (import.meta.env.VITE_POSTHOG_KEY && import.meta.env.PROD) {
    posthog.init(import.meta.env.VITE_POSTHOG_KEY, {
        api_host: import.meta.env.VITE_POSTHOG_HOST || 'https://us.i.posthog.com',
        capture_pageview: true,
        capture_pageleave: true,
        autocapture: true,
    })
}

// ─── Restore session (access token is memory-only) ───────────────────────
restoreSession().finally(() => {
    ReactDOM.createRoot(document.getElementById('root')).render(
        <StrictMode>
            <ErrorBoundary>
                <App />
            </ErrorBoundary>
        </StrictMode>,
    )
})

// ─── Service Worker (PWA offline support) ────────────────────────────────────
if ('serviceWorker' in navigator && import.meta.env.PROD) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').catch(() => {
            // SW registration failed — non-critical, app works without it
        });
    });
}
