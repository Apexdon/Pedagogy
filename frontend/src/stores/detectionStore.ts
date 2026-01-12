/**
 * Detection State Store
 *
 * Manages the detection workflow state machine and screen capture data.
 * Supports automatic screen capture when monitored windows are detected.
 */

import { create } from 'zustand';
import type {
  DetectionStatus,
  DetectionSession,
  CaptureResult,
  WindowPattern,
  WindowMatchEvent,
  CaptureResponse,
} from '@/types/detection';
import * as detectionApi from '@/api/detection';

interface DetectionState {
  // Current session
  session: DetectionSession | null;

  // Configuration
  autoCapture: boolean;
  windowPatterns: WindowPattern[];
  isMonitoring: boolean;
  captureIntervalMs: number;
  lastMatchedWindow: WindowMatchEvent | null;

  // History (last N captures)
  captureHistory: DetectionSession[];
  maxHistorySize: number;

  // Actions
  startCapture: () => Promise<void>;
  analyzeCapture: (capture: CaptureResult) => Promise<void>;
  resetSession: () => void;
  clearError: () => void;

  // Configuration actions
  setAutoCapture: (enabled: boolean) => void;
  setWindowPatterns: (patterns: WindowPattern[]) => void;
  setCaptureInterval: (ms: number) => void;
  startMonitoring: () => Promise<void>;
  stopMonitoring: () => Promise<void>;

  // Window match handler
  handleWindowMatch: (event: WindowMatchEvent) => void;
}

// Generate a simple unique ID
const generateId = (): string => {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

// Convert CaptureResponse to CaptureResult
const responseToResult = (response: CaptureResponse): CaptureResult | undefined => {
  if (!response.success || !response.image_base64) return undefined;
  return {
    image_base64: response.image_base64,
    width: response.width || 0,
    height: response.height || 0,
    monitor_name: response.monitor_name || 'Unknown',
  };
};

export const useDetectionStore = create<DetectionState>((set, get) => ({
  // Initial state
  session: null,
  autoCapture: false,
  windowPatterns: [],
  isMonitoring: false,
  captureIntervalMs: 5000, // Default: capture every 5 seconds when window matches
  lastMatchedWindow: null,
  captureHistory: [],
  maxHistorySize: 10,

  // Start screen capture
  startCapture: async () => {
    const sessionId = generateId();

    set({
      session: {
        session_id: sessionId,
        started_at: new Date(),
        status: 'capturing',
      },
    });

    try {
      const captureResponse = await detectionApi.captureScreen();

      if (!captureResponse.success || !captureResponse.image_base64) {
        throw new Error(captureResponse.error || 'Capture failed');
      }

      const captureResult = responseToResult(captureResponse);

      set((state) => ({
        session: state.session
          ? {
              ...state.session,
              status: 'analyzing' as DetectionStatus,
              capture: captureResult,
            }
          : null,
      }));

      // Automatically proceed to analysis
      if (captureResult) {
        await get().analyzeCapture(captureResult);
      }
    } catch (error) {
      set((state) => ({
        session: state.session
          ? {
              ...state.session,
              status: 'error' as DetectionStatus,
              error: error instanceof Error ? error.message : 'Unknown error',
            }
          : null,
      }));
    }
  },

  // Analyze captured image
  analyzeCapture: async (capture: CaptureResult) => {
    try {
      const screenState = await detectionApi.analyzeScreen({
        image: capture.image_base64,
        resize: true,
        fuse_labels: true,
      });

      set((state) => {
        const updatedSession = state.session
          ? {
              ...state.session,
              status: 'ready' as DetectionStatus,
              screen_state: screenState,
            }
          : null;

        // Add to history
        const newHistory = updatedSession
          ? [updatedSession, ...state.captureHistory].slice(0, state.maxHistorySize)
          : state.captureHistory;

        return {
          session: updatedSession,
          captureHistory: newHistory,
        };
      });
    } catch (error) {
      set((state) => ({
        session: state.session
          ? {
              ...state.session,
              status: 'error' as DetectionStatus,
              error: error instanceof Error ? error.message : 'Analysis failed',
            }
          : null,
      }));
    }
  },

  // Reset session to idle
  resetSession: () => {
    set({ session: null });
  },

  // Clear error and go back to idle
  clearError: () => {
    set((state) => ({
      session: state.session?.status === 'error' ? null : state.session,
    }));
  },

  // Configuration
  setAutoCapture: (enabled: boolean) => {
    set({ autoCapture: enabled });
  },

  setWindowPatterns: (patterns: WindowPattern[]) => {
    set({ windowPatterns: patterns });
  },

  setCaptureInterval: (ms: number) => {
    set({ captureIntervalMs: Math.max(1000, ms) }); // Minimum 1 second
  },

  // Start window monitoring
  startMonitoring: async () => {
    const { windowPatterns } = get();

    if (windowPatterns.length === 0) {
      console.warn('No window patterns configured for monitoring');
      return;
    }

    try {
      await detectionApi.startWindowMonitoring({
        patterns: windowPatterns,
        poll_interval_ms: 500,
      });

      set({ isMonitoring: true });
    } catch (error) {
      console.error('Failed to start window monitoring:', error);
    }
  },

  // Stop window monitoring
  stopMonitoring: async () => {
    try {
      await detectionApi.stopWindowMonitoring();
      set({ isMonitoring: false, lastMatchedWindow: null });
    } catch (error) {
      console.error('Failed to stop window monitoring:', error);
    }
  },

  // Handle window match event - triggers auto-capture if enabled
  handleWindowMatch: (event: WindowMatchEvent) => {
    const { autoCapture, session } = get();

    set({ lastMatchedWindow: event });

    console.log('Window matched:', event.window_info.title, '| Pattern:', event.matched_pattern);

    // Auto-capture if enabled and not already capturing
    if (autoCapture && (!session || session.status === 'idle' || session.status === 'ready' || session.status === 'error')) {
      console.log('Auto-capturing screen for matched window...');
      get().startCapture();
    }
  },
}));
