-- 006_admin_permanent_library.sql
-- Backward-compatible additive migration for Permanent Vocabulary Archive,
-- Individual Admin Memorization Progress, Spaced Repetition (1/3/7/14/30d),
-- Resumable Admin Learning Sessions, and Admin Quiz History.

CREATE TABLE IF NOT EXISTS vocabulary_archive (
    id SERIAL PRIMARY KEY,
    vocabulary_id INTEGER REFERENCES vocabulary(id) ON DELETE SET NULL,
    normalized_expression VARCHAR(255) NOT NULL,
    basic_expression VARCHAR(255) NOT NULL,
    advanced_expression VARCHAR(255) NOT NULL,
    translation_uz TEXT NOT NULL,
    translation_ru TEXT,
    definition_en TEXT NOT NULL,
    basic_example_en TEXT,
    example_en TEXT NOT NULL,
    example_uz TEXT,
    example_ru TEXT,
    usage_context VARCHAR(128) NOT NULL DEFAULT 'Writing Task 2 & Speaking Part 3',
    cefr_level VARCHAR(32) NOT NULL DEFAULT 'B2–C1',
    category VARCHAR(64) NOT NULL DEFAULT 'everyday_upgrade',
    original_generation_date DATE NOT NULL,
    origin_type VARCHAR(48) NOT NULL DEFAULT 'daily_lesson',
    option_a VARCHAR(255) NOT NULL,
    option_b VARCHAR(255) NOT NULL,
    option_c VARCHAR(255) NOT NULL,
    option_d VARCHAR(255) NOT NULL,
    correct_option INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_vocabulary_archive_normalized UNIQUE (normalized_expression),
    CONSTRAINT ck_vocabulary_archive_correct_opt CHECK (correct_option >= 0 AND correct_option <= 3)
);

CREATE INDEX IF NOT EXISTS ix_vocabulary_archive_norm ON vocabulary_archive(normalized_expression);
CREATE INDEX IF NOT EXISTS ix_vocabulary_archive_gen_date ON vocabulary_archive(original_generation_date DESC);
CREATE INDEX IF NOT EXISTS ix_vocabulary_archive_category ON vocabulary_archive(category);

CREATE TABLE IF NOT EXISTS admin_vocab_progress (
    id SERIAL PRIMARY KEY,
    admin_id BIGINT NOT NULL,
    archive_id INTEGER NOT NULL REFERENCES vocabulary_archive(id) ON DELETE CASCADE,
    status VARCHAR(24) NOT NULL DEFAULT 'unmemorized',
    srs_stage INTEGER NOT NULL DEFAULT 0,
    interval_days INTEGER NOT NULL DEFAULT 0,
    next_review_at TIMESTAMPTZ,
    last_reviewed_at TIMESTAMPTZ,
    memorized_at TIMESTAMPTZ,
    review_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    wrong_count INTEGER NOT NULL DEFAULT 0,
    last_quiz_wrong BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_admin_vocab_progress_admin_archive UNIQUE (admin_id, archive_id),
    CONSTRAINT ck_admin_vocab_progress_status CHECK (status IN ('unmemorized', 'memorized', 'difficult', 'later'))
);

CREATE INDEX IF NOT EXISTS ix_admin_vocab_progress_admin_id ON admin_vocab_progress(admin_id);
CREATE INDEX IF NOT EXISTS ix_admin_vocab_progress_status ON admin_vocab_progress(admin_id, status);
CREATE INDEX IF NOT EXISTS ix_admin_vocab_progress_next_review ON admin_vocab_progress(admin_id, next_review_at);

CREATE TABLE IF NOT EXISTS admin_learning_sessions (
    id SERIAL PRIMARY KEY,
    admin_id BIGINT NOT NULL UNIQUE,
    mode VARCHAR(64) NOT NULL DEFAULT 'all',
    filter_meta JSONB,
    archive_ids JSONB NOT NULL,
    current_index INTEGER NOT NULL DEFAULT 0,
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_admin_learning_sessions_admin UNIQUE (admin_id)
);

CREATE INDEX IF NOT EXISTS ix_admin_learning_sessions_admin_id ON admin_learning_sessions(admin_id);

CREATE TABLE IF NOT EXISTS admin_quiz_history (
    id SERIAL PRIMARY KEY,
    admin_id BIGINT NOT NULL,
    question_count INTEGER NOT NULL,
    correct_count INTEGER NOT NULL,
    accuracy INTEGER NOT NULL,
    wrong_archive_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    filter_mode VARCHAR(64) NOT NULL DEFAULT 'all',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_admin_quiz_history_admin_id ON admin_quiz_history(admin_id);

CREATE TABLE IF NOT EXISTS vocabulary_reserve (
    id SERIAL PRIMARY KEY,
    simple_word VARCHAR(255) NOT NULL,
    advanced_word VARCHAR(255) NOT NULL,
    normalized_expression VARCHAR(255) NOT NULL,
    translation_uz TEXT NOT NULL,
    translation_ru TEXT NOT NULL,
    definition_en TEXT NOT NULL,
    basic_example_en TEXT,
    example_en TEXT NOT NULL,
    example_uz TEXT NOT NULL,
    example_ru TEXT NOT NULL,
    cefr_level VARCHAR(32) NOT NULL DEFAULT 'B2–C1',
    category VARCHAR(64) NOT NULL DEFAULT 'everyday_upgrade',
    ielts_usage VARCHAR(128) DEFAULT 'Writing Task 2 & Speaking Part 3',
    source_name VARCHAR(128) NOT NULL DEFAULT 'Cambridge Dictionary',
    source_url TEXT,
    quiz_question_uz TEXT,
    quiz_question_ru TEXT,
    quiz_question_en TEXT,
    option_a VARCHAR(255) NOT NULL,
    option_b VARCHAR(255) NOT NULL,
    option_c VARCHAR(255) NOT NULL,
    option_d VARCHAR(255) NOT NULL,
    correct_option INTEGER NOT NULL DEFAULT 0,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    used_at TIMESTAMPTZ,
    CONSTRAINT uq_vocabulary_reserve_normalized UNIQUE (normalized_expression),
    CONSTRAINT ck_vocabulary_reserve_correct_opt CHECK (correct_option >= 0 AND correct_option <= 3)
);

CREATE INDEX IF NOT EXISTS ix_vocabulary_reserve_unused_cat ON vocabulary_reserve(is_used, category);
CREATE INDEX IF NOT EXISTS ix_vocabulary_reserve_norm ON vocabulary_reserve(normalized_expression);
