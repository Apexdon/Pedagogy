/**
 * GuidanceSessionPanel Component
 *
 * Right panel showing the current step and navigation controls.
 * Visual guidance (screen capture, CV, halo overlay) is handled
 * automatically by the GuidanceCoordinator service.
 */

import { Card, CardBody, Button, Loading } from '@/components/ui';
import { StepProgressBar } from './StepProgressBar';
import { useGuidance } from '@/hooks';

export function GuidanceSessionPanel() {
  const {
    query,
    steps,
    currentStep,
    totalSteps,
    currentStepData,
    contextSummary,
    overallConfidence,
    status,
    hasActiveSession,
    isGenerating,
    isAdvancing,
    canAdvance,
    canGoBack,
    isLastStep,
    // Actions
    completeStep,
    skipCurrentStep,
    goToPreviousStep,
    goToStep,
    pause,
    resume,
    endSession,
  } = useGuidance();

  // Empty state - no active session
  if (!hasActiveSession && !isGenerating) {
    return (
      <Card className="h-full">
        <CardBody className="h-full flex flex-col items-center justify-center text-gray-400">
          <svg
            className="w-20 h-20 mb-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1}
              d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
            />
          </svg>
          <p className="text-lg font-medium text-gray-500">No Active Session</p>
          <p className="text-sm text-gray-400 mt-1">
            Enter a question on the left to start
          </p>
        </CardBody>
      </Card>
    );
  }

  // Loading state
  if (isGenerating) {
    return (
      <Card className="h-full">
        <CardBody className="h-full flex flex-col items-center justify-center">
          <Loading size="lg" />
          <p className="mt-4 text-lg font-medium text-gray-700">
            Generating Guidance...
          </p>
          <p className="text-sm text-gray-500 mt-2">
            Analyzing your question and creating step-by-step instructions
          </p>
          <p className="text-xs text-gray-400 mt-4">
            This may take 1-2 minutes on first request
          </p>
        </CardBody>
      </Card>
    );
  }

  // Completed state
  if (status === 'completed') {
    return (
      <Card className="h-full">
        <CardBody className="h-full flex flex-col items-center justify-center">
          <div className="w-20 h-20 rounded-full bg-green-100 flex items-center justify-center mb-4">
            <svg
              className="w-10 h-10 text-green-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <p className="text-xl font-semibold text-gray-900">
            Guidance Complete!
          </p>
          <p className="text-sm text-gray-500 mt-2 text-center max-w-md">
            You've completed all {totalSteps} steps for "{query}"
          </p>

          {/* Summary */}
          <div className="mt-6 p-4 bg-gray-50 rounded-lg max-w-md w-full">
            <p className="text-sm text-gray-700">
              <span className="font-medium">Completed:</span>{' '}
              {steps.filter((s) => s.status === 'completed').length} steps
            </p>
            <p className="text-sm text-gray-700 mt-1">
              <span className="font-medium">Skipped:</span>{' '}
              {steps.filter((s) => s.status === 'skipped').length} steps
            </p>
          </div>

          <Button onClick={endSession} variant="secondary" className="mt-6">
            Start New Session
          </Button>
        </CardBody>
      </Card>
    );
  }

  // Active session - show current step
  return (
    <Card className="h-full flex flex-col">
      <CardBody className="flex flex-col h-full p-6">
        {/* Query Context */}
        <div className="mb-4">
          <p className="text-sm text-gray-500">Currently helping with:</p>
          <p className="text-base font-medium text-gray-900 mt-1">"{query}"</p>
          {contextSummary && (
            <p className="text-sm text-gray-600 mt-2">{contextSummary}</p>
          )}
        </div>

        {/* Progress Bar */}
        <div className="mb-6">
          <StepProgressBar
            steps={steps}
            currentStep={currentStep}
            onStepClick={goToStep}
          />
        </div>

        {/* Current Step Display */}
        {currentStepData && (
          <div className="flex-1 flex flex-col">
            {/* Step Header */}
            <div className="flex items-center gap-3 mb-4">
              <span className="flex items-center justify-center w-10 h-10 rounded-full bg-primary-100 text-primary-700 text-lg font-bold">
                {currentStep}
              </span>
              <div>
                <p className="text-sm text-gray-500">Current Step</p>
                <p className="text-sm text-gray-700">
                  {currentStepData.action_type.charAt(0).toUpperCase() +
                    currentStepData.action_type.slice(1)}{' '}
                  action
                </p>
              </div>
            </div>

            {/* Main Instruction */}
            <div className="bg-primary-50 border-l-4 border-primary-500 p-4 rounded-r-lg mb-4">
              <p className="text-lg font-medium text-gray-900">
                {currentStepData.instruction}
              </p>
            </div>

            {/* Detailed Instruction */}
            {currentStepData.detailed_instruction && (
              <div className="bg-gray-50 p-4 rounded-lg mb-4">
                <p className="text-sm text-gray-600">
                  {currentStepData.detailed_instruction}
                </p>
              </div>
            )}

            {/* Action Value (if applicable) */}
            {currentStepData.action_value && (
              <div className="bg-gray-100 p-3 rounded-lg mb-4">
                <p className="text-sm text-gray-600 mb-1">Enter this value:</p>
                <code className="text-base font-mono bg-white px-3 py-1 rounded border">
                  {currentStepData.action_value}
                </code>
              </div>
            )}

            {/* Confidence (if available) */}
            {overallConfidence > 0 && (
              <p className="text-xs text-gray-400 mb-4">
                Confidence: {Math.round(overallConfidence * 100)}%
              </p>
            )}

            {/* Spacer */}
            <div className="flex-1" />

            {/* Navigation Controls */}
            <div className="border-t pt-4 mt-4">
              <div className="flex items-center gap-3">
                {/* Previous Button */}
                <Button
                  variant="secondary"
                  onClick={goToPreviousStep}
                  disabled={!canGoBack || isAdvancing}
                  className="flex items-center gap-1"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                  Previous
                </Button>

                {/* Skip Button */}
                <Button
                  variant="ghost"
                  onClick={skipCurrentStep}
                  disabled={isAdvancing}
                  className="text-gray-600"
                >
                  Skip
                </Button>

                {/* Spacer */}
                <div className="flex-1" />

                {/* Next/Complete Button */}
                <Button
                  onClick={completeStep}
                  disabled={!canAdvance || isAdvancing}
                  className="flex items-center gap-1"
                >
                  {isAdvancing ? (
                    <Loading size="sm" />
                  ) : (
                    <>
                      {isLastStep ? 'Complete' : 'Next'}
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </>
                  )}
                </Button>
              </div>

              {/* Session Controls */}
              <div className="flex items-center justify-center gap-4 mt-4 pt-4 border-t">
                {status === 'paused' ? (
                  <button
                    onClick={resume}
                    className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                  >
                    Resume Session
                  </button>
                ) : (
                  <button
                    onClick={pause}
                    className="text-sm text-gray-500 hover:text-gray-700"
                  >
                    Pause Session
                  </button>
                )}
                <span className="text-gray-300">|</span>
                <button
                  onClick={endSession}
                  className="text-sm text-red-500 hover:text-red-700"
                >
                  End Session
                </button>
              </div>
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
