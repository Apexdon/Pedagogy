import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, UserOrganisationInfo, OrganisationBasic } from '@/types';
import { getAccessToken, clearTokens } from '@/api/client';

interface AuthState {
  // State
  user: User | null;
  selectedOrg: OrganisationBasic | null;
  organisations: UserOrganisationInfo[];
  role: string | null;
  isAuthenticated: boolean;
  isOrgSelected: boolean;
  hasPreliminaryToken: boolean;

  // Actions
  setUser: (user: User) => void;
  setOrganisations: (orgs: UserOrganisationInfo[]) => void;
  selectOrganisation: (org: OrganisationBasic, role: string) => void;
  setHasPreliminaryToken: (value: boolean) => void;
  logout: () => void;
  checkAuth: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      selectedOrg: null,
      organisations: [],
      role: null,
      isAuthenticated: false,
      isOrgSelected: false,
      hasPreliminaryToken: false,

      // Actions
      setUser: (user) => {
        set({ user });
      },

      setOrganisations: (organisations) => {
        set({ organisations, hasPreliminaryToken: true });
      },

      selectOrganisation: (org, role) => {
        set({
          selectedOrg: org,
          role,
          isAuthenticated: true,
          isOrgSelected: true,
          hasPreliminaryToken: false,
        });
      },

      setHasPreliminaryToken: (value) => {
        set({ hasPreliminaryToken: value });
      },

      logout: () => {
        clearTokens();
        set({
          user: null,
          selectedOrg: null,
          organisations: [],
          role: null,
          isAuthenticated: false,
          isOrgSelected: false,
          hasPreliminaryToken: false,
        });
      },

      checkAuth: () => {
        const token = getAccessToken();
        const { selectedOrg } = get();
        const isAuth = !!token && !!selectedOrg;
        set({ isAuthenticated: isAuth, isOrgSelected: !!selectedOrg });
        return isAuth;
      },
    }),
    {
      name: 'pedagogy-auth',
      partialize: (state) => ({
        user: state.user,
        selectedOrg: state.selectedOrg,
        organisations: state.organisations,
        role: state.role,
      }),
    }
  )
);
