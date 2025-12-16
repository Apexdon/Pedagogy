import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthLayout } from '@/components/layout';
import { Button, Card, CardBody, Loading, SearchableSelect } from '@/components/ui';
import type { SelectOption } from '@/components/ui';
import { useAuthStore, useUIStore } from '@/stores';
import { selectOrganisation, listOrganisations, joinOrganisation } from '@/api';
import type { AxiosError } from 'axios';
import type { HttpErrorResponse, UserOrganisationInfo, OrganisationListItem } from '@/types';

export function SelectOrgPage() {
  const navigate = useNavigate();
  const { user, organisations, setOrganisations, selectOrganisation: setSelectedOrg, logout } = useAuthStore();
  const { addToast } = useUIStore();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedOrgToJoin, setSelectedOrgToJoin] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isJoining, setIsJoining] = useState(false);
  const [availableOrgs, setAvailableOrgs] = useState<OrganisationListItem[]>([]);
  const [loadingOrgs, setLoadingOrgs] = useState(true);

  // Fetch all available organisations on mount
  useEffect(() => {
    const fetchOrgs = async () => {
      try {
        const orgs = await listOrganisations();
        setAvailableOrgs(orgs);
      } catch (error) {
        console.error('Failed to fetch organisations:', error);
      } finally {
        setLoadingOrgs(false);
      }
    };
    fetchOrgs();
  }, []);

  // Get org IDs user is already a member of
  const memberOrgIds = new Set(organisations.map((org) => org.org_id));

  // Filter to orgs user can join (not already a member)
  const orgsToJoin = availableOrgs.filter((org) => !memberOrgIds.has(org.org_id));

  // Convert to select options
  const orgOptions: SelectOption[] = orgsToJoin.map((org) => ({
    value: org.org_id,
    label: org.org_name,
    sublabel: `/${org.org_slug}`,
    color: org.primary_color,
  }));

  const handleSelect = async (org: UserOrganisationInfo) => {
    setSelectedId(org.org_id);
    setIsLoading(true);

    try {
      const response = await selectOrganisation({ org_id: org.org_id });

      setSelectedOrg(response.organisation, response.role);

      addToast({
        type: 'success',
        message: `Welcome to ${response.organisation.org_name}!`,
      });
      navigate('/dashboard');
    } catch (error) {
      const axiosError = error as AxiosError<HttpErrorResponse>;
      const message = axiosError.response?.data?.detail || 'Failed to select organisation';
      addToast({ type: 'error', message });
      setSelectedId(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleJoin = async () => {
    if (!selectedOrgToJoin) return;

    const org = orgsToJoin.find((o) => o.org_id === selectedOrgToJoin);
    if (!org) return;

    setIsJoining(true);

    try {
      const response = await joinOrganisation(selectedOrgToJoin);

      if (response.success && response.member) {
        // Add to user's organisations list
        const newOrgInfo: UserOrganisationInfo = {
          org_id: org.org_id,
          org_name: org.org_name,
          org_slug: org.org_slug,
          role: response.member.role,
          is_default: false,
        };
        setOrganisations([...organisations, newOrgInfo]);
        setSelectedOrgToJoin(null);

        addToast({
          type: 'success',
          message: response.message,
        });

        // Automatically select the joined org and proceed to dashboard
        setIsJoining(false);
        await handleSelect(newOrgInfo);
        return;
      }
    } catch (error) {
      const axiosError = error as AxiosError<HttpErrorResponse>;
      const message = axiosError.response?.data?.detail || 'Failed to join organisation';
      addToast({ type: 'error', message });
    } finally {
      setIsJoining(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getRoleBadgeColor = (role: string) => {
    switch (role) {
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

  if (loadingOrgs) {
    return (
      <AuthLayout title="Loading..." subtitle="Fetching available organisations">
        <div className="flex justify-center py-8">
          <Loading size="lg" />
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Select organisation"
      subtitle={`Welcome back, ${user?.full_name || user?.email}! Choose an organisation to continue.`}
    >
      <div className="space-y-6">
        {/* User's current organisations */}
        {organisations.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">Your organisations</h3>
            <div className="space-y-3">
              {organisations.map((org) => (
                <Card
                  key={org.org_id}
                  hover
                  onClick={() => !isLoading && handleSelect(org)}
                  className={`transition-all cursor-pointer ${
                    selectedId === org.org_id ? 'ring-2 ring-primary-500' : ''
                  } ${isLoading && selectedId !== org.org_id ? 'opacity-50' : ''}`}
                >
                  <CardBody className="flex items-center gap-4">
                    {/* Org avatar */}
                    <div
                      className="w-12 h-12 rounded-lg flex items-center justify-center text-white font-bold text-lg flex-shrink-0"
                      style={{ backgroundColor: '#3B82F6' }}
                    >
                      {org.org_name.charAt(0).toUpperCase()}
                    </div>

                    {/* Org info */}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-gray-900 truncate">{org.org_name}</h3>
                      <p className="text-sm text-gray-500">/{org.org_slug}</p>
                    </div>

                    {/* Role badge */}
                    <span
                      className={`px-2.5 py-1 rounded-full text-xs font-medium ${getRoleBadgeColor(org.role)}`}
                    >
                      {org.role.replace('_', ' ')}
                    </span>

                    {/* Loading indicator */}
                    {isLoading && selectedId === org.org_id && (
                      <Loading size="sm" />
                    )}
                  </CardBody>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Join new organisation section */}
        {orgsToJoin.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">
              {organisations.length > 0 ? 'Join another organisation' : 'Join an organisation'}
            </h3>
            <div className="space-y-3">
              <SearchableSelect
                options={orgOptions}
                value={selectedOrgToJoin}
                onChange={setSelectedOrgToJoin}
                placeholder="Search or select an organisation..."
                searchPlaceholder="Search organisations..."
                emptyMessage="No organisations available to join"
                isLoading={loadingOrgs}
              />
              {selectedOrgToJoin && (
                <Button
                  onClick={handleJoin}
                  isLoading={isJoining}
                  className="w-full"
                >
                  Join Organisation
                </Button>
              )}
            </div>
          </div>
        )}

        {/* No organisations available */}
        {organisations.length === 0 && orgsToJoin.length === 0 && (
          <div className="text-center py-6">
            <div className="p-4 bg-amber-50 rounded-lg">
              <svg className="w-12 h-12 mx-auto text-amber-500 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p className="text-amber-800 font-medium">No organisations available</p>
              <p className="text-amber-700 text-sm mt-1">
                There are no organisations to join at this time.
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="mt-6 text-center">
        <button
          onClick={handleLogout}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          Use a different account
        </button>
      </div>
    </AuthLayout>
  );
}
