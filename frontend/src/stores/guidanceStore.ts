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
  startGuidance,
  captureStep,
} from '@/api/guidance';
import type {
  GuidanceStep,
  GuidanceSession,
  HaloTarget,
  DetectedElement,
  GenerateGuidanceRequest,
  GenerateGuidanceResponse,
  StartGuidanceResponse,
  CaptureStepResponse,
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

  // Computed-like getters (available via store)
  session: GuidanceSession | null;
  hasActiveSession: boolean;

  // Visual guidance state (screen capture & CV)
  visualGuidanceActive: boolean;
  targetAppConfigured: boolean;
  targetWindowFound: boolean;
  targetWindowTitle: string | null;
  detectedElements: DetectedElement[];
  captureTimeMs: number;
  matchConfidence: number;

  // UI state
  isGenerating: boolean;
  isAdvancing: boolean;
  isCapturing: boolean;
  isStartingVisual: boolean;
  error: string | null;

  // Actions
  generate: (request: GenerateGuidanceRequest) => Promise<GenerateGuidanceResponse | null>;
  startVisualGuidance: () => Promise<StartGuidanceResponse | null>;
  captureCurrentStep: () => Promise<CaptureStepResponse | null>;
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
  steps: [] as GuidanceStep[],
  currentStep: 0,
  totalSteps: 0,
  currentTarget: null,
  contextSummary: null,
  overallConfidence: 0,
  // Computed properties - these get overwritten by getters
  session: null as GuidanceSession | null,
  hasActiveSession: false,
  // Visual guidance state
  visualGuidanceActive: false,
  targetAppConfigured: false,
  targetWindowFound: false,
  targetWindowTitle: null,
  detectedElements: [] as DetectedElement[],
  captureTimeMs: 0,
  matchConfidence: 0,
  // UI state
  isGenerating: false,
  isAdvancing: false,
  isCapturing: false,
  isStartingVisual: false,
  error: null,
};

export const useGuidanceStore = create<GuidanceState>((set, get) => ({
  ...initialState,

  // These are updated by the generate/reset functions - not computed
  session: null,
  hasActiveSession: false,

  generate: async (request) => {
    set({ isGenerating: true, error: null, status: 'generating' });

    try {
      const response = await generateGuidance(request);

      // Construct the session object
      const session: GuidanceSession = {
        session_id: response.session_id,
        query: response.query,
        status: 'active',
        current_step: 1,
        total_steps: response.total_steps,
        application_context: null,
        overall_confidence: response.overall_confidence,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        completed_at: null,
      };

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
        // Set computed-like properties
        session,
        hasActiveSession: true,
      });

      return response;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to generate guidance';
      set({ error: message, status: 'error', isGenerating: false });
      return null;
    }
  },

  startVisualGuidance: async () => {
    const { sessionId, status } = get();
    if (!sessionId || status !== 'active') return null;

    set({ isStartingVisual: true, error: null });

    try {
      const response = await startGuidance(sessionId);

      set({
        visualGuidanceActive: true,
        targetAppConfigured: response.target_app_configured,
        targetWindowFound: response.target_window_found,
        targetWindowTitle: response.target_window_title,
        currentTarget: response.current_target,
        isStartingVisual: false,
      });

      return response;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to start visual guidance';
      set({ error: message, isStartingVisual: false });
      return null;
    }
  },

  captureCurrentStep: async () => {
    const { sessionId, status } = get();
    if (!sessionId || status !== 'active') return null;

    set({ isCapturing: true, error: null });

    try {
      const response = await captureStep(sessionId);

      set({
        currentTarget: response.target,
        detectedElements: response.all_elements,
        captureTimeMs: response.capture_time_ms,
        matchConfidence: response.match_confidence,
        targetWindowTitle: response.window_title,
        isCapturing: false,
      });

      return response;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to capture step';
      set({ error: message, isCapturing: false });
      return null;
    }
  },

  advance: async () => {
    const { sessionId, status, currentStep, totalSteps, isAdvancing } = get();
    console.log('[GuidanceStore] advance() called:', { sessionId, status, currentStep, totalSteps, isAdvancing });

    // Guard against double-clicks or rapid calls
    if (isAdvancing) {
      console.log('[GuidanceStore] advance() skipped: already advancing');
      return false;
    }

    if (!sessionId || status !== 'active') {
      console.log('[GuidanceStore] advance() aborted: invalid state', { sessionId, status });
      return false;
    }

    // Set advancing immediately
    set({ isAdvancing: true, error: null });
    console.log('[GuidanceStore] isAdvancing set to true');

    try {
      const response = await advanceStep(sessionId);
      console.log('[GuidanceStore] advanceStep response:', response);

      if (response.is_completed) {
        set({
          status: 'completed',
          currentStep: response.current_step,
          currentTarget: null,
          isAdvancing: false,
          hasActiveSession: false,
        });
        console.log('[GuidanceStore] Session completed, isAdvancing set to false');
      } else {
        // Update current step and target, plus reset isAdvancing in one atomic update
        set((state) => ({
          currentStep: response.current_step,
          currentTarget: response.current_target,
          isAdvancing: false,
          steps: state.steps.map((step) => {
            if (step.step_number < response.current_step) {
              return { ...step, status: 'completed' };
            } else if (step.step_number === response.current_step) {
              return { ...step, status: 'current' };
            }
            return step;
          }),
        }));
        console.log('[GuidanceStore] Step advanced to', response.current_step, ', isAdvancing set to false');
      }

      return true;
    } catch (error) {
      console.error('[GuidanceStore] advance() error:', error);
      const message = error instanceof Error ? error.message : 'Failed to advance step';
      set({ error: message, isAdvancing: false });
      console.log('[GuidanceStore] Error occurred, isAdvancing set to false');
      return false;
    } finally {
      // Safety net: ensure isAdvancing is reset even if something unexpected happens
      // Use setTimeout to ensure this runs after the state updates propagate
      setTimeout(() => {
        const currentState = get();
        if (currentState.isAdvancing) {
          console.warn('[GuidanceStore] Safety net: isAdvancing was still true after 100ms, force resetting');
          set({ isAdvancing: false });
        }
      }, 100);
    }
  },

  skip: async () => {
    const { sessionId, status, currentStep, isAdvancing } = get();
    console.log('[GuidanceStore] skip() called:', { sessionId, status, currentStep, isAdvancing });

    // Guard against double-clicks or rapid calls
    if (isAdvancing) {
      console.log('[GuidanceStore] skip() skipped: already advancing');
      return false;
    }

    if (!sessionId || status !== 'active') {
      console.log('[GuidanceStore] skip() aborted: invalid state');
      return false;
    }

    set({ isAdvancing: true, error: null });
    console.log('[GuidanceStore] skip: isAdvancing set to true');

    try {
      const response = await skipStep(sessionId);
      console.log('[GuidanceStore] skipStep response:', response);

      if (response.is_completed) {
        set({
          status: 'completed',
          currentStep: response.current_step,
          currentTarget: null,
          isAdvancing: false,
          hasActiveSession: false,
        });
        console.log('[GuidanceStore] Session completed via skip, isAdvancing set to false');
      } else {
        // Atomic update for skip
        set((state) => ({
          currentStep: response.current_step,
          currentTarget: response.current_target,
          isAdvancing: false,
          steps: state.steps.map((step) => {
            if (step.step_number === response.previous_step) {
              return { ...step, status: 'skipped' };
            } else if (step.step_number === response.current_step) {
              return { ...step, status: 'current' };
            }
            return step;
          }),
        }));
        console.log('[GuidanceStore] Step skipped to', response.current_step, ', isAdvancing set to false');
      }

      return true;
    } catch (error) {
      console.error('[GuidanceStore] skip() error:', error);
      const message = error instanceof Error ? error.message : 'Failed to skip step';
      set({ error: message, isAdvancing: false });
      console.log('[GuidanceStore] Skip error, isAdvancing set to false');
      return false;
    } finally {
      // Safety net with timeout
      setTimeout(() => {
        const currentState = get();
        if (currentState.isAdvancing) {
          console.warn('[GuidanceStore] skip: Safety net - isAdvancing still true after 100ms, force resetting');
          set({ isAdvancing: false });
        }
      }, 100);
    }
  },

  goTo: async (stepNumber) => {
    const { sessionId, isAdvancing } = get();

    // Guard against rapid calls
    if (isAdvancing) {
      console.log('[GuidanceStore] goTo() skipped: already advancing');
      return false;
    }

    if (!sessionId) return false;

    set({ isAdvancing: true, error: null });
    console.log('[GuidanceStore] goTo: isAdvancing set to true, going to step', stepNumber);

    try {
      const response = await goToStep(sessionId, stepNumber);

      set({
        status: response.status === 'completed' ? 'completed' : 'active',
        currentStep: response.current_step,
        currentTarget: response.current_target,
        steps: response.steps,
        isAdvancing: false,
      });
      console.log('[GuidanceStore] goTo complete, went to step', response.current_step, ', isAdvancing set to false');

      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to go to step';
      set({ error: message, isAdvancing: false });
      console.log('[GuidanceStore] goTo error, isAdvancing set to false');
      return false;
    } finally {
      // Safety net with timeout
      setTimeout(() => {
        const currentState = get();
        if (currentState.isAdvancing) {
          console.warn('[GuidanceStore] goTo: Safety net - isAdvancing still true after 100ms, force resetting');
          set({ isAdvancing: false });
        }
      }, 100);
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
