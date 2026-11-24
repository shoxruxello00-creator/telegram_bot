-- 005_miniapp_gamification.sql
-- Safe additive migration for Telegram Mini App gamification, journey progress, and game sessions

ALTER TABLE user_settings
    ADD COLUMN IF NOT EXISTS daily_goal INTEGER NOT NULL DEFAULT 10;

CREATE TABLE IF NOT EXISTS user_journey_progress (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    node_id VARCHAR(64) NOT NULL,
    stars INTEGER NOT NULL DEFAULT 0,
    best_score INTEGER NOT NULL DEFAULT 0,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_journey_progress_user_node UNIQUE (user_id, node_id)
);

CREATE INDEX IF NOT EXISTS ix_user_journey_progress_user_id ON user_journey_progress(user_id);

CREATE TABLE IF NOT EXISTS user_game_runs (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    game_mode VARCHAR(64) NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    earned_xp INTEGER NOT NULL DEFAULT 0,
    played_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_user_game_runs_user_id ON user_game_runs(user_id);
