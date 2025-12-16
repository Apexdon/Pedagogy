import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { AuthLayout } from '@/components/layout';
import { Button, Input } from '@/components/ui';
import { useAuthStore, useUIStore } from '@/stores';
import { login } from '@/api';
import type { AxiosError } from 'axios';
import type { HttpErrorResponse } from '@/types';

export function LoginPage() {
  const navigate = useNavigate();
  const { setUser, setOrganisations, selectOrganisation } = useAuthStore();
  const { addToast } = useUIStore();

  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    // Clear error when user types
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: '' }));
    }
  };

  const validate = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.email) {
      newErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Invalid email format';
    }

    if (!formData.password) {
      newErrors.password = 'Password is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) return;

    setIsLoading(true);

    try {
      const response = await login(formData);

      console.log('Login response:', response);
      console.log('requires_org_selection:', response.requires_org_selection);
      console.log('tokens:', response.tokens);
      console.log('organisation:', response.organisation);

      setUser(response.user);
      setOrganisations(response.organisations);

      // For org_admin/manager users, backend returns full tokens directly
      if (!response.requires_org_selection && response.tokens && response.organisation && response.role) {
        console.log('Org admin detected, navigating to dashboard');
        selectOrganisation(response.organisation, response.role);
        navigate('/dashboard');
        return;
      }

      // Regular user - go to select-org page
      console.log('Regular user, navigating to select-org');
      navigate('/select-org');
    } catch (error) {
      console.error('Login error:', error);
      const axiosError = error as AxiosError<HttpErrorResponse>;
      const message = axiosError.response?.data?.detail || 'Login failed. Please try again.';
      addToast({ type: 'error', message });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to your Pedagogy account">
      <form onSubmit={handleSubmit} className="space-y-6">
        <Input
          label="Email address"
          type="email"
          name="email"
          value={formData.email}
          onChange={handleChange}
          error={errors.email}
          placeholder="you@example.com"
          autoComplete="email"
        />

        <Input
          label="Password"
          type="password"
          name="password"
          value={formData.password}
          onChange={handleChange}
          error={errors.password}
          placeholder="Enter your password"
          autoComplete="current-password"
        />

        <Button type="submit" className="w-full" isLoading={isLoading}>
          Sign in
        </Button>
      </form>

      <div className="mt-6">
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-200" />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-white text-gray-500">New to Pedagogy?</span>
          </div>
        </div>

        <div className="mt-6 space-y-3">
          <Link to="/register">
            <Button variant="secondary" className="w-full">
              Create an account
            </Button>
          </Link>
          <Link to="/onboard">
            <Button variant="ghost" className="w-full">
              Set up a new organisation
            </Button>
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
