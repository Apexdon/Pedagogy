import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/stores';
import { getAccessToken, getPreliminaryToken } from '@/api/client';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiresOrg?: boolean;
}

export function ProtectedRoute({ children, requiresOrg = true }: ProtectedRouteProps) {
  const location = useLocation();
  const { isAuthenticated, isOrgSelected, hasPreliminaryToken, selectedOrg, user } = useAuthStore();

  const hasAccessToken = !!getAccessToken();
  const hasPrelimToken = hasPreliminaryToken || !!getPreliminaryToken();

  // Debug logging
  console.log('[ProtectedRoute] Debug:', {
    path: location.pathname,
    hasAccessToken,
    hasPrelimToken,
    isAuthenticated,
    isOrgSelected,
    hasPreliminaryToken,
    selectedOrg: selectedOrg?.org_name,
    user: user?.email,
  });

  // If no access token and no preliminary token, redirect to login
  if (!hasAccessToken && !hasPrelimToken) {
    console.log('[ProtectedRoute] Redirecting to /login - no tokens');
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // If has preliminary token but no access token, should be selecting org
  if (hasPrelimToken && !hasAccessToken && requiresOrg) {
    console.log('[ProtectedRoute] Redirecting to /select-org - has prelim token but no access token');
    return <Navigate to="/select-org" state={{ from: location }} replace />;
  }

  // Check if org is actually selected (from persisted state)
  const hasSelectedOrg = !!selectedOrg;

  // If requires org but none selected, redirect to org selection
  if (requiresOrg && !hasSelectedOrg) {
    console.log('[ProtectedRoute] Redirecting to /select-org - no org selected');
    return <Navigate to="/select-org" state={{ from: location }} replace />;
  }

  console.log('[ProtectedRoute] Access granted');
  return <>{children}</>;
}

interface PublicOnlyRouteProps {
  children: React.ReactNode;
}

export function PublicOnlyRoute({ children }: PublicOnlyRouteProps) {
  const { isAuthenticated, role } = useAuthStore();

  // If already authenticated with org, redirect based on role
  if (isAuthenticated) {
    const isOrgAdmin = role === 'org_admin' || role === 'manager';
    return <Navigate to={isOrgAdmin ? '/org/dashboard' : '/dashboard'} replace />;
  }

  return <>{children}</>;
}
