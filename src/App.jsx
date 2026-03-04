import { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import ErrorBoundary from './components/ErrorBoundary';
import { ToastProvider, useToast } from './contexts/ToastContext';
import { useAuthStore } from './store/authStore';

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

// Protected — Courses / LMS
const CourseCatalog = lazy(() => import('./pages/CourseCatalog'));
const CourseDetail = lazy(() => import('./pages/CourseDetail'));
const LessonPlayer = lazy(() => import('./pages/LessonPlayer'));
const MyLearning = lazy(() => import('./pages/MyLearning'));
const CourseProgress = lazy(() => import('./pages/CourseProgress'));
const CertificateView = lazy(() => import('./pages/CertificateView'));
const CertificateVerify = lazy(() => import('./pages/CertificateVerify'));

// Protected — Assessments
const AssessmentCatalog = lazy(() => import('./pages/AssessmentCatalog'));
const AssessmentDetail = lazy(() => import('./pages/AssessmentDetail'));
const AssessmentPlayer = lazy(() => import('./pages/AssessmentPlayer'));
const AssessmentResults = lazy(() => import('./pages/AssessmentResults'));
const MyAssessments = lazy(() => import('./pages/MyAssessments'));
const SkillBadgeProfile = lazy(() => import('./pages/SkillBadgeProfile'));
const BadgeVerify = lazy(() => import('./pages/BadgeVerify'));
const CompanyAssessmentDashboard = lazy(() => import('./pages/CompanyAssessmentDashboard'));

// Protected — Reviews & Question Banks
const CompanyReviews = lazy(() => import('./pages/CompanyReviews'));
const WriteReview = lazy(() => import('./pages/WriteReview'));
const QuestionBankManager = lazy(() => import('./pages/QuestionBankManager'));

// Protected — Developer Platform
const DeveloperPortal = lazy(() => import('./pages/DeveloperPortal'));
const APIKeysManager = lazy(() => import('./pages/APIKeysManager'));
const WebhookManager = lazy(() => import('./pages/WebhookManager'));
const OAuthAppManager = lazy(() => import('./pages/OAuthAppManager'));

// Protected — Compliance
const PrivacyCenter = lazy(() => import('./pages/PrivacyCenter'));
const TeamManagement = lazy(() => import('./pages/TeamManagement'));
const AuditLog = lazy(() => import('./pages/AuditLog'));
const TeamInvite = lazy(() => import('./pages/TeamInvite'));

// Protected — Revenue & Growth (WS4)
const BillingCenter = lazy(() => import(/* webpackChunkName: "billing" */ './pages/BillingCenter'));
const SubscriptionPlans = lazy(() => import(/* webpackChunkName: "plans" */ './pages/SubscriptionPlans'));
const ReferralProgram = lazy(() => import(/* webpackChunkName: "referrals" */ './pages/ReferralProgram'));
const SponsoredPosts = lazy(() => import(/* webpackChunkName: "sponsored" */ './pages/SponsoredPosts'));
const CRMPipeline = lazy(() => import(/* webpackChunkName: "crm" */ './pages/CRMPipeline'));
const RevenueDashboard = lazy(() => import(/* webpackChunkName: "revenue" */ './pages/RevenueDashboard'));

// Protected — AI/ML Platform (WS5)
const AIJobWriter = lazy(() => import(/* webpackChunkName: "ai-writer" */ './pages/AIJobWriter'));
const InterviewScheduler = lazy(() => import(/* webpackChunkName: "interviews" */ './pages/InterviewScheduler'));
const CompensationBenchmark = lazy(() => import(/* webpackChunkName: "compensation" */ './pages/CompensationBenchmark'));

// Protected — Utility / Discovery
const TalentSearch = lazy(() => import(/* webpackChunkName: "talent-search" */ './pages/TalentSearch'));
const CompanyDirectory = lazy(() => import(/* webpackChunkName: "company-dir" */ './pages/CompanyDirectory'));

// Protected — Admin Operations
const FeatureFlagAdmin = lazy(() => import(/* webpackChunkName: "flags" */ './pages/FeatureFlagAdmin'));
const PolicyManager = lazy(() => import(/* webpackChunkName: "policies" */ './pages/PolicyManager'));

// Global overlay — AI Chatbot (not a route)
const AIChatbot = lazy(() => import(/* webpackChunkName: "chatbot" */ './pages/AIChatbot'));

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

                    {/* ── Courses / LMS routes ──────────────────────── */}
                    <Route path="/courses" element={
                        <ProtectedRoute allowedRoles={['TALENT', 'COMPANY', 'ADMIN']}>
                            <CourseCatalog />
                        </ProtectedRoute>
                    } />
                    <Route path="/courses/:id" element={
                        <ProtectedRoute allowedRoles={['TALENT', 'COMPANY', 'ADMIN']}>
                            <CourseDetail />
                        </ProtectedRoute>
                    } />
                    <Route path="/courses/:courseId/lessons/:lessonId" element={
                        <ProtectedRoute allowedRoles={['TALENT']}>
                            <LessonPlayer />
                        </ProtectedRoute>
                    } />
                    <Route path="/courses/:courseId/progress" element={
                        <ProtectedRoute allowedRoles={['TALENT']}>
                            <CourseProgress />
                        </ProtectedRoute>
                    } />
                    <Route path="/my-learning" element={
                        <ProtectedRoute allowedRoles={['TALENT']}>
                            <MyLearning />
                        </ProtectedRoute>
                    } />
                    <Route path="/certificates/:certId" element={
                        <ProtectedRoute allowedRoles={['TALENT']}>
                            <CertificateView />
                        </ProtectedRoute>
                    } />
                    <Route path="/certificates/verify/:certificateId" element={<CertificateVerify />} />

                    {/* ── Assessments routes ────────────────────────── */}
                    <Route path="/assessments" element={
                        <ProtectedRoute allowedRoles={['TALENT', 'COMPANY', 'ADMIN']}>
                            <AssessmentCatalog />
                        </ProtectedRoute>
                    } />
                    <Route path="/assessments/:id" element={
                        <ProtectedRoute allowedRoles={['TALENT', 'COMPANY', 'ADMIN']}>
                            <AssessmentDetail />
                        </ProtectedRoute>
                    } />
                    <Route path="/assessments/:assessmentId/attempt/:attemptId" element={
                        <ProtectedRoute allowedRoles={['TALENT']}>
                            <AssessmentPlayer />
                        </ProtectedRoute>
                    } />
                    <Route path="/assessments/:assessmentId/results/:resultId" element={
                        <ProtectedRoute allowedRoles={['TALENT', 'COMPANY', 'ADMIN']}>
                            <AssessmentResults />
                        </ProtectedRoute>
                    } />
                    <Route path="/my-assessments" element={
                        <ProtectedRoute allowedRoles={['TALENT']}>
                            <MyAssessments />
                        </ProtectedRoute>
                    } />
                    <Route path="/badges" element={
                        <ProtectedRoute allowedRoles={['TALENT']}>
                            <SkillBadgeProfile />
                        </ProtectedRoute>
                    } />
                    <Route path="/badges/verify/:badgeId" element={<BadgeVerify />} />
                    <Route path="/company/assessments" element={
                        <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
                            <CompanyAssessmentDashboard />
                        </ProtectedRoute>
                    } />
                    <Route path="/company/question-banks" element={
                        <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
                            <QuestionBankManager />
                        </ProtectedRoute>
                    } />

                    {/* ── Reviews routes ──────────────────────────────── */}
                    <Route path="/reviews/:companyId" element={
                        <ProtectedRoute allowedRoles={['TALENT', 'COMPANY', 'ADMIN']}>
                            <CompanyReviews />
                        </ProtectedRoute>
                    } />
                    <Route path="/reviews/:companyId/write" element={
                        <ProtectedRoute allowedRoles={['TALENT']}>
                            <WriteReview />
                        </ProtectedRoute>
                    } />

                    {/* ── Developer Platform routes ──────────────────── */}
                    <Route path="/company/developer" element={
                        <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
                            <DeveloperPortal />
                        </ProtectedRoute>
                    } />
                    <Route path="/company/api-keys" element={
                        <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
                            <APIKeysManager />
                        </ProtectedRoute>
                    } />
                    <Route path="/company/webhooks" element={
                        <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
                            <WebhookManager />
                        </ProtectedRoute>
                    } />
                    <Route path="/company/oauth-apps" element={
                        <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
                            <OAuthAppManager />
                        </ProtectedRoute>
                    } />

                    {/* ── Compliance / Trust routes (continued) ──────── */}
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

                    {/* ── Revenue & Growth (WS4) ──────────────────── */}
                    <Route path="/billing" element={
                        <ProtectedRoute allowedRoles={['TALENT', 'COMPANY']}>
                            <ErrorBoundary><BillingCenter /></ErrorBoundary>
                        </ProtectedRoute>
                    } />
                    <Route path="/plans" element={
                        <ProtectedRoute>
                            <ErrorBoundary><SubscriptionPlans /></ErrorBoundary>
                        </ProtectedRoute>
                    } />
                    <Route path="/referrals" element={
                        <ProtectedRoute>
                            <ErrorBoundary><ReferralProgram /></ErrorBoundary>
                        </ProtectedRoute>
                    } />
                    <Route path="/company/sponsored" element={
                        <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
                            <ErrorBoundary><SponsoredPosts /></ErrorBoundary>
                        </ProtectedRoute>
                    } />
                    <Route path="/company/crm" element={
                        <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
                            <ErrorBoundary><CRMPipeline /></ErrorBoundary>
                        </ProtectedRoute>
                    } />
                    <Route path="/admin/revenue" element={
                        <ProtectedRoute allowedRoles={['ADMIN']}>
                            <ErrorBoundary><RevenueDashboard /></ErrorBoundary>
                        </ProtectedRoute>
                    } />

                    {/* ── AI/ML Platform (WS5) ────────────────────── */}
                    <Route path="/company/ai-job-writer" element={
                        <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
                            <ErrorBoundary><AIJobWriter /></ErrorBoundary>
                        </ProtectedRoute>
                    } />
                    <Route path="/company/interviews" element={
                        <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
                            <ErrorBoundary><InterviewScheduler /></ErrorBoundary>
                        </ProtectedRoute>
                    } />
                    <Route path="/compensation" element={
                        <ProtectedRoute allowedRoles={['TALENT', 'COMPANY', 'ADMIN']}>
                            <ErrorBoundary><CompensationBenchmark /></ErrorBoundary>
                        </ProtectedRoute>
                    } />

                    {/* ── Utility / Discovery ──────────────────────── */}
                    <Route path="/talent-search" element={
                        <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
                            <ErrorBoundary><TalentSearch /></ErrorBoundary>
                        </ProtectedRoute>
                    } />
                    <Route path="/companies" element={
                        <ProtectedRoute>
                            <ErrorBoundary><CompanyDirectory /></ErrorBoundary>
                        </ProtectedRoute>
                    } />

                    {/* ── Admin Operations ─────────────────────────── */}
                    <Route path="/admin/feature-flags" element={
                        <ProtectedRoute allowedRoles={['ADMIN']}>
                            <ErrorBoundary><FeatureFlagAdmin /></ErrorBoundary>
                        </ProtectedRoute>
                    } />
                    <Route path="/admin/policies" element={
                        <ProtectedRoute allowedRoles={['ADMIN']}>
                            <ErrorBoundary><PolicyManager /></ErrorBoundary>
                        </ProtectedRoute>
                    } />

                    <Route path="*" element={<NotFound />} />
            </Routes>

            {/* ── AI Chatbot Overlay (global, non-critical) ───── */}
            {useAuthStore.getState().isAuthenticated && (
                <ErrorBoundary fallback={null}>
                    <Suspense fallback={null}>
                        <AIChatbot />
                    </Suspense>
                </ErrorBoundary>
            )}
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
