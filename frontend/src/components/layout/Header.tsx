import { useAuthStore, useUIStore } from '@/stores';
import { useNavigate } from 'react-router-dom';
import { logout as apiLogout } from '@/api';

export function Header() {
  const { user, selectedOrg, logout } = useAuthStore();
  const { toggleSidebar, addToast } = useUIStore();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await apiLogout();
      logout();
      addToast({ type: 'success', message: 'Logged out successfully' });
      navigate('/login');
    } catch {
      // Even if API call fails, clear local state
      logout();
      navigate('/login');
    }
  };

  return (
    <header className="bg-white border-b border-gray-200 px-4 py-3">
      <div className="flex items-center justify-between">
        {/* Left: Menu toggle + Org name */}
        <div className="flex items-center gap-4">
          <button
            onClick={toggleSidebar}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            aria-label="Toggle sidebar"
          >
            <svg className="w-5 h-5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          {selectedOrg && (
            <div className="flex items-center gap-2">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-sm"
                style={{ backgroundColor: selectedOrg.primary_color }}
              >
                {selectedOrg.org_name.charAt(0).toUpperCase()}
              </div>
              <span className="font-medium text-gray-900">{selectedOrg.org_name}</span>
            </div>
          )}
        </div>

        {/* Right: User menu */}
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="text-sm font-medium text-gray-900">{user?.full_name || user?.email}</p>
            <p className="text-xs text-gray-500">{user?.email}</p>
          </div>

          <button
            onClick={handleLogout}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors text-gray-600"
            title="Logout"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
              />
            </svg>
          </button>
        </div>
      </div>
    </header>
  );
}
