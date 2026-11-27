-- 007_mock_test_system.sql
-- Backward-compatible additive migration for the IELTS Mock Test System
-- (Public Catalog with UZS informational price, Protected Materials,
-- Complimentary User Access Management with Expiration, and Admin Audit Logs).

CREATE TABLE IF NOT EXISTS mock_tests (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(64) NOT NULL DEFAULT 'Full Mock Test',
    description TEXT NOT NULL,
    price_uzs INTEGER NOT NULL DEFAULT 0,
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    questions_count INTEGER NOT NULL DEFAULT 40,
    instructions TEXT,
    preview_image_file_id TEXT,
    is_published BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_mock_tests_price_non_negative CHECK (price_uzs >= 0),
    CONSTRAINT ck_mock_tests_duration_positive CHECK (duration_minutes > 0)
);

CREATE INDEX IF NOT EXISTS ix_mock_tests_pub_active ON mock_tests(is_published, is_active);
CREATE INDEX IF NOT EXISTS ix_mock_tests_category ON mock_tests(category);

CREATE TABLE IF NOT EXISTS mock_test_files (
    id SERIAL PRIMARY KEY,
    mock_test_id INTEGER NOT NULL REFERENCES mock_tests(id) ON DELETE CASCADE,
    file_type VARCHAR(32) NOT NULL DEFAULT 'pdf',
    material_role VARCHAR(32) NOT NULL DEFAULT 'question_paper',
    title VARCHAR(255) NOT NULL DEFAULT 'Mock Test Material',
    telegram_file_id TEXT,
    file_name VARCHAR(255),
    mime_type VARCHAR(128),
    text_content TEXT,
    position INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_mock_test_files_type CHECK (
        file_type IN ('pdf', 'audio', 'voice', 'image', 'text', 'document')
    ),
    CONSTRAINT ck_mock_test_files_role CHECK (
        material_role IN ('question_paper', 'audio_track', 'reading_passage', 'answer_sheet', 'answer_key', 'instructions')
    )
);

CREATE INDEX IF NOT EXISTS ix_mock_test_files_test_id ON mock_test_files(mock_test_id, position);

CREATE TABLE IF NOT EXISTS mock_test_access (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    mock_test_id INTEGER NOT NULL REFERENCES mock_tests(id) ON DELETE CASCADE,
    granted_by BIGINT NOT NULL DEFAULT 0,
    access_type VARCHAR(32) NOT NULL DEFAULT 'admin_grant',
    access_reason VARCHAR(255) NOT NULL DEFAULT 'Complimentary educational access',
    duration_label VARCHAR(64) NOT NULL DEFAULT 'Permanent',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revoked_by BIGINT,
    CONSTRAINT uq_mock_test_access_user_test UNIQUE (user_id, mock_test_id)
);

CREATE INDEX IF NOT EXISTS ix_mock_test_access_user ON mock_test_access(user_id, is_active);
CREATE INDEX IF NOT EXISTS ix_mock_test_access_test ON mock_test_access(mock_test_id, is_active);

CREATE TABLE IF NOT EXISTS mock_test_admin_logs (
    id SERIAL PRIMARY KEY,
    admin_id BIGINT NOT NULL,
    target_user_id BIGINT,
    mock_test_id INTEGER,
    action VARCHAR(64) NOT NULL,
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_mock_test_admin_logs_admin ON mock_test_admin_logs(admin_id);
CREATE INDEX IF NOT EXISTS ix_mock_test_admin_logs_test ON mock_test_admin_logs(mock_test_id);
