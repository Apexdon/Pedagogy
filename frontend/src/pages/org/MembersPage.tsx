import { useEffect, useState } from 'react';
import { Card, CardBody, CardHeader, Button, Input, Loading } from '@/components/ui';
import { useAuthStore, useUIStore } from '@/stores';
import { listMembers, addMember, removeMember } from '@/api';
import type { Member } from '@/types';
import type { AxiosError } from 'axios';
import type { HttpErrorResponse } from '@/types';

export function MembersPage() {
  const { user, role } = useAuthStore();
  const { addToast } = useUIStore();

  const [members, setMembers] = useState<Member[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);

  const [newMember, setNewMember] = useState({
    email: '',
    role: 'user' as 'org_admin' | 'manager' | 'user' | 'viewer',
  });

  const isAdmin = role === 'org_admin';
  const canAddMembers = role === 'org_admin' || role === 'manager';

  useEffect(() => {
    fetchMembers();
  }, []);

  const fetchMembers = async () => {
    try {
      const data = await listMembers();
      setMembers(data);
    } catch {
      addToast({ type: 'error', message: 'Failed to load members' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!newMember.email) {
      addToast({ type: 'error', message: 'Email is required' });
      return;
    }

    setIsAdding(true);

    try {
      const response = await addMember(newMember);
      if (response.member) {
        setMembers((prev) => [...prev, response.member!]);
      }
      addToast({ type: 'success', message: response.message });
      setNewMember({ email: '', role: 'user' });
      setShowAddForm(false);
    } catch (error) {
      const axiosError = error as AxiosError<HttpErrorResponse>;
      const message = axiosError.response?.data?.detail || 'Failed to add member';
      addToast({ type: 'error', message });
    } finally {
      setIsAdding(false);
    }
  };

  const handleRemoveMember = async (memberId: string) => {
    if (memberId === user?.user_id) {
      addToast({ type: 'error', message: 'You cannot remove yourself' });
      return;
    }

    setRemovingId(memberId);

    try {
      await removeMember(memberId);
      setMembers((prev) => prev.filter((m) => m.user_id !== memberId));
      addToast({ type: 'success', message: 'Member removed successfully' });
    } catch (error) {
      const axiosError = error as AxiosError<HttpErrorResponse>;
      const message = axiosError.response?.data?.detail || 'Failed to remove member';
      addToast({ type: 'error', message });
    } finally {
      setRemovingId(null);
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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loading size="lg" message="Loading members..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Members</h1>
          <p className="text-gray-600 mt-1">
            Manage your organisation's team members
          </p>
        </div>
        {canAddMembers && !showAddForm && (
          <Button onClick={() => setShowAddForm(true)}>Add Member</Button>
        )}
      </div>

      {/* Add member form */}
      {showAddForm && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-gray-900">Add New Member</h2>
          </CardHeader>
          <CardBody>
            <form onSubmit={handleAddMember} className="space-y-4">
              <Input
                label="Email address"
                type="email"
                value={newMember.email}
                onChange={(e) => setNewMember((prev) => ({ ...prev, email: e.target.value }))}
                placeholder="user@example.com"
                helperText="The user must have an existing account"
              />

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
                <select
                  value={newMember.role}
                  onChange={(e) => setNewMember((prev) => ({ ...prev, role: e.target.value as typeof newMember.role }))}
                  className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <option value="viewer">Viewer</option>
                  <option value="user">User</option>
                  <option value="manager">Manager</option>
                  {isAdmin && <option value="org_admin">Admin</option>}
                </select>
              </div>

              <div className="flex justify-end gap-3">
                <Button type="button" variant="secondary" onClick={() => setShowAddForm(false)}>
                  Cancel
                </Button>
                <Button type="submit" isLoading={isAdding}>
                  Add Member
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>
      )}

      {/* Members list */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Team Members</h2>
            <span className="text-sm text-gray-500">{members.length} members</span>
          </div>
        </CardHeader>
        <CardBody className="p-0">
          <div className="divide-y divide-gray-200">
            {members.map((member) => (
              <div
                key={member.user_id}
                className="px-6 py-4 flex items-center justify-between hover:bg-gray-50"
              >
                <div className="flex items-center gap-4">
                  {/* Avatar */}
                  <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center">
                    <span className="text-sm font-medium text-gray-600">
                      {(member.full_name || member.email).charAt(0).toUpperCase()}
                    </span>
                  </div>

                  {/* Info */}
                  <div>
                    <p className="font-medium text-gray-900">
                      {member.full_name || 'No name'}
                      {member.user_id === user?.user_id && (
                        <span className="ml-2 text-xs text-gray-500">(you)</span>
                      )}
                    </p>
                    <p className="text-sm text-gray-500">{member.email}</p>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  {/* Role badge */}
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-medium ${getRoleBadgeColor(member.role)}`}
                  >
                    {member.role.replace('_', ' ')}
                  </span>

                  {/* Remove button (admin only, can't remove self) */}
                  {isAdmin && member.user_id !== user?.user_id && (
                    <button
                      onClick={() => handleRemoveMember(member.user_id)}
                      disabled={removingId === member.user_id}
                      className="p-2 text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
                      title="Remove member"
                    >
                      {removingId === member.user_id ? (
                        <Loading size="sm" />
                      ) : (
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                          />
                        </svg>
                      )}
                    </button>
                  )}
                </div>
              </div>
            ))}

            {members.length === 0 && (
              <div className="px-6 py-12 text-center text-gray-500">
                No members found
              </div>
            )}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
