import { useEffect, useState } from 'react';
import { Card, CardBody, CardHeader, Button, Input, Loading } from '@/components/ui';
import { useAuthStore, useUIStore } from '@/stores';
import { getOrganisationProfile, updateOrganisationProfile } from '@/api';
import type { OrganisationProfile } from '@/types';
import type { AxiosError } from 'axios';
import type { HttpErrorResponse } from '@/types';

export function ProfilePage() {
  const { selectedOrg, role, selectOrganisation } = useAuthStore();
  const { addToast } = useUIStore();

  const [profile, setProfile] = useState<OrganisationProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const [editData, setEditData] = useState({
    org_name: '',
    primary_color: '',
  });

  const isAdmin = role === 'org_admin';

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const data = await getOrganisationProfile();
        setProfile(data);
        setEditData({
          org_name: data.org_name,
          primary_color: data.primary_color,
        });
      } catch {
        addToast({ type: 'error', message: 'Failed to load organisation profile' });
      } finally {
        setIsLoading(false);
      }
    };

    fetchProfile();
  }, [addToast]);

  const handleSave = async () => {
    if (!profile) return;

    setIsSaving(true);

    try {
      const response = await updateOrganisationProfile({
        org_name: editData.org_name !== profile.org_name ? editData.org_name : undefined,
        primary_color: editData.primary_color !== profile.primary_color ? editData.primary_color : undefined,
      });

      // Update local state
      setProfile((prev) => prev ? { ...prev, ...editData } : null);

      // Update store if org name or color changed
      if (selectedOrg && role) {
        selectOrganisation(
          {
            ...selectedOrg,
            org_name: editData.org_name,
            primary_color: editData.primary_color,
          },
          role
        );
      }

      addToast({ type: 'success', message: response.message });
      setIsEditing(false);
    } catch (error) {
      const axiosError = error as AxiosError<HttpErrorResponse>;
      const message = axiosError.response?.data?.detail || 'Failed to update profile';
      addToast({ type: 'error', message });
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    if (profile) {
      setEditData({
        org_name: profile.org_name,
        primary_color: profile.primary_color,
      });
    }
    setIsEditing(false);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loading size="lg" message="Loading profile..." />
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Failed to load organisation profile</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Organisation Profile</h1>
          <p className="text-gray-600 mt-1">Manage your organisation settings and branding</p>
        </div>
        {isAdmin && !isEditing && (
          <Button onClick={() => setIsEditing(true)}>Edit Profile</Button>
        )}
      </div>

      {/* Basic info */}
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">Basic Information</h2>
        </CardHeader>
        <CardBody>
          {isEditing ? (
            <div className="space-y-4">
              <Input
                label="Organisation Name"
                value={editData.org_name}
                onChange={(e) => setEditData((prev) => ({ ...prev, org_name: e.target.value }))}
              />
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Slug</label>
                <p className="text-gray-900">/{profile.org_slug}</p>
                <p className="text-xs text-gray-500 mt-1">Slug cannot be changed after creation</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-500">Organisation Name</label>
                <p className="mt-1 text-gray-900 text-lg">{profile.org_name}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-500">Slug</label>
                <p className="mt-1 text-gray-900">/{profile.org_slug}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-500">Organisation ID</label>
                <p className="mt-1 text-gray-500 text-sm font-mono">{profile.org_id}</p>
              </div>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Branding */}
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">Branding</h2>
        </CardHeader>
        <CardBody>
          {isEditing ? (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Primary Color</label>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={editData.primary_color}
                    onChange={(e) => setEditData((prev) => ({ ...prev, primary_color: e.target.value }))}
                    className="h-10 w-20 border border-gray-300 rounded cursor-pointer"
                  />
                  <input
                    type="text"
                    value={editData.primary_color}
                    onChange={(e) => setEditData((prev) => ({ ...prev, primary_color: e.target.value }))}
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-500">Primary Color</label>
                <div className="mt-1 flex items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-lg border border-gray-200"
                    style={{ backgroundColor: profile.primary_color }}
                  />
                  <span className="text-gray-900 font-mono">{profile.primary_color}</span>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-500">Logo</label>
                <p className="mt-1 text-gray-500 text-sm">
                  {profile.logo_path || 'No logo uploaded'}
                </p>
              </div>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Stats */}
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">Statistics</h2>
        </CardHeader>
        <CardBody>
          <div className="grid grid-cols-3 gap-6">
            <div className="text-center">
              <p className="text-3xl font-bold text-gray-900">{profile.stats.total_users}</p>
              <p className="text-sm text-gray-500">Total Users</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-gray-900">{profile.stats.total_sessions}</p>
              <p className="text-sm text-gray-500">Sessions</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-gray-900">{profile.knowledge_bases.length}</p>
              <p className="text-sm text-gray-500">Knowledge Bases</p>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Edit actions */}
      {isEditing && (
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={handleCancel}>
            Cancel
          </Button>
          <Button onClick={handleSave} isLoading={isSaving}>
            Save Changes
          </Button>
        </div>
      )}
    </div>
  );
}
