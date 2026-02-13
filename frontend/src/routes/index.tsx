import { createBrowserRouter, Navigate } from 'react-router-dom';
import { DashboardLayout } from '@/components/layout';
import { ProtectedRoute, PublicOnlyRoute } from './ProtectedRoute';
import { useAuthStore } from '@/stores/authStore';

/**
 * Role-based redirect component for the root route.
 * Redirects org admins/managers to /org/dashboard, regular users to /dashboard.
 */
function RoleBasedRedirect() {
  const { isAuthenticated, role } = useAuthStore();

  // Not authenticated - go to login
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Org admin or manager - go to org dashboard
  if (role === 'org_admin' || role === 'manager') {
    return <Navigate to="/org/dashboard" replace />;
  }

  // Regular user - go to user dashboard
  return <Navigate to="/dashboard" replace />;
}

// Auth pages
import { LoginPage, RegisterPage, SelectOrgPage } from '@/pages/auth';

// Dashboard pages
import { DashboardPage, SettingsPage, GuidancePage, HistoryPage } from '@/pages/dashboard';

// Organisation pages
import { OnboardPage, ProfilePage, MembersPage, OrgDashboardPage, KnowledgeBasePage, TargetAppsPage, CVDiagnosticPage } from '@/pages/org';

export const router = createBrowserRouter([
  // Public routes
  {
    path: '/login',
    element: (
      <PublicOnlyRoute>
        <LoginPage />
      </PublicOnlyRoute>
    ),
  },
  {
    path: '/register',
    element: (
      <PublicOnlyRoute>
        <RegisterPage />
      </PublicOnlyRoute>
    ),
  },
  {
    path: '/onboard',
    element: <OnboardPage />,
  },

  // Semi-protected (needs preliminary token)
  {
    path: '/select-org',
    element: <SelectOrgPage />,
  },

  // Protected routes (need full auth + org)
  {
    path: '/dashboard',
    element: (
      <ProtectedRoute>
        <DashboardLayout>
          <DashboardPage />
        </DashboardLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: '/settings',
    element: (
      <ProtectedRoute>
        <DashboardLayout>
          <SettingsPage />
        </DashboardLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: '/guidance',
    element: (
      <ProtectedRoute>
        <DashboardLayout>
          <GuidancePage />
        </DashboardLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: '/history',
    element: (
      <ProtectedRoute>
        <DashboardLayout>
          <HistoryPage />
        </DashboardLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: '/org/dashboard',
    element: (
      <ProtectedRoute>
        <DashboardLayout>
          <OrgDashboardPage />
        </DashboardLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: '/org/profile',
    element: (
      <ProtectedRoute>
        <DashboardLayout>
          <ProfilePage />
        </DashboardLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: '/org/members',
    element: (
      <ProtectedRoute>
        <DashboardLayout>
          <MembersPage />
        </DashboardLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: '/org/knowledge',
    element: (
      <ProtectedRoute>
        <DashboardLayout>
          <KnowledgeBasePage />
        </DashboardLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: '/org/target-apps',
    element: (
      <ProtectedRoute>
        <DashboardLayout>
          <TargetAppsPage />
        </DashboardLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: '/org/cv-diagnostic',
    element: (
      <ProtectedRoute>
        <DashboardLayout>
          <CVDiagnosticPage />
        </DashboardLayout>
      </ProtectedRoute>
    ),
  },
  // Redirect root based on user role
  {
    path: '/',
    element: <RoleBasedRedirect />,
  },

  // 404 fallback - redirect based on role
  {
    path: '*',
    element: <RoleBasedRedirect />,
  },
]);
