/**
 * Detection Hook
 *
 * Provides a convenient interface for detection functionality
 * with automatic event listener setup and cleanup.
 *
 * When autoCapture is enabled and monitoring is active, the hook will
 * automatically capture and analyze the screen when a matching window is detected.
 */

import { useEffect, useCallback, useRef } from 'react';
import { useDetectionStore } from '@/stores/detectionStore';
import * as detectionApi from '@/api/detection';
import type { WindowMatchEvent, WindowPattern } from '@/types/detection';

interface UseDetectionOptions {
  /** Additional callback when window match is detected */
  onWindowMatch?: (event: WindowMatchEvent) => void;
  /** Callback when screen state is ready after auto-capture */
  onScreenReady?: (screenState: ReturnType<typeof useDetectionStore.getState>['session']) => void;
  /** Window patterns to monitor (if not set in store) */
  patterns?: WindowPattern[];
  /** Enable auto-capture when window matches */
  autoCapture?: boolean;
  /** Interval between captures when continuously monitoring (ms) */
  captureIntervalMs?: number;
}

export function useDetection(options: UseDetectionOptions = {}) {
  const {
    onWindowMatch,
    onScreenReady,
    patterns,
    autoCapture: autoCaptureOption,
    captureIntervalMs,
  } = options;

  const {
    session,
    autoCapture,
    isMonitoring,
    captureHistory,
    captureIntervalMs: storeCaptureInterval,
    lastMatchedWindow,
    startCapture,
    resetSession,
    clearError,
    startMonitoring,
    stopMonitoring,
    setWindowPatterns,
    setAutoCapture,
    setCaptureInterval,
    handleWindowMatch,
  } = useDetectionStore();

  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Apply options to store on mount
  useEffect(() => {
    if (patterns && patterns.length > 0) {
      setWindowPatterns(patterns);
    }
    if (autoCaptureOption !== undefined) {
      setAutoCapture(autoCaptureOption);
    }
    if (captureIntervalMs !== undefined) {
      setCaptureInterval(captureIntervalMs);
    }
  }, [patterns, autoCaptureOption, captureIntervalMs, setWindowPatterns, setAutoCapture, setCaptureInterval]);

  // Set up window match listener that triggers store handler
  useEffect(() => {
    if (!isMonitoring) return;

    let unlisten: (() => void) | null = null;

    const setupListener = async () => {
      try {
        unlisten = await detectionApi.onWindowMatch((event) => {
          // Call store handler (triggers auto-capture if enabled)
          handleWindowMatch(event);
          // Call user-provided callback
          onWindowMatch?.(event);
        });
      } catch (error) {
        console.error('Failed to set up window match listener:', error);
      }
    };

    setupListener();

    return () => {
      if (unlisten) {
        unlisten();
      }
    };
  }, [isMonitoring, handleWindowMatch, onWindowMatch]);

  // Call onScreenReady when analysis completes
  useEffect(() => {
    if (session?.status === 'ready' && onScreenReady) {
      onScreenReady(session);
    }
  }, [session, onScreenReady]);

  // Set up continuous capture interval when window is matched and autoCapture is on
  useEffect(() => {
    // Clear any existing interval
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    // Only set up interval if:
    // - Auto-capture is enabled
    // - Monitoring is active
    // - We have a matched window
    if (autoCapture && isMonitoring && lastMatchedWindow) {
      intervalRef.current = setInterval(async () => {
        const currentState = useDetectionStore.getState();
        const currentSession = currentState.session;

        // Only capture if not already capturing/analyzing
        if (!currentSession || currentSession.status === 'idle' || currentSession.status === 'ready') {
          try {
            // Check if current window still matches patterns before capturing
            const activeWindow = await detectionApi.getActiveWindowTitle();
            const patterns = currentState.windowPatterns;

            const stillMatches = patterns.some((p) => {
              const title = activeWindow.title.toLowerCase();
              const pattern = p.pattern.toLowerCase();
              if (p.mode === 'exact') {
                return title === pattern;
              }
              return title.includes(pattern);
            });

            if (stillMatches) {
              console.log('Periodic auto-capture triggered for:', activeWindow.title);
              currentState.startCapture();
            } else {
              console.log('Skipping capture - window no longer matches:', activeWindow.title);
            }
          } catch (error) {
            console.error('Failed to check active window:', error);
          }
        }
      }, storeCaptureInterval);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [autoCapture, isMonitoring, lastMatchedWindow, storeCaptureInterval]);

  // Manual capture trigger
  const capture = useCallback(async () => {
    await startCapture();
  }, [startCapture]);

  // Get active window info
  const getActiveWindow = useCallback(async () => {
    return detectionApi.getActiveWindowTitle();
  }, []);

  // Get monitor info
  const getMonitors = useCallback(async () => {
    return detectionApi.getMonitors();
  }, []);

  return {
    // State
    session,
    status: session?.status ?? 'idle',
    capture: session?.capture,
    screenState: session?.screen_state,
    error: session?.error,
    isCapturing: session?.status === 'capturing',
    isAnalyzing: session?.status === 'analyzing',
    isReady: session?.status === 'ready',
    hasError: session?.status === 'error',
    lastMatchedWindow,

    // History
    captureHistory,

    // Configuration
    autoCapture,
    isMonitoring,
    captureIntervalMs: storeCaptureInterval,

    // Actions
    startCapture: capture,
    resetSession,
    clearError,
    getActiveWindow,
    getMonitors,

    // Configuration actions
    setAutoCapture,
    setWindowPatterns,
    setCaptureInterval,

    // Monitoring
    startMonitoring,
    stopMonitoring,
  };
}
