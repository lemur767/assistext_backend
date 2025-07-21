-- AssisText Corrected Database Schema
-- Run this FIRST before the data script

-- =============================================
-- EXTENSIONS
-- =============================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================
-- CUSTOM TYPES
-- =============================================
CREATE TYPE subscription_tier AS ENUM ('basic', 'professional', 'enterprise');
CREATE TYPE relationship_status AS ENUM ('new', 'regular', 'vip', 'blocked');
CREATE TYPE message_status AS ENUM ('pending', 'sent', 'delivered', 'failed', 'queued');

-- =============================================
-- USERS TABLE
-- =============================================
CREATE TABLE users (
    id VARCHAR(50) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,  -- This column was missing
    company_name VARCHAR(255),
    phone_number VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    subscription_tier subscription_tier DEFAULT 'basic',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- USER SETTINGS TABLE
-- =============================================
CREATE TABLE user_settings (
    user_id VARCHAR(50) PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    ai_enabled BOOLEAN DEFAULT TRUE,
    ai_model VARCHAR(50) DEFAULT 'dolphin-mistral:7b',
    ai_temperature DECIMAL(3,2) DEFAULT 0.7,
    ai_max_tokens INTEGER DEFAULT 150,
    ai_personality TEXT,
    auto_reply_enabled BOOLEAN DEFAULT TRUE,
    auto_reply_delay INTEGER DEFAULT 30,
    business_hours_start TIME,
    business_hours_end TIME,
    business_days TEXT DEFAULT 'monday,tuesday,wednesday,thursday,friday',
    after_hours_message TEXT,
    timezone VARCHAR(50) DEFAULT 'America/Toronto',
    confidence_threshold DECIMAL(3,2) DEFAULT 0.8,
    fallback_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- SIGNALWIRE SETTINGS TABLE
-- =============================================
CREATE TABLE signalwire_settings (
    user_id VARCHAR(50) PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    signalwire_project_id VARCHAR(255),
    signalwire_space_url VARCHAR(255),
    signalwire_phone_number VARCHAR(20),
    webhook_url TEXT,
    signalwire_configured BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- CLIENTS TABLE
-- =============================================
CREATE TABLE clients (
    id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(id) ON DELETE CASCADE,
    phone_number VARCHAR(20) NOT NULL,
    name VARCHAR(255),
    nickname VARCHAR(100),  -- Added this column
    email VARCHAR(255),
    display_name VARCHAR(255) NOT NULL,
    notes TEXT,
    tags TEXT[],
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    timezone VARCHAR(50) DEFAULT 'America/Toronto',
    relationship_status relationship_status DEFAULT 'new',
    priority_level INTEGER DEFAULT 3,
    client_type VARCHAR(50),
    first_contact TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_interaction TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    total_interactions INTEGER DEFAULT 0,
    total_messages_received INTEGER DEFAULT 0,
    total_messages_sent INTEGER DEFAULT 0,
    custom_ai_personality TEXT,
    custom_greeting TEXT,
    auto_reply_enabled BOOLEAN DEFAULT TRUE,
    ai_response_style VARCHAR(50),
    is_blocked BOOLEAN DEFAULT FALSE,
    block_reason TEXT,
    blocked_at TIMESTAMP WITH TIME ZONE,
    is_favorite BOOLEAN DEFAULT FALSE,
    is_flagged BOOLEAN DEFAULT FALSE,
    flag_reasons TEXT[],
    risk_level VARCHAR(20) DEFAULT 'low',
    trust_score DECIMAL(3,2) DEFAULT 0.5,
    verified_client BOOLEAN DEFAULT FALSE,
    avg_response_time INTEGER,
    last_message_sentiment DECIMAL(3,2),
    engagement_score DECIMAL(3,2) DEFAULT 0.5,
    preferred_contact_time VARCHAR(50),
    communication_style VARCHAR(50),
    language_preference VARCHAR(10) DEFAULT 'english',
    emoji_preference BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- MESSAGES TABLE
-- =============================================
CREATE TABLE messages (
    id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_incoming BOOLEAN NOT NULL,
    sender_number VARCHAR(20) NOT NULL,    -- Added this column
    recipient_number VARCHAR(20) NOT NULL, -- Added this column
    ai_generated BOOLEAN DEFAULT FALSE,
    ai_confidence DECIMAL(3,2),
    ai_model_used VARCHAR(50),
    sentiment_score DECIMAL(3,2),
    intent_classification VARCHAR(100),
    confidence_score DECIMAL(3,2),
    is_read BOOLEAN DEFAULT FALSE,
    is_flagged BOOLEAN DEFAULT FALSE,
    flag_reasons TEXT[],
    processing_status message_status DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- Added this column
    sent_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    read_at TIMESTAMP WITH TIME ZONE,
    time_since TEXT,
    conversation_partner VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- MESSAGE TEMPLATES TABLE
-- =============================================
CREATE TABLE message_templates (
    id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(100),
    description TEXT,  -- Added this column
    usage_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- SUBSCRIPTIONS TABLE
-- =============================================
CREATE TABLE subscriptions (
    id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(id) ON DELETE CASCADE,
    stripe_subscription_id VARCHAR(255) UNIQUE,
    plan_type subscription_tier NOT NULL,  -- Added this column
    status VARCHAR(50) DEFAULT 'active',
    current_period_start TIMESTAMP WITH TIME ZONE,
    current_period_end TIMESTAMP WITH TIME ZONE,
    monthly_price DECIMAL(10,2),
    features JSONB,
    usage_limits JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- USAGE ANALYTICS TABLE
-- =============================================
CREATE TABLE usage_analytics (
    id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(id) ON DELETE CASCADE,
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,
    messages_sent INTEGER DEFAULT 0,
    messages_received INTEGER DEFAULT 0,
    ai_responses_generated INTEGER DEFAULT 0,
    templates_used INTEGER DEFAULT 0,
    unique_conversations INTEGER DEFAULT 0,
    avg_response_time INTEGER,
    sentiment_avg DECIMAL(3,2),
    engagement_score DECIMAL(3,2),
    peak_hour INTEGER,
    peak_day VARCHAR(10),
    total_cost DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- CONVERSATION ANALYTICS TABLE
-- =============================================
CREATE TABLE conversation_analytics (
    id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(id) ON DELETE CASCADE,
    client_id VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    phone_number VARCHAR(20) NOT NULL,
    total_messages INTEGER DEFAULT 0,
    ai_responses INTEGER DEFAULT 0,
    response_rate DECIMAL(3,2) DEFAULT 0,
    avg_response_time INTEGER,
    sentiment_score DECIMAL(3,2) DEFAULT 0,
    engagement_score DECIMAL(3,2) DEFAULT 0,
    last_interaction TIMESTAMP WITH TIME ZONE,
    conversation_status VARCHAR(50) DEFAULT 'active',
    peak_hours JSONB,
    daily_stats JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- WEBHOOK LOGS TABLE
-- =============================================
CREATE TABLE webhook_logs (
    id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(id) ON DELETE CASCADE,
    webhook_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    processing_status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    received_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE
);

-- =============================================
-- INDEXES
-- =============================================
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_clients_user_id ON clients(user_id);
CREATE INDEX idx_clients_phone_number ON clients(phone_number);
CREATE INDEX idx_messages_user_id ON messages(user_id);
CREATE INDEX idx_messages_timestamp ON messages(timestamp DESC);
CREATE INDEX idx_messages_conversation ON messages(sender_number, recipient_number);
CREATE INDEX idx_templates_user_id ON message_templates(user_id);
CREATE INDEX idx_usage_analytics_user_month ON usage_analytics(user_id, year, month);
CREATE INDEX idx_conversation_analytics_user_client ON conversation_analytics(user_id, client_id);
CREATE INDEX idx_webhook_logs_user_id ON webhook_logs(user_id);

-- =============================================
-- SUCCESS MESSAGE
-- =============================================
SELECT 'Schema created successfully! Ready for data insertion.' as status;
