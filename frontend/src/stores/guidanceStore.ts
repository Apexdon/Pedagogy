import { create } from 'zustand';
import {
  generateGuidance,
  getSessionState,
  advanceStep,
  skipStep,
  goToStep,
  pauseSession,
  resumeSession,
  abandonSession,
} from '@/api/guidance';
import type {
  GuidanceStep,
  HaloTarget,
  GenerateGuidanceRequest,
  GenerateGuidanceResponse,
} from '@/types';

export type GuidanceStatus = 'idle' | 'generating' | 'active' | 'paused' | 'completed' | 'error';

interface GuidanceState {
  // Session state
  sessionId: string | null;
  status: GuidanceStatus;
  query: string | null;
  steps: GuidanceStep[];
  currentStep: number;
  totalSteps: number;
  currentTarget: HaloTarget | null;
  contextSummary: string | null;
  overallConfidence: number;

  // UI state
  isGenerating: boolean;
  isAdvancing: boolean;
  error: string | null;

  // Actions
  generate: (request: GenerateGuidanceRequest) => Promise<GenerateGuidanceResponse | null>;
  advance: () => Promise<boolean>;
  skip: () => Promise<boolean>;
  goTo: (stepNumber: number) => Promise<boolean>;
  pause: () => Promise<boolean>;
  resume: () => Promise<boolean>;
  abandon: () => Promise<boolean>;
  refresh: () => Promise<void>;
  reset: () => void;
}

const initialState = {
  sessionId: null,
  status: 'idle' as GuidanceStatus,
  query: null,
  steps: [],
  currentStep: 0,
  totalSteps: 0,
  currentTarget: null,
  contextSummary: null,
  overallConfidence: 0,
  isGenerating: false,
  isAdvancing: false,
  error: null,
};

export const useGuidanceStore = create<GuidanceState>((set, get) => ({
  ...initialState,

  generate: async (request) => {
    set({ isGenerating: true, error: null, status: 'generating' });

    try {
      const response = await generateGuidance(request);

      set({
        sessionId: response.session_id,
        status: 'active',
        query: response.query,
        steps: response.steps,
        currentStep: 1,
        totalSteps: response.total_steps,
        currentTarget: response.current_target,
        contextSummary: response.context_summary,
        overallConfidence: response.overall_confidence,
        isGenerating: false,
      });

      return response;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to generate guidance';
      set({ error: message, status: 'error', isGenerating: false });
      return null;
    }
  },

  advance: async () => {
    const { sessionId, status } = get();
    if (!sessionId || status !== 'active') return false;

    set({ isAdvancing: true, error: null });

    try {
      const response = await advanceStep(sessionId);

      if (response.is_completed) {
        set({
          status: 'completed',
          currentStep: response.current_step,
          currentTarget: null,
          isAdvancing: false,
        });
      } else {
        set({
          currentStep: response.current_step,
          currentTarget: response.current_target,
          isAdvancing: false,
        });

        // Update step statuses
        set((state) => ({
          steps: state.steps.map((step) => {
            if (step.step_number < response.current_step) {
              return { ...step, status: 'completed' };
            } else if (step.step_number === response.current_step) {
              return { ...step, status: 'current' };
            }
            return step;
          }),
        }));
      }

      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to advance step';
      set({ error: message, isAdvancing: false });
      return false;
    }
  },

  skip: async () => {
    const { sessionId, status } = get();
    if (!sessionId || status !== 'active') return false;

    set({ isAdvancing: true, error: null });

    try {
      const response = await skipStep(sessionId);

      if (response.is_completed) {
        set({
          status: 'completed',
          currentStep: response.current_step,
          currentTarget: null,
          isAdvancing: false,
        });
      } else {
        set({
          currentStep: response.current_step,
          currentTarget: response.current_target,
          isAdvancing: false,
        });

        // Update step statuses
        set((state) => ({
          steps: state.steps.map((step) => {
            if (step.step_number === response.previous_step) {
              return { ...step, status: 'skipped' };
            } else if (step.step_number === response.current_step) {
              return { ...step, status: 'current' };
            }
            return step;
          }),
        }));
      }

      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to skip step';
      set({ error: message, isAdvancing: false });
      return false;
    }
  },

  goTo: async (stepNumber) => {
    const { sessionId } = get();
    if (!sessionId) return false;

    set({ isAdvancing: true, error: null });

    try {
      const response = await goToStep(sessionId, stepNumber);

      set({
        status: response.status === 'completed' ? 'completed' : 'active',
        currentStep: response.current_step,
        currentTarget: response.current_target,
        steps: response.steps,
        isAdvancing: false,
      });

      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to go to step';
      set({ error: message, isAdvancing: false });
      return false;
    }
  },

  pause: async () => {
    const { sessionId } = get();
    if (!sessionId) return false;

    try {
      await pauseSession(sessionId);
      set({ status: 'paused' });
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to pause session';
      set({ error: message });
      return false;
    }
  },

  resume: async () => {
    const { sessionId } = get();
    if (!sessionId) return false;

    try {
      const response = await resumeSession(sessionId);
      set({
        status: 'active',
        currentStep: response.current_step,
        currentTarget: response.current_target,
        steps: response.steps,
      });
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to resume session';
      set({ error: message });
      return false;
    }
  },

  abandon: async () => {
    const { sessionId } = get();
    if (!sessionId) return false;

    try {
      await abandonSession(sessionId);
      set(initialState);
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to abandon session';
      set({ error: message });
      return false;
    }
  },

  refresh: async () => {
    const { sessionId } = get();
    if (!sessionId) return;

    try {
      const response = await getSessionState(sessionId);
      set({
        status: response.status === 'completed' ? 'completed' : 'active',
        currentStep: response.current_step,
        totalSteps: response.total_steps,
        currentTarget: response.current_target,
        steps: response.steps,
      });
    } catch (error) {
      console.error('Failed to refresh session state:', error);
    }
  },

  reset: () => {
    set(initialState);
  },
}));
