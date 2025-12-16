import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { AuthLayout } from '@/components/layout';
import { Button, Input } from '@/components/ui';
import { useUIStore } from '@/stores';
import { onboardOrganisation } from '@/api';
import type { AxiosError } from 'axios';
import type { HttpErrorResponse } from '@/types';

export function OnboardPage() {
  const navigate = useNavigate();
  const { addToast } = useUIStore();

  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    org_name: '',
    org_slug: '',
    admin_email: '',
    admin_password: '',
    admin_name: '',
    primary_color: '#3B82F6',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;

    // Auto-generate slug from org name
    if (name === 'org_name') {
      const slug = value
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '');
      setFormData((prev) => ({ ...prev, org_name: value, org_slug: slug }));
    } else {
      setFormData((prev) => ({ ...prev, [name]: value }));
    }

    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: '' }));
    }
  };

  const validateStep1 = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.org_name.trim()) {
      newErrors.org_name = 'Organisation name is required';
    }

    if (!formData.org_slug.trim()) {
      newErrors.org_slug = 'Slug is required';
    } else if (!/^[a-z0-9-]+$/.test(formData.org_slug)) {
      newErrors.org_slug = 'Slug can only contain lowercase letters, numbers, and hyphens';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateStep2 = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.admin_name.trim()) {
      newErrors.admin_name = 'Admin name is required';
    }

    if (!formData.admin_email) {
      newErrors.admin_email = 'Admin email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.admin_email)) {
      newErrors.admin_email = 'Invalid email format';
    }

    if (!formData.admin_password) {
      newErrors.admin_password = 'Password is required';
    } else if (formData.admin_password.length < 8) {
      newErrors.admin_password = 'Password must be at least 8 characters';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (step === 1 && validateStep1()) {
      setStep(2);
    }
  };

  const handleBack = () => {
    setStep(1);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateStep2()) return;

    setIsLoading(true);

    try {
      await onboardOrganisation({
        org_name: formData.org_name,
        org_slug: formData.org_slug,
        admin_email: formData.admin_email,
        admin_password: formData.admin_password,
        admin_name: formData.admin_name,
        branding: {
          primary_color: formData.primary_color,
        },
      });

      addToast({
        type: 'success',
        message: 'Organisation created successfully! Please login to continue.',
      });
      navigate('/login');
    } catch (error) {
      const axiosError = error as AxiosError<HttpErrorResponse>;
      const message = axiosError.response?.data?.detail || 'Failed to create organisation';
      addToast({ type: 'error', message });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout
      title={step === 1 ? 'Create your organisation' : 'Set up admin account'}
      subtitle={
        step === 1
          ? 'Get started with Pedagogy by creating your organisation'
          : 'Create the admin account for your organisation'
      }
    >
      {/* Progress indicator */}
      <div className="mb-8">
        <div className="flex items-center justify-center gap-2">
          <div
            className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
              step >= 1 ? 'bg-primary-500 text-white' : 'bg-gray-200 text-gray-600'
            }`}
          >
            1
          </div>
          <div className={`w-16 h-1 ${step >= 2 ? 'bg-primary-500' : 'bg-gray-200'}`} />
          <div
            className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
              step >= 2 ? 'bg-primary-500 text-white' : 'bg-gray-200 text-gray-600'
            }`}
          >
            2
          </div>
        </div>
        <div className="flex justify-between mt-2 text-xs text-gray-500">
          <span className="w-24 text-center">Organisation</span>
          <span className="w-24 text-center">Admin Setup</span>
        </div>
      </div>

      {step === 1 ? (
        <form onSubmit={(e) => { e.preventDefault(); handleNext(); }} className="space-y-6">
          <Input
            label="Organisation name"
            type="text"
            name="org_name"
            value={formData.org_name}
            onChange={handleChange}
            error={errors.org_name}
            placeholder="Acme Corporation"
          />

          <Input
            label="Organisation slug"
            type="text"
            name="org_slug"
            value={formData.org_slug}
            onChange={handleChange}
            error={errors.org_slug}
            placeholder="acme-corp"
            helperText="This will be used in URLs: pedagogy.app/acme-corp"
          />

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Brand color
            </label>
            <div className="flex items-center gap-3">
              <input
                type="color"
                name="primary_color"
                value={formData.primary_color}
                onChange={handleChange}
                className="h-10 w-20 border border-gray-300 rounded cursor-pointer"
              />
              <input
                type="text"
                value={formData.primary_color}
                onChange={(e) => setFormData((prev) => ({ ...prev, primary_color: e.target.value }))}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                placeholder="#3B82F6"
              />
            </div>
          </div>

          <Button type="submit" className="w-full">
            Continue
          </Button>
        </form>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-6">
          <Input
            label="Admin name"
            type="text"
            name="admin_name"
            value={formData.admin_name}
            onChange={handleChange}
            error={errors.admin_name}
            placeholder="John Doe"
          />

          <Input
            label="Admin email"
            type="email"
            name="admin_email"
            value={formData.admin_email}
            onChange={handleChange}
            error={errors.admin_email}
            placeholder="admin@example.com"
          />

          <Input
            label="Admin password"
            type="password"
            name="admin_password"
            value={formData.admin_password}
            onChange={handleChange}
            error={errors.admin_password}
            placeholder="At least 8 characters"
          />

          <div className="flex gap-3">
            <Button type="button" variant="secondary" onClick={handleBack} className="flex-1">
              Back
            </Button>
            <Button type="submit" className="flex-1" isLoading={isLoading}>
              Create Organisation
            </Button>
          </div>
        </form>
      )}

      <p className="mt-6 text-center text-sm text-gray-600">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-primary-600 hover:text-primary-500">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}
