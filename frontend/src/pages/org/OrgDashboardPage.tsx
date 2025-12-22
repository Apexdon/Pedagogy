import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardBody, CardHeader, Button, Loading } from '@/components/ui';
import { useAuthStore, useUIStore } from '@/stores';
import { getOrgDashboardStats, createKnowledgeBase, uploadDocuments, listKnowledgeBases } from '@/api';
import type { OrgDashboardStats, RecentActivityItem, TeamMemberSummary, KnowledgeBase } from '@/types';

export function OrgDashboardPage() {
  const navigate = useNavigate();
  const { user, selectedOrg } = useAuthStore();
  const { addToast } = useUIStore();

  const [stats, setStats] = useState<OrgDashboardStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Modal states for quick actions
  const [showCreateKBModal, setShowCreateKBModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [newKBName, setNewKBName] = useState('');
  const [newKBDescription, setNewKBDescription] = useState('');
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [selectedKBId, setSelectedKBId] = useState<string>('');
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [isLoadingKBs, setIsLoadingKBs] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await getOrgDashboardStats();
        setStats(data);
      } catch (error) {
        console.error('Failed to fetch dashboard stats:', error);
        addToast({ type: 'error', message: 'Failed to load dashboard statistics' });
      } finally {
        setIsLoading(false);
      }
    };

    fetchStats();
  }, [addToast]);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'member_joined':
        return (
          <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
            <svg className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
            </svg>
          </div>
        );
      case 'document_uploaded':
        return (
          <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
            <svg className="w-4 h-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
        );
      case 'kb_created':
        return (
          <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center">
            <svg className="w-4 h-4 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
        );
      default:
        return (
          <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
            <svg className="w-4 h-4 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
        );
    }
  };

  const getRoleBadgeColor = (memberRole: string) => {
    switch (memberRole) {
      case 'org_admin':
        return 'bg-purple-100 text-purple-700';
      case 'manager':
        return 'bg-blue-100 text-blue-700';
      case 'viewer':
        return 'bg-gray-100 text-gray-700';
      default:
        return 'bg-green-100 text-green-700';
    }
  };

  const getTrendIcon = (trend: string) => {
    if (trend === 'up') {
      return (
        <span className="text-green-500 flex items-center text-sm">
          <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
          </svg>
          Up
        </span>
      );
    } else if (trend === 'down') {
      return (
        <span className="text-red-500 flex items-center text-sm">
          <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
          Down
        </span>
      );
    }
    return <span className="text-gray-500 text-sm">Stable</span>;
  };

  // Quick action handlers
  const handleCreateKB = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKBName.trim()) return;

    try {
      setIsSubmitting(true);
      await createKnowledgeBase({
        kb_name: newKBName.trim(),
        description: newKBDescription.trim() || undefined,
      });
      addToast({ type: 'success', message: 'Knowledge base created successfully!' });
      setShowCreateKBModal(false);
      setNewKBName('');
      setNewKBDescription('');
      // Refresh stats
      const data = await getOrgDashboardStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to create KB:', error);
      addToast({ type: 'error', message: 'Failed to create knowledge base' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    setUploadFiles((prev) => [...prev, ...files]);
  };

  const handleRemoveFile = (index: number) => {
    setUploadFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleOpenUploadModal = async () => {
    setShowUploadModal(true);
    setIsLoadingKBs(true);
    try {
      const response = await listKnowledgeBases();
      setKnowledgeBases(response.knowledge_bases);
      // Pre-select first KB if available
      if (response.knowledge_bases.length > 0) {
        setSelectedKBId(response.knowledge_bases[0].kb_id);
      }
    } catch (error) {
      console.error('Failed to fetch knowledge bases:', error);
      addToast({ type: 'error', message: 'Failed to load knowledge bases' });
    } finally {
      setIsLoadingKBs(false);
    }
  };

  const handleUploadDocuments = async (e: React.FormEvent) => {
    e.preventDefault();
    if (uploadFiles.length === 0) return;
    if (!selectedKBId) {
      addToast({ type: 'error', message: 'Please select a knowledge base' });
      return;
    }

    try {
      setIsSubmitting(true);
      await uploadDocuments(uploadFiles, { kb_id: selectedKBId });
      addToast({ type: 'success', message: `${uploadFiles.length} document(s) uploaded successfully!` });
      setShowUploadModal(false);
      setUploadFiles([]);
      setSelectedKBId('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      // Refresh stats
      const data = await getOrgDashboardStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to upload documents:', error);
      addToast({ type: 'error', message: 'Failed to upload documents' });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loading size="lg" message="Loading dashboard..." />
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Failed to load dashboard data</p>
        <Button onClick={() => window.location.reload()} className="mt-4">
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Welcome header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Organisation Dashboard
          </h1>
          <p className="text-gray-600 mt-1">
            Welcome back, {user?.full_name || 'Admin'}! Here's an overview of {selectedOrg?.org_name}.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => navigate('/org/members')}>
            Manage Members
          </Button>
          <Button variant="secondary" size="sm" onClick={() => navigate('/org/profile')}>
            Org Settings
          </Button>
        </div>
      </div>

      {/* Onboarding Progress (if not complete) */}
      {stats.onboarding_completion < 100 && (
        <Card className="border-amber-200 bg-amber-50">
          <CardBody>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center">
                  <svg className="w-6 h-6 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-semibold text-amber-800">Complete Your Setup</h3>
                  <p className="text-sm text-amber-700">
                    {stats.onboarding_completion}% complete - {stats.pending_setup_items.length} item(s) remaining
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="w-32 bg-amber-200 rounded-full h-2">
                  <div
                    className="bg-amber-500 h-2 rounded-full transition-all"
                    style={{ width: `${stats.onboarding_completion}%` }}
                  />
                </div>
                <Button size="sm" onClick={() => navigate('/org/profile')}>
                  Continue Setup
                </Button>
              </div>
            </div>
            {stats.pending_setup_items.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {stats.pending_setup_items.map((item, idx) => (
                  <span key={idx} className="px-2 py-1 bg-amber-100 text-amber-700 rounded text-xs">
                    {item}
                  </span>
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardBody className="text-center">
            <div className="w-12 h-12 mx-auto rounded-full bg-blue-100 flex items-center justify-center mb-3">
              <svg className="w-6 h-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            </div>
            <p className="text-3xl font-bold text-gray-900">{stats.total_members}</p>
            <p className="text-sm text-gray-500">Team Members</p>
          </CardBody>
        </Card>

        <Card>
          <CardBody className="text-center">
            <div className="w-12 h-12 mx-auto rounded-full bg-green-100 flex items-center justify-center mb-3">
              <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p className="text-3xl font-bold text-gray-900">{stats.total_documents}</p>
            <p className="text-sm text-gray-500">Documents</p>
          </CardBody>
        </Card>

        <Card>
          <CardBody className="text-center">
            <div className="w-12 h-12 mx-auto rounded-full bg-purple-100 flex items-center justify-center mb-3">
              <svg className="w-6 h-6 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <p className="text-3xl font-bold text-gray-900">{stats.total_knowledge_bases}</p>
            <p className="text-sm text-gray-500">Knowledge Bases</p>
          </CardBody>
        </Card>

        <Card>
          <CardBody className="text-center">
            <div className="w-12 h-12 mx-auto rounded-full bg-orange-100 flex items-center justify-center mb-3">
              <svg className="w-6 h-6 text-orange-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-3xl font-bold text-gray-900">{stats.total_sessions}</p>
            <p className="text-sm text-gray-500">Total Sessions</p>
            <div className="mt-2 flex items-center justify-center gap-2">
              <span className="text-xs text-gray-400">This week: {stats.sessions_this_week}</span>
              {getTrendIcon(stats.sessions_trend)}
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">Quick Actions</h2>
        </CardHeader>
        <CardBody>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <button
              onClick={() => navigate('/org/members')}
              className="flex flex-col items-center p-4 rounded-lg border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors"
            >
              <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center mb-2">
                <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
                </svg>
              </div>
              <span className="text-sm font-medium text-gray-700">Add Member</span>
            </button>

            <button
              onClick={handleOpenUploadModal}
              className="flex flex-col items-center p-4 rounded-lg border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors"
            >
              <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center mb-2">
                <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <span className="text-sm font-medium text-gray-700">Upload Document</span>
            </button>

            <button
              onClick={() => setShowCreateKBModal(true)}
              className="flex flex-col items-center p-4 rounded-lg border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors"
            >
              <div className="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center mb-2">
                <svg className="w-5 h-5 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
              </div>
              <span className="text-sm font-medium text-gray-700">Create KB</span>
            </button>

            <button
              onClick={() => navigate('/org/profile')}
              className="flex flex-col items-center p-4 rounded-lg border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors"
            >
              <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center mb-2">
                <svg className="w-5 h-5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </div>
              <span className="text-sm font-medium text-gray-700">Settings</span>
            </button>
          </div>
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Team Overview */}
        <Card>
          <CardHeader className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Team Overview</h2>
            <Button variant="ghost" size="sm" onClick={() => navigate('/org/members')}>
              View All
            </Button>
          </CardHeader>
          <CardBody>
            {/* Role distribution */}
            <div className="mb-4 flex flex-wrap gap-2">
              {Object.entries(stats.members_by_role).map(([roleName, count]) => (
                <span
                  key={roleName}
                  className={`px-2 py-1 rounded text-xs font-medium ${getRoleBadgeColor(roleName)}`}
                >
                  {count} {roleName.replace('_', ' ')}
                </span>
              ))}
            </div>

            {/* Recent team members */}
            <div className="space-y-3">
              {stats.team_members.slice(0, 5).map((member: TeamMemberSummary) => (
                <div key={member.user_id} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-sm font-medium text-gray-600">
                      {(member.full_name || member.email).charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {member.full_name || member.email}
                      </p>
                      <p className="text-xs text-gray-500">{member.email}</p>
                    </div>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-xs ${getRoleBadgeColor(member.role)}`}>
                    {member.role.replace('_', ' ')}
                  </span>
                </div>
              ))}
              {stats.team_members.length === 0 && (
                <p className="text-sm text-gray-500 text-center py-4">No team members yet</p>
              )}
            </div>
          </CardBody>
        </Card>

        {/* Knowledge Base Summary */}
        <Card>
          <CardHeader className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Knowledge Base</h2>
            <Button variant="ghost" size="sm" onClick={() => navigate('/org/knowledge')}>
              Manage
            </Button>
          </CardHeader>
          <CardBody>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-gray-900">{stats.knowledge_base.total_documents}</p>
                <p className="text-xs text-gray-500">Documents</p>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-gray-900">{stats.knowledge_base.total_chunks}</p>
                <p className="text-xs text-gray-500">Processed Chunks</p>
              </div>
            </div>

            {/* Processing status */}
            {Object.keys(stats.knowledge_base.processing_status).length > 0 && (
              <div className="mb-4">
                <p className="text-xs font-medium text-gray-500 mb-2">Processing Status</p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(stats.knowledge_base.processing_status).map(([status, count]) => (
                    <span
                      key={status}
                      className={`px-2 py-1 rounded text-xs ${
                        status === 'completed'
                          ? 'bg-green-100 text-green-700'
                          : status === 'processing'
                          ? 'bg-blue-100 text-blue-700'
                          : status === 'failed'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {count} {status}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Recent uploads */}
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2">Recent Uploads</p>
              {stats.knowledge_base.recent_uploads.length > 0 ? (
                <div className="space-y-2">
                  {stats.knowledge_base.recent_uploads.slice(0, 3).map((doc) => (
                    <div key={doc.doc_id} className="flex items-center gap-2 text-sm">
                      <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <span className="flex-1 truncate text-gray-700">{doc.file_name}</span>
                      <span className="text-xs text-gray-400">{formatDate(doc.uploaded_at)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500 text-center py-2">No documents uploaded yet</p>
              )}
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">Recent Activity</h2>
        </CardHeader>
        <CardBody>
          {stats.recent_activities.length > 0 ? (
            <div className="space-y-4">
              {stats.recent_activities.slice(0, 10).map((activity: RecentActivityItem) => (
                <div key={activity.activity_id} className="flex items-start gap-3">
                  {getActivityIcon(activity.activity_type)}
                  <div className="flex-1">
                    <p className="text-sm text-gray-900">{activity.description}</p>
                    <p className="text-xs text-gray-500">
                      {activity.user_name && <span className="font-medium">{activity.user_name} - </span>}
                      {formatDate(activity.timestamp)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <svg className="w-12 h-12 mx-auto text-gray-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p>No recent activity</p>
              <p className="text-sm mt-1">Activity will appear here as your team uses Pedagogy</p>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Create KB Modal */}
      {showCreateKBModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Create Knowledge Base</h2>
            <form onSubmit={handleCreateKB}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                  <input
                    type="text"
                    value={newKBName}
                    onChange={(e) => setNewKBName(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder="Enter knowledge base name"
                    required
                    autoFocus
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                  <textarea
                    value={newKBDescription}
                    onChange={(e) => setNewKBDescription(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder="Enter description (optional)"
                    rows={3}
                  />
                </div>
              </div>
              <div className="mt-6 flex justify-end gap-3">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setShowCreateKBModal(false);
                    setNewKBName('');
                    setNewKBDescription('');
                  }}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting || !newKBName.trim()}>
                  {isSubmitting ? 'Creating...' : 'Create'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Upload Documents Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-lg mx-4">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Upload Documents</h2>
            <form onSubmit={handleUploadDocuments}>
              <div className="space-y-4">
                {/* Knowledge Base Selector */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Knowledge Base *
                  </label>
                  {isLoadingKBs ? (
                    <div className="flex items-center justify-center py-3">
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary-600"></div>
                      <span className="ml-2 text-sm text-gray-500">Loading knowledge bases...</span>
                    </div>
                  ) : knowledgeBases.length === 0 ? (
                    <div className="text-center py-3 bg-amber-50 border border-amber-200 rounded-lg">
                      <p className="text-sm text-amber-700">No knowledge bases found.</p>
                      <p className="text-xs text-amber-600 mt-1">
                        Please create a knowledge base first using the "Create KB" quick action.
                      </p>
                    </div>
                  ) : (
                    <select
                      value={selectedKBId}
                      onChange={(e) => setSelectedKBId(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      required
                    >
                      {knowledgeBases.map((kb) => (
                        <option key={kb.kb_id} value={kb.kb_id}>
                          {kb.kb_name} ({kb.document_count} docs)
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                {/* File Drop Zone */}
                <div
                  className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-primary-500 cursor-pointer transition-colors"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <svg
                    className="mx-auto h-12 w-12 text-gray-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                    />
                  </svg>
                  <p className="mt-2 text-sm text-gray-600">Click to select files or drag and drop</p>
                  <p className="text-xs text-gray-500 mt-1">PDF, DOCX, MD, TXT (max 50MB)</p>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.docx,.md,.markdown,.txt"
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                </div>

                {/* Selected Files List */}
                {uploadFiles.length > 0 && (
                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-gray-700">
                      Selected files ({uploadFiles.length})
                    </label>
                    <div className="max-h-40 overflow-y-auto space-y-2">
                      {uploadFiles.map((file, index) => (
                        <div
                          key={index}
                          className="flex items-center justify-between bg-gray-50 px-3 py-2 rounded-lg"
                        >
                          <div className="flex items-center min-w-0">
                            <svg
                              className="w-4 h-4 text-gray-400 mr-2 flex-shrink-0"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                              />
                            </svg>
                            <span className="text-sm text-gray-700 truncate">{file.name}</span>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleRemoveFile(index)}
                            className="ml-2 text-gray-400 hover:text-red-500"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <div className="mt-6 flex justify-end gap-3">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setShowUploadModal(false);
                    setUploadFiles([]);
                    setSelectedKBId('');
                  }}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting || uploadFiles.length === 0 || !selectedKBId}>
                  {isSubmitting ? 'Uploading...' : 'Upload'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
