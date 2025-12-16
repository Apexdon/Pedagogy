import { Card, CardBody, CardHeader } from '@/components/ui';
import { useAuthStore } from '@/stores';

export function SettingsPage() {
  const { user, selectedOrg, role } = useAuthStore();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-600 mt-1">Manage your account and preferences</p>
      </div>

      {/* Profile section */}
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">Profile Information</h2>
        </CardHeader>
        <CardBody>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-500">Full Name</label>
              <p className="mt-1 text-gray-900">{user?.full_name || 'Not set'}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-500">Email</label>
              <p className="mt-1 text-gray-900">{user?.email}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-500">Email Verified</label>
              <p className="mt-1">
                {user?.email_verified ? (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    Verified
                  </span>
                ) : (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                    Not verified
                  </span>
                )}
              </p>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Organisation context */}
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">Current Organisation</h2>
        </CardHeader>
        <CardBody>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-500">Organisation</label>
              <p className="mt-1 text-gray-900">{selectedOrg?.org_name}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-500">Slug</label>
              <p className="mt-1 text-gray-900">/{selectedOrg?.org_slug}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-500">Your Role</label>
              <p className="mt-1">
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800">
                  {role?.replace('_', ' ')}
                </span>
              </p>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Preferences */}
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">Preferences</h2>
        </CardHeader>
        <CardBody>
          <p className="text-gray-500 text-sm">
            Preference settings will be available in a future update.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
