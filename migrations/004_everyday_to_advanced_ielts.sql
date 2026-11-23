-- 004_everyday_to_advanced_ielts.sql
-- Safe additive migration for Everyday -> Advanced English IELTS upgrades (4+2+2+2 distribution)

ALTER TABLE vocabulary
    ALTER COLUMN cefr_level TYPE VARCHAR(32);

ALTER TABLE vocabulary
    ADD COLUMN IF NOT EXISTS basic_example_en TEXT;

ALTER TABLE vocabulary
    ADD COLUMN IF NOT EXISTS ielts_usage VARCHAR(128) DEFAULT 'Writing Task 2 & Speaking Part 3';
