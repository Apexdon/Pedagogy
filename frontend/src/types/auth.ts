// User types
export interface User {
  user_id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  email_verified: boolean;
  created_at: string;
  last_login: string | null;
}

// Organisation types for auth context
export interface UserOrganisationInfo {
  org_id: string;
  org_name: string;
  org_slug: string;
  role: 'org_admin' | 'manager' | 'user' | 'viewer';
  is_default: boolean;
  joined_at: string;
}

export interface OrganisationBasic {
  org_id: string;
  org_name: string;
  org_slug: string;
  primary_color: string;
}

// Token types
export interface Token {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// Request types
export interface UserRegisterRequest {
  email: string;
  password: string;
  full_name: string;
}

export interface UserLoginRequest {
  email: string;
  password: string;
}

export interface SelectOrganisationRequest {
  org_id: string;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

// Response types
export interface RegisterResponse {
  success: boolean;
  user: User;
  message: string;
}

export interface LoginResponse {
  success: boolean;
  user: User;
  organisations: UserOrganisationInfo[];
  requires_org_selection: boolean;
  preliminary_token: string | null;
  // For org_admin/manager - direct login without org selection
  tokens?: Token;
  organisation?: OrganisationBasic;
  role?: string;
}

export interface SelectOrgResponse {
  success: boolean;
  user: User;
  organisation: OrganisationBasic;
  role: string;
  tokens: Token;
}

export interface LogoutResponse {
  success: boolean;
  message: string;
  sessions_terminated: number;
}
