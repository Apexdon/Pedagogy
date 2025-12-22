import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardBody, CardHeader, Button, SlidePanel } from '@/components/ui';
import { GuidanceChat } from '@/components/guidance';
import { useAuthStore } from '@/stores';

export function DashboardPage() {
  const navigate = useNavigate();
  const { user, selectedOrg } = useAuthStore();
  const [isGuidancePanelOpen, setIsGuidancePanelOpen] = useState(false);

  const handleSwitchOrg = () => {
    navigate('/select-org');
  };

  const handleOpenGuidance = () => {
    setIsGuidancePanelOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* Welcome header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Welcome, {user?.full_name || 'User'}!
          </h1>
          <p className="text-gray-600 mt-1">
            Ready to learn and get guidance from {selectedOrg?.org_name}.
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={handleSwitchOrg}>
          Switch Organisation
        </Button>
      </div>

      {/* Current Organisation Card */}
      <Card>
        <CardBody>
          <div className="flex items-center gap-4">
            <div
              className="w-16 h-16 rounded-xl flex items-center justify-center text-white font-bold text-2xl flex-shrink-0"
              style={{ backgroundColor: selectedOrg?.primary_color || '#3B82F6' }}
            >
              {selectedOrg?.org_name?.charAt(0).toUpperCase() || 'O'}
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-semibold text-gray-900">{selectedOrg?.org_name}</h2>
              <p className="text-gray-500">/{selectedOrg?.org_slug}</p>
              <p className="text-sm text-gray-600 mt-1">
                You're receiving guidance from this organisation
              </p>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Quick Actions */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Get Started</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Start Guidance Session */}
          <Card hover className="cursor-pointer" onClick={handleOpenGuidance}>
            <CardBody className="text-center py-8">
              <div className="w-16 h-16 mx-auto rounded-full bg-primary-100 flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="font-semibold text-gray-900 mb-2">Start Guidance Session</h3>
              <p className="text-sm text-gray-500">
                Get step-by-step guidance on your current task
              </p>
            </CardBody>
          </Card>

          {/* Browse Guides */}
          <Card hover className="cursor-pointer">
            <CardBody className="text-center py-8">
              <div className="w-16 h-16 mx-auto rounded-full bg-green-100 flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
              </div>
              <h3 className="font-semibold text-gray-900 mb-2">Browse Guides</h3>
              <p className="text-sm text-gray-500">
                Explore available tutorials and documentation
              </p>
            </CardBody>
          </Card>

          {/* Ask a Question */}
          <Card hover className="cursor-pointer" onClick={handleOpenGuidance}>
            <CardBody className="text-center py-8">
              <div className="w-16 h-16 mx-auto rounded-full bg-purple-100 flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="font-semibold text-gray-900 mb-2">Ask a Question</h3>
              <p className="text-sm text-gray-500">
                Get answers based on the organisation's knowledge
              </p>
            </CardBody>
          </Card>
        </div>
      </div>

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">Recent Activity</h2>
        </CardHeader>
        <CardBody>
          <div className="text-center py-8 text-gray-500">
            <svg className="w-12 h-12 mx-auto text-gray-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p>No recent activity yet</p>
            <p className="text-sm mt-1">Start a guidance session to see your history here</p>
          </div>
        </CardBody>
      </Card>

      {/* Guidance Panel */}
      <SlidePanel
        isOpen={isGuidancePanelOpen}
        onClose={() => setIsGuidancePanelOpen(false)}
        title="Guidance Session"
        width="lg"
      >
        <GuidanceChat />
      </SlidePanel>
    </div>
  );
}
