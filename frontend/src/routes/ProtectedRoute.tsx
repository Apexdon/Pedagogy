import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/stores';
import { getAccessToken, getPreliminaryToken } from '@/api/client';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiresOrg?: boolean;
}

export function ProtectedRoute({ children, requiresOrg = true }: ProtectedRouteProps) {
  const location = useLocation();
  const { isAuthenticated, isOrgSelected, hasPreliminaryToken } = useAuthStore();

  const hasAccessToken = !!getAccessToken();
  const hasPrelimToken = hasPreliminaryToken || !!getPreliminaryToken();

  // If no access token and no preliminary token, redirect to login
  if (!hasAccessToken && !hasPrelimToken) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // If has preliminary token but no access token, should be selecting org
  if (hasPrelimToken && !hasAccessToken && requiresOrg) {
    return <Navigate to="/select-org" state={{ from: location }} replace />;
  }

  // If requires org but none selected, redirect to org selection
  if (requiresOrg && !isOrgSelected && !isAuthenticated) {
    return <Navigate to="/select-org" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

interface PublicOnlyRouteProps {
  children: React.ReactNode;
}

export function PublicOnlyRoute({ children }: PublicOnlyRouteProps) {
  const { isAuthenticated } = useAuthStore();

  // If already authenticated with org, redirect to dashboard
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
