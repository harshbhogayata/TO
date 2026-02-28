import { BrowserRouter, Routes, Route } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import { ToastProvider } from './contexts/ToastContext';

// Public pages
import Home from './pages/Home';
import AuthPage from './pages/AuthPage';
import Pricing from './pages/Pricing';
import About from './pages/About';
import HelpDesk from './pages/HelpDesk';
import NotFound from './pages/NotFound';
import PasswordRecovery from './pages/PasswordRecovery';
import PaymentSuccess from './pages/PaymentSuccess';
import PaymentCancel from './pages/PaymentCancel';

// Registration (public — must be logged out)
import CompanyRegistration from './pages/CompanyRegistration';
import UserRegistration from './pages/UserRegistration';

// Protected dashboard pages
import CompanyDashboard from './pages/CompanyDashboard';
import UserDashboard from './pages/UserDashboard';
import JobBoard from './pages/JobBoard';
import SkillHub from './pages/SkillHub';
import UserProfile from './pages/UserProfile';
import AdminConsole from './pages/AdminConsole';
import Settings from './pages/Settings';
import Inbox from './pages/Inbox';

// New specialized components
import JobDetail from './pages/JobDetail';
import CompanyProfilePage from './pages/CompanyProfile';
import ApplicantReview from './pages/ApplicantReview';
import MyApplications from './pages/MyApplications';
import SavedJobs from './pages/SavedJobs';
import Notifications from './pages/Notifications';
import Blog from './pages/Blog';
import Terms from './pages/Terms';
import Privacy from './pages/Privacy';
import PostJob from './pages/PostJob';

function App() {
    return (
        <ToastProvider>
            <BrowserRouter>
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
                    <Route path="/payment/success" element={<PaymentSuccess />} />
                    <Route path="/payment/cancel" element={<PaymentCancel />} />

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

                    {/* ── Admin-only routes ─────────────────────────── */}
                    <Route path="/admin" element={
                        <ProtectedRoute allowedRoles={['ADMIN']}>
                            <AdminConsole />
                        </ProtectedRoute>
                    } />

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

                    <Route path="*" element={<NotFound />} />
                </Routes>
            </BrowserRouter>
        </ToastProvider >
    );
}

export default App;
