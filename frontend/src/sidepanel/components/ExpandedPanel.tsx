import React, { useState } from 'react';
import type { TimingBreakdown } from '../types';

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
  const [showTiming, setShowTiming] = useState(false);
  const [showDetectionTiming, setShowDetectionTiming] = useState(false);
  const [showRegionTiming, setShowRegionTiming] = useState(false);

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

          {/* Timing breakdown (collapsible) */}
          {currentStep.timing && (
            <div className="timing-section">
              <button
                className="timing-toggle"
                onClick={() => setShowTiming(!showTiming)}
              >
                <span className="timing-icon">⏱</span>
                <span>Analysis: {currentStep.timing.total_ms.toFixed(0)}ms</span>
                <span className="toggle-arrow">{showTiming ? '▼' : '▶'}</span>
              </button>
              {showTiming && (
                <div className="timing-details">
                  <div className="timing-row">
                    <span className="timing-label">Preprocessing</span>
                    <span className="timing-value">{currentStep.timing.preprocessing_ms.toFixed(0)}ms</span>
                  </div>
                  <div className="timing-row">
                    <span className="timing-label">Detection (UI)</span>
                    <span className="timing-value">{currentStep.timing.detection_ms.toFixed(0)}ms</span>
                  </div>
                  {/* Detection timing breakdown (expandable) */}
                  {currentStep.timing.detection_timing && (
                    <div className="region-timing-section">
                      <button
                        className="region-timing-toggle"
                        onClick={() => setShowDetectionTiming(!showDetectionTiming)}
                      >
                        <span className="timing-label">  ↳ Detection Breakdown</span>
                        <span className="toggle-arrow">{showDetectionTiming ? '▼' : '▶'}</span>
                      </button>
                      {showDetectionTiming && (
                        <div className="detection-timing-list">
                          <div className="timing-row timing-sub">
                            <span className="timing-label">Preprocess</span>
                            <span className="timing-value">{currentStep.timing.detection_timing.preprocess_ms.toFixed(0)}ms</span>
                          </div>
                          <div className="timing-row timing-sub">
                            <span className="timing-label">Inference</span>
                            <span className="timing-value">{currentStep.timing.detection_timing.inference_ms.toFixed(0)}ms</span>
                          </div>
                          <div className="timing-row timing-sub">
                            <span className="timing-label">Postprocess</span>
                            <span className="timing-value">{currentStep.timing.detection_timing.postprocess_ms.toFixed(0)}ms</span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                  <div className="timing-row">
                    <span className="timing-label">OCR Total</span>
                    <span className="timing-value">{currentStep.timing.ocr_ms.toFixed(0)}ms</span>
                  </div>
                  {/* OCR breakdown - indented */}
                  <div className="timing-row timing-sub">
                    <span className="timing-label">↳ Text Detection</span>
                    <span className="timing-value">{(currentStep.timing.ocr_detection_ms ?? 0).toFixed(0)}ms</span>
                  </div>
                  <div className="timing-row timing-sub">
                    <span className="timing-label">↳ Text Recognition</span>
                    <span className="timing-value">{(currentStep.timing.ocr_recognition_ms ?? 0).toFixed(0)}ms</span>
                  </div>
                  {/* Per-region timing breakdown (expandable) */}
                  {currentStep.timing.region_timings && currentStep.timing.region_timings.length > 0 && (
                    <div className="region-timing-section">
                      <button
                        className="region-timing-toggle"
                        onClick={() => setShowRegionTiming(!showRegionTiming)}
                      >
                        <span className="timing-label">  ↳ Per-Region Details ({currentStep.timing.region_timings.length})</span>
                        <span className="toggle-arrow">{showRegionTiming ? '▼' : '▶'}</span>
                      </button>
                      {showRegionTiming && (
                        <div className="region-timing-list">
                          {currentStep.timing.region_timings.map((region) => (
                            <div key={region.region_index} className="region-timing-item">
                              <div className="region-header">
                                <span className="region-index">#{region.region_index + 1}</span>
                                <span className="region-text" title={region.text}>
                                  {region.text.length > 20 ? region.text.substring(0, 20) + '...' : region.text}
                                </span>
                                <span className="region-total">{region.total_ms.toFixed(0)}ms</span>
                              </div>
                              <div className="region-details">
                                <span className="region-size">{region.crop_width}×{region.crop_height}</span>
                                <span className="region-breakdown">
                                  pre:{region.preprocess_ms.toFixed(0)} inf:{region.inference_ms.toFixed(0)} dec:{region.decode_ms.toFixed(0)}
                                </span>
                                <span className="region-conf">{(region.confidence * 100).toFixed(0)}%</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  <div className="timing-row">
                    <span className="timing-label">Matching</span>
                    <span className="timing-value">{currentStep.timing.matching_ms.toFixed(0)}ms</span>
                  </div>
                  <div className="timing-row">
                    <span className="timing-label">Verification</span>
                    <span className="timing-value">{currentStep.timing.verification_ms.toFixed(0)}ms</span>
                  </div>
                  <div className="timing-divider" />
                  <div className="timing-row">
                    <span className="timing-label">Elements found</span>
                    <span className="timing-value">{currentStep.timing.element_count}</span>
                  </div>
                  <div className="timing-row">
                    <span className="timing-label">Text regions</span>
                    <span className="timing-value">{currentStep.timing.text_region_count}</span>
                  </div>
                </div>
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
