import type { ReactNode } from 'react';

interface AuthLayoutProps {
  children: ReactNode;
  title: string;
  subtitle?: string;
}

export function AuthLayout({ children, title, subtitle }: AuthLayoutProps) {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        {/* Logo/Brand */}
        <div className="flex justify-center">
          <div className="w-12 h-12 bg-primary-500 rounded-xl flex items-center justify-center">
            <span className="text-2xl font-bold text-white">P</span>
          </div>
        </div>

        {/* Title */}
        <h2 className="mt-6 text-center text-3xl font-bold text-gray-900">{title}</h2>

        {/* Subtitle */}
        {subtitle && <p className="mt-2 text-center text-sm text-gray-600">{subtitle}</p>}
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow-sm rounded-xl sm:px-10 border border-gray-200">
          {children}
        </div>
      </div>
    </div>
  );
}
