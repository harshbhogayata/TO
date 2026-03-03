import { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import { ToastProvider, useToast } from './contexts/ToastContext';

// ── Lightweight global loading fallback ──────────────────────────────────────
const PageLoader = () => (
    <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', width: '100vw',
        background: 'var(--bg-cream, #f5f0eb)', color: 'var(--text-black, #1a1a1a)',
        fontFamily: 'var(--font-display, "Anton", sans-serif)',
        fontSize: 'clamp(14px, 3vw, 18px)', letterSpacing: '2px', textTransform: 'uppercase',
    }}>
        Loading…
    </div>
);

// ── Lazy-loaded pages (code-split at route level) ────────────────────────────
// Public
const Home = lazy(() => import('./pages/Home'));
const AuthPage = lazy(() => import('./pages/AuthPage'));
const Pricing = lazy(() => import('./pages/Pricing'));
const About = lazy(() => import('./pages/About'));
const HelpDesk = lazy(() => import('./pages/HelpDesk'));
const NotFound = lazy(() => import('./pages/NotFound'));
const PasswordRecovery = lazy(() => import('./pages/PasswordRecovery'));
const PaymentSuccess = lazy(() => import('./pages/PaymentSuccess'));
const PaymentCancel = lazy(() => import('./pages/PaymentCancel'));
const CompanyRegistration = lazy(() => import('./pages/CompanyRegistration'));
const UserRegistration = lazy(() => import('./pages/UserRegistration'));
const Blog = lazy(() => import('./pages/Blog'));
const Terms = lazy(() => import('./pages/Terms'));
const Privacy = lazy(() => import('./pages/Privacy'));
const JobDetail = lazy(() => import('./pages/JobDetail'));
const SearchPage = lazy(() => import('./pages/SearchPage'));
const VerifyEmail = lazy(() => import('./pages/VerifyEmail'));

// Protected — Talent
const UserDashboard = lazy(() => import('./pages/UserDashboard'));
const JobBoard = lazy(() => import('./pages/JobBoard'));
const SkillHub = lazy(() => import('./pages/SkillHub'));
const UserProfile = lazy(() => import('./pages/UserProfile'));
const MyApplications = lazy(() => import('./pages/MyApplications'));
const SavedJobs = lazy(() => import('./pages/SavedJobs'));

// Protected — Company
const CompanyDashboard = lazy(() => import('./pages/CompanyDashboard'));
const PostJob = lazy(() => import('./pages/PostJob'));
const CompanyProfilePage = lazy(() => import('./pages/CompanyProfile'));
const ApplicantReview = lazy(() => import('./pages/ApplicantReview'));

// Protected — Admin
const AdminConsole = lazy(() => import('./pages/AdminConsole'));
const AdminAnalytics = lazy(() => import('./pages/AdminAnalytics'));

// Protected — Intelligence
const RecommendedJobs = lazy(() => import('./pages/RecommendedJobs'));
const ResumeParser = lazy(() => import('./pages/ResumeParser'));
const CompanyAnalytics = lazy(() => import('./pages/CompanyAnalytics'));
const SkillTaxonomy = lazy(() => import('./pages/SkillTaxonomy'));

// Protected — Shared
const Settings = lazy(() => import('./pages/Settings'));
const Inbox = lazy(() => import('./pages/Inbox'));
const Notifications = lazy(() => import('./pages/Notifications'));

// Protected — Compliance
const PrivacyCenter = lazy(() => import('./pages/PrivacyCenter'));
const TeamManagement = lazy(() => import('./pages/TeamManagement'));
const AuditLog = lazy(() => import('./pages/AuditLog'));
const TeamInvite = lazy(() => import('./pages/TeamInvite'));

function AppRoutes() {
    const { addToast } = useToast();

    useEffect(() => {
        const handler = () => {
            addToast('Session expired — please log in again.', 'error');
        };
        window.addEventListener('talentorbit:session-expired', handler);
        return () => window.removeEventListener('talentorbit:session-expired', handler);
    }, [addToast]);

    return (
        <Suspense fallback={<PageLoader />}>
            <Routes>
                    {/* ── Public ───────────────────────────────────── */}
                    <Route path="/" element={<Home />} />
                    <Route path="/auth" element={<AuthPage />} />
                    <Route path="/pricing" element={<Pricing />} />
                    <Route path="/about" element={<About />} />
                    <Route path="/support" element={<HelpDesk />} />
                    <Route path="/recovery" element={<PasswordRecovery />} />
                    <Route path="/register/company" element={<CompanyRegistration />} />
                    <Route path="/register/user" element={<UserRegistration />} />
                    <Route path="/blog" element={<Blog />} />
                    <Route path="/terms" element={<Terms />} />
                    <Route path="/privacy" element={<Privacy />} />
                    <Route path="/jobs/:id" element={<JobDetail />} />
                    <Route path="/search" element={<SearchPage />} />
                    <Route path="/payment/success" element={<PaymentSuccess />} />
                    <Route path="/payment/cancel" element={<PaymentCancel />} />
                    <Route path="/verify-email" element={<VerifyEmail />} />

                    {/* ── Talent-only routes ────────────────────────── */}
                    <Route path="/user" element={
                        <ProtectedRoute allowedRoles={['TALENT']}>
                            <UserDashboard />
                        </ProtectedRoute>
                    } />
                    <Route path="/jobs" element={
                        <ProtectedRoute allowedRoles={['TALENT', 'COMPANY', 'ADMIN']}>
                            <JobBoard />
                        </ProtectedRoute>
                    } />
                    <Route path="/skills" element={
                        <ProtectedRoute allowedRoles={['TALENT']}>
                            <SkillHub />
                        </ProtectedRoute>
                    } />
                    <Route path="/profile" element={
                        <ProtectedRoute allowedRoles={['TALENT']}>
                            <UserProfile />
                        </ProtectedRoute>
                    } />
                    <Route path="/applications" element={
                        <ProtectedRoute allowedRoles={['TALENT', 'ADMIN']}>
                            <MyApplications />
                        </ProtectedRoute>
                    } />
                    <Route path="/saved" element={
                        <ProtectedRoute allowedRoles={['TALENT', 'ADMIN']}>
                            <SavedJobs />
                        </ProtectedRoute>
                    } />
                    <Route path="/recommendations" element={
                        <ProtectedRoute allowedRoles={['TALENT']}>
                            <RecommendedJobs />
                        </ProtectedRoute>
                    } />
                    <Route path="/resume-parser" element={
                        <ProtectedRoute allowedRoles={['TALENT']}>
                            <ResumeParser />
                        </ProtectedRoute>
                    } />

                    {/* ── Company-only routes ───────────────────────── */}
                    <Route path="/company" element={
                        <ProtectedRoute allowedRoles={['COMPANY']}>
                            <CompanyDashboard />
                        </ProtectedRoute>
                    } />
                    <Route path="/company/post-job" element={
                        <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
                            <PostJob />
                        </ProtectedRoute>
                    } />
                    <Route path="/company/profile" element={
                        <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
                            <CompanyProfilePage />
                        </ProtectedRoute>
                    } />
                    <Route path="/company/applicants/:jobId" element={
                        <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
                            <ApplicantReview />
                        </ProtectedRoute>
                    } />

                    {/* ── Company analytics ──────────────────────────── */}
                    <Route path="/company/analytics" element={
                        <ProtectedRoute allowedRoles={['COMPANY']}>
                            <CompanyAnalytics />
                        </ProtectedRoute>
                    } />

                    {/* ── Admin-only routes ─────────────────────────────── */}
                    <Route path="/admin" element={
                        <ProtectedRoute allowedRoles={['ADMIN']}>
                            <AdminConsole />
                        </ProtectedRoute>
                    } />
                    <Route path="/admin/analytics" element={
                        <ProtectedRoute allowedRoles={['ADMIN']}>
                            <AdminAnalytics />
                        </ProtectedRoute>
                    } />

                    {/* ── Compliance / Trust routes ──────────────────── */}
                    <Route path="/privacy-center" element={
                        <ProtectedRoute>
                            <PrivacyCenter />
                        </ProtectedRoute>
                    } />
                    <Route path="/company/team" element={
                        <ProtectedRoute allowedRoles={['COMPANY']}>
                            <TeamManagement />
                        </ProtectedRoute>
                    } />
                    <Route path="/admin/audit-log" element={
                        <ProtectedRoute allowedRoles={['ADMIN']}>
                            <AuditLog />
                        </ProtectedRoute>
                    } />
                    <Route path="/team/invite/:token" element={<TeamInvite />} />

                    {/* ── Shared authenticated routes ───────────────── */}
                    <Route path="/settings" element={
                        <ProtectedRoute>
                            <Settings />
                        </ProtectedRoute>
                    } />
                    <Route path="/inbox" element={
                        <ProtectedRoute>
                            <Inbox />
                        </ProtectedRoute>
                    } />
                    <Route path="/notifications" element={
                        <ProtectedRoute>
                            <Notifications />
                        </ProtectedRoute>
                    } />
                    <Route path="/skills/taxonomy" element={
                        <ProtectedRoute>
                            <SkillTaxonomy />
                        </ProtectedRoute>
                    } />

                    <Route path="*" element={<NotFound />} />
            </Routes>
        </Suspense>
    );
}

function App() {
    return (
        <ToastProvider>
            <BrowserRouter>
                <AppRoutes />
            </BrowserRouter>
        </ToastProvider>
    );
}

export default App;
