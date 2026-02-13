/**
 * useGuidanceCoordinator Hook
 *
 * React hook for managing the GuidanceCoordinator service.
 * Provides reactive state updates and lifecycle management.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getCoordinator,
  resetCoordinator,
  type CoordinatorState,
  type CoordinatorStatus,
  type CoordinatorConfig,
  type CoordinatorEvent,
} from '../services/GuidanceCoordinator';
import type { GuidanceSession, GuidanceStep } from '../types/guidance';

export interface UseGuidanceCoordinatorOptions {
  config?: Partial<CoordinatorConfig>;
  onTargetWindowFound?: (windowTitle: string) => void;
  onTargetWindowLost?: (windowTitle: string) => void;
  onStepTargetFound?: (data: { step: GuidanceStep; target: unknown; bounds: unknown }) => void;
  onSessionCompleted?: (session: GuidanceSession) => void;
  onError?: (error: { message: string; error: string }) => void;
  // Callbacks for panel navigation buttons
  onPanelNextClicked?: () => Promise<void>;
  onPanelPrevClicked?: () => Promise<void>;
  onPanelSkipClicked?: () => Promise<void>;
  onPanelEndSession?: () => Promise<void>;
}

export interface UseGuidanceCoordinatorResult {
  // State
  status: CoordinatorStatus;
  state: CoordinatorState | null;
  isInitialized: boolean;
  isActive: boolean;
  isTargetWindowActive: boolean;
  error: string | null;

  // Actions
  initialize: (session: GuidanceSession, steps: GuidanceStep[], appId?: string) => Promise<void>;
  start: () => Promise<void>;
  pause: () => void;
  resume: () => void;
  stop: () => Promise<void>;
  nextStep: () => Promise<void>;
  skipStep: () => Promise<void>;
  reset: () => Promise<void>;
  updateCurrentStep: (stepNumber: number) => void;
}

export function useGuidanceCoordinator(
  options: UseGuidanceCoordinatorOptions = {}
): UseGuidanceCoordinatorResult {
  const {
    config,
    onTargetWindowFound,
    onTargetWindowLost,
    onStepTargetFound,
    onSessionCompleted,
    onError,
    onPanelNextClicked,
    onPanelPrevClicked,
    onPanelSkipClicked,
    onPanelEndSession,
  } = options;

  // State
  const [state, setState] = useState<CoordinatorState | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Ref to track if component is mounted
  const isMountedRef = useRef(true);
  const coordinatorRef = useRef(getCoordinator(config));

  // Derived state
  const status = state?.status ?? 'idle';
  const isActive = ['capturing', 'showing_halo', 'waiting_action'].includes(status);
  const isTargetWindowActive = state?.isTargetWindowActive ?? false;

  // Update state from coordinator
  const updateState = useCallback(() => {
    if (isMountedRef.current) {
      const newState = coordinatorRef.current.getState();
      console.log('useGuidanceCoordinator - updateState called, lastTiming:', newState.lastTiming);
      setState(newState);
    }
  }, []);

  // Initialize coordinator
  const initialize = useCallback(async (session: GuidanceSession, steps: GuidanceStep[], appId?: string) => {
    try {
      setError(null);
      await coordinatorRef.current.initialize(session, steps, appId);
      setIsInitialized(true);
      updateState();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err);
      setError(errorMessage);
      throw err;
    }
  }, [updateState]);

  // Start active guidance
  const start = useCallback(async () => {
    try {
      setError(null);
      await coordinatorRef.current.startActiveGuidance();
      updateState();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err);
      setError(errorMessage);
      throw err;
    }
  }, [updateState]);

  // Pause guidance
  const pause = useCallback(() => {
    coordinatorRef.current.pause();
    updateState();
  }, [updateState]);

  // Resume guidance
  const resume = useCallback(() => {
    coordinatorRef.current.resume();
    updateState();
  }, [updateState]);

  // Stop guidance
  const stop = useCallback(async () => {
    await coordinatorRef.current.stop();
    setIsInitialized(false);
    updateState();
  }, [updateState]);

  // Next step
  const nextStep = useCallback(async () => {
    await coordinatorRef.current.nextStep();
    updateState();
  }, [updateState]);

  // Skip step
  const skipStep = useCallback(async () => {
    await coordinatorRef.current.skipStep();
    updateState();
  }, [updateState]);

  // Update current step (sync with store)
  const updateCurrentStep = useCallback((stepNumber: number) => {
    coordinatorRef.current.updateCurrentStep(stepNumber);
    updateState();
  }, [updateState]);

  // Reset coordinator
  const reset = useCallback(async () => {
    await resetCoordinator();
    coordinatorRef.current = getCoordinator(config);
    setIsInitialized(false);
    setState(null);
    setError(null);
  }, [config]);

  // Setup event listeners
  useEffect(() => {
    const coordinator = coordinatorRef.current;
    const unsubscribers: (() => void)[] = [];

    // Status changes
    unsubscribers.push(
      coordinator.on('status_changed', () => {
        updateState();
      })
    );

    // Target window found
    if (onTargetWindowFound) {
      unsubscribers.push(
        coordinator.on('target_window_found', (event: CoordinatorEvent) => {
          const data = event.data as { windowTitle: string };
          onTargetWindowFound(data.windowTitle);
          updateState();
        })
      );
    }

    // Target window lost
    if (onTargetWindowLost) {
      unsubscribers.push(
        coordinator.on('target_window_lost', (event: CoordinatorEvent) => {
          const data = event.data as { windowTitle: string };
          onTargetWindowLost(data.windowTitle);
          updateState();
        })
      );
    }

    // Step target found
    if (onStepTargetFound) {
      unsubscribers.push(
        coordinator.on('step_target_found', (event: CoordinatorEvent) => {
          const data = event.data as { step: GuidanceStep; target: unknown; bounds: unknown };
          onStepTargetFound(data);
          updateState();
        })
      );
    }

    // Session completed
    if (onSessionCompleted) {
      unsubscribers.push(
        coordinator.on('session_completed', (event: CoordinatorEvent) => {
          const data = event.data as { session: GuidanceSession };
          onSessionCompleted(data.session);
          updateState();
        })
      );
    }

    // Error
    unsubscribers.push(
      coordinator.on('error', (event: CoordinatorEvent) => {
        const data = event.data as { message: string; error: string };
        setError(`${data.message}: ${data.error}`);
        if (onError) {
          onError(data);
        }
        updateState();
      })
    );

    // Cleanup
    return () => {
      unsubscribers.forEach(unsub => unsub());
    };
  }, [updateState, onTargetWindowFound, onTargetWindowLost, onStepTargetFound, onSessionCompleted, onError]);

  // Wire up panel navigation callbacks
  useEffect(() => {
    const coordinator = coordinatorRef.current;

    // Set callbacks on coordinator for panel events
    coordinator.onPanelNextClicked = onPanelNextClicked || null;
    coordinator.onPanelPrevClicked = onPanelPrevClicked || null;
    coordinator.onPanelSkipClicked = onPanelSkipClicked || null;
    coordinator.onPanelEndSession = onPanelEndSession || null;

    return () => {
      // Clear callbacks on cleanup
      coordinator.onPanelNextClicked = null;
      coordinator.onPanelPrevClicked = null;
      coordinator.onPanelSkipClicked = null;
      coordinator.onPanelEndSession = null;
    };
  }, [onPanelNextClicked, onPanelPrevClicked, onPanelSkipClicked, onPanelEndSession]);

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
    };
  }, []);

  return {
    // State
    status,
    state,
    isInitialized,
    isActive,
    isTargetWindowActive,
    error,

    // Actions
    initialize,
    start,
    pause,
    resume,
    stop,
    nextStep,
    skipStep,
    reset,
    updateCurrentStep,
  };
}

export default useGuidanceCoordinator;
