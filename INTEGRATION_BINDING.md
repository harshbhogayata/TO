# TalentOrbit — Enterprise Integration Binding Guide

> How to wire the 14 new page components into the existing codebase — the enterprise way.  
> NO shortcuts. Every integration point includes security, accessibility, error handling, and performance requirements.

---

## ⚠️ HONEST STATUS: What These Pages Actually Are Right Now

Before integration, acknowledge the truth:

| Reality | Detail |
|---------|--------|
| **Pages are UI shells only** | All 14 files render hardcoded mock data with zero API calls |
| **Zero input validation** | Forms accept any input — no Zod, no Yup, no sanitization |
| **Zero error handling** | No try/catch, no ErrorBoundary, no fallback states |
| **Zero accessibility** | No ARIA labels, no keyboard navigation, no focus management, no screen reader support |
| **Inline styles only** | ~2,800 lines of inline styles across 14 files, not using CSS custom properties |
| **No DashboardLayout** | Each page renders its own `<main>` — bypasses sidebar, tape bar, skip-link |
| **No security** | PolicyManager has a "rich text editor" with zero XSS prevention; forms have no CSRF tokens |
| **No loading/error/empty states** | Pages assume data always exists and always loads |
| **Not route-registered** | None of the 14 pages are reachable — no lazy imports, no `<Route>`, no sidebar links |

**These are design prototypes, not production pages. Each one requires full enterprise hardening before it ships.**

---

## Table of Contents

1. [Prerequisites — Must Complete Before ANY Integration](#1-prerequisites)
2. [Step 1 — Route Registration with Code-Splitting & Error Boundaries](#2-step-1--route-registration)
3. [Step 2 — Sidebar Navigation with Feature Flag Gating](#3-step-2--sidebar-navigation)
4. [Step 3 — DashboardLayout Wrapping (Mandatory)](#4-step-3--dashboardlayout-wrapping)
5. [Step 4 — Security Requirements Per Page](#5-step-4--security-requirements)
6. [Step 5 — Accessibility Requirements (WCAG 2.1 AA)](#6-step-5--accessibility-requirements)
7. [Step 6 — Input Validation & Sanitization](#7-step-6--input-validation--sanitization)
8. [Step 7 — Error Handling & Resilience Patterns](#8-step-7--error-handling--resilience)
9. [Step 8 — State Management & API Binding](#9-step-8--state-management--api-binding)
10. [Step 9 — Performance Budgets & Optimization](#10-step-9--performance-budgets)
11. [Step 10 — AIChatbot Overlay Integration](#11-step-10--aichatbot-overlay)
12. [Step 11 — Real-Time Features (WebSocket)](#12-step-11--real-time-features)
13. [Step 12 — Backend Route Verification & Blockers](#13-step-12--backend-route-verification)
14. [Page-by-Page Enterprise Binding Spec](#14-page-by-page-enterprise-binding-spec)
15. [Integration Acceptance Criteria](#15-integration-acceptance-criteria)

---

## 1. Prerequisites

**These MUST be completed before touching ANY of the 14 pages:**

### 1a. Database Migrations (CRITICAL BLOCKER)

4 Django apps have models but **ZERO migration files** — the database tables do not exist:

```bash
cd backend
python manage.py makemigrations payments assessments developer reviews
python manage.py migrate --plan          # Review the plan FIRST
python manage.py migrate                 # Apply
python manage.py showmigrations          # Verify all [X]
```

**Without this, 6 of 14 pages (all WS4) will 500-error on every API call.**

### 1b. Migration Rollback Plan

Before applying, create a rollback script:

```bash
# Record current state
python manage.py showmigrations > migration_state_before.txt

# If rollback needed:
python manage.py migrate payments zero
python manage.py migrate assessments zero
python manage.py migrate developer zero
python manage.py migrate reviews zero
```

### 1c. Install Missing Frontend Dependencies

```bash
npm install zod dompurify @types/dompurify    # Input validation + XSS sanitization
npm install -D @axe-core/react                 # Accessibility testing in dev
```

### 1d. Verify Backend Endpoints Exist

Run this audit — every frontend service call must have a matching Django URL:

```bash
cd backend
python manage.py show_urls | grep -E "(payments|intelligence/ai|compliance/policies|search/companies)"
```

If `show_urls` is not available, install `django-extensions` or manually verify `urls.py` files.

---

## 2. Step 1 — Route Registration

### 2a. Lazy Imports with Webpack Magic Comments

Add after existing lazy imports in `App.jsx` (~line 100). Use `webpackChunkName` for debuggable chunk names and `webpackPrefetch` for likely-next-navigations:

```jsx
// ── Revenue & Growth (WS4) ───────────────────────────────────────────────
const BillingCenter        = lazy(() => import(/* webpackChunkName: "billing" */ './pages/BillingCenter'));
const SubscriptionPlans    = lazy(() => import(/* webpackChunkName: "plans" */ './pages/SubscriptionPlans'));
const ReferralProgram      = lazy(() => import(/* webpackChunkName: "referrals" */ './pages/ReferralProgram'));
const SponsoredPosts       = lazy(() => import(/* webpackChunkName: "sponsored" */ './pages/SponsoredPosts'));
const CRMPipeline          = lazy(() => import(/* webpackChunkName: "crm" */ './pages/CRMPipeline'));
const RevenueDashboard     = lazy(() => import(/* webpackChunkName: "revenue" */ './pages/RevenueDashboard'));

// ── AI/ML Platform (WS5) ────────────────────────────────────────────────
const AIJobWriter          = lazy(() => import(/* webpackChunkName: "ai-writer" */ './pages/AIJobWriter'));
const InterviewScheduler   = lazy(() => import(/* webpackChunkName: "interviews" */ './pages/InterviewScheduler'));
const CompensationBenchmark = lazy(() => import(/* webpackChunkName: "compensation" */ './pages/CompensationBenchmark'));

// ── Utility / Discovery ─────────────────────────────────────────────────
const TalentSearch         = lazy(() => import(/* webpackChunkName: "talent-search" */ './pages/TalentSearch'));
const CompanyDirectory     = lazy(() => import(/* webpackChunkName: "company-dir" */ './pages/CompanyDirectory'));

// ── Admin Operations ────────────────────────────────────────────────────
const FeatureFlagAdmin     = lazy(() => import(/* webpackChunkName: "flags" */ './pages/FeatureFlagAdmin'));
const PolicyManager        = lazy(() => import(/* webpackChunkName: "policies" */ './pages/PolicyManager'));
```

> `AIChatbot` is NOT lazy-loaded as a route — it's a global overlay. See Step 10.

### 2b. Route Definitions with Per-Route Error Boundaries

Each route MUST be wrapped in an `<ErrorBoundary>` so a crash in one page doesn't blank the entire app. The existing `ErrorBoundary` component in `src/components/ErrorBoundary.jsx` should be used:

```jsx
import ErrorBoundary from './components/ErrorBoundary';

{/* ── Revenue & Growth (WS4) ─────────────────────────────────────── */}
<Route path="/billing" element={
    <ProtectedRoute allowedRoles={['TALENT', 'COMPANY']}>
        <ErrorBoundary>
            <BillingCenter />
        </ErrorBoundary>
    </ProtectedRoute>
} />
<Route path="/plans" element={
    <ProtectedRoute>
        <ErrorBoundary>
            <SubscriptionPlans />
        </ErrorBoundary>
    </ProtectedRoute>
} />
<Route path="/referrals" element={
    <ProtectedRoute>
        <ErrorBoundary>
            <ReferralProgram />
        </ErrorBoundary>
    </ProtectedRoute>
} />
<Route path="/company/sponsored" element={
    <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
        <ErrorBoundary>
            <SponsoredPosts />
        </ErrorBoundary>
    </ProtectedRoute>
} />
<Route path="/company/crm" element={
    <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
        <ErrorBoundary>
            <CRMPipeline />
        </ErrorBoundary>
    </ProtectedRoute>
} />
<Route path="/admin/revenue" element={
    <ProtectedRoute allowedRoles={['ADMIN']}>
        <ErrorBoundary>
            <RevenueDashboard />
        </ErrorBoundary>
    </ProtectedRoute>
} />

{/* ── AI/ML Platform (WS5) ──────────────────────────────────────── */}
<Route path="/company/ai-job-writer" element={
    <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
        <ErrorBoundary>
            <AIJobWriter />
        </ErrorBoundary>
    </ProtectedRoute>
} />
<Route path="/company/interviews" element={
    <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
        <ErrorBoundary>
            <InterviewScheduler />
        </ErrorBoundary>
    </ProtectedRoute>
} />
<Route path="/compensation" element={
    <ProtectedRoute allowedRoles={['TALENT', 'COMPANY', 'ADMIN']}>
        <ErrorBoundary>
            <CompensationBenchmark />
        </ErrorBoundary>
    </ProtectedRoute>
} />

{/* ── Utility / Discovery ────────────────────────────────────────── */}
<Route path="/talent-search" element={
    <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
        <ErrorBoundary>
            <TalentSearch />
        </ErrorBoundary>
    </ProtectedRoute>
} />
<Route path="/companies" element={
    <ProtectedRoute>
        <ErrorBoundary>
            <CompanyDirectory />
        </ErrorBoundary>
    </ProtectedRoute>
} />

{/* ── Admin Operations ───────────────────────────────────────────── */}
<Route path="/admin/feature-flags" element={
    <ProtectedRoute allowedRoles={['ADMIN']}>
        <ErrorBoundary>
            <FeatureFlagAdmin />
        </ErrorBoundary>
    </ProtectedRoute>
} />
<Route path="/admin/policies" element={
    <ProtectedRoute allowedRoles={['ADMIN']}>
        <ErrorBoundary>
            <PolicyManager />
        </ErrorBoundary>
    </ProtectedRoute>
} />
```

---

## 3. Step 2 — Sidebar Navigation

### Feature Flag Gating for Gradual Rollout

**Do NOT hard-code nav items immediately.** Gate new pages behind feature flags using the existing `useFeatureFlags` hook so pages can be rolled out incrementally:

```jsx
// In Sidebar.jsx — conditional nav item injection:
import { useFeatureFlags } from '../hooks/useFeatureFlags';

const Sidebar = () => {
    const billingEnabled   = useFeatureFlags('ws4_billing');
    const crmEnabled       = useFeatureFlags('ws4_crm');
    const aiWriterEnabled  = useFeatureFlags('ws5_ai_writer');
    // ... etc for each new page

    const companyGrowthNav = [
        billingEnabled   && { num: '20', label: 'Billing', path: '/billing' },
        billingEnabled   && { num: '21', label: 'Plans', path: '/plans' },
        billingEnabled   && { num: '22', label: 'Referrals', path: '/referrals' },
        crmEnabled       && { num: '23', label: 'Sponsored Posts', path: '/company/sponsored' },
        crmEnabled       && { num: '24', label: 'CRM Pipeline', path: '/company/crm' },
        aiWriterEnabled  && { num: '25', label: 'AI Job Writer', path: '/company/ai-job-writer' },
        aiWriterEnabled  && { num: '26', label: 'Interviews', path: '/company/interviews' },
        // ... etc
    ].filter(Boolean);
};
```

### Final Nav Items (when flags are 100%):

**Talent Nav** — append to section 3:
```jsx
{ num: '20', label: 'Billing', path: '/billing' },
{ num: '21', label: 'Plans', path: '/plans' },
{ num: '22', label: 'Referrals', path: '/referrals' },
{ num: '23', label: 'Company Directory', path: '/companies' },
{ num: '24', label: 'Compensation Data', path: '/compensation' },
```

**Company Nav** — new section after Team:
```jsx
[
    { num: '20', label: 'Billing', path: '/billing' },
    { num: '21', label: 'Plans', path: '/plans' },
    { num: '22', label: 'Referrals', path: '/referrals' },
    { num: '23', label: 'Sponsored Posts', path: '/company/sponsored' },
    { num: '24', label: 'CRM Pipeline', path: '/company/crm' },
    { num: '25', label: 'AI Job Writer', path: '/company/ai-job-writer' },
    { num: '26', label: 'Interviews', path: '/company/interviews' },
    { num: '27', label: 'Talent Search', path: '/talent-search' },
    { num: '28', label: 'Compensation Data', path: '/compensation' },
    { num: '29', label: 'Company Directory', path: '/companies' },
]
```

**Admin Nav** — append to section 2:
```jsx
{ num: '11', label: 'Revenue Dashboard', path: '/admin/revenue' },
{ num: '12', label: 'Feature Flags', path: '/admin/feature-flags' },
{ num: '13', label: 'Policy Manager', path: '/admin/policies' },
{ num: '14', label: 'Talent Search', path: '/talent-search' },
{ num: '15', label: 'Compensation Data', path: '/compensation' },
```

---

## 4. Step 3 — DashboardLayout Wrapping

Every page MUST use `DashboardLayout` — no exceptions. Pages rendering their own `<main>` bypass the sidebar, tape bar, skip-link, and ARIA landmarks.

### Mandatory Transformation Pattern

**BEFORE** (current — broken):
```jsx
const BillingCenter = () => (
  <main style={{ backgroundColor: '#E6E2D8', ... }}>
    <header style={...}><h1 style={...}>Bill<br/>Ing</h1></header>
    <div>...content with hardcoded data...</div>
  </main>
);
```

**AFTER** (enterprise — correct):
```jsx
import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { usePaymentStore } from '../store/paymentStore';
import { useToast } from '../contexts/ToastContext';
import { getApiErrorMessage } from '../services/api';

const BillingCenter = () => {
    usePageTitle('Billing Center', 'Manage your subscription, invoices, and payment methods.');
    const { billing, billingLoading, fetchBilling } = usePaymentStore();
    const { addToast } = useToast();
    const [error, setError] = useState(null);

    const loadBilling = useCallback(async () => {
        try {
            setError(null);
            await fetchBilling();
        } catch (err) {
            setError(err);
            addToast(getApiErrorMessage(err, 'Failed to load billing data.'), 'error');
        }
    }, [fetchBilling, addToast]);

    useEffect(() => { loadBilling(); }, [loadBilling]);

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit v2.1 // Billing Terminal",
                status: "Payments Module",
                info: billingLoading ? 'Loading...' : 'Active'
            }}
            pageTitleLine1="Bill"
            pageTitleLine2="Ing"
            headerRightContent={/* ...live stats from billing state... */}
        >
            {billingLoading && <BillingSkeleton />}
            {error && <ErrorRetry onRetry={loadBilling} error={error} />}
            {!billingLoading && !error && billing && <BillingContent data={billing} />}
            {!billingLoading && !error && !billing && <EmptyState message="No billing data yet." />}
        </DashboardLayout>
    );
};
```

### Required State Quartet — Every Page Must Have:

1. **Loading state** → `<Skeleton />` shimmer (existing component)
2. **Error state** → Retry button + toast notification + Sentry capture
3. **Empty state** → Contextual message + CTA
4. **Data state** → Actual content rendered from API response

### CSS Migration Rules

| Inline Style | Replace With | Rationale |
|-------------|-------------|-----------|
| `'#E6E2D8'` | `var(--bg-beige)` | Design token |
| `'#111111'` | `var(--bg-dark)` | Design token |
| `'#000000'` | `var(--text-black)` or `var(--border-color)` | Design token |
| `'#F0F0F0'` | `var(--text-white)` | Design token |
| `"'Anton', sans-serif"` | `var(--font-display)` | Design token |
| `"'Bodoni Moda', serif"` | `var(--font-serif)` | Design token |
| `"'Inter', sans-serif"` | `var(--font-sans)` | Design token |
| `1px solid #000000` | `1px solid var(--border-color)` | Design token |

Extract inline styles into `src/pages/GrowthPages.css` using BEM naming, import as CSS module or global.

---

## 5. Step 4 — Security Requirements

### Per-Page Security Specifications

| Page | Threat | Mitigation |
|------|--------|------------|
| **BillingCenter** | PCI DSS scope — card data display | NEVER render full card numbers. Use Stripe Elements. Never store card data client-side. |
| **SubscriptionPlans** | Plan tampering via devtools | Validate plan selection server-side. Never trust client-side price. |
| **ReferralProgram** | Referral fraud (self-referral, bots) | Server-side IP + email domain + device fingerprint checks. Rate-limit referral creation. |
| **SponsoredPosts** | Budget manipulation | Server-side budget validation. Never trust client-side spend amounts. |
| **CRMPipeline** | Candidate PII exposure | Ensure `select_related` only returns fields the user is authorized to see. Mask email/phone on hover-only. |
| **RevenueDashboard** | Financial data leakage | ADMIN-only. Add `X-Content-Type-Options: nosniff`. No caching of financial data. |
| **AIJobWriter** | Prompt injection, XSS in generated JD | Sanitize all LLM output with DOMPurify before rendering. Never `dangerouslySetInnerHTML` raw AI text. |
| **InterviewScheduler** | Calendar data exposure | OAuth scopes must be minimal (read-only calendar). Never store OAuth tokens client-side. |
| **AIChatbot** | PII in chat messages, prompt injection | Server-side PII detection (regex for SSN, card numbers, emails). Strip PII before sending to LLM. Content moderation on responses. |
| **CompensationBenchmark** | Salary data scraping | Rate-limit queries. Require authentication. No bulk export. |
| **TalentSearch** | Candidate profile scraping | Paginate results (max 20). Rate-limit search. No full-profile data in list view. |
| **CompanyDirectory** | Competitive intelligence scraping | Rate-limit. Cache aggressively. Limit detail exposure to authenticated users. |
| **FeatureFlagAdmin** | Unauthorized flag mutation | ADMIN-only. Audit log every flag change. Require confirmation for production flags. |
| **PolicyManager** | XSS via rich text editor, policy tampering | **DOMPurify** on ALL rich text content before save AND before render. Sanitize on both sides. HMAC-sign policy versions. |

### Global Security Patterns

```jsx
// src/utils/sanitize.js — MUST be used on all user-generated and AI-generated content
import DOMPurify from 'dompurify';

export const sanitizeHTML = (dirty) => DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'p', 'br', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'a'],
    ALLOWED_ATTR: ['href', 'target', 'rel'],
    ALLOW_DATA_ATTR: false,
});

export const sanitizePlainText = (dirty) => DOMPurify.sanitize(dirty, { ALLOWED_TAGS: [] });
```

---

## 6. Step 5 — Accessibility Requirements (WCAG 2.1 AA)

**Every page MUST pass these checks before merge:**

### Mandatory Per-Page

| Requirement | Standard | How to Verify |
|-------------|----------|--------------|
| All interactive elements are keyboard-navigable | WCAG 2.1.1 | Tab through entire page, verify focus ring on every button/link/input |
| Focus management on modals/drawers | WCAG 2.4.3 | Opening a modal traps focus. Closing returns to trigger. |
| Color contrast ≥ 4.5:1 for text | WCAG 1.4.3 | Check `#000000` on `#E6E2D8` (passes: 13.5:1). Check `#F0F0F0` on `#111111` (passes: 15.3:1). |
| All images have `alt` text | WCAG 1.1.1 | No `<img>` without `alt`. Decorative images get `alt=""` + `aria-hidden="true"`. |
| Form inputs have visible labels | WCAG 1.3.1 | Every `<input>`/`<select>` has a `<label>` with `htmlFor` matching `id`. |
| Error messages are associated with inputs | WCAG 3.3.1 | Use `aria-describedby` linking input to error `<span>`. |
| ARIA landmarks | WCAG 1.3.1 | `DashboardLayout` provides `<main role="main">`. Pages must not duplicate. |
| Live regions for async updates | WCAG 4.1.3 | Toast notifications use `aria-live="polite"` (already in ToastContext). CRM card moves need `aria-live="assertive"`. |
| Skip to content | WCAG 2.4.1 | Already in `DashboardLayout`. Verify it works per page. |

### Page-Specific Accessibility

| Page | Specific Requirement |
|------|---------------------|
| **CRMPipeline** | Kanban columns MUST be navigable via arrow keys. Cards must have `role="listitem"`. Stage changes must be announced to screen readers via `aria-live`. |
| **AIJobWriter** | Tone slider needs `aria-valuemin`, `aria-valuemax`, `aria-valuenow`, `aria-label`. |
| **InterviewScheduler** | Calendar grid needs `role="grid"`, cells need `role="gridcell"`, navigate with arrow keys. |
| **AIChatbot** | Chat messages need `role="log"` with `aria-live="polite"`. Send button needs `aria-label`. |
| **FeatureFlagAdmin** | Toggle switches need `role="switch"` with `aria-checked`. Rollout slider needs ARIA value props. |
| **PolicyManager** | Rich text editor needs `role="textbox"` with `aria-multiline="true"` and `aria-label`. |
| **CompensationBenchmark** | Charts need `role="img"` with `aria-label` describing the data. Provide data table alternative. |
| **RevenueDashboard** | Cohort heatmap needs `aria-label` per cell. Provide text summary. |

### Dev-Time Enforcement

```jsx
// In main.jsx (dev only):
if (import.meta.env.DEV) {
    import('@axe-core/react').then(({ default: axe }) => {
        axe(React, ReactDOM, 1000);
    });
}
```

---

## 7. Step 6 — Input Validation & Sanitization

### Zod Schema Definitions

Create `src/utils/schemas.js`:

```js
import { z } from 'zod';

// BillingCenter — no user input (read-only view)

// SubscriptionPlans — plan selection
export const planSelectionSchema = z.object({
    planId: z.string().uuid(),
    interval: z.enum(['monthly', 'annual']),
    couponCode: z.string().max(50).optional(),
});

// ReferralProgram — create referral
export const referralSchema = z.object({
    refereeEmail: z.string().email().max(255),
});

// SponsoredPosts — boost campaign form
export const boostCampaignSchema = z.object({
    jobId: z.string().uuid(),
    dailyBudget: z.number().min(1).max(10000),
    durationDays: z.number().int().min(1).max(90),
    targetAudience: z.string().min(1).max(255),
});

// CRMPipeline — move candidate
export const moveCandidateSchema = z.object({
    candidateId: z.string().uuid(),
    stageId: z.string().uuid(),
});

// AIJobWriter — generate JD
export const jobDescriptionSchema = z.object({
    roleTitle: z.string().min(2).max(200).trim(),
    requirements: z.string().min(10).max(5000).trim(),
    tone: z.number().min(0).max(100),   // 0 = formal, 100 = casual
    checkBias: z.boolean(),
});

// InterviewScheduler — schedule interview
export const scheduleInterviewSchema = z.object({
    candidateId: z.string().uuid(),
    interviewerIds: z.array(z.string().uuid()).min(1),
    duration: z.number().int().min(15).max(480),  // minutes
    preferredDate: z.string().datetime().optional(),
});

// AIChatbot — send message
export const chatMessageSchema = z.object({
    message: z.string().min(1).max(2000).trim(),
});

// FeatureFlagAdmin — create/update flag
export const featureFlagSchema = z.object({
    key: z.string().regex(/^[a-z][a-z0-9_]*$/).min(2).max(100),
    name: z.string().min(2).max(200),
    rolloutPercentage: z.number().min(0).max(100),
    enabled: z.boolean(),
});

// PolicyManager — create/update policy
export const policySchema = z.object({
    title: z.string().min(5).max(300).trim(),
    type: z.enum(['terms_of_service', 'privacy_policy', 'cookie_policy', 'dpa', 'acceptable_use']),
    content: z.string().min(100).max(500000),  // Will be sanitized with DOMPurify
    effectiveDate: z.string().datetime(),
});

// CompensationBenchmark — search
export const compensationSearchSchema = z.object({
    roleTitle: z.string().min(2).max(200).trim(),
    location: z.string().max(200).optional(),
    experienceLevel: z.enum(['junior', 'mid', 'senior', 'lead', 'executive']).optional(),
});
```

### Validation Pattern in Components

```jsx
// EVERY form submission must validate BEFORE calling the API:
const handleSubmit = async () => {
    const parsed = boostCampaignSchema.safeParse(formData);
    if (!parsed.success) {
        const firstError = parsed.error.issues[0];
        addToast(firstError.message, 'error');
        setFieldErrors(parsed.error.flatten().fieldErrors);
        return;
    }
    // Only after validation passes:
    await paymentsService.createSponsoredCampaign(parsed.data);
};
```

---

## 8. Step 7 — Error Handling & Resilience

### The Four Error Categories

| Category | Example | Handling |
|----------|---------|----------|
| **Network errors** | Timeout, offline, DNS failure | Show "Connection lost" banner. Auto-retry with exponential backoff. |
| **Auth errors** | 401, 403 | 401 → silent refresh (already handled by interceptor). 403 → redirect to role-appropriate dashboard + toast. |
| **Validation errors** | 400 with field errors | Map server errors to form fields. Display inline. |
| **Server errors** | 500, 502, 503 | Show "Something went wrong" with retry button. Log to Sentry. |

### Per-Page Error Handling Contract

```jsx
// MANDATORY pattern for EVERY data-fetching page:
const [state, setState] = useState({ data: null, loading: true, error: null });

const fetchData = useCallback(async () => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
        const result = await someService.getData();
        setState({ data: result.data, loading: false, error: null });
    } catch (err) {
        setState(prev => ({ ...prev, loading: false, error: err }));
        addToast(getApiErrorMessage(err, 'Failed to load data.'), 'error');
        // Sentry captures via the global axios interceptor
    }
}, [addToast]);

useEffect(() => { fetchData(); }, [fetchData]);

// CLEANUP: Prevent state updates on unmounted components
useEffect(() => {
    const controller = new AbortController();
    fetchData(controller.signal);
    return () => controller.abort();
}, [fetchData]);
```

### Retry Strategy

```jsx
// For mutation-heavy pages (CRM, SponsoredPosts, PolicyManager):
const retryWithBackoff = async (fn, maxRetries = 3) => {
    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            return await fn();
        } catch (err) {
            if (attempt === maxRetries - 1) throw err;
            if (err.response?.status >= 400 && err.response?.status < 500) throw err; // Don't retry client errors
            await new Promise(r => setTimeout(r, Math.pow(2, attempt) * 1000));
        }
    }
};
```

### Optimistic Updates (CRM Pipeline ONLY)

```jsx
// CRM card drag-and-drop MUST use optimistic update:
const moveCard = async (candidateId, newStageId) => {
    const previousState = candidates; // Save rollback state
    // Optimistic: update UI immediately
    setCandidates(prev => moveToStage(prev, candidateId, newStageId));
    try {
        await paymentsService.moveCandidate(candidateId, newStageId);
    } catch (err) {
        // Rollback on failure
        setCandidates(previousState);
        addToast('Failed to move candidate. Reverted.', 'error');
    }
};
```

---

## 9. Step 8 — State Management & API Binding

### Store-to-Page Mapping

| Page | Store | Mount Actions | Cleanup Required |
|------|-------|---------------|------------------|
| BillingCenter | `usePaymentStore` | `fetchBilling()` | No |
| SubscriptionPlans | `usePaymentStore` | `fetchPlans(audience)` | No |
| ReferralProgram | `usePaymentStore` | `fetchReferralProgram()` + `fetchReferralStats()` + `fetchReferrals()` + `fetchRewards()` | No |
| SponsoredPosts | `usePaymentStore` | `fetchCampaigns()` | No |
| CRMPipeline | `usePaymentStore` | `fetchPipelines()` → then `fetchCandidates(pipelineId)` | **Yes — close WebSocket** |
| RevenueDashboard | `usePaymentStore` | `fetchRevenueMetrics()` + `fetchRevenueTrend(12)` | No |
| AIJobWriter | **New `useAIStore`** | None (user-initiated) | Cancel pending generation |
| InterviewScheduler | **New `useAIStore`** | None (user-initiated) | Cancel pending schedule |
| AIChatbot | **New `useAIStore`** | Load chat history from sessionStorage | **Yes — clear stale messages** |
| CompensationBenchmark | **New `useAIStore`** | None (user-initiated search) | Cancel pending request |
| TalentSearch | `useSearchStore` | None (user-initiated search) | Clear search results on unmount |
| CompanyDirectory | `useSearchStore` (extend) | `fetchFeaturedEmployers()` | No |
| FeatureFlagAdmin | Direct service calls | `intelligenceService.getFeatureFlags()` | No |
| PolicyManager | Direct service calls | `complianceService.getPolicies()` | No |

### New Store: `src/store/aiStore.js`

```js
import { create } from 'zustand';
import { intelligenceService, getApiErrorMessage } from '../services/api';

export const useAIStore = create((set, get) => ({
    // ── AI Job Writer ──────────────────────────────────────────────
    generatedJD: null,
    jdLoading: false,
    jdError: null,
    generateJobDescription: async (data) => {
        set({ jdLoading: true, jdError: null });
        try {
            const { data: result } = await intelligenceService.generateJobDescription(data);
            set({ generatedJD: result, jdLoading: false });
            return result;
        } catch (err) {
            set({ jdLoading: false, jdError: getApiErrorMessage(err) });
            throw err;
        }
    },

    // ── Interview Scheduler ────────────────────────────────────────
    interviewSlots: [],
    slotsLoading: false,
    slotsError: null,
    fetchInterviewSlots: async (data) => {
        set({ slotsLoading: true, slotsError: null });
        try {
            const { data: result } = await intelligenceService.scheduleInterviews(data);
            set({ interviewSlots: result.slots || [], slotsLoading: false });
        } catch (err) {
            set({ slotsLoading: false, slotsError: getApiErrorMessage(err) });
            throw err;
        }
    },

    // ── AI Chatbot ─────────────────────────────────────────────────
    chatHistory: [],
    chatLoading: false,
    sendChatMessage: async (message) => {
        const userMsg = { role: 'user', content: message, timestamp: Date.now() };
        set(state => ({ chatHistory: [...state.chatHistory, userMsg], chatLoading: true }));
        try {
            const { data } = await intelligenceService.chatWithAI(message, {});
            const assistantMsg = { role: 'assistant', content: data.reply, timestamp: Date.now() };
            set(state => ({
                chatHistory: [...state.chatHistory, assistantMsg],
                chatLoading: false,
            }));
        } catch (err) {
            const errorMsg = { role: 'error', content: 'Failed to get response. Try again.', timestamp: Date.now() };
            set(state => ({
                chatHistory: [...state.chatHistory, errorMsg],
                chatLoading: false,
            }));
        }
    },
    clearChat: () => set({ chatHistory: [] }),

    // ── Compensation Benchmark ─────────────────────────────────────
    compensationData: null,
    compensationLoading: false,
    compensationError: null,
    fetchCompensation: async (role, location) => {
        set({ compensationLoading: true, compensationError: null });
        try {
            const { data } = await intelligenceService.getCompensationBenchmark(role, location);
            set({ compensationData: data, compensationLoading: false });
        } catch (err) {
            set({ compensationLoading: false, compensationError: getApiErrorMessage(err) });
            throw err;
        }
    },
}));
```

### New API Endpoints to Add in `services/api.js`

```js
// Add to intelligenceService object:
getCompensationBenchmark: (role, location) =>
    api.get('/intelligence/ai/compensation/', { params: { role, location } }),
chatWithAI: (message, context) =>
    api.post('/intelligence/ai/chat/', { message, context }),
updateFeatureFlag: (id, data) =>
    api.patch(`/intelligence/experiments/flags/${id}/`, data),
createFeatureFlag: (data) =>
    api.post('/intelligence/experiments/flags/', data),
deleteFeatureFlag: (id) =>
    api.delete(`/intelligence/experiments/flags/${id}/`),

// Add new searchService methods or create companyService:
getCompanyDirectory: (params) =>
    api.get('/search/companies/', { params }),
getFeaturedEmployers: () =>
    api.get('/search/companies/featured/'),
```

---

## 10. Step 9 — Performance Budgets

### Bundle Size Budget

| Chunk | Max Size (gzip) | Current Estimate | Action if Over |
|-------|----------------|------------------|----------------|
| Each lazy page chunk | ≤ 30 KB | ~15–25 KB | Extract shared styles to CSS, tree-shake imports |
| `aiStore.js` | ≤ 5 KB | ~3 KB | Acceptable |
| `GrowthPages.css` | ≤ 10 KB | ~6 KB | Acceptable |
| Total JS increase (14 pages) | ≤ 200 KB | ~180 KB | Lazy-loaded, so only affects per-page load |

### Runtime Performance

| Metric | Target | How to Achieve |
|--------|--------|----------------|
| LCP (per page) | ≤ 2.5s | Skeleton loading, no layout shift |
| FID | ≤ 100ms | No heavy computation on main thread |
| CLS | ≤ 0.1 | Fixed-dimension skeletons matching final layout |
| TTI | ≤ 3.5s | Code-split per page, defer non-critical data |

### Data Fetching Optimization

```jsx
// CRMPipeline — fetch all stage data in PARALLEL, not sequentially:
useEffect(() => {
    const loadPipeline = async () => {
        const pipeline = await paymentsService.getPipeline(activePipelineId);
        // Fetch all stages in parallel:
        const stageData = await Promise.allSettled(
            pipeline.stages.map(stage =>
                paymentsService.getCandidates(activePipelineId, stage.id)
            )
        );
        // Handle partial failures:
        stageData.forEach((result, idx) => {
            if (result.status === 'rejected') {
                console.error(`Failed to load stage ${pipeline.stages[idx].name}`);
            }
        });
    };
    loadPipeline();
}, [activePipelineId]);
```

### N+1 Prevention (Backend)

Every list endpoint consumed by these pages must use `select_related` / `prefetch_related`:

```python
# WRONG:
candidates = TalentPoolCandidate.objects.filter(pipeline=pipeline)
# Each access to candidate.user triggers a separate query

# RIGHT:
candidates = TalentPoolCandidate.objects.filter(
    pipeline=pipeline
).select_related('user', 'user__talentprofile').prefetch_related('tags')
```

---

## 11. Step 10 — AIChatbot Overlay

`AIChatbot` is a **floating overlay**, not a routed page. It renders on all authenticated pages.

### Integration Point

In `App.jsx`, inside `AppRoutes()`:

```jsx
import { useAuthStore } from './store/authStore';

// At the END of AppRoutes, AFTER <Routes>:
const { isAuthenticated } = useAuthStore();

return (
    <Suspense fallback={<PageLoader />}>
        <Routes>{/* ... all routes ... */}</Routes>
        {isAuthenticated && (
            <ErrorBoundary fallback={null}>  {/* Silent fail — chatbot is non-critical */}
                <Suspense fallback={null}>
                    <AIChatbot />
                </Suspense>
            </ErrorBoundary>
        )}
    </Suspense>
);
```

### AIChatbot Security Requirements

- **PII Detection**: Before sending to LLM, regex-strip SSN patterns, credit card numbers, phone numbers
- **Content Moderation**: Sanitize all AI responses with `DOMPurify.sanitize()` before rendering
- **Rate Limiting**: Max 10 messages/minute client-side, enforced server-side via `throttle_scope`
- **Session Isolation**: Chat history stored in component state or sessionStorage — NOT persisted to backend
- **Escalation**: "Talk to Human" button creates a HelpDesk ticket, does NOT expose chat to human directly

---

## 12. Step 11 — Real-Time Features

### CRM Pipeline WebSocket

The existing `src/services/websocket.js` WebSocket manager supports auto-reconnect and heartbeat. Connect it for CRM:

```jsx
// In CRMPipeline.jsx:
import { useEffect } from 'react';
import websocketManager from '../services/websocket';

useEffect(() => {
    const unsubscribe = websocketManager.subscribe('pipeline_update', (data) => {
        if (data.pipeline_id === activePipelineId) {
            // Update candidate position in local state
            updateCandidateStage(data.candidate_id, data.new_stage);
        }
    });
    return () => unsubscribe();
}, [activePipelineId]);
```

### Backend Consumer Required

```python
# realtime/consumers.py — new consumer for pipeline events:
class PipelineConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.pipeline_id = self.scope['url_route']['kwargs']['pipeline_id']
        # Permission check: user must be COMPANY/ADMIN and own the pipeline
        await self.channel_layer.group_add(f'pipeline_{self.pipeline_id}', self.channel_name)
        await self.accept()
```

---

## 13. Step 12 — Backend Route Verification

| Frontend Call | Backend URL | Status |
|--------------|-------------|--------|
| `paymentsService.getBillingOverview()` | `/api/payments/billing/` | 🔴 **Blocked — needs migration** |
| `paymentsService.getPlans()` | `/api/payments/plans/` | 🔴 **Blocked — needs migration** |
| `paymentsService.createCheckoutSession()` | `/api/payments/create-checkout-session/` | 🔴 **Blocked — needs migration** |
| `paymentsService.createPortalSession()` | `/api/payments/customer-portal/` | 🔴 **Blocked — needs migration** |
| `paymentsService.downloadInvoice(id)` | `/api/payments/invoice/:id/` | 🔴 **Blocked — needs migration** |
| `paymentsService.getReferralProgram()` | `/api/payments/referrals/program/` | 🔴 **Blocked — needs migration** |
| `paymentsService.getSponsoredCampaigns()` | `/api/payments/sponsored/` | 🔴 **Blocked — needs migration** |
| `paymentsService.getPipelines()` | `/api/payments/pipelines/` | 🔴 **Blocked — needs migration** |
| `paymentsService.getRevenueDashboard()` | `/api/payments/revenue/dashboard/` | 🔴 **Blocked — needs migration** |
| `intelligenceService.generateJobDescription()` | `/api/intelligence/ai/job-description/` | 🟡 **Route exists, but view is scaffold — zero LLM calls** |
| `intelligenceService.scheduleInterviews()` | `/api/intelligence/ai/schedule-interviews/` | 🔴 **Route exists, view is empty — zero calendar integration** |
| `intelligenceService.getFeatureFlags()` | `/api/intelligence/experiments/flags/` | ✅ Works (PostHog SDK) |
| `complianceService.getPolicies()` | `/api/compliance/policies/` | ✅ Works |
| `intelligenceService.getCompensationBenchmark()` | `/api/intelligence/ai/compensation/` | 🔴 **Does not exist** |
| `intelligenceService.chatWithAI()` | `/api/intelligence/ai/chat/` | 🔴 **Does not exist** |
| `searchService.getCompanyDirectory()` | `/api/search/companies/` | 🔴 **Does not exist** |

---

## 14. Page-by-Page Enterprise Binding Spec

| # | Page | Route | Roles | Store | Validation | A11y Critical | Security Critical |
|---|------|-------|-------|-------|------------|--------------|-------------------|
| 1 | BillingCenter | `/billing` | TALENT, COMPANY | `paymentStore` | None (read-only) | Data tables | PCI — use Stripe Elements only |
| 2 | SubscriptionPlans | `/plans` | All auth | `paymentStore` | `planSelectionSchema` | Plan comparison grid | Server-side price validation |
| 3 | ReferralProgram | `/referrals` | All auth | `paymentStore` | `referralSchema` | Copy button a11y | Anti-fraud checks |
| 4 | SponsoredPosts | `/company/sponsored` | COMPANY, ADMIN | `paymentStore` | `boostCampaignSchema` | Form inputs | Budget tampering |
| 5 | CRMPipeline | `/company/crm` | COMPANY, ADMIN | `paymentStore` | `moveCandidateSchema` | Keyboard Kanban nav | PII in candidate cards |
| 6 | RevenueDashboard | `/admin/revenue` | ADMIN | `paymentStore` | None (read-only) | Chart descriptions | Financial data — no cache |
| 7 | AIJobWriter | `/company/ai-job-writer` | COMPANY, ADMIN | `aiStore` | `jobDescriptionSchema` | Slider ARIA | Sanitize LLM output |
| 8 | InterviewScheduler | `/company/interviews` | COMPANY, ADMIN | `aiStore` | `scheduleInterviewSchema` | Calendar grid nav | OAuth token security |
| 9 | AIChatbot | Overlay (global) | All auth | `aiStore` | `chatMessageSchema` | `role="log"` | PII stripping + moderation |
| 10 | CompensationBenchmark | `/compensation` | All auth | `aiStore` | `compensationSearchSchema` | Chart alt text | Anti-scraping |
| 11 | TalentSearch | `/talent-search` | COMPANY, ADMIN | `searchStore` | None | Filter checkboxes | Anti-scraping |
| 12 | CompanyDirectory | `/companies` | All auth | `searchStore` | None | Grid navigation | Anti-scraping |
| 13 | FeatureFlagAdmin | `/admin/feature-flags` | ADMIN | Direct | `featureFlagSchema` | Toggle `role="switch"` | Audit every mutation |
| 14 | PolicyManager | `/admin/policies` | ADMIN | Direct | `policySchema` | Rich text ARIA | DOMPurify mandatory |

---

## 15. Integration Acceptance Criteria

**A page is NOT ready for merge until ALL of these pass:**

- [ ] Wrapped in `<DashboardLayout>` with correct `tapeBarProps`, title lines, and header content
- [ ] `usePageTitle()` sets document title + meta description
- [ ] Registered in `App.jsx` with `<ProtectedRoute>` + `<ErrorBoundary>`
- [ ] Added to `Sidebar.jsx` nav for appropriate roles (behind feature flag initially)
- [ ] All inline styles replaced with CSS custom properties / CSS classes
- [ ] Loading state shows `<Skeleton />` with correct dimensions
- [ ] Error state shows retry button + fires toast + logs to Sentry
- [ ] Empty state shows contextual message + CTA
- [ ] All user inputs validated with Zod schema before API call
- [ ] All form fields have `<label htmlFor>`, `aria-describedby` for errors
- [ ] All interactive elements keyboard-navigable with visible focus ring
- [ ] No `dangerouslySetInnerHTML` without `DOMPurify.sanitize()`
- [ ] API calls use `AbortController` for cleanup on unmount
- [ ] Page passes `axe-core` with zero violations
- [ ] Vitest component test exists (render, loading, error, data states)
- [ ] Bundle chunk size ≤ 30 KB gzipped
