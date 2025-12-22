// Organisation types
export interface Organisation {
  org_id: string;
  org_name: string;
  org_slug: string;
  logo_path: string | null;
  primary_color: string;
  subscription_tier: string;
  is_active: boolean;
  created_at: string;
}

export interface OrganisationListItem {
  org_id: string;
  org_name: string;
  org_slug: string;
  primary_color: string;
}

export interface OrganisationStats {
  total_users: number;
  total_sessions: number;
  last_activity: string | null;
}

export interface KnowledgeBaseInfo {
  kb_id: string;
  kb_name: string;
  document_count: number;
  step_count: number;
}

export interface OrganisationProfile {
  org_id: string;
  org_name: string;
  org_slug: string;
  logo_path: string | null;
  primary_color: string;
  branding: Record<string, unknown>;
  settings: Record<string, unknown>;
  knowledge_bases: KnowledgeBaseInfo[];
  stats: OrganisationStats;
}

export interface OnboardingStatus {
  org_id: string;
  org_name: string;
  onboarding_status: 'pending' | 'in_progress' | 'completed';
  checklist: Record<string, boolean>;
  completion_percentage: number;
  pending_items: string[];
}

// Member types
export interface Member {
  user_id: string;
  email: string;
  full_name: string | null;
  role: 'org_admin' | 'manager' | 'user' | 'viewer';
  joined_at: string;
}

// Request types
export interface OrganisationOnboardRequest {
  org_name: string;
  org_slug: string;
  admin_email: string;
  admin_password: string;
  admin_name: string;
  branding?: {
    primary_color?: string;
    logo_base64?: string;
  };
  settings?: {
    hotkey?: string;
    auto_capture_on_query?: boolean;
    default_language?: string;
  };
  initial_users?: {
    email: string;
    role: 'org_admin' | 'manager' | 'user' | 'viewer';
  }[];
}

export interface AddMemberRequest {
  email: string;
  role: 'org_admin' | 'manager' | 'user' | 'viewer';
}

export interface UpdateProfileRequest {
  org_name?: string;
  primary_color?: string;
}

// Response types
export interface OnboardingResponse {
  success: boolean;
  organisation: Organisation;
  admin_user: {
    user_id: string;
    email: string;
    role: string;
  };
  users_invited: number;
  next_steps: string[];
}

export interface AddMemberResponse {
  success: boolean;
  message: string;
  member: Member | null;
}

export interface UpdateProfileResponse {
  success: boolean;
  message: string;
  organisation: Organisation;
}

// Org Dashboard types
export interface RecentActivityItem {
  activity_id: string;
  activity_type: 'member_joined' | 'document_uploaded' | 'kb_created' | 'settings_updated';
  description: string;
  timestamp: string;
  user_name?: string;
  metadata: Record<string, unknown>;
}

export interface TeamMemberSummary {
  user_id: string;
  full_name?: string;
  email: string;
  role: string;
  joined_at: string;
}

export interface KnowledgeBaseSummary {
  total_documents: number;
  total_chunks: number;
  recent_uploads: Array<{
    doc_id: string;
    file_name: string;
    uploaded_at: string;
  }>;
  processing_status: Record<string, number>;
}

export interface OrgDashboardStats {
  total_members: number;
  total_documents: number;
  total_sessions: number;
  total_knowledge_bases: number;
  onboarding_completion: number;
  pending_setup_items: string[];
  recent_activities: RecentActivityItem[];
  team_members: TeamMemberSummary[];
  members_by_role: Record<string, number>;
  knowledge_base: KnowledgeBaseSummary;
  sessions_this_week: number;
  sessions_trend: 'up' | 'down' | 'stable';
}
