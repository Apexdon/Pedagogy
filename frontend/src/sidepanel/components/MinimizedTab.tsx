import React from 'react';

interface MinimizedTabProps {
  stepNumber: number;
  totalSteps: number;
  onExpand: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  isHovering: boolean;
}

export const MinimizedTab: React.FC<MinimizedTabProps> = ({
  stepNumber,
  totalSteps,
  onExpand,
  onMouseEnter,
  onMouseLeave,
  isHovering,
}) => {
  return (
    <div
      className={`minimized-tab ${isHovering ? 'hovering' : ''}`}
      onClick={onExpand}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      title="Click to expand guidance panel"
    >
      {/* Show step number badge or icon */}
      {stepNumber > 0 ? (
        <div className="tab-step-badge">
          <span className="step-current">{stepNumber}</span>
        </div>
      ) : (
        <div className="tab-icon">📚</div>
      )}

      {/* Hover preview tooltip */}
      {isHovering && (
        <div className="hover-preview">
          <span>Guidance Panel</span>
          {stepNumber > 0 && (
            <span className="preview-step">Step {stepNumber} of {totalSteps}</span>
          )}
        </div>
      )}
    </div>
  );
};
