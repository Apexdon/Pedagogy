import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { AuthLayout } from '@/components/layout';
import { Button, Input } from '@/components/ui';
import { useUIStore } from '@/stores';
import { register } from '@/api';
import type { AxiosError } from 'axios';
import type { HttpErrorResponse } from '@/types';

export function RegisterPage() {
  const navigate = useNavigate();
  const { addToast } = useUIStore();

  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: '' }));
    }
  };

  const validate = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.full_name.trim()) {
      newErrors.full_name = 'Full name is required';
    }

    if (!formData.email) {
      newErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Invalid email format';
    }

    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    }

    if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) return;

    setIsLoading(true);

    try {
      await register({
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name,
      });

      addToast({
        type: 'success',
        message: 'Registration successful! Please login to continue.',
      });
      navigate('/login');
    } catch (error) {
      const axiosError = error as AxiosError<HttpErrorResponse>;
      const message = axiosError.response?.data?.detail || 'Registration failed. Please try again.';
      addToast({ type: 'error', message });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout title="Create your account" subtitle="Join Pedagogy to get started">
      <form onSubmit={handleSubmit} className="space-y-6">
        <Input
          label="Full name"
          type="text"
          name="full_name"
          value={formData.full_name}
          onChange={handleChange}
          error={errors.full_name}
          placeholder="John Doe"
          autoComplete="name"
        />

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
          placeholder="At least 8 characters"
          autoComplete="new-password"
        />

        <Input
          label="Confirm password"
          type="password"
          name="confirmPassword"
          value={formData.confirmPassword}
          onChange={handleChange}
          error={errors.confirmPassword}
          placeholder="Confirm your password"
          autoComplete="new-password"
        />

        <Button type="submit" className="w-full" isLoading={isLoading}>
          Create account
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-gray-600">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-primary-600 hover:text-primary-500">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}
