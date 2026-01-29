import { useState, useEffect, useCallback } from 'react';
import {
  listTargetApps,
  createTargetApp,
  updateTargetApp,
  deleteTargetApp,
  setDefaultTargetApp,
  toggleTargetAppActive,
} from '@/api/guidance';
import type {
  TargetApplication,
  TargetAppCreateRequest,
  TargetAppUpdateRequest,
} from '@/types';

type ModalMode = 'create' | 'edit' | null;

export function TargetAppsPage() {
  const [targetApps, setTargetApps] = useState<TargetApplication[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [modalMode, setModalMode] = useState<ModalMode>(null);
  const [editingApp, setEditingApp] = useState<TargetApplication | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Form states
  const [formData, setFormData] = useState<TargetAppCreateRequest>({
    app_name: '',
    description: '',
    match_mode: 'auto',
    url_patterns: [],
    brand_keywords: [],
    process_name: '',
    is_active: true,
    is_default: false,
  });

  // Comma-separated inputs
  const [urlPatternsInput, setUrlPatternsInput] = useState('');
  const [brandKeywordsInput, setBrandKeywordsInput] = useState('');

  const fetchTargetApps = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await listTargetApps();
      setTargetApps(response.target_apps);
    } catch (err) {
      setError('Failed to load target applications');
      console.error('Error fetching target apps:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTargetApps();
  }, [fetchTargetApps]);

  const resetForm = () => {
    setFormData({
      app_name: '',
      description: '',
      match_mode: 'auto',
      url_patterns: [],
      brand_keywords: [],
      process_name: '',
      is_active: true,
      is_default: false,
    });
    setUrlPatternsInput('');
    setBrandKeywordsInput('');
  };

  const openCreateModal = () => {
    resetForm();
    setEditingApp(null);
    setModalMode('create');
  };

  const openEditModal = (app: TargetApplication) => {
    setEditingApp(app);
    setFormData({
      app_name: app.app_name,
      description: app.description || '',
      match_mode: app.match_mode,
      url_patterns: app.url_patterns || [],
      brand_keywords: app.brand_keywords || [],
      process_name: app.process_name || '',
      is_active: app.is_active,
      is_default: app.is_default,
    });
    setUrlPatternsInput((app.url_patterns || []).join(', '));
    setBrandKeywordsInput((app.brand_keywords || []).join(', '));
    setModalMode('edit');
  };

  const closeModal = () => {
    setModalMode(null);
    setEditingApp(null);
    resetForm();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.app_name.trim()) return;

    try {
      setIsSubmitting(true);

      // Parse URL patterns from comma-separated input
      const urlPatterns = urlPatternsInput
        .split(',')
        .map(p => p.trim())
        .filter(p => p.length > 0);

      // Parse brand keywords from comma-separated input
      const brandKeywords = brandKeywordsInput
        .split(',')
        .map(p => p.trim())
        .filter(p => p.length > 0);

      // Build data object explicitly to control what gets sent
      const data: TargetAppCreateRequest = {
        app_name: formData.app_name.trim(),
        description: formData.description?.trim() || undefined,
        match_mode: 'auto', // Always use auto mode
        url_patterns: urlPatterns.length > 0 ? urlPatterns : undefined,
        brand_keywords: brandKeywords.length > 0 ? brandKeywords : undefined,
        process_name: formData.process_name?.trim() || undefined,
        is_active: formData.is_active,
        is_default: formData.is_default,
      };

      console.log('Submitting target app data:', data);

      if (modalMode === 'create') {
        await createTargetApp(data);
      } else if (modalMode === 'edit' && editingApp) {
        const updateData: TargetAppUpdateRequest = {
          app_name: data.app_name,
          description: data.description,
          url_patterns: data.url_patterns,
          brand_keywords: data.brand_keywords,
          process_name: data.process_name,
        };
        console.log('Update data:', updateData);
        await updateTargetApp(editingApp.app_id, updateData);
      }

      closeModal();
      await fetchTargetApps();
    } catch (err) {
      setError(modalMode === 'create' ? 'Failed to create target app' : 'Failed to update target app');
      console.error('Error saving target app:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (appId: string) => {
    try {
      setIsSubmitting(true);
      await deleteTargetApp(appId);
      setShowDeleteConfirm(null);
      await fetchTargetApps();
    } catch (err) {
      setError('Failed to delete target application');
      console.error('Error deleting target app:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSetDefault = async (appId: string) => {
    try {
      await setDefaultTargetApp(appId);
      await fetchTargetApps();
    } catch (err) {
      setError('Failed to set default');
      console.error('Error setting default:', err);
    }
  };

  const handleToggleActive = async (appId: string) => {
    try {
      await toggleTargetAppActive(appId);
      await fetchTargetApps();
    } catch (err) {
      setError('Failed to toggle active status');
      console.error('Error toggling active:', err);
    }
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  // Render loading state
  if (isLoading && targetApps.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Target Applications</h1>
          <p className="text-gray-600 mt-1">
            Configure applications and websites to guide users through
          </p>
        </div>
        <button
          onClick={openCreateModal}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Application
        </button>
      </div>

      {/* Error message */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex justify-between items-center">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">
            Dismiss
          </button>
        </div>
      )}

      {/* Target Apps Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {targetApps.length === 0 ? (
          <div className="col-span-full text-center py-12">
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
                d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
              />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">No target applications</h3>
            <p className="mt-1 text-sm text-gray-500">
              Add applications or websites to guide users through.
            </p>
            <div className="mt-6">
              <button
                onClick={openCreateModal}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
              >
                Add Application
              </button>
            </div>
          </div>
        ) : (
          targetApps.map((app) => (
            <div
              key={app.app_id}
              className={`bg-white rounded-xl border p-5 hover:shadow-md transition-shadow ${
                app.is_default ? 'border-primary-300 ring-1 ring-primary-200' : 'border-gray-200'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold text-gray-900 truncate">{app.app_name}</h3>
                    {app.is_default && (
                      <span className="px-2 py-0.5 text-xs font-medium bg-primary-100 text-primary-700 rounded-full">
                        Default
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-500 mt-1 line-clamp-2">
                    {app.description || 'No description'}
                  </p>
                </div>
                <span
                  className={`ml-2 px-2 py-1 text-xs rounded-full ${
                    app.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {app.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>

              <div className="mt-4 space-y-2 text-sm">
                {app.url_patterns && app.url_patterns.length > 0 && (
                  <div className="flex items-start gap-2">
                    <span className="text-gray-500 w-20 flex-shrink-0">URL:</span>
                    <span className="font-medium text-primary-700">
                      {app.url_patterns.slice(0, 2).join(', ')}
                      {app.url_patterns.length > 2 && ` +${app.url_patterns.length - 2} more`}
                    </span>
                  </div>
                )}
                {app.process_name && (
                  <div className="flex items-center gap-2">
                    <span className="text-gray-500 w-20">Process:</span>
                    <span className="font-medium text-gray-900 truncate">{app.process_name}</span>
                  </div>
                )}
                {app.brand_keywords && app.brand_keywords.length > 0 && (
                  <div className="flex items-start gap-2">
                    <span className="text-gray-500 w-20 flex-shrink-0">Keywords:</span>
                    <span className="font-medium text-gray-600 text-xs">
                      {app.brand_keywords.slice(0, 3).join(', ')}
                      {app.brand_keywords.length > 3 && ` +${app.brand_keywords.length - 3} more`}
                    </span>
                  </div>
                )}
                {!app.url_patterns?.length && !app.process_name && (
                  <p className="text-amber-600 text-xs">
                    No detection configured. Add URL patterns (for web apps) or process name (for desktop apps).
                  </p>
                )}
              </div>

              <div className="mt-4 pt-4 border-t border-gray-100 flex items-center justify-between">
                <span className="text-xs text-gray-500">Updated {formatDate(app.updated_at)}</span>
                <div className="flex gap-1">
                  {!app.is_default && (
                    <button
                      onClick={() => handleSetDefault(app.app_id)}
                      className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                      title="Set as default"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                      </svg>
                    </button>
                  )}
                  <button
                    onClick={() => handleToggleActive(app.app_id)}
                    className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                    title={app.is_active ? 'Deactivate' : 'Activate'}
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      {app.is_active ? (
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                      ) : (
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      )}
                    </svg>
                  </button>
                  <button
                    onClick={() => openEditModal(app)}
                    className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                    title="Edit"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </button>
                  <button
                    onClick={() => setShowDeleteConfirm(app.app_id)}
                    className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
                    title="Delete"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Create/Edit Modal */}
      {modalMode && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              {modalMode === 'create' ? 'Add Target Application' : 'Edit Target Application'}
            </h2>
            <form onSubmit={handleSubmit}>
              <div className="space-y-4">
                {/* Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                  <input
                    type="text"
                    value={formData.app_name}
                    onChange={(e) => setFormData({ ...formData, app_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder="e.g., RS Components Website"
                    required
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder="Optional description"
                    rows={2}
                  />
                </div>

                {/* URL Patterns - Primary detection for web apps */}
                <div className="p-4 bg-primary-50 rounded-lg border border-primary-200">
                  <label className="block text-sm font-medium text-primary-900 mb-1">
                    URL Patterns (For Web Apps) ⭐
                  </label>
                  <input
                    type="text"
                    value={urlPatternsInput}
                    onChange={(e) => setUrlPatternsInput(e.target.value)}
                    className="w-full px-3 py-2 border border-primary-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white"
                    placeholder="e.g., uk.rs-online.com, rs-online.com"
                  />
                  <p className="mt-2 text-xs text-primary-700">
                    Comma-separated domain patterns. The system identifies the target browser window
                    by extracting the URL from the address bar. This is the most reliable method
                    for websites as URLs stay constant across page navigations.
                  </p>
                </div>

                {/* Brand Keywords - Secondary/fallback */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Brand Keywords (Fallback)
                  </label>
                  <input
                    type="text"
                    value={brandKeywordsInput}
                    onChange={(e) => setBrandKeywordsInput(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder="e.g., RS Components, rs-online"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Used as fallback if URL matching fails. Keywords in browser window title.
                  </p>
                </div>

                {/* Process Name - For desktop apps */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Process Name (Desktop Apps Only)
                  </label>
                  <input
                    type="text"
                    value={formData.process_name}
                    onChange={(e) => setFormData({ ...formData, process_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder="e.g., Code.exe, excel.exe"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Only needed for desktop applications. Leave empty for websites.
                  </p>
                </div>

                {/* Set as default checkbox (only for create) */}
                {modalMode === 'create' && (
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="is_default"
                      checked={formData.is_default}
                      onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                      className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                    />
                    <label htmlFor="is_default" className="text-sm text-gray-700">
                      Set as default application
                    </label>
                  </div>
                )}
              </div>

              <div className="mt-6 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={closeModal}
                  className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !formData.app_name.trim()}
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
                >
                  {isSubmitting ? 'Saving...' : modalMode === 'create' ? 'Create' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md">
            <h2 className="text-xl font-semibold text-gray-900 mb-2">Delete Target Application?</h2>
            <p className="text-gray-600 mb-6">
              This will permanently delete this target application. Any guidance sessions using
              this app will need to select a different target.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowDeleteConfirm(null)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(showDeleteConfirm)}
                disabled={isSubmitting}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                {isSubmitting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
