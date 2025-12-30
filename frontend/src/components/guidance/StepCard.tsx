/**
 * StepCard Component
 *
 * Displays an individual guidance step with status indicator.
 */

import type { GuidanceStep } from '@/types';

interface StepCardProps {
  step: GuidanceStep;
  isActive: boolean;
  onClick?: () => void;
}

const statusStyles = {
  pending: 'bg-gray-50 border-gray-200 text-gray-600',
  current: 'bg-primary-50 border-primary-500 text-primary-700 shadow-sm',
  completed: 'bg-green-50 border-green-500 text-green-700',
  skipped: 'bg-yellow-50 border-yellow-500 text-yellow-700',
  failed: 'bg-red-50 border-red-500 text-red-700',
};

const statusIcons = {
  pending: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <circle cx="12" cy="12" r="10" strokeWidth={2} />
    </svg>
  ),
  current: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 9l3 3m0 0l-3 3m3-3H8m13 0a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  completed: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  skipped: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
    </svg>
  ),
  failed: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
};

const actionTypeBadges: Record<string, { label: string; color: string }> = {
  click: { label: 'Click', color: 'bg-blue-100 text-blue-700' },
  type: { label: 'Type', color: 'bg-purple-100 text-purple-700' },
  select: { label: 'Select', color: 'bg-indigo-100 text-indigo-700' },
  navigate: { label: 'Navigate', color: 'bg-teal-100 text-teal-700' },
  press: { label: 'Press', color: 'bg-orange-100 text-orange-700' },
  scroll: { label: 'Scroll', color: 'bg-cyan-100 text-cyan-700' },
};

export function StepCard({ step, isActive, onClick }: StepCardProps) {
  const actionBadge = actionTypeBadges[step.action_type] || {
    label: step.action_type,
    color: 'bg-gray-100 text-gray-700',
  };

  return (
    <div
      className={`
        p-3 rounded-lg border-2 transition-all cursor-pointer
        ${statusStyles[step.status]}
        ${isActive ? 'ring-2 ring-primary-300' : ''}
        hover:shadow-md
      `}
      onClick={onClick}
    >
      {/* Header Row */}
      <div className="flex items-center gap-2 mb-2">
        {/* Step Number */}
        <span className="flex items-center justify-center w-6 h-6 rounded-full bg-current bg-opacity-20 text-sm font-semibold">
          {step.step_number}
        </span>

        {/* Status Icon */}
        <span className="flex-shrink-0">{statusIcons[step.status]}</span>

        {/* Action Type Badge */}
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${actionBadge.color}`}>
          {actionBadge.label}
        </span>

        {/* Confidence (if available) */}
        {step.match_confidence > 0 && (
          <span className="ml-auto text-xs text-gray-500">
            {Math.round(step.match_confidence * 100)}% match
          </span>
        )}
      </div>

      {/* Instruction */}
      <p className="text-sm font-medium leading-snug">{step.instruction}</p>

      {/* Detailed Instruction (shown for active step) */}
      {isActive && step.detailed_instruction && (
        <p className="mt-2 text-xs text-gray-600 leading-relaxed">
          {step.detailed_instruction}
        </p>
      )}

      {/* Action Value (if applicable) */}
      {step.action_value && (
        <div className="mt-2 flex items-center gap-1">
          <span className="text-xs text-gray-500">Value:</span>
          <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded text-gray-700">
            {step.action_value}
          </code>
        </div>
      )}
    </div>
  );
}
