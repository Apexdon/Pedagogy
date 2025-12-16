import { create } from 'zustand';

interface Toast {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  message: string;
  duration?: number;
}

interface UIState {
  // Loading states
  isLoading: boolean;
  loadingMessage: string | null;

  // Toasts
  toasts: Toast[];

  // Sidebar
  isSidebarOpen: boolean;

  // Actions
  setLoading: (isLoading: boolean, message?: string) => void;
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (isOpen: boolean) => void;
}

export const useUIStore = create<UIState>((set, get) => ({
  // Initial state
  isLoading: false,
  loadingMessage: null,
  toasts: [],
  isSidebarOpen: true,

  // Actions
  setLoading: (isLoading, message) => {
    set({ isLoading, loadingMessage: message ?? null });
  },

  addToast: (toast) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newToast = { ...toast, id };
    set((state) => ({ toasts: [...state.toasts, newToast] }));

    // Auto-remove after duration (default 5 seconds)
    const duration = toast.duration || 5000;
    setTimeout(() => {
      get().removeToast(id);
    }, duration);
  },

  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }));
  },

  toggleSidebar: () => {
    set((state) => ({ isSidebarOpen: !state.isSidebarOpen }));
  },

  setSidebarOpen: (isOpen) => {
    set({ isSidebarOpen: isOpen });
  },
}));
