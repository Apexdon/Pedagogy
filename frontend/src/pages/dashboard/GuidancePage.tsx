/**
 * GuidancePage
 *
 * Main page for AI-powered step-by-step guidance.
 * Two-panel layout: Left (query input + steps), Right (active step display)
 *
 * Integrates with GuidanceCoordinator for automatic window detection,
 * screen capture, and halo overlay display.
 */

import { useEffect, useRef, useCallback } from 'react';
import { useAuthStore, useGuidanceStore } from '@/stores';
import { GuidanceQueryPanel, GuidanceSessionPanel } from '@/components/guidance';
import { useGuidanceCoordinator } from '@/hooks';

export function GuidancePage() {
  const { selectedOrg } = useAuthStore();
  const { session, steps, hasActiveSession, currentStep, advance, skip, goTo, abandon } = useGuidanceStore();

  // Callbacks for panel navigation (wrapped in useCallback for stability)
  const handlePanelNext = useCallback(async () => {
    console.log('[GuidancePage] Panel next clicked, calling advance()');
    await advance();
  }, [advance]);

  const handlePanelPrev = useCallback(async () => {
    console.log('[GuidancePage] Panel prev clicked, going to step', currentStep - 1);
    if (currentStep > 1) {
      await goTo(currentStep - 1);
    }
  }, [currentStep, goTo]);

  const handlePanelSkip = useCallback(async () => {
    console.log('[GuidancePage] Panel skip clicked, calling skip()');
    await skip();
  }, [skip]);

  const handlePanelEndSession = useCallback(async () => {
    console.log('[GuidancePage] Panel end session clicked, calling abandon()');
    await abandon();
  }, [abandon]);

  // Track previous step for detecting changes
  const prevStepRef = useRef<number | null>(null);

  // Initialize the coordinator for automatic detection
  const {
    status: coordinatorStatus,
    isInitialized: coordinatorInitialized,
    isActive: coordinatorActive,
    isTargetWindowActive,
    error: coordinatorError,
    initialize: initializeCoordinator,
    start: startCoordinator,
    stop: stopCoordinator,
    updateCurrentStep: updateCoordinatorStep,
  } = useGuidanceCoordinator({
    config: {
      captureIntervalMs: 2000,
      windowPollIntervalMs: 500,
      autoStartOnTargetWindow: true,
      showHaloOnStepChange: true,
    },
    onTargetWindowFound: (windowTitle) => {
      console.log('Target window found:', windowTitle);
    },
    onTargetWindowLost: (windowTitle) => {
      console.log('Target window lost:', windowTitle);
    },
    onStepTargetFound: (data) => {
      console.log('Step target found:', data);
    },
    onSessionCompleted: (completedSession) => {
      console.log('Session completed:', completedSession);
    },
    onError: (error) => {
      console.error('Coordinator error:', error);
    },
    // Panel navigation callbacks - wired to store actions
    onPanelNextClicked: handlePanelNext,
    onPanelPrevClicked: handlePanelPrev,
    onPanelSkipClicked: handlePanelSkip,
    onPanelEndSession: handlePanelEndSession,
  });

  // Initialize coordinator when session becomes active
  // The coordinator will automatically use the org's default target app settings
  useEffect(() => {
    if (hasActiveSession && session && steps.length > 0 && !coordinatorInitialized) {
      initializeCoordinator(session, steps).then(() => {
        console.log('Coordinator initialized - starting automatic detection');
        startCoordinator().catch(console.error);
      }).catch(console.error);
    }
  }, [hasActiveSession, session, steps, coordinatorInitialized, initializeCoordinator, startCoordinator]);

  // Cleanup coordinator when session ends
  useEffect(() => {
    if (!hasActiveSession && coordinatorInitialized) {
      stopCoordinator().catch(console.error);
    }
  }, [hasActiveSession, coordinatorInitialized, stopCoordinator]);

  // Sync coordinator when store's currentStep changes (from UI navigation)
  useEffect(() => {
    if (coordinatorInitialized && hasActiveSession && currentStep > 0) {
      // Only update if step actually changed
      if (prevStepRef.current !== null && prevStepRef.current !== currentStep) {
        console.log('[GuidancePage] Step changed from', prevStepRef.current, 'to', currentStep, '- syncing coordinator');
        updateCoordinatorStep(currentStep);
      }
      prevStepRef.current = currentStep;
    }
  }, [currentStep, coordinatorInitialized, hasActiveSession, updateCoordinatorStep]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCoordinator().catch(console.error);
    };
  }, [stopCoordinator]);

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col">
      {/* Header */}
      <div className="mb-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">AI Guidance</h1>
            <p className="text-gray-600">
              Get step-by-step instructions powered by AI
              {selectedOrg?.org_name && ` and ${selectedOrg.org_name}'s knowledge base`}
            </p>
          </div>

          {/* Coordinator Status Indicator */}
          {hasActiveSession && coordinatorInitialized && (
            <div className="flex items-center gap-2">
              {coordinatorStatus === 'error' ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                  <span className="w-2 h-2 rounded-full bg-red-500" />
                  Error
                </span>
              ) : isTargetWindowActive ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  Tracking Active
                </span>
              ) : coordinatorActive ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                  <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                  Scanning
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                  <span className="w-2 h-2 rounded-full bg-yellow-500" />
                  Waiting for App
                </span>
              )}
            </div>
          )}
        </div>

        {/* Coordinator Error Display */}
        {coordinatorError && (
          <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{coordinatorError}</p>
          </div>
        )}
      </div>

      {/* Two-Panel Layout */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* Left Panel - Query Input & Step List (1/3 width) */}
        <div className="w-1/3 min-w-[320px]">
          <GuidanceQueryPanel />
        </div>

        {/* Right Panel - Active Step Display (2/3 width) */}
        <div className="flex-1">
          <GuidanceSessionPanel />
        </div>
      </div>
    </div>
  );
}
