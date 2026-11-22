-- 002_multilingual_ai_update.sql
-- Multilingual user settings, strictly unique vocabulary, daily lessons, and AI generation logs

CREATE TABLE IF NOT EXISTS vocabulary (
    id SERIAL PRIMARY KEY,
    simple_word VARCHAR(255) NOT NULL,
    advanced_word VARCHAR(255) NOT NULL,
    normalized_expression VARCHAR(255) NOT NULL,
    translation_uz TEXT NOT NULL,
    translation_ru TEXT NOT NULL,
    definition_en TEXT NOT NULL,
    example_en TEXT NOT NULL,
    example_uz TEXT NOT NULL,
    example_ru TEXT NOT NULL,
    cefr_level VARCHAR(10) NOT NULL DEFAULT 'C1',
    category VARCHAR(64) NOT NULL DEFAULT 'idiom',
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_vocabulary_normalized_expression UNIQUE (normalized_expression),
    CONSTRAINT ck_vocabulary_correct_option CHECK (correct_option >= 0 AND correct_option <= 3)
);

CREATE INDEX IF NOT EXISTS ix_vocabulary_normalized_expression ON vocabulary(normalized_expression);

CREATE TABLE IF NOT EXISTS user_settings (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    language_code VARCHAR(5) NOT NULL DEFAULT 'uz',
    reminders_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_user_settings_language_code CHECK (language_code IN ('uz', 'ru', 'en'))
);

CREATE INDEX IF NOT EXISTS ix_user_settings_user_id ON user_settings(user_id);

CREATE TABLE IF NOT EXISTS daily_lessons (
    id SERIAL PRIMARY KEY,
    lesson_date DATE NOT NULL,
    vocabulary_ids JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_daily_lessons_lesson_date UNIQUE (lesson_date)
);

CREATE INDEX IF NOT EXISTS ix_daily_lessons_lesson_date ON daily_lessons(lesson_date);

CREATE TABLE IF NOT EXISTS daily_lesson_items (
    id SERIAL PRIMARY KEY,
    lesson_id INTEGER NOT NULL REFERENCES daily_lessons(id) ON DELETE CASCADE,
    vocabulary_id INTEGER NOT NULL REFERENCES vocabulary(id) ON DELETE RESTRICT,
    position INTEGER NOT NULL,
    CONSTRAINT uq_daily_lesson_items_vocabulary_id UNIQUE (vocabulary_id),
    CONSTRAINT uq_daily_lesson_items_lesson_pos UNIQUE (lesson_id, position)
);

CREATE TABLE IF NOT EXISTS user_daily_progress (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    lesson_date DATE NOT NULL,
    is_memorized BOOLEAN NOT NULL DEFAULT FALSE,
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    score INTEGER NOT NULL DEFAULT 0,
    earned_xp INTEGER NOT NULL DEFAULT 0,
    memorized_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    CONSTRAINT uq_user_daily_progress_user_date UNIQUE (user_id, lesson_date)
);

CREATE INDEX IF NOT EXISTS ix_user_daily_progress_user_date ON user_daily_progress(user_id, lesson_date);

CREATE TABLE IF NOT EXISTS user_learned_words (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    vocabulary_id INTEGER NOT NULL REFERENCES vocabulary(id) ON DELETE CASCADE,
    learned_date DATE NOT NULL,
    is_correct_in_quiz BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_learned_words_user_vocab UNIQUE (user_id, vocabulary_id)
);

CREATE INDEX IF NOT EXISTS ix_user_learned_words_user_id ON user_learned_words(user_id);

CREATE TABLE IF NOT EXISTS generation_logs (
    id SERIAL PRIMARY KEY,
    lesson_date DATE NOT NULL,
    generation_status VARCHAR(32) NOT NULL,
    generated_count INTEGER NOT NULL DEFAULT 0,
    rejected_duplicates INTEGER NOT NULL DEFAULT 0,
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_generation_logs_lesson_date ON generation_logs(lesson_date);
