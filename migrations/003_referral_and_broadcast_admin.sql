-- 003_referral_and_broadcast_admin.sql
-- Safe additive migration for Referral & Rewards System, Admin Broadcast System, and Multi-Admin System

ALTER TABLE user_settings
    ADD COLUMN IF NOT EXISTS broadcast_enabled BOOLEAN NOT NULL DEFAULT TRUE;

CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    referrer_user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    referred_user_id BIGINT NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    is_suspicious BOOLEAN NOT NULL DEFAULT FALSE,
    suspicion_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ,
    CONSTRAINT uq_referrals_referred_user_id UNIQUE (referred_user_id),
    CONSTRAINT ck_referrals_status CHECK (status IN ('pending', 'confirmed', 'rejected')),
    CONSTRAINT ck_referrals_no_self_referral CHECK (referrer_user_id <> referred_user_id)
);

CREATE INDEX IF NOT EXISTS ix_referrals_referrer_user_id ON referrals(referrer_user_id);
CREATE INDEX IF NOT EXISTS ix_referrals_referred_user_id ON referrals(referred_user_id);
CREATE INDEX IF NOT EXISTS ix_referrals_status ON referrals(status);

CREATE TABLE IF NOT EXISTS referral_rewards (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    reward_type VARCHAR(64) NOT NULL,
    milestone INTEGER NOT NULL,
    unlocked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at TIMESTAMPTZ,
    CONSTRAINT uq_referral_rewards_user_milestone UNIQUE (user_id, milestone)
);

CREATE INDEX IF NOT EXISTS ix_referral_rewards_user_id ON referral_rewards(user_id);

CREATE TABLE IF NOT EXISTS bonus_packs (
    id SERIAL PRIMARY KEY,
    pack_type VARCHAR(64) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    required_referrals INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(32) NOT NULL DEFAULT 'ready',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_bonus_packs_pack_type UNIQUE (pack_type)
);

CREATE INDEX IF NOT EXISTS ix_bonus_packs_pack_type ON bonus_packs(pack_type);
CREATE INDEX IF NOT EXISTS ix_bonus_packs_required_referrals ON bonus_packs(required_referrals);

CREATE TABLE IF NOT EXISTS bonus_pack_words (
    id SERIAL PRIMARY KEY,
    pack_id INTEGER NOT NULL REFERENCES bonus_packs(id) ON DELETE CASCADE,
    vocabulary_id INTEGER NOT NULL REFERENCES vocabulary(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    CONSTRAINT uq_bonus_pack_words_pack_vocab UNIQUE (pack_id, vocabulary_id),
    CONSTRAINT uq_bonus_pack_words_pack_pos UNIQUE (pack_id, position)
);

CREATE INDEX IF NOT EXISTS ix_bonus_pack_words_pack_id ON bonus_pack_words(pack_id);

CREATE TABLE IF NOT EXISTS user_bonus_progress (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    pack_id INTEGER NOT NULL REFERENCES bonus_packs(id) ON DELETE CASCADE,
    completed_words INTEGER NOT NULL DEFAULT 0,
    completed_quizzes INTEGER NOT NULL DEFAULT 0,
    completed_at TIMESTAMPTZ,
    CONSTRAINT uq_user_bonus_progress_user_pack UNIQUE (user_id, pack_id)
);

CREATE INDEX IF NOT EXISTS ix_user_bonus_progress_user_id ON user_bonus_progress(user_id);
CREATE INDEX IF NOT EXISTS ix_user_bonus_progress_pack_id ON user_bonus_progress(pack_id);

CREATE TABLE IF NOT EXISTS admins (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL UNIQUE,
    role VARCHAR(32) NOT NULL DEFAULT 'moderator',
    added_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_admins_telegram_id UNIQUE (telegram_id),
    CONSTRAINT ck_admins_role CHECK (role IN ('super_admin', 'moderator'))
);

CREATE INDEX IF NOT EXISTS ix_admins_telegram_id ON admins(telegram_id);

CREATE TABLE IF NOT EXISTS broadcasts (
    id SERIAL PRIMARY KEY,
    created_by BIGINT NOT NULL,
    source_chat_id BIGINT NOT NULL,
    source_message_id BIGINT NOT NULL,
    message_type VARCHAR(32) NOT NULL DEFAULT 'text',
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    total_recipients INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    CONSTRAINT ck_broadcasts_status CHECK (status IN ('pending', 'running', 'completed', 'cancelled', 'failed'))
);

CREATE INDEX IF NOT EXISTS ix_broadcasts_status ON broadcasts(status);
CREATE INDEX IF NOT EXISTS ix_broadcasts_created_by ON broadcasts(created_by);

CREATE TABLE IF NOT EXISTS broadcast_recipients (
    id SERIAL PRIMARY KEY,
    broadcast_id INTEGER NOT NULL REFERENCES broadcasts(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    sent_at TIMESTAMPTZ,
    CONSTRAINT uq_broadcast_recipients_broadcast_user UNIQUE (broadcast_id, user_id),
    CONSTRAINT ck_broadcast_recipients_status CHECK (status IN ('pending', 'sent', 'failed', 'skipped'))
);

CREATE INDEX IF NOT EXISTS ix_broadcast_recipients_broadcast_id ON broadcast_recipients(broadcast_id);
CREATE INDEX IF NOT EXISTS ix_broadcast_recipients_user_id ON broadcast_recipients(user_id);
CREATE INDEX IF NOT EXISTS ix_broadcast_recipients_status ON broadcast_recipients(status);
