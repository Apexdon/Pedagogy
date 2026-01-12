import React from 'react';

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
}

interface CoordinatorStatus {
  status: string;
  isTargetActive: boolean;
  targetWindow: string | null;
}

interface ExpandedPanelProps {
  session: SessionData | null;
  currentStep: CurrentStep | null;
  coordinatorStatus: CoordinatorStatus;
  onMinimize: () => void;
  onNext: () => void;
  onPrevious: () => void;
  onSkip: () => void;
  onEndSession: () => void;
}

export const ExpandedPanel: React.FC<ExpandedPanelProps> = ({
  session,
  currentStep,
  coordinatorStatus,
  onMinimize,
  onNext,
  onPrevious,
  onSkip,
  onEndSession,
}) => {
  const progress = currentStep
    ? (currentStep.stepNumber / currentStep.totalSteps) * 100
    : 0;

  const getStatusColor = () => {
    switch (coordinatorStatus.status) {
      case 'tracking':
        return '#10b981'; // green
      case 'scanning':
        return '#f59e0b'; // yellow
      case 'waiting':
        return '#6b7280'; // gray
      case 'error':
        return '#ef4444'; // red
      default:
        return '#6b7280';
    }
  };

  const getStatusText = () => {
    switch (coordinatorStatus.status) {
      case 'tracking':
        return 'Tracking Active';
      case 'scanning':
        return 'Scanning...';
      case 'waiting':
        return 'Waiting for App';
      case 'error':
        return 'Error';
      default:
        return 'Ready';
    }
  };

  const getActionIcon = () => {
    switch (currentStep?.actionType) {
      case 'click':
        return '👆';
      case 'type':
        return '⌨️';
      case 'select':
        return '📋';
      case 'scroll':
        return '📜';
      case 'navigate':
        return '🔗';
      default:
        return '👉';
    }
  };

  return (
    <div className="expanded-panel">
      {/* Title bar with minimize button */}
      <div className="panel-header">
        <div className="panel-title">
          <span className="panel-icon">📚</span>
          <span>Pedagogy Guidance</span>
        </div>
        <button className="minimize-btn" onClick={onMinimize} title="Minimize">
          <span>−</span>
        </button>
      </div>

      {/* Status indicator */}
      <div className="status-bar">
        <div className="status-indicator" style={{ backgroundColor: getStatusColor() }} />
        <span className="status-text">{getStatusText()}</span>
        {coordinatorStatus.targetWindow && (
          <span className="target-window" title={coordinatorStatus.targetWindow}>
            {coordinatorStatus.targetWindow.length > 20
              ? coordinatorStatus.targetWindow.substring(0, 20) + '...'
              : coordinatorStatus.targetWindow}
          </span>
        )}
      </div>

      {session && currentStep ? (
        <>
          {/* Progress section */}
          <div className="progress-section">
            <div className="step-counter">
              Step {currentStep.stepNumber} of {currentStep.totalSteps}
            </div>
            <div className="progress-bar-container">
              <div className="progress-bar" style={{ width: `${progress}%` }} />
            </div>
          </div>

          {/* Main instruction */}
          <div className="instruction-section">
            <div className="action-badge">
              <span className="action-icon">{getActionIcon()}</span>
              <span className="action-type">{currentStep.actionType}</span>
            </div>
            <p className="main-instruction">{currentStep.instruction}</p>
            {currentStep.detailedInstruction && (
              <p className="detailed-instruction">{currentStep.detailedInstruction}</p>
            )}
          </div>

          {/* Target info */}
          {currentStep.targetLabel && (
            <div className="target-info">
              <span className="target-label">Target: </span>
              <span className="target-value">{currentStep.targetLabel}</span>
              {currentStep.confidence !== null && (
                <span className="confidence-badge">
                  {Math.round(currentStep.confidence * 100)}%
                </span>
              )}
            </div>
          )}

          {/* Navigation controls */}
          <div className="navigation-controls">
            <button
              className="nav-btn secondary"
              onClick={onPrevious}
              disabled={currentStep.stepNumber <= 1}
            >
              ← Prev
            </button>
            <button className="nav-btn tertiary" onClick={onSkip}>
              Skip
            </button>
            <button
              className="nav-btn primary"
              onClick={onNext}
              disabled={currentStep.stepNumber >= currentStep.totalSteps}
            >
              Next →
            </button>
          </div>

          {/* End session button */}
          <div className="session-controls">
            <button className="end-session-btn" onClick={onEndSession}>
              End Session
            </button>
          </div>
        </>
      ) : (
        <div className="no-session">
          <p className="no-session-text">No active guidance session</p>
          <p className="no-session-hint">Start a session from the main app</p>
        </div>
      )}

      {/* Drag handle */}
      <div className="drag-handle" title="Drag to reposition">
        <span>⋮⋮</span>
      </div>
    </div>
  );
};
