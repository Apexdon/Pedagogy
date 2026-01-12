import { useCallback } from 'react';
import { useGuidanceStore } from '@/stores';
import type { GenerateGuidanceRequest, GuidanceStep, HaloTarget } from '@/types';

/**
 * Hook for managing AI guidance sessions
 *
 * Provides a simplified interface to the guidance store with
 * computed properties and convenience methods.
 */
export function useGuidance() {
  const store = useGuidanceStore();

  // Computed: Get current step object
  const currentStepData: GuidanceStep | null =
    store.steps.find((s) => s.step_number === store.currentStep) || null;

  // Computed: Progress percentage
  const progress = store.totalSteps > 0 ? (store.currentStep / store.totalSteps) * 100 : 0;

  // Computed: Completed steps count
  const completedSteps = store.steps.filter(
    (s) => s.status === 'completed' || s.status === 'skipped'
  ).length;

  // Computed: Is first step
  const isFirstStep = store.currentStep === 1;

  // Computed: Is last step
  const isLastStep = store.currentStep === store.totalSteps;

  // Computed: Has active session
  const hasActiveSession = store.sessionId !== null && store.status !== 'idle';

  // Computed: Can advance (also true for last step to allow completing the session)
  const canAdvance =
    store.status === 'active' && !store.isAdvancing && store.currentStep <= store.totalSteps;

  // Computed: Can go back
  const canGoBack = store.status === 'active' && !store.isAdvancing && store.currentStep > 1;

  /**
   * Start a new guidance session
   */
  const startGuidance = useCallback(
    async (query: string, options?: Partial<GenerateGuidanceRequest>) => {
      return store.generate({
        query,
        ...options,
      });
    },
    [store]
  );

  /**
   * Complete current step and move to next
   */
  const completeStep = useCallback(async () => {
    return store.advance();
  }, [store]);

  /**
   * Skip current step without completing
   */
  const skipCurrentStep = useCallback(async () => {
    return store.skip();
  }, [store]);

  /**
   * Go back to previous step
   */
  const goToPreviousStep = useCallback(async () => {
    if (store.currentStep > 1) {
      return store.goTo(store.currentStep - 1);
    }
    return false;
  }, [store]);

  /**
   * Go to a specific step
   */
  const goToStep = useCallback(
    async (stepNumber: number) => {
      return store.goTo(stepNumber);
    },
    [store]
  );

  /**
   * End the current session
   */
  const endSession = useCallback(async () => {
    return store.abandon();
  }, [store]);

  return {
    // State
    sessionId: store.sessionId,
    status: store.status,
    query: store.query,
    steps: store.steps,
    currentStep: store.currentStep,
    totalSteps: store.totalSteps,
    currentTarget: store.currentTarget,
    contextSummary: store.contextSummary,
    overallConfidence: store.overallConfidence,
    error: store.error,

    // Visual guidance state
    visualGuidanceActive: store.visualGuidanceActive,
    targetAppConfigured: store.targetAppConfigured,
    targetWindowFound: store.targetWindowFound,
    targetWindowTitle: store.targetWindowTitle,
    detectedElements: store.detectedElements,
    captureTimeMs: store.captureTimeMs,
    matchConfidence: store.matchConfidence,

    // Loading states
    isGenerating: store.isGenerating,
    isAdvancing: store.isAdvancing,
    isCapturing: store.isCapturing,
    isStartingVisual: store.isStartingVisual,

    // Computed
    currentStepData,
    progress,
    completedSteps,
    isFirstStep,
    isLastStep,
    hasActiveSession,
    canAdvance,
    canGoBack,

    // Actions
    startGuidance,
    startVisualGuidance: store.startVisualGuidance,
    captureCurrentStep: store.captureCurrentStep,
    completeStep,
    skipCurrentStep,
    goToPreviousStep,
    goToStep,
    endSession,
    pause: store.pause,
    resume: store.resume,
    refresh: store.refresh,
    reset: store.reset,
  };
}

/**
 * Hook for accessing just the current Halo target
 *
 * Useful for the Halo overlay component that only needs target info.
 */
export function useHaloTarget(): HaloTarget | null {
  return useGuidanceStore((state) => state.currentTarget);
}

/**
 * Hook for accessing step list and navigation
 */
export function useGuidanceSteps() {
  const store = useGuidanceStore();

  return {
    steps: store.steps,
    currentStep: store.currentStep,
    totalSteps: store.totalSteps,
    goTo: store.goTo,
  };
}
