-- =============================================
-- PEDAGOGY DATABASE SCHEMA - Multi-Organisation
-- PostgreSQL 16 with pgvector extension
-- =============================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- =============================================
-- ORGANISATIONS TABLE
-- Multi-tenant: Users can belong to multiple organisations
-- =============================================

CREATE TABLE organisations (
    org_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    org_name VARCHAR(255) NOT NULL,
    org_slug VARCHAR(100) UNIQUE NOT NULL,
    logo_path VARCHAR(500),
    primary_color VARCHAR(7) DEFAULT '#3B82F6',
    subscription_tier VARCHAR(50) DEFAULT 'standard',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for organisations
CREATE INDEX idx_organisations_slug ON organisations(org_slug);
CREATE INDEX idx_organisations_active ON organisations(is_active);

-- =============================================
-- USERS TABLE
-- Users exist independently of organisations
-- =============================================

CREATE TABLE users (
    user_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Indexes for users
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active);

-- =============================================
-- USER_ORGANISATIONS TABLE (Junction)
-- Many-to-many relationship between users and organisations
-- =============================================

CREATE TABLE user_organisations (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    user_id VARCHAR(36) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    org_id VARCHAR(36) NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('org_admin', 'manager', 'user', 'viewer')),
    is_default BOOLEAN DEFAULT FALSE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, org_id)
);

-- Indexes for user_organisations
CREATE INDEX idx_user_organisations_user ON user_organisations(user_id);
CREATE INDEX idx_user_organisations_org ON user_organisations(org_id);

-- =============================================
-- USER SETTINGS TABLE
-- =============================================

CREATE TABLE user_settings (
    setting_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    user_id VARCHAR(36) UNIQUE NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    hotkey VARCHAR(50) DEFAULT 'Ctrl+Shift+P',
    auto_capture_on_query BOOLEAN DEFAULT FALSE,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for user settings
CREATE INDEX idx_user_settings_user ON user_settings(user_id);

-- =============================================
-- HELPER FUNCTIONS & TRIGGERS
-- =============================================

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to organisations
CREATE TRIGGER update_organisations_updated_at
    BEFORE UPDATE ON organisations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to user_settings
CREATE TRIGGER update_user_settings_updated_at
    BEFORE UPDATE ON user_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================
-- SEED DATA (Development Only)
-- =============================================

-- Insert test organisations
INSERT INTO organisations (org_name, org_slug, primary_color)
VALUES
    ('Test Organisation', 'test-org', '#3B82F6'),
    ('Demo Company', 'demo-company', '#10B981');

-- Note: Test users should be created via the API with proper password hashing
