import React, { useEffect, useState, useCallback } from 'react';
import { listen } from '@tauri-apps/api/event';
import { invoke } from '@tauri-apps/api/core';
import { ExpandedPanel } from './components/ExpandedPanel';
import { MinimizedTab } from './components/MinimizedTab';
import type {
  PanelState,
  SessionStartedPayload,
  StepChangedPayload,
  SessionEndedPayload,
  StateChangedPayload,
  CoordinatorStatusPayload,
  TimingBreakdown,
} from './types';
import { PANEL_EVENTS } from './types';

interface SessionData {
  sessionId: string;
  query: string;
  totalSteps: number;
  applicationContext: string | null;
}

interface CurrentStep {
  stepNumber: number;
  totalSteps: number;
  instruction: string;
  detailedInstruction: string | null;
  actionType: string;
  targetLabel: string | null;
  confidence: number | null;
  timing?: TimingBreakdown | null;
}

interface CoordinatorStatus {
  status: string;
  isTargetActive: boolean;
  targetWindow: string | null;
}

export const SidePanelApp: React.FC = () => {
  const [panelState, setPanelState] = useState<PanelState>('expanded');
  const [session, setSession] = useState<SessionData | null>(null);
  const [currentStep, setCurrentStep] = useState<CurrentStep | null>(null);
  const [coordinatorStatus, setCoordinatorStatus] = useState<CoordinatorStatus>({
    status: 'idle',
    isTargetActive: false,
    targetWindow: null,
  });
  const [isHovering, setIsHovering] = useState(false);

  // Handle panel state changes from Rust
  useEffect(() => {
    const unlistenState = listen<StateChangedPayload>(
      PANEL_EVENTS.STATE_CHANGED,
      (event) => {
        console.log('Panel state changed:', event.payload);
        setPanelState(event.payload.state);
      }
    );

    return () => {
      unlistenState.then((fn) => fn());
    };
  }, []);

  // Listen for session events
  useEffect(() => {
    const unlistenSessionStarted = listen<SessionStartedPayload>(
      PANEL_EVENTS.SESSION_STARTED,
      (event) => {
        console.log('Session started:', event.payload);
        setSession({
          sessionId: event.payload.session_id,
          query: event.payload.query,
          totalSteps: event.payload.total_steps,
          applicationContext: event.payload.application_context,
        });
      }
    );

    const unlistenStepChanged = listen<StepChangedPayload>(
      PANEL_EVENTS.STEP_CHANGED,
      (event) => {
        console.log('Step changed:', event.payload);
        setCurrentStep({
          stepNumber: event.payload.step_number,
          totalSteps: event.payload.total_steps,
          instruction: event.payload.instruction,
          detailedInstruction: event.payload.detailed_instruction,
          actionType: event.payload.action_type,
          targetLabel: event.payload.target_label,
          confidence: event.payload.confidence,
          timing: event.payload.timing,
        });
      }
    );

    const unlistenSessionEnded = listen<SessionEndedPayload>(
      PANEL_EVENTS.SESSION_ENDED,
      (event) => {
        console.log('Session ended:', event.payload);
        setSession(null);
        setCurrentStep(null);
      }
    );

    const unlistenCoordinatorStatus = listen<CoordinatorStatusPayload>(
      PANEL_EVENTS.COORDINATOR_STATUS,
      (event) => {
        console.log('Coordinator status:', event.payload);
        setCoordinatorStatus({
          status: event.payload.status,
          isTargetActive: event.payload.is_target_active,
          targetWindow: event.payload.target_window,
        });
      }
    );

    // Notify the main app that the panel is ready to receive events
    // This allows the main app to re-send the current session state
    const notifyReady = async () => {
      try {
        const { emit } = await import('@tauri-apps/api/event');
        await emit('panel:ready', {});
        console.log('Panel ready event emitted');
      } catch (error) {
        console.error('Failed to emit panel ready event:', error);
      }
    };
    notifyReady();

    return () => {
      unlistenSessionStarted.then((fn) => fn());
      unlistenStepChanged.then((fn) => fn());
      unlistenSessionEnded.then((fn) => fn());
      unlistenCoordinatorStatus.then((fn) => fn());
    };
  }, []);

  // Navigation handlers - emit events to main window
  const handleNext = useCallback(async () => {
    try {
      // Emit event to main window
      const { emit } = await import('@tauri-apps/api/event');
      await emit('panel:next_clicked', {});
    } catch (error) {
      console.error('Failed to emit next event:', error);
    }
  }, []);

  const handlePrevious = useCallback(async () => {
    try {
      const { emit } = await import('@tauri-apps/api/event');
      await emit('panel:prev_clicked', {});
    } catch (error) {
      console.error('Failed to emit prev event:', error);
    }
  }, []);

  const handleSkip = useCallback(async () => {
    try {
      const { emit } = await import('@tauri-apps/api/event');
      await emit('panel:skip_clicked', {});
    } catch (error) {
      console.error('Failed to emit skip event:', error);
    }
  }, []);

  const handleEndSession = useCallback(async () => {
    try {
      const { emit } = await import('@tauri-apps/api/event');
      await emit('panel:end_session', {});
    } catch (error) {
      console.error('Failed to emit end session event:', error);
    }
  }, []);

  // Panel control handlers
  const handleMinimize = useCallback(async () => {
    try {
      await invoke('minimize_sidepanel');
    } catch (error) {
      console.error('Failed to minimize panel:', error);
    }
  }, []);

  const handleExpand = useCallback(async () => {
    try {
      await invoke('expand_sidepanel');
    } catch (error) {
      console.error('Failed to expand panel:', error);
    }
  }, []);

  // Handle hover for auto-expand when minimized
  const handleMouseEnter = useCallback(() => {
    setIsHovering(true);
    if (panelState === 'minimized') {
      handleExpand();
    }
  }, [panelState, handleExpand]);

  const handleMouseLeave = useCallback(() => {
    setIsHovering(false);
  }, []);

  // Render based on panel state
  if (panelState === 'hidden') {
    return null;
  }

  if (panelState === 'minimized') {
    return (
      <MinimizedTab
        stepNumber={currentStep?.stepNumber ?? 0}
        totalSteps={currentStep?.totalSteps ?? 0}
        onExpand={handleExpand}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        isHovering={isHovering}
      />
    );
  }

  return (
    <ExpandedPanel
      session={session}
      currentStep={currentStep}
      coordinatorStatus={coordinatorStatus}
      onMinimize={handleMinimize}
      onNext={handleNext}
      onPrevious={handlePrevious}
      onSkip={handleSkip}
      onEndSession={handleEndSession}
    />
  );
};
