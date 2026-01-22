-- Initial database setup for Real-Time Analytics Platform
-- This script runs when PostgreSQL container starts for the first time

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pg_trgm; -- For text search

-- Create schemas
CREATE SCHEMA IF NOT EXISTS analytics;

-- Set search path
SET search_path TO public, analytics;

-- Create enum types (will be recreated by SQLAlchemy, but good to have)
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('admin', 'user', 'viewer');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create initial admin user (password: admin123)
-- Will be created by the application, this is just a placeholder

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE analytics TO rtap_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO rtap_user;
GRANT ALL PRIVILEGES ON SCHEMA analytics TO rtap_user;

-- Performance optimizations
ALTER DATABASE analytics SET timezone TO 'UTC';

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Database initialized successfully!';
    RAISE NOTICE 'TimescaleDB extension enabled';
    RAISE NOTICE 'Ready for Real-Time Analytics Platform';
END
$$;