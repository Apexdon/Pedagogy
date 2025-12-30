import { createBrowserRouter, Navigate } from 'react-router-dom';
import { DashboardLayout } from '@/components/layout';
import { ProtectedRoute, PublicOnlyRoute } from './ProtectedRoute';

// Auth pages
import { LoginPage, RegisterPage, SelectOrgPage } from '@/pages/auth';

// Dashboard pages
import { DashboardPage, SettingsPage, GuidancePage, HistoryPage, DetectionTestPage } from '@/pages/dashboard';

// Organisation pages
import { OnboardPage, ProfilePage, MembersPage, OrgDashboardPage, KnowledgeBasePage } from '@/pages/org';

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
    path: '/detection-test',
    element: (
      <ProtectedRoute>
        <DashboardLayout>
          <DetectionTestPage />
        </DashboardLayout>
      </ProtectedRoute>
    ),
  },

  // Redirect root to dashboard or login
  {
    path: '/',
    element: <Navigate to="/dashboard" replace />,
  },

  // 404 fallback
  {
    path: '*',
    element: <Navigate to="/dashboard" replace />,
  },
]);
