/**
 * HistoryPage
 *
 * Shows list of past guidance sessions with ability to view details or resume.
 */

import { useState, useEffect } from 'react';
import { Card, CardBody, Button, Loading } from '@/components/ui';
import { listGuidanceSessions, resumeSession } from '@/api/guidance';
import { useGuidanceStore } from '@/stores';
import { useNavigate } from 'react-router-dom';
import type { GuidanceSession } from '@/types';

const statusColors: Record<string, { bg: string; text: string; label: string }> = {
  active: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Active' },
  paused: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Paused' },
  completed: { bg: 'bg-green-100', text: 'text-green-700', label: 'Completed' },
  abandoned: { bg: 'bg-gray-100', text: 'text-gray-600', label: 'Abandoned' },
  error: { bg: 'bg-red-100', text: 'text-red-700', label: 'Error' },
};

export function HistoryPage() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<GuidanceSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [resumingId, setResumingId] = useState<string | null>(null);

  const guidanceStore = useGuidanceStore();

  // Fetch sessions
  useEffect(() => {
    const fetchSessions = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await listGuidanceSessions(statusFilter || undefined, 50);
        setSessions(response.sessions);
      } catch (err) {
        setError('Failed to load guidance history');
        console.error('Failed to fetch sessions:', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchSessions();
  }, [statusFilter]);

  const handleResumeSession = async (session: GuidanceSession) => {
    if (session.status !== 'paused' && session.status !== 'active') return;

    setResumingId(session.session_id);
    try {
      const response = await resumeSession(session.session_id);

      // Update store with session data
      guidanceStore.reset();
      // Navigate to guidance page - the store will pick up the session
      navigate('/guidance');
    } catch (err) {
      console.error('Failed to resume session:', err);
      setError('Failed to resume session');
    } finally {
      setResumingId(null);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Guidance History</h1>
          <p className="text-gray-600">View and resume your past guidance sessions</p>
        </div>

        {/* Filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        >
          <option value="">All Sessions</option>
          <option value="active">Active</option>
          <option value="paused">Paused</option>
          <option value="completed">Completed</option>
          <option value="abandoned">Abandoned</option>
        </select>
      </div>

      {/* Error Display */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Sessions List */}
      <Card className="flex-1 overflow-hidden">
        <CardBody className="h-full overflow-y-auto p-0">
          {isLoading ? (
            <div className="h-full flex items-center justify-center">
              <Loading size="lg" />
            </div>
          ) : sessions.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-gray-400">
              <svg
                className="w-16 h-16 mb-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <p className="text-lg font-medium">No Sessions Found</p>
              <p className="text-sm mt-1">
                {statusFilter
                  ? `No ${statusFilter} sessions`
                  : 'Start a guidance session to see it here'}
              </p>
              <Button
                onClick={() => navigate('/guidance')}
                className="mt-4"
              >
                Start New Session
              </Button>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {sessions.map((session) => {
                const statusInfo = statusColors[session.status] || statusColors.error;
                const canResume = session.status === 'paused' || session.status === 'active';

                return (
                  <div
                    key={session.session_id}
                    className="p-4 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-4">
                      {/* Session Info */}
                      <div className="flex-1 min-w-0">
                        {/* Query */}
                        <p className="font-medium text-gray-900 truncate">
                          {session.query}
                        </p>

                        {/* Metadata Row */}
                        <div className="flex items-center gap-3 mt-2 text-sm text-gray-500">
                          {/* Status Badge */}
                          <span
                            className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusInfo.bg} ${statusInfo.text}`}
                          >
                            {statusInfo.label}
                          </span>

                          {/* Progress */}
                          <span>
                            {session.current_step}/{session.total_steps} steps
                          </span>

                          {/* Application Context */}
                          {session.application_context && (
                            <span className="text-gray-400">
                              {session.application_context}
                            </span>
                          )}

                          {/* Confidence */}
                          {session.overall_confidence > 0 && (
                            <span>
                              {Math.round(session.overall_confidence * 100)}% confidence
                            </span>
                          )}
                        </div>

                        {/* Timestamp */}
                        <p className="text-xs text-gray-400 mt-1">
                          {formatDate(session.created_at)}
                          {session.completed_at && (
                            <> &bull; Completed {formatDate(session.completed_at)}</>
                          )}
                        </p>
                      </div>

                      {/* Actions */}
                      <div className="flex-shrink-0">
                        {canResume && (
                          <Button
                            size="sm"
                            onClick={() => handleResumeSession(session)}
                            disabled={resumingId === session.session_id}
                          >
                            {resumingId === session.session_id ? (
                              <Loading size="sm" />
                            ) : (
                              'Resume'
                            )}
                          </Button>
                        )}
                        {session.status === 'completed' && (
                          <span className="text-sm text-green-600 font-medium">
                            Completed
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Progress Bar (for active/paused) */}
                    {(session.status === 'active' || session.status === 'paused') && (
                      <div className="mt-3">
                        <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary-500 transition-all"
                            style={{
                              width: `${(session.current_step / session.total_steps) * 100}%`,
                            }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
