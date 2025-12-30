/**
 * StepProgressBar Component
 *
 * Horizontal progress bar showing step completion status.
 */

import type { GuidanceStep } from '@/types';

interface StepProgressBarProps {
  steps: GuidanceStep[];
  currentStep: number;
  onStepClick?: (stepNumber: number) => void;
}

const stepColors = {
  pending: 'bg-gray-300',
  current: 'bg-primary-500',
  completed: 'bg-green-500',
  skipped: 'bg-yellow-500',
  failed: 'bg-red-500',
};

export function StepProgressBar({ steps, currentStep, onStepClick }: StepProgressBarProps) {
  if (steps.length === 0) return null;

  const completedCount = steps.filter(
    (s) => s.status === 'completed' || s.status === 'skipped'
  ).length;
  const progressPercent = (completedCount / steps.length) * 100;

  return (
    <div className="w-full">
      {/* Progress Text */}
      <div className="flex justify-between items-center mb-2">
        <span className="text-sm font-medium text-gray-700">
          Step {currentStep} of {steps.length}
        </span>
        <span className="text-sm text-gray-500">
          {Math.round(progressPercent)}% complete
        </span>
      </div>

      {/* Progress Bar */}
      <div className="relative">
        {/* Background Bar */}
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-green-500 transition-all duration-300 ease-out"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {/* Step Indicators */}
        <div className="absolute inset-0 flex items-center justify-between px-0">
          {steps.map((step, index) => {
            const position = (index / (steps.length - 1)) * 100;
            const isClickable = onStepClick !== undefined;

            return (
              <button
                key={step.step_id}
                onClick={() => isClickable && onStepClick?.(step.step_number)}
                disabled={!isClickable}
                className={`
                  w-4 h-4 rounded-full border-2 border-white shadow-sm
                  transition-transform duration-200
                  ${stepColors[step.status]}
                  ${step.step_number === currentStep ? 'scale-125 ring-2 ring-primary-300' : ''}
                  ${isClickable ? 'hover:scale-125 cursor-pointer' : 'cursor-default'}
                `}
                style={{
                  position: 'absolute',
                  left: steps.length === 1 ? '50%' : `${position}%`,
                  transform: 'translateX(-50%)',
                }}
                title={`Step ${step.step_number}: ${step.instruction.substring(0, 50)}...`}
              />
            );
          })}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-green-500" />
          <span>Completed</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-primary-500" />
          <span>Current</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-yellow-500" />
          <span>Skipped</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-gray-300" />
          <span>Pending</span>
        </div>
      </div>
    </div>
  );
}
