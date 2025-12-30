/**
 * GuidancePage
 *
 * Main page for AI-powered step-by-step guidance.
 * Two-panel layout: Left (query input + steps), Right (active step display)
 */

import { useAuthStore } from '@/stores';
import { GuidanceQueryPanel, GuidanceSessionPanel } from '@/components/guidance';

export function GuidancePage() {
  const { selectedOrg } = useAuthStore();

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col">
      {/* Header */}
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900">AI Guidance</h1>
        <p className="text-gray-600">
          Get step-by-step instructions powered by AI
          {selectedOrg?.org_name && ` and ${selectedOrg.org_name}'s knowledge base`}
        </p>
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
