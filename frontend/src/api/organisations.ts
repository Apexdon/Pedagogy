import apiClient, { getPreliminaryToken } from './client';
import type {
  OrganisationListItem,
  OrganisationProfile,
  OnboardingStatus,
  OrganisationOnboardRequest,
  OnboardingResponse,
  Member,
  AddMemberRequest,
  AddMemberResponse,
  UpdateProfileRequest,
  UpdateProfileResponse,
  OrgDashboardStats,
} from '@/types';

/**
 * List all active organisations (public endpoint)
 */
export const listOrganisations = async (): Promise<OrganisationListItem[]> => {
  const response = await apiClient.get<OrganisationListItem[]>('/org/list');
  return response.data;
};

/**
 * Onboard a new organisation with admin user
 */
export const onboardOrganisation = async (
  data: OrganisationOnboardRequest
): Promise<OnboardingResponse> => {
  const response = await apiClient.post<OnboardingResponse>('/org/onboard', data);
  return response.data;
};

/**
 * Get current organisation's profile
 */
export const getOrganisationProfile = async (): Promise<OrganisationProfile> => {
  const response = await apiClient.get<OrganisationProfile>('/org/profile');
  return response.data;
};

/**
 * Update organisation profile (admin only)
 */
export const updateOrganisationProfile = async (
  data: UpdateProfileRequest
): Promise<UpdateProfileResponse> => {
  const params = new URLSearchParams();
  if (data.org_name) params.append('org_name', data.org_name);
  if (data.primary_color) params.append('primary_color', data.primary_color);

  const response = await apiClient.put<UpdateProfileResponse>(
    `/org/profile?${params.toString()}`
  );
  return response.data;
};

/**
 * Get onboarding status
 */
export const getOnboardingStatus = async (): Promise<OnboardingStatus> => {
  const response = await apiClient.get<OnboardingStatus>('/org/onboarding-status');
  return response.data;
};

/**
 * List organisation members
 */
export const listMembers = async (): Promise<Member[]> => {
  const response = await apiClient.get<Member[]>('/org/members');
  return response.data;
};

/**
 * Add a member to the organisation (admin/manager only)
 */
export const addMember = async (data: AddMemberRequest): Promise<AddMemberResponse> => {
  const response = await apiClient.post<AddMemberResponse>('/org/members', data);
  return response.data;
};

/**
 * Remove a member from the organisation (admin only)
 */
export const removeMember = async (userId: string): Promise<{ success: boolean; message: string }> => {
  const response = await apiClient.delete<{ success: boolean; message: string }>(
    `/org/members/${userId}`
  );
  return response.data;
};

/**
 * Join an organisation as a user
 * Uses preliminary token (called before org selection)
 */
export const joinOrganisation = async (orgId: string): Promise<AddMemberResponse> => {
  const preliminaryToken = getPreliminaryToken();

  if (!preliminaryToken) {
    throw new Error('No preliminary token found. Please login again.');
  }

  const response = await apiClient.post<AddMemberResponse>(
    `/org/join/${orgId}`,
    {},
    {
      headers: {
        Authorization: `Bearer ${preliminaryToken}`,
      },
    }
  );
  return response.data;
};

/**
 * Get organisation dashboard stats (org_admin/manager only)
 */
export const getOrgDashboardStats = async (): Promise<OrgDashboardStats> => {
  const response = await apiClient.get<OrgDashboardStats>('/org/dashboard');
  return response.data;
};
