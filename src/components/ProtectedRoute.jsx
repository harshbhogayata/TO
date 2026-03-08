/**
 * src/components/ProtectedRoute.jsx
 * Guards dashboard routes behind authentication.
 * Also enforces role-based access (e.g. only COMPANY accounts can see /company).
 */
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

const ProtectedRoute = ({ children, allowedRoles }) => {
    const { isAuthenticated, isLoading, user } = useAuthStore();
    const location = useLocation();

    if (isLoading) {
        return (
            <div style={{ padding: '32px', fontSize: '11px', opacity: 0.5, textTransform: 'uppercase' }}>
                Loading...
            </div>
        );
    }

    if (!isAuthenticated) {
        // Redirect to login, preserving the target URL
        return <Navigate to={'/auth'} state={{ from: location }} replace />;
    }

    if (allowedRoles && (!user?.role || !allowedRoles.includes(user.role))) {
        // Authenticated but wrong role; redirect to their correct dashboard
        const dashboardMap = {
            TALENT: '/user',
            COMPANY: '/company',
            ADMIN: '/admin',
        };
        return <Navigate to={dashboardMap[user?.role] || '/'} replace />;
    }

    return children;
};

export default ProtectedRoute;