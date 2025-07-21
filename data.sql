-- AssisText Corrected Fake Data
-- Run this AFTER the corrected schema

-- =============================================
-- USERS
-- =============================================
INSERT INTO users (id, email, password_hash, name, company_name, phone_number, is_active, subscription_tier, created_at, updated_at) VALUES
('usr_001', 'sarah.johnson@healthcareplus.com', '$2b$12$hashed_password_1', 'Sarah Johnson', 'HealthCare Plus Clinic', '+15551234567', true, 'professional', '2024-01-15 09:30:00', '2024-03-20 14:22:00'),
('usr_002', 'mike.rodriguez@techstartup.io', '$2b$12$hashed_password_2', 'Mike Rodriguez', 'TechStartup Solutions', '+15551234568', true, 'enterprise', '2024-02-01 11:15:00', '2024-03-19 16:45:00'),
('usr_003', 'lisa.chen@legalfirm.com', '$2b$12$hashed_password_3', 'Lisa Chen', 'Chen & Associates Law', '+15551234569', true, 'basic', '2024-02-10 08:45:00', '2024-03-18 10:30:00'),
('usr_004', 'david.williams@realestate.ca', '$2b$12$hashed_password_4', 'David Williams', 'Williams Real Estate', '+14161234567', true, 'professional', '2024-01-20 13:20:00', '2024-03-17 09:15:00'),
('usr_005', 'emma.davis@consultancy.com', '$2b$12$hashed_password_5', 'Emma Davis', 'Davis Business Consultancy', '+15551234570', true, 'enterprise', '2024-02-05 15:10:00', '2024-03-21 11:00:00');

-- =============================================
-- USER SETTINGS
-- =============================================
INSERT INTO user_settings (user_id, ai_enabled, ai_model, ai_temperature, ai_max_tokens, ai_personality, auto_reply_enabled, auto_reply_delay, business_hours_start, business_hours_end, business_days, after_hours_message, timezone, confidence_threshold, fallback_message) VALUES
('usr_001', true, 'dolphin-mistral:7b', 0.7, 150, 'Professional healthcare assistant focused on patient care and appointment scheduling', true, 45, '08:00', '18:00', 'monday,tuesday,wednesday,thursday,friday', 'Thank you for contacting HealthCare Plus. Our office hours are 8 AM to 6 PM, Monday through Friday.', 'America/Toronto', 0.85, 'Thank you for your message. I''ll get back to you shortly.'),
('usr_002', true, 'dolphin-mistral:7b', 0.8, 200, 'Tech-savvy and innovative assistant for a cutting-edge startup environment', true, 30, '09:00', '17:00', 'monday,tuesday,wednesday,thursday,friday', 'Thanks for reaching out to TechStartup Solutions!', 'America/Vancouver', 0.80, 'Thanks for your message! Our team will respond soon.'),
('usr_003', true, 'llama2:7b', 0.6, 120, 'Professional legal assistant with formal communication style', true, 60, '09:00', '17:00', 'monday,tuesday,wednesday,thursday,friday', 'Thank you for contacting Chen & Associates Law.', 'America/Toronto', 0.90, 'Thank you for your inquiry. We will review your message.'),
('usr_004', true, 'dolphin-mistral:7b', 0.75, 180, 'Friendly real estate professional focused on helping clients find their perfect home', true, 20, '08:00', '20:00', 'monday,tuesday,wednesday,thursday,friday,saturday,sunday', 'Hi! Thanks for your interest in Williams Real Estate.', 'America/Toronto', 0.75, 'Thanks for reaching out about your real estate needs.'),
('usr_005', true, 'dolphin-mistral:7b', 0.7, 160, 'Business consultant with strategic insights and professional guidance', true, 40, '09:00', '18:00', 'monday,tuesday,wednesday,thursday,friday', 'Thank you for contacting Davis Business Consultancy.', 'America/New_York', 0.82, 'Thank you for your message. I look forward to helping your business grow.');

-- =============================================
-- SIGNALWIRE SETTINGS
-- =============================================
INSERT INTO signalwire_settings (user_id, signalwire_project_id, signalwire_space_url, signalwire_phone_number, webhook_url, signalwire_configured, created_at, updated_at) VALUES
('usr_001', 'proj_healthcare_001', 'healthcare-plus.signalwire.com', '+15551001001', 'https://api.assistext.ca/webhooks/signalwire/usr_001', true, '2024-01-15 10:00:00', '2024-03-20 14:22:00'),
('usr_002', 'proj_techstartup_002', 'techstartup.signalwire.com', '+15551001002', 'https://api.assistext.ca/webhooks/signalwire/usr_002', true, '2024-02-01 12:00:00', '2024-03-19 16:45:00'),
('usr_003', 'proj_legal_003', 'chen-law.signalwire.com', '+15551001003', 'https://api.assistext.ca/webhooks/signalwire/usr_003', true, '2024-02-10 09:30:00', '2024-03-18 10:30:00'),
('usr_004', 'proj_realestate_004', 'williams-re.signalwire.com', '+14161001004', 'https://api.assistext.ca/webhooks/signalwire/usr_004', true, '2024-01-20 14:00:00', '2024-03-17 09:15:00'),
('usr_005', 'proj_consulting_005', 'davis-consulting.signalwire.com', '+15551001005', 'https://api.assistext.ca/webhooks/signalwire/usr_005', true, '2024-02-05 16:00:00', '2024-03-21 11:00:00');

-- =============================================
-- CLIENTS
-- =============================================
INSERT INTO clients (id, user_id, phone_number, name, nickname, email, display_name, notes, tags, city, state, country, timezone, relationship_status, priority_level, client_type, first_contact, last_interaction, total_interactions, total_messages_received, total_messages_sent, custom_ai_personality, custom_greeting, auto_reply_enabled, ai_response_style, is_blocked, block_reason, is_favorite, is_flagged, flag_reasons, risk_level, trust_score, verified_client, avg_response_time, last_message_sentiment, engagement_score, preferred_contact_time, communication_style, language_preference, emoji_preference, created_at, updated_at) VALUES

-- Sarah's Healthcare Clients
('cli_001', 'usr_001', '+15552001001', 'Jennifer Martinez', 'Jen', 'jen.martinez@email.com', 'Jennifer Martinez', 'Regular patient, prefers morning appointments', ARRAY['regular-patient', 'morning-preference'], 'Toronto', 'ON', 'Canada', 'America/Toronto', 'regular', 3, 'patient', '2024-01-20 10:30:00', '2024-03-21 14:20:00', 15, 8, 7, null, 'Good morning Jennifer!', true, 'professional', false, null, true, false, null, 'low', 0.92, true, 1200, 0.3, 0.85, 'morning', 'formal', 'english', false, '2024-01-20 10:30:00', '2024-03-21 14:20:00'),

('cli_002', 'usr_001', '+15552001002', 'Robert Thompson', 'Bob', 'bob.thompson@email.com', 'Robert Thompson', 'Senior patient, needs clear instructions', ARRAY['senior-patient', 'needs-assistance'], 'Mississauga', 'ON', 'Canada', 'America/Toronto', 'regular', 4, 'patient', '2024-01-25 11:15:00', '2024-03-20 16:45:00', 22, 12, 10, 'Extra patient and clear in explanations', null, true, 'gentle', false, null, false, false, null, 'low', 0.88, true, 1800, 0.1, 0.75, 'afternoon', 'simple', 'english', false, '2024-01-25 11:15:00', '2024-03-20 16:45:00'),

('cli_003', 'usr_001', '+15552001003', 'Maria Santos', 'Maria', 'maria.santos@email.com', 'Maria Santos', 'Spanish speaker, emergency contact: daughter', ARRAY['spanish-speaker', 'family-contact'], 'Toronto', 'ON', 'Canada', 'America/Toronto', 'regular', 3, 'patient', '2024-02-01 09:45:00', '2024-03-19 12:30:00', 18, 10, 8, null, 'Hola Maria!', true, 'bilingual', false, null, false, false, null, 'low', 0.95, true, 900, 0.4, 0.90, 'morning', 'friendly', 'spanish', true, '2024-02-01 09:45:00', '2024-03-19 12:30:00'),

-- Mike's TechStartup Clients
('cli_004', 'usr_002', '+15552002001', 'Alex Chen', 'Alex', 'alex.chen@techcorp.com', 'Alex Chen - TechCorp', 'Lead developer, interested in API solutions', ARRAY['developer', 'enterprise', 'api-integration'], 'Vancouver', 'BC', 'Canada', 'America/Vancouver', 'vip', 5, 'enterprise', '2024-02-05 14:20:00', '2024-03-21 10:15:00', 28, 15, 13, null, null, true, 'technical', false, null, true, false, null, 'low', 0.94, true, 600, 0.2, 0.88, 'afternoon', 'technical', 'english', false, '2024-02-05 14:20:00', '2024-03-21 10:15:00'),

('cli_005', 'usr_002', '+15552002002', 'Sarah Kim', 'Sarah', 'sarah.kim@startup.io', 'Sarah Kim - Startup.io', 'Startup founder, needs scalable solution', ARRAY['founder', 'startup', 'scalability'], 'San Francisco', 'CA', 'USA', 'America/Los_Angeles', 'vip', 5, 'startup', '2024-02-10 16:30:00', '2024-03-20 14:45:00', 35, 18, 17, 'Entrepreneurial and solution-focused', null, true, 'innovative', false, null, true, false, null, 'low', 0.96, true, 450, 0.5, 0.92, 'evening', 'direct', 'english', true, '2024-02-10 16:30:00', '2024-03-20 14:45:00'),

-- Other users' clients
('cli_006', 'usr_003', '+15552003001', 'Michael Brown', 'Mike', 'michael.brown@email.com', 'Michael Brown', 'Divorce case, sensitive communication required', ARRAY['divorce-case', 'sensitive'], 'Toronto', 'ON', 'Canada', 'America/Toronto', 'regular', 4, 'family-law', '2024-02-15 13:10:00', '2024-03-18 11:20:00', 12, 7, 5, 'Extra compassionate and professional', null, true, 'empathetic', false, null, false, false, null, 'medium', 0.85, true, 2400, -0.2, 0.70, 'afternoon', 'formal', 'english', false, '2024-02-15 13:10:00', '2024-03-18 11:20:00'),

('cli_007', 'usr_004', '+14162003001', 'Emily Johnson', 'Emily', 'emily.johnson@email.com', 'Emily Johnson', 'First-time homebuyer, very excited', ARRAY['first-time-buyer', 'excited'], 'Toronto', 'ON', 'Canada', 'America/Toronto', 'new', 3, 'buyer', '2024-03-10 15:30:00', '2024-03-21 09:45:00', 8, 5, 3, null, 'Hi Emily! Excited to help you find your dream home!', true, 'enthusiastic', false, null, false, false, null, 'low', 0.89, true, 800, 0.7, 0.95, 'evening', 'casual', 'english', true, '2024-03-10 15:30:00', '2024-03-21 09:45:00'),

('cli_008', 'usr_004', '+14162003002', 'John Wilson', 'John', 'john.wilson@email.com', 'John Wilson', 'Investor looking for rental properties', ARRAY['investor', 'rental-properties'], 'Mississauga', 'ON', 'Canada', 'America/Toronto', 'vip', 5, 'investor', '2024-02-20 12:15:00', '2024-03-20 17:30:00', 25, 13, 12, 'Business-focused with investment insights', null, true, 'professional', false, null, true, false, null, 'low', 0.93, true, 1200, 0.1, 0.82, 'morning', 'business', 'english', false, '2024-02-20 12:15:00', '2024-03-20 17:30:00'),

('cli_009', 'usr_005', '+15552005001', 'Rachel Green', 'Rachel', 'rachel.green@smallbiz.com', 'Rachel Green - SmallBiz Inc', 'Small business owner, needs growth strategy', ARRAY['small-business', 'growth-strategy'], 'New York', 'NY', 'USA', 'America/New_York', 'new', 4, 'small-business', '2024-03-05 10:45:00', '2024-03-21 13:15:00', 6, 3, 3, null, null, true, 'strategic', false, null, false, false, null, 'low', 0.87, true, 1500, 0.3, 0.80, 'morning', 'professional', 'english', false, '2024-03-05 10:45:00', '2024-03-21 13:15:00'),

('cli_010', 'usr_005', '+15552005002', 'Thomas Anderson', 'Tom', 'tom.anderson@enterprise.com', 'Thomas Anderson - Enterprise Corp', 'Large corporation, digital transformation project', ARRAY['enterprise', 'digital-transformation'], 'Boston', 'MA', 'USA', 'America/New_York', 'vip', 5, 'enterprise', '2024-02-25 14:20:00', '2024-03-19 16:00:00', 18, 9, 9, 'Executive-level communication style', null, true, 'executive', false, null, true, false, null, 'low', 0.91, true, 900, 0.2, 0.88, 'afternoon', 'executive', 'english', false, '2024-02-25 14:20:00', '2024-03-19 16:00:00');

-- =============================================
-- MESSAGES
-- =============================================
INSERT INTO messages (id, user_id, sender_number, recipient_number, content, is_incoming, ai_generated, ai_confidence, ai_model_used, sentiment_score, intent_classification, confidence_score, is_read, is_flagged, flag_reasons, processing_status, retry_count, error_message, timestamp, sent_at, delivered_at, read_at, time_since, conversation_partner) VALUES

-- Jennifer's conversation with HealthCare Plus
('msg_001', 'usr_001', '+15552001001', '+15551001001', 'Hi, I need to reschedule my appointment for tomorrow', true, false, null, null, 0.1, 'appointment_scheduling', 0.9, true, false, null, 'delivered', 0, null, '2024-03-21 09:15:00', '2024-03-21 09:15:00', '2024-03-21 09:15:05', '2024-03-21 09:16:00', '2 hours ago', '+15552001001'),
('msg_002', 'usr_001', '+15551001001', '+15552001001', 'Of course! I can help you reschedule. What day and time would work better for you?', false, true, 0.92, 'dolphin-mistral:7b', 0.4, 'helpful_response', 0.92, true, false, null, 'delivered', 0, null, '2024-03-21 09:16:30', '2024-03-21 09:16:30', '2024-03-21 09:16:35', '2024-03-21 09:17:00', '2 hours ago', '+15552001001'),
('msg_003', 'usr_001', '+15552001001', '+15551001001', 'Friday at 2 PM would be perfect if available', true, false, null, null, 0.3, 'appointment_request', 0.95, true, false, null, 'delivered', 0, null, '2024-03-21 09:18:00', '2024-03-21 09:18:00', '2024-03-21 09:18:05', '2024-03-21 09:19:00', '2 hours ago', '+15552001001'),
('msg_004', 'usr_001', '+15551001001', '+15552001001', 'Perfect! I have you scheduled for Friday, March 22nd at 2:00 PM. You''ll receive a confirmation text 24 hours before your appointment.', false, true, 0.89, 'dolphin-mistral:7b', 0.5, 'confirmation', 0.89, true, false, null, 'delivered', 0, null, '2024-03-21 09:19:15', '2024-03-21 09:19:15', '2024-03-21 09:19:20', '2024-03-21 09:20:00', '2 hours ago', '+15552001001'),

-- Bob's conversation
('msg_005', 'usr_001', '+15552001002', '+15551001001', 'My prescription is ready?', true, false, null, null, 0.0, 'prescription_inquiry', 0.85, true, false, null, 'delivered', 0, null, '2024-03-20 15:30:00', '2024-03-20 15:30:00', '2024-03-20 15:30:05', '2024-03-20 15:31:00', '18 hours ago', '+15552001002'),
('msg_006', 'usr_001', '+15551001001', '+15552001002', 'Yes, Mr. Thompson! Your prescription is ready for pickup. Our pharmacy is open until 6 PM today.', false, true, 0.94, 'dolphin-mistral:7b', 0.4, 'information_response', 0.94, true, false, null, 'delivered', 0, null, '2024-03-20 15:31:45', '2024-03-20 15:31:45', '2024-03-20 15:31:50', '2024-03-20 15:32:00', '18 hours ago', '+15552001002'),

-- Alex's conversation with TechStartup
('msg_007', 'usr_002', '+15552002001', '+15551001002', 'Hey Mike, can we schedule a demo of your API integration platform?', true, false, null, null, 0.2, 'meeting_request', 0.92, true, false, null, 'delivered', 0, null, '2024-03-21 10:15:00', '2024-03-21 10:15:00', '2024-03-21 10:15:05', '2024-03-21 10:16:00', '1 hour ago', '+15552002001'),
('msg_008', 'usr_002', '+15551001002', '+15552002001', 'Absolutely! I''d love to show you what we''ve built. Are you available this Thursday at 3 PM?', false, true, 0.88, 'dolphin-mistral:7b', 0.6, 'meeting_scheduling', 0.88, true, false, null, 'delivered', 0, null, '2024-03-21 10:16:45', '2024-03-21 10:16:45', '2024-03-21 10:16:50', '2024-03-21 10:17:00', '1 hour ago', '+15552002001'),

-- Emily's conversation with Real Estate
('msg_009', 'usr_004', '+14162003001', '+14161001004', 'David! I saw that house on Maple Street online. Is it still available?', true, false, null, null, 0.6, 'property_inquiry', 0.95, true, false, null, 'delivered', 0, null, '2024-03-21 09:45:00', '2024-03-21 09:45:00', '2024-03-21 09:45:05', '2024-03-21 09:46:00', '1 hour ago', '+14162003001'),
('msg_010', 'usr_004', '+14161001004', '+14162003001', 'Hi Emily! Yes, it''s still available! Want to see it this weekend?', false, true, 0.93, 'dolphin-mistral:7b', 0.8, 'property_availability', 0.93, true, false, null, 'delivered', 0, null, '2024-03-21 09:46:20', '2024-03-21 09:46:20', '2024-03-21 09:46:25', '2024-03-21 09:47:00', '1 hour ago', '+14162003001'),

-- Flagged message example
('msg_011', 'usr_003', '+15552003001', '+15551001003', 'Lisa, my ex is threatening to take the kids if I don''t give her the house. What can I do?', true, false, null, null, -0.6, 'legal_emergency', 0.9, true, true, ARRAY['urgent', 'custody'], 'delivered', 0, null, '2024-03-18 16:45:00', '2024-03-18 16:45:00', '2024-03-18 16:45:05', '2024-03-18 16:50:00', '3 days ago', '+15552003001'),

-- Rachel's conversation with Business Consulting
('msg_012', 'usr_005', '+15552005001', '+15551001005', 'Emma, our Q1 numbers are in and we''re 30% above projections! Ready to talk expansion?', true, false, null, null, 0.7, 'business_update', 0.95, true, false, null, 'delivered', 0, null, '2024-03-21 13:15:00', '2024-03-21 13:15:00', '2024-03-21 13:15:05', '2024-03-21 13:16:00', '30 minutes ago', '+15552005001'),
('msg_013', 'usr_005', '+15551001005', '+15552005001', 'Rachel, that''s fantastic news! Let''s schedule a strategy session to discuss expansion plans.', false, true, 0.90, 'dolphin-mistral:7b', 0.6, 'congratulations_scheduling', 0.90, true, false, null, 'delivered', 0, null, '2024-03-21 13:16:40', '2024-03-21 13:16:40', '2024-03-21 13:16:45', '2024-03-21 13:17:00', '30 minutes ago', '+15552005001');

-- =============================================
-- MESSAGE TEMPLATES
-- =============================================
INSERT INTO message_templates (id, user_id, name, content, category, description, usage_count, is_active, sort_order, created_at, updated_at) VALUES
('tpl_001', 'usr_001', 'Appointment Confirmation', 'Your appointment is confirmed for {date} at {time}. Please arrive 15 minutes early.', 'appointments', 'Standard appointment confirmation message', 25, true, 1, '2024-01-20 10:00:00', '2024-03-15 14:30:00'),
('tpl_002', 'usr_001', 'Prescription Ready', 'Your prescription is ready for pickup. Pharmacy hours: Mon-Fri 9 AM - 6 PM.', 'pharmacy', 'Notification for prescription pickup', 18, true, 2, '2024-01-20 10:05:00', '2024-03-10 11:20:00'),
('tpl_003', 'usr_002', 'Demo Scheduling', 'Thanks for your interest! I''d love to show you our platform. Are you available for a demo this week?', 'sales', 'Initial demo scheduling message', 15, true, 1, '2024-02-01 12:00:00', '2024-03-18 10:30:00'),
('tpl_004', 'usr_004', 'Property Showing', 'Great! I''ve scheduled your showing for {property_address} on {date} at {time}.', 'showings', 'Property showing confirmation', 32, true, 1, '2024-01-20 14:00:00', '2024-03-20 16:30:00'),
('tpl_005', 'usr_005', 'Strategy Session', 'Let''s schedule a strategy session to discuss your business goals. I have availability {availability}.', 'scheduling', 'Strategy session scheduling', 18, true, 1, '2024-02-05 16:00:00', '2024-03-19 11:30:00');

-- =============================================
-- SUBSCRIPTIONS
-- =============================================
INSERT INTO subscriptions (id, user_id, stripe_subscription_id, plan_type, status, current_period_start, current_period_end, monthly_price, features, usage_limits, created_at, updated_at) VALUES
('sub_001', 'usr_001', 'sub_1234567890abcdef', 'professional', 'active', '2024-03-01 00:00:00', '2024-04-01 00:00:00', 49.99, '{"ai_responses": true, "templates": true, "analytics": true}', '{"monthly_messages": 2000, "clients": 100}', '2024-01-15 10:00:00', '2024-03-01 00:00:00'),
('sub_002', 'usr_002', 'sub_2345678901bcdefg', 'enterprise', 'active', '2024-03-01 00:00:00', '2024-04-01 00:00:00', 199.99, '{"ai_responses": true, "templates": true, "analytics": true, "white_label": true}', '{"monthly_messages": 10000, "clients": 1000}', '2024-02-01 12:00:00', '2024-03-01 00:00:00'),
('sub_003', 'usr_003', 'sub_3456789012cdefgh', 'basic', 'active', '2024-03-01 00:00:00', '2024-04-01 00:00:00', 19.99, '{"ai_responses": true, "templates": true}', '{"monthly_messages": 500, "clients": 25}', '2024-02-10 09:00:00', '2024-03-01 00:00:00'),
('sub_004', 'usr_004', 'sub_4567890123defghi', 'professional', 'active', '2024-03-01 00:00:00', '2024-04-01 00:00:00', 49.99, '{"ai_responses": true, "templates": true, "analytics": true}', '{"monthly_messages": 2000, "clients": 100}', '2024-01-20 14:00:00', '2024-03-01 00:00:00'),
('sub_005', 'usr_005', 'sub_5678901234efghij', 'enterprise', 'active', '2024-03-01 00:00:00', '2024-04-01 00:00:00', 199.99, '{"ai_responses": true, "templates": true, "analytics": true, "white_label": true}', '{"monthly_messages": 10000, "clients": 1000}', '2024-02-05 16:00:00', '2024-03-01 00:00:00');

-- =============================================
-- USAGE ANALYTICS
-- =============================================
INSERT INTO usage_analytics (id, user_id, month, year, messages_sent, messages_received, ai_responses_generated, templates_used, unique_conversations, avg_response_time, sentiment_avg, engagement_score, peak_hour, peak_day, total_cost, created_at) VALUES
('ana_001', 'usr_001', 3, 2024, 156, 189, 142, 89, 48, 1350, 0.25, 0.82, 14, 'tuesday', 23.40, '2024-04-01 00:00:00'),
('ana_002', 'usr_002', 3, 2024, 445, 398, 321, 156, 87, 720, 0.35, 0.89, 16, 'tuesday', 66.75, '2024-04-01 00:00:00'),
('ana_003', 'usr_003', 3, 2024, 89, 76, 58, 34, 23, 2100, 0.05, 0.72, 11, 'monday', 13.35, '2024-04-01 00:00:00'),
('ana_004', 'usr_004', 3, 2024, 234, 189, 178, 142, 67, 950, 0.68, 0.94, 19, 'saturday', 35.10, '2024-04-01 00:00:00'),
('ana_005', 'usr_005', 3, 2024, 298, 256, 223, 134, 58, 1120, 0.38, 0.87, 14, 'wednesday', 44.70, '2024-04-01 00:00:00');

-- =============================================
-- CONVERSATION ANALYTICS
-- =============================================
INSERT INTO conversation_analytics (id, user_id, client_id, phone_number, total_messages, ai_responses, response_rate, avg_response_time, sentiment_score, engagement_score, last_interaction, conversation_status, peak_hours, daily_stats, created_at, updated_at) VALUES
('con_001', 'usr_001', 'cli_001', '+15552001001', 15, 7, 0.87, 1200, 0.3, 0.85, '2024-03-21 14:20:00', 'active', '[{"hour": 9, "count": 4}, {"hour": 14, "count": 3}]', '[{"date": "2024-03-21", "sent": 2, "received": 2}]', '2024-03-21 14:20:00', '2024-03-21 14:20:00'),
('con_002', 'usr_001', 'cli_002', '+15552001002', 22, 10, 0.91, 1800, 0.1, 0.75, '2024-03-20 16:45:00', 'active', '[{"hour": 15, "count": 5}, {"hour": 10, "count": 3}]', '[{"date": "2024-03-20", "sent": 2, "received": 1}]', '2024-03-20 16:45:00', '2024-03-20 16:45:00'),
('con_003', 'usr_002', 'cli_004', '+15552002001', 28, 13, 0.93, 600, 0.2, 0.88, '2024-03-21 10:15:00', 'active', '[{"hour": 10, "count": 6}, {"hour": 14, "count": 4}]', '[{"date": "2024-03-21", "sent": 2, "received": 2}]', '2024-03-21 10:15:00', '2024-03-21 10:15:00'),
('con_004', 'usr_004', 'cli_007', '+14162003001', 8, 3, 0.75, 800, 0.7, 0.95, '2024-03-21 09:45:00', 'active', '[{"hour": 9, "count": 2}, {"hour": 19, "count": 2}]', '[{"date": "2024-03-21", "sent": 2, "received": 2}]', '2024-03-21 09:45:00', '2024-03-21 09:45:00'),
('con_005', 'usr_005', 'cli_009', '+15552005001', 6, 3, 1.0, 1500, 0.3, 0.80, '2024-03-21 13:15:00', 'active', '[{"hour": 10, "count": 2}, {"hour": 13, "count": 2}]', '[{"date": "2024-03-21", "sent": 1, "received": 1}]', '2024-03-21 13:15:00', '2024-03-21 13:15:00');

-- =============================================
-- WEBHOOK LOGS
-- =============================================
INSERT INTO webhook_logs (id, user_id, webhook_type, payload, processing_status, error_message, received_at, processed_at) VALUES
('wh_001', 'usr_001', 'incoming_sms', '{"MessageSid": "SM1234567890", "From": "+15552001001", "To": "+15551001001", "Body": "Hi, I need to reschedule"}', 'processed', null, '2024-03-21 09:15:00', '2024-03-21 09:15:02'),
('wh_002', 'usr_002', 'incoming_sms', '{"MessageSid": "SM2345678901", "From": "+15552002001", "To": "+15551001002", "Body": "Can we schedule a demo?"}', 'processed', null, '2024-03-21 10:15:00', '2024-03-21 10:15:01'),
('wh_003', 'usr_004', 'incoming_sms', '{"MessageSid": "SM3456789012", "From": "+14162003001", "To": "+14161001004", "Body": "Is that house still available?"}', 'processed', null, '2024-03-21 09:45:00', '2024-03-21 09:45:01');

-- =============================================
-- SUCCESS MESSAGE
-- =============================================
SELECT 'Data inserted successfully! Database is ready for use.' as status,
       (SELECT COUNT(*) FROM users) as users_count,
       (SELECT COUNT(*) FROM clients) as clients_count,
       (SELECT COUNT(*) FROM messages) as messages_count,
       (SELECT COUNT(*) FROM message_templates) as templates_count;x
