-- Neon PostgreSQL & SQLite Compatible DDL Schema for Creator Safety Shield

CREATE TABLE IF NOT EXISTS moderation_logs (
    id SERIAL PRIMARY KEY,
    author_username VARCHAR(255) DEFAULT 'Anonymous',
    author_name VARCHAR(255) DEFAULT 'Anonymous User',
    comment_text TEXT NOT NULL,
    is_toxic BOOLEAN DEFAULT FALSE,
    label VARCHAR(50) DEFAULT 'Non-Toxic',
    category VARCHAR(255) DEFAULT 'Safe',
    confidence FLOAT DEFAULT 0.0,
    threat_detected BOOLEAN DEFAULT FALSE,
    platform VARCHAR(50) DEFAULT 'Web Playground',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usage_tracker (
    id SERIAL PRIMARY KEY,
    year_month VARCHAR(20) UNIQUE NOT NULL,
    processed_count INT DEFAULT 0,
    limit_count INT DEFAULT 25000
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    plan_name VARCHAR(100) DEFAULT 'Creator Safety Shield ₹99',
    amount_inr INT DEFAULT 99,
    status VARCHAR(50) DEFAULT 'active',
    razorpay_payment_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
