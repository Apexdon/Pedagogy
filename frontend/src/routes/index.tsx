import { createBrowserRouter, Navigate } from 'react-router-dom';
import { DashboardLayout } from '@/components/layout';
import { ProtectedRoute, PublicOnlyRoute } from './ProtectedRoute';

// Auth pages
import { LoginPage, RegisterPage, SelectOrgPage } from '@/pages/auth';

// Dashboard pages
import { DashboardPage, SettingsPage } from '@/pages/dashboard';

// Organisation pages
import { OnboardPage, ProfilePage, MembersPage } from '@/pages/org';

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
