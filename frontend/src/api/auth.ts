import apiClient, { setPreliminaryToken, getPreliminaryToken, clearPreliminaryToken, setTokens, clearTokens, getAccessToken } from './client';
import type {
  UserRegisterRequest,
  UserLoginRequest,
  SelectOrganisationRequest,
  RegisterResponse,
  LoginResponse,
  SelectOrgResponse,
  LogoutResponse,
  User,
  Token,
} from '@/types';

/**
 * Register a new user account
 */
export const register = async (data: UserRegisterRequest): Promise<RegisterResponse> => {
  const response = await apiClient.post<RegisterResponse>('/auth/register', data);
  return response.data;
};

/**
 * Login and get preliminary token + organisations list
 * For org_admin/manager users, returns full tokens directly (no org selection needed)
 */
export const login = async (data: UserLoginRequest): Promise<LoginResponse> => {
  const response = await apiClient.post<LoginResponse>('/auth/login', data);

  // For org_admin/manager users, backend returns full tokens directly
  if (response.data.tokens) {
    setTokens(response.data.tokens);
  } else if (response.data.preliminary_token) {
    // Store preliminary token for org selection (regular users)
    setPreliminaryToken(response.data.preliminary_token);
  }

  return response.data;
};

/**
 * Select an organisation and get full access tokens (initial login flow)
 */
export const selectOrganisation = async (data: SelectOrganisationRequest): Promise<SelectOrgResponse> => {
  const preliminaryToken = getPreliminaryToken();
  const accessToken = getAccessToken();

  // If user has access token but no preliminary token, use switch endpoint
  if (accessToken && !preliminaryToken) {
    return switchOrganisation(data);
  }

  if (!preliminaryToken) {
    throw new Error('No preliminary token found. Please login again.');
  }

  const response = await apiClient.post<SelectOrgResponse>(
    '/auth/select-organisation',
    data,
    {
      headers: {
        Authorization: `Bearer ${preliminaryToken}`,
      },
    }
  );

  // Store full tokens and clear preliminary token
  if (response.data.tokens) {
    setTokens(response.data.tokens);
    clearPreliminaryToken();
  }

  return response.data;
};

/**
 * Switch organisation for an already authenticated user
 */
export const switchOrganisation = async (data: SelectOrganisationRequest): Promise<SelectOrgResponse> => {
  const response = await apiClient.post<SelectOrgResponse>(
    '/auth/switch-organisation',
    data
  );

  // Store new tokens
  if (response.data.tokens) {
    setTokens(response.data.tokens);
  }

  return response.data;
};

/**
 * Logout the current user
 */
export const logout = async (): Promise<LogoutResponse> => {
  try {
    const response = await apiClient.post<LogoutResponse>('/auth/logout');
    return response.data;
  } finally {
    clearTokens();
  }
};

/**
 * Refresh the access token
 */
export const refreshToken = async (refresh_token: string): Promise<Token> => {
  const response = await apiClient.post<Token>('/auth/refresh', {
    refresh_token,
  });

  if (response.data) {
    setTokens(response.data);
  }

  return response.data;
};

/**
 * Get current user profile
 */
export const getCurrentUser = async (): Promise<User> => {
  const response = await apiClient.get<User>('/auth/me');
  return response.data;
};
