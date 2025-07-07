-- Database Migration: Consolidate Profile functionality into User table
-- This migration eliminates the separate profiles concept and moves everything to the user level

BEGIN;

-- =============================================================================
-- STEP 1: Add new columns to users table
-- =============================================================================

-- Profile Information (integrated)
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS personal_phone VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'UTC';

-- SignalWire Integration
ALTER TABLE users ADD COLUMN IF NOT EXISTS signalwire_phone_number VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS signalwire_configured BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS signalwire_project_id VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS signalwire_space_url VARCHAR(200);

-- AI Settings (integrated from profile)
ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_personality TEXT DEFAULT 'You are a helpful assistant.';
ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_response_style VARCHAR(50) DEFAULT 'professional';
ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_language VARCHAR(10) DEFAULT 'en';
ALTER TABLE users ADD COLUMN IF NOT EXISTS use_emojis BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS casual_language BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS custom_instructions TEXT;

-- Auto Reply Settings
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_reply_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS custom_greeting TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS out_of_office_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS out_of_office_message TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS out_of_office_start TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS out_of_office_end TIMESTAMP;

-- Business Hours
ALTER TABLE users ADD COLUMN IF NOT EXISTS business_hours_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS business_hours_start TIME;
ALTER TABLE users ADD COLUMN IF NOT EXISTS business_hours_end TIME;
ALTER TABLE users ADD COLUMN IF NOT EXISTS business_days VARCHAR(20) DEFAULT '1,2,3,4,5';
ALTER TABLE users ADD COLUMN IF NOT EXISTS after_hours_message TEXT;

-- Safety & Security
ALTER TABLE users ADD COLUMN IF NOT EXISTS enable_flagged_word_detection BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS custom_flagged_words TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_block_suspicious BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS require_manual_review BOOLEAN DEFAULT FALSE;

-- Account Status
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMP;

-- Timestamps
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP;

-- =============================================================================
-- STEP 2: Migrate data from profiles table to users table (if profiles table exists)
-- =============================================================================

DO $$
BEGIN
    -- Check if profiles table exists
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'profiles') THEN
        
        -- Migrate profile data to users table
        UPDATE users 
        SET 
            display_name = p.name,
            timezone = p.timezone,
            signalwire_phone_number = p.phone_number,
            signalwire_configured = p.signalwire_configured,
            signalwire_project_id = p.signalwire_project_id,
            signalwire_space_url = p.signalwire_space_url,
            ai_enabled = p.ai_enabled,
            ai_personality = p.ai_personality,
            ai_response_style = p.ai_response_style,
            ai_language = p.ai_language,
            use_emojis = p.use_emojis,
            casual_language = p.casual_language,
            custom_instructions = p.custom_instructions,
            auto_reply_enabled = p.auto_reply_enabled,
            custom_greeting = p.custom_greeting,
            out_of_office_enabled = p.out_of_office_enabled,
            out_of_office_message = p.out_of_office_message,
            out_of_office_start = p.out_of_office_start,
            out_of_office_end = p.out_of_office_end,
            business_hours_enabled = p.business_hours_enabled,
            business_hours_start = p.business_hours_start,
            business_hours_end = p.business_hours_end,
            business_days = p.business_days,
            after_hours_message = p.after_hours_message,
            enable_flagged_word_detection = p.enable_flagged_word_detection,
            custom_flagged_words = p.custom_flagged_words,
            auto_block_suspicious = p.auto_block_suspicious,
            require_manual_review = p.require_manual_review,
            is_active = p.is_active,
            updated_at = p.updated_at
        FROM profiles p
        WHERE users.id = p.user_id;
        
        RAISE NOTICE 'Migrated data from profiles table to users table';
    ELSE
        RAISE NOTICE 'Profiles table does not exist, skipping data migration';
    END IF;
END
$$;

-- =============================================================================
-- STEP 3: Add user_id column to messages table (if using profile_id)
-- =============================================================================

DO $$
BEGIN
    -- Check if messages table has profile_id column
    IF EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'messages' AND column_name = 'profile_id') THEN
        
        -- Add user_id column if it doesn't exist
        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'messages' AND column_name = 'user_id') THEN
            ALTER TABLE messages ADD COLUMN user_id INTEGER;
            
            -- Create foreign key constraint
            ALTER TABLE messages ADD CONSTRAINT fk_messages_user_id 
                FOREIGN KEY (user_id) REFERENCES users(id);
            
            -- Create index for performance
            CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
        END IF;
        
        -- Migrate profile_id to user_id via profiles table
        IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'profiles') THEN
            UPDATE messages 
            SET user_id = p.user_id
            FROM profiles p
            WHERE messages.profile_id = p.id;
            
            RAISE NOTICE 'Migrated message profile_id to user_id';
        END IF;
        
    ELSE
        RAISE NOTICE 'Messages table does not have profile_id column, skipping migration';
    END IF;
END
$$;

-- =============================================================================
-- STEP 4: Add user_id column to clients table (if using profile_id)
-- =============================================================================

DO $$
BEGIN
    -- Check if clients table exists and has the right structure
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'clients') THEN
        
        -- Add user_id column if it doesn't exist
        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'clients' AND column_name = 'user_id') THEN
            ALTER TABLE clients ADD COLUMN user_id INTEGER;
            
            -- Create foreign key constraint
            ALTER TABLE clients ADD CONSTRAINT fk_clients_user_id 
                FOREIGN KEY (user_id) REFERENCES users(id);
            
            -- Create index for performance
            CREATE INDEX IF NOT EXISTS idx_clients_user_id ON clients(user_id);
        END IF;
        
        -- Add new columns to clients table for enhanced functionality
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS nickname VARCHAR(100);
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS email VARCHAR(255);
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS notes TEXT;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS tags VARCHAR(500);
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS city VARCHAR(100);
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS state VARCHAR(50);
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS country VARCHAR(50);
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS timezone VARCHAR(50);
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS relationship_status VARCHAR(50) DEFAULT 'new';
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS priority_level INTEGER DEFAULT 1;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS client_type VARCHAR(50);
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS total_interactions INTEGER DEFAULT 0;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS total_messages_received INTEGER DEFAULT 0;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS total_messages_sent INTEGER DEFAULT 0;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS custom_ai_personality TEXT;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS custom_greeting TEXT;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS auto_reply_enabled BOOLEAN DEFAULT TRUE;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS ai_response_style VARCHAR(50);
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS block_reason VARCHAR(200);
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS blocked_at TIMESTAMP;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN DEFAULT FALSE;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS is_flagged BOOLEAN DEFAULT FALSE;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS flag_reasons TEXT;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS risk_level VARCHAR(20) DEFAULT 'low';
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS trust_score FLOAT DEFAULT 0.5;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS verified_client BOOLEAN DEFAULT FALSE;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS avg_response_time FLOAT;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS last_message_sentiment FLOAT;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS engagement_score FLOAT DEFAULT 0.0;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS preferred_contact_time VARCHAR(50);
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS communication_style VARCHAR(50);
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS language_preference VARCHAR(10) DEFAULT 'en';
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS emoji_preference BOOLEAN DEFAULT TRUE;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        
        -- Update timestamps if they don't exist
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        
        RAISE NOTICE 'Enhanced clients table structure';
        
    ELSE
        RAISE NOTICE 'Clients table does not exist, skipping migration';
    END IF;
END
$$;

-- =============================================================================
-- STEP 5: Create message_templates table for user-specific templates
-- =============================================================================

CREATE TABLE IF NOT EXISTS message_templates (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(50),
    description TEXT,
    usage_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_message_templates_user_id ON message_templates(user_id);
CREATE INDEX IF NOT EXISTS idx_message_templates_category ON message_templates(category);

-- =============================================================================
-- STEP 6: Update message table structure for enhanced functionality
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'messages') THEN
        
        -- Add enhanced columns to messages table
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS ai_confidence FLOAT;
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS ai_model_used VARCHAR(50);
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS flag_reasons TEXT;
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS twilio_sid VARCHAR(100);
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS signalwire_id VARCHAR(100);
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS processing_status VARCHAR(20) DEFAULT 'delivered';
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS error_message TEXT;
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS sentiment_score FLOAT;
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS intent_classification VARCHAR(100);
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS confidence_score FLOAT;
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS sent_at TIMESTAMP;
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP;
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS read_at TIMESTAMP;
        
        -- Rename timestamp to ensure consistency
        DO $inner$
        BEGIN
            IF EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'messages' AND column_name = 'time') THEN
                ALTER TABLE messages RENAME COLUMN time TO timestamp;
            END IF;
        EXCEPTION WHEN OTHERS THEN
            -- Column might already be named timestamp
            NULL;
        END
        $inner$;
        
        -- Ensure timestamp column exists
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        
        -- Create indexes for performance
        CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
        CREATE INDEX IF NOT EXISTS idx_messages_sender_number ON messages(sender_number);
        CREATE INDEX IF NOT EXISTS idx_messages_recipient_number ON messages(recipient_number);
        CREATE INDEX IF NOT EXISTS idx_messages_is_incoming ON messages(is_incoming);
        CREATE INDEX IF NOT EXISTS idx_messages_ai_generated ON messages(ai_generated);
        CREATE INDEX IF NOT EXISTS idx_messages_is_flagged ON messages(is_flagged);
        CREATE INDEX IF NOT EXISTS idx_messages_processing_status ON messages(processing_status);
        
        RAISE NOTICE 'Enhanced messages table structure';
    END IF;
END
$$;

-- =============================================================================
-- STEP 7: Drop old profile-related tables (UNCOMMENT WHEN READY)
-- =============================================================================

-- WARNING: Only run these DROP statements after confirming data migration is successful
-- and you have a backup of your database!

/*
-- Drop profile-related tables
DROP TABLE IF EXISTS text_examples CASCADE;
DROP TABLE IF EXISTS auto_replies CASCADE;
DROP TABLE IF EXISTS out_of_office_replies CASCADE;
DROP TABLE IF EXISTS profile_clients CASCADE;
DROP TABLE IF EXISTS profiles CASCADE;

-- Remove profile_id columns from tables
ALTER TABLE messages DROP COLUMN IF EXISTS profile_id;

RAISE NOTICE 'Dropped old profile-related tables and columns';
*/

-- =============================================================================
-- STEP 8: Create updated indexes and constraints
-- =============================================================================

-- Ensure proper indexes exist
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_signalwire_phone ON users(signalwire_phone_number);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);

CREATE INDEX IF NOT EXISTS idx_clients_phone_number ON clients(phone_number);
CREATE INDEX IF NOT EXISTS idx_clients_relationship_status ON clients(relationship_status);
CREATE INDEX IF NOT EXISTS idx_clients_is_blocked ON clients(is_blocked);
CREATE INDEX IF NOT EXISTS idx_clients_is_flagged ON clients(is_flagged);
CREATE INDEX IF NOT EXISTS idx_clients_risk_level ON clients(risk_level);

-- =============================================================================
-- STEP 9: Update any remaining foreign key constraints
-- =============================================================================

-- Make sure all foreign keys are properly set
DO $$
BEGIN
    -- Ensure messages.user_id foreign key exists
    IF NOT EXISTS (
        SELECT FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_messages_user_id'
    ) THEN
        ALTER TABLE messages ADD CONSTRAINT fk_messages_user_id 
            FOREIGN KEY (user_id) REFERENCES users(id);
    END IF;
    
    -- Ensure clients.user_id foreign key exists
    IF NOT EXISTS (
        SELECT FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_clients_user_id'
    ) THEN
        ALTER TABLE clients ADD CONSTRAINT fk_clients_user_id 
            FOREIGN KEY (user_id) REFERENCES users(id);
    END IF;
    
    RAISE NOTICE 'Updated foreign key constraints';
END
$$;

-- =============================================================================
-- STEP 10: Data cleanup and validation
-- =============================================================================

-- Update any NULL user_id values to prevent constraint violations
UPDATE messages SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1);
UPDATE clients SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1);

-- Update any missing timestamps
UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL;
UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;
UPDATE messages SET timestamp = CURRENT_TIMESTAMP WHERE timestamp IS NULL;
UPDATE clients SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL;
UPDATE clients SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;
UPDATE clients SET first_contact = CURRENT_TIMESTAMP WHERE first_contact IS NULL;
UPDATE clients SET last_interaction = CURRENT_TIMESTAMP WHERE last_interaction IS NULL;

COMMIT;

-- =============================================================================
-- MIGRATION SUMMARY
-- =============================================================================

DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE 'PROFILE TO USER CONSOLIDATION COMPLETED';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Changes made:';
    RAISE NOTICE '1. Added profile functionality to users table';
    RAISE NOTICE '2. Migrated data from profiles to users (if existed)';
    RAISE NOTICE '3. Updated messages table to use user_id';
    RAISE NOTICE '4. Enhanced clients table structure';
    RAISE NOTICE '5. Created message_templates table';
    RAISE NOTICE '6. Added performance indexes';
    RAISE NOTICE '7. Updated foreign key constraints';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '1. Test your application thoroughly';
    RAISE NOTICE '2. Update your API endpoints to use user_id';
    RAISE NOTICE '3. Update frontend to remove profile selection';
    RAISE NOTICE '4. When confident, uncomment DROP statements above';
    RAISE NOTICE '============================================';
END
$$;