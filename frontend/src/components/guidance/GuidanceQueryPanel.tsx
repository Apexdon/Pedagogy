/**
 * GuidanceQueryPanel Component
 *
 * Left panel containing query input and step list.
 */

import { useState, useEffect } from 'react';
import { Card, CardBody, Button, Input, Loading } from '@/components/ui';
import { StepCard } from './StepCard';
import { useGuidance } from '@/hooks';
import { listKnowledgeBases } from '@/api';
import type { KnowledgeBase } from '@/types';

export function GuidanceQueryPanel() {
  const {
    steps,
    currentStep,
    hasActiveSession,
    isGenerating,
    error,
    startGuidance,
    goToStep,
    reset,
  } = useGuidance();

  const [query, setQuery] = useState('');
  const [applicationContext, setApplicationContext] = useState('');
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKBId, setSelectedKBId] = useState<string>('');

  // Fetch knowledge bases on mount
  useEffect(() => {
    const fetchKBs = async () => {
      try {
        const response = await listKnowledgeBases();
        setKnowledgeBases(response.knowledge_bases);
      } catch (err) {
        console.error('Failed to fetch knowledge bases:', err);
      }
    };

    fetchKBs();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isGenerating) return;

    // Target app is configured by org admins - coordinator will use the default
    await startGuidance(query.trim(), {
      kb_id: selectedKBId || undefined,
      application_context: applicationContext.trim() || undefined,
    });

    // Clear form on success
    if (!error) {
      setQuery('');
    }
  };

  const handleNewSession = () => {
    reset();
    setQuery('');
    setApplicationContext('');
  };

  return (
    <Card className="h-full flex flex-col">
      <CardBody className="flex flex-col h-full p-4">
        {/* Header */}
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-gray-900">AI Guidance</h2>
          <p className="text-sm text-gray-500">
            Ask a question to get step-by-step instructions
          </p>
        </div>

        {/* Query Form (shown when no active session or generating) */}
        {(!hasActiveSession || isGenerating) && (
          <form onSubmit={handleSubmit} className="space-y-3 mb-4">
            {/* Query Input */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                What do you need help with?
              </label>
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g., How do I save a file?"
                disabled={isGenerating}
              />
            </div>

            {/* Application Context (optional) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Application Context (optional)
              </label>
              <Input
                value={applicationContext}
                onChange={(e) => setApplicationContext(e.target.value)}
                placeholder="Additional context about what you're doing"
                disabled={isGenerating}
              />
            </div>

            {/* Knowledge Base Selector (optional) */}
            {knowledgeBases.length > 0 && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Knowledge Base (optional)
                </label>
                <select
                  value={selectedKBId}
                  onChange={(e) => setSelectedKBId(e.target.value)}
                  disabled={isGenerating}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
                >
                  <option value="">All Knowledge Bases</option>
                  {knowledgeBases.map((kb) => (
                    <option key={kb.kb_id} value={kb.kb_id}>
                      {kb.kb_name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Submit Button */}
            <Button
              type="submit"
              disabled={!query.trim() || isGenerating}
              className="w-full"
            >
              {isGenerating ? (
                <span className="flex items-center justify-center gap-2">
                  <Loading size="sm" />
                  <span>Generating...</span>
                </span>
              ) : (
                'Get Guidance'
              )}
            </Button>

            {/* Note about LLM time */}
            {isGenerating && (
              <p className="text-xs text-gray-500 text-center">
                This may take 1-2 minutes on first request
              </p>
            )}
          </form>
        )}

        {/* Error Display */}
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm text-red-700">{error}</p>
            <button
              onClick={() => reset()}
              className="mt-2 text-sm text-red-600 underline hover:no-underline"
            >
              Try again
            </button>
          </div>
        )}

        {/* Steps List (shown when session is active) */}
        {hasActiveSession && !isGenerating && (
          <>
            {/* Session Header */}
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-gray-700">
                {steps.length} Steps
              </span>
              <button
                onClick={handleNewSession}
                className="text-sm text-primary-600 hover:text-primary-700 font-medium"
              >
                New Query
              </button>
            </div>

            {/* Steps */}
            <div className="flex-1 overflow-y-auto space-y-2">
              {steps.map((step) => (
                <StepCard
                  key={step.step_id}
                  step={step}
                  isActive={step.step_number === currentStep}
                  onClick={() => goToStep(step.step_number)}
                />
              ))}
            </div>
          </>
        )}

        {/* Empty State (no session, not generating) */}
        {!hasActiveSession && !isGenerating && !error && (
          <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
            <svg
              className="w-12 h-12 mb-3"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
              />
            </svg>
            <p className="text-sm">Enter a question to get started</p>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
