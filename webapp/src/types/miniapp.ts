export type LanguageCode = 'uz' | 'ru' | 'en';
export type ThemeMode = 'dark' | 'light';
export type TabId = 'home' | 'journey' | 'play' | 'ranks' | 'profile';

export type VoxyMood =
  | 'welcome'
  | 'idle'
  | 'blink'
  | 'celebrate'
  | 'encourage'
  | 'complete'
  | 'levelup'
  | 'achievement'
  | 'loading';

export type LeagueId = 'bronze' | 'silver' | 'gold' | 'platinum' | 'diamond' | 'master';

export interface LeagueTier {
  id: LeagueId;
  name: string;
  min_xp: number;
  next_xp: number;
  color: string;
}

export interface LeagueInfo {
  id: LeagueId;
  name: string;
  min_xp: number;
  next_xp: number;
  progress_pct: number;
  all_leagues: LeagueTier[];
}

export interface UserProfile {
  user_id: number;
  username: string;
  full_name: string;
  xp: number;
  streak: number;
  best_streak: number;
  total_quizzes: number;
  total_correct: number;
  total_questions: number;
  accuracy: number;
  learned_count: number;
  language_code: LanguageCode;
  reminders_enabled: boolean;
  broadcast_enabled: boolean;
  daily_goal: number;
  is_admin?: boolean;
  admin_role?: string | null;
  badge: string;
  level: number;
  level_title: string;
  xp_in_level: number;
  xp_for_next_level: number;
  progress_pct: number;
  league: LeagueInfo;
}

export interface VocabularyItem {
  id: number;
  simple_word: string;
  advanced_word: string;
  translation_uz: string;
  translation_ru: string;
  definition_en: string;
  basic_example_en: string;
  example_en: string;
  example_uz: string;
  example_ru: string;
  cefr_level: string;
  category: string;
  ielts_usage: string;
  source_name: string;
  source_url?: string;
  quiz_question_uz?: string;
  quiz_question_ru?: string;
  quiz_question_en?: string;
  options: string[];
  correct_option: number;
  sentence_with_blank?: string;
}

export interface DailyLessonPayload {
  lesson_date: string;
  total_words: number;
  memorized_count: number;
  memorized_ids: number[];
  is_memorized: boolean;
  is_completed: boolean;
  score: number;
  earned_xp: number;
  distribution: {
    everyday_upgrade: number;
    academic_upgrade: number;
    collocation: number;
    phrasal_verb: number;
  };
  words: VocabularyItem[];
}

export interface MissionItem {
  id: string;
  title_en: string;
  title_uz: string;
  title_ru: string;
  current: number;
  target: number;
  xp_reward: number;
  completed: boolean;
}

export interface JourneyNode {
  id: string;
  world_id: string;
  cefr: string;
  index: number;
  type: 'lesson' | 'practice' | 'checkpoint';
  title_en: string;
  title_uz: string;
  title_ru: string;
  status: 'completed' | 'active' | 'locked';
  stars: number;
  max_stars: number;
  xp_reward: number;
  words: VocabularyItem[];
}

export interface JourneyWorld {
  id: string;
  cefr: string;
  title_en: string;
  title_uz: string;
  title_ru: string;
  subtitle_en: string;
  subtitle_uz: string;
  subtitle_ru: string;
  theme_color: string;
  accent: string;
  status: 'completed' | 'active' | 'locked';
  stars: number;
  max_stars: number;
  nodes: JourneyNode[];
}

export interface WeeklyCalendarDay {
  date: string;
  day_name: string;
  day_num: number;
  xp: number;
  words: number;
  quizzes: number;
  active: boolean;
  is_today: boolean;
}

export interface HeatmapDay {
  date: string;
  xp: number;
  intensity: 0 | 1 | 2 | 3;
}

export interface CategoryMasteryItem {
  category: string;
  label: string;
  learned: number;
  total: number;
  percentage: number;
  color: string;
}

export interface AchievementItem {
  id: string;
  icon: string;
  title_en: string;
  title_uz: string;
  title_ru: string;
  desc_en: string;
  desc_uz: string;
  desc_ru: string;
  unlocked: boolean;
  progress: number;
  target: number;
  xp_bonus: number;
}

export interface BootstrapPayload {
  user: UserProfile;
  daily_lesson: DailyLessonPayload;
  missions: {
    daily: MissionItem[];
    weekly: MissionItem[];
  };
  journey: JourneyWorld[];
  weekly_calendar: WeeklyCalendarDay[];
  heatmap_28: HeatmapDay[];
  category_mastery: CategoryMasteryItem[];
  achievements: AchievementItem[];
  words_for_revision: VocabularyItem[];
  learned_words: VocabularyItem[];
  referral_preview: {
    invited: number;
    confirmed: number;
    unlocked_count: number;
    next_target: number;
    next_reward_title: string;
  };
}

export interface LeaderboardEntry {
  rank: number;
  user_id: number;
  username: string;
  full_name: string;
  xp: number;
  weekly_xp: number;
  streak: number;
  referrals: number;
  metric_value: number;
  league_id: LeagueId;
  league_name: string;
  badge: string;
  trend: 'up' | 'down' | 'same';
  is_current_user: boolean;
}

export interface LeaderboardPayload {
  all_time: { entries: LeaderboardEntry[]; user_rank: number };
  weekly: { entries: LeaderboardEntry[]; user_rank: number };
  referrals: { entries: LeaderboardEntry[]; user_rank: number };
}

export interface ReferralMilestone {
  id: number;
  pack_type: string;
  title: string;
  required_referrals: number;
  unlocked: boolean;
  progress: number;
  word_count: number;
  words: VocabularyItem[];
}

export interface ReferralsPayload {
  referral_link: string;
  share_url: string;
  invited: number;
  confirmed: number;
  pending: number;
  unlocked_count: number;
  next_reward_title: string;
  next_reward_target: number;
  milestones: ReferralMilestone[];
}

export type GameModeId =
  | 'word_battle'
  | 'brain_rush'
  | 'word_match'
  | 'missing_word'
  | 'synonym_master'
  | 'ielts_arena'
  | 'memory_challenge'
  | 'daily_challenge';

export interface GameSessionPayload {
  mode: GameModeId;
  time_limit_sec: number;
  opponent?: {
    name: string;
    title: string;
    accuracy_rate: number;
  } | null;
  items: VocabularyItem[];
}

export type AdminFilterMode =
  | 'all'
  | 'unmemorized'
  | 'memorized'
  | 'difficult'
  | 'incorrect'
  | 'today'
  | 'last_7d'
  | 'last_30d'
  | 'srs_due';

export interface AdminArchiveItem {
  id: number;
  normalized_expression: string;
  basic_expression: string;
  advanced_expression: string;
  translation_uz: string;
  translation_ru: string;
  definition_en: string;
  basic_example_en: string;
  example_en: string;
  example_uz: string;
  example_ru: string;
  usage_context: string;
  cefr_level: string;
  category: string;
  original_generation_date: string;
  origin_type: string;
  options: string[];
  correct_option: number;
  admin_status: 'unmemorized' | 'memorized' | 'difficult' | 'later';
  srs_stage: number;
  interval_days: number;
  next_review_at?: string | null;
  review_count: number;
  correct_count: number;
  wrong_count: number;
  last_quiz_wrong: boolean;
  is_revision_due: boolean;
}

export interface AdminStats {
  total_archived: number;
  added_today: number;
  added_this_week: number;
  added_this_month: number;
  memorized_count: number;
  unmemorized_count: number;
  difficult_count: number;
  incorrect_count: number;
  revision_due_count: number;
  quiz_accuracy: number;
  total_quizzes_taken: number;
  completion_percentage: number;
  categories: Record<string, number>;
  dates: Record<string, number>;
  origins: Record<string, number>;
}

export interface AdminSavedSession {
  mode: string;
  archive_ids: number[];
  current_index: number;
  total: number;
  updated_at?: string;
  items?: AdminArchiveItem[];
}

export interface AdminAiMonitoring {
  date: string;
  billing_policy: string;
  paid_apis_blocked: boolean;
  active_model: string;
  ai_temporarily_disabled: boolean;
  ai_disabled_reason?: string | null;
  total_requests_today: number;
  successful_requests_today: number;
  total_tokens_today: number;
  active_model_quota: {
    rpd_used: number;
    rpd_limit: number;
    rpd_remaining: number;
    rpm_used: number;
    rpm_limit: number;
    rpm_remaining: number;
    tpm_used: number;
    tpm_limit: number;
    tpm_remaining: number;
  };
  combined_free_rpd_remaining: number;
  combined_free_rpd_limit: number;
  errors: {
    errors_404: number;
    errors_429: number;
    errors_validation: number;
    errors_other: number;
    last_error?: string | null;
  };
  reserve: {
    unused_count: number;
    target_min: number;
    target_max: number;
    fallbacks_today: number;
    healthy: boolean;
  };
}

export interface AdminLibraryResponse {
  ok: boolean;
  admin_role: string;
  items: AdminArchiveItem[];
  total_filtered: number;
  page: number;
  page_size: number;
  total_pages: number;
  stats: AdminStats;
  saved_session: AdminSavedSession | null;
  ai_monitoring?: AdminAiMonitoring;
}

export interface AdminQuizQuestion {
  archive_id: number;
  basic_expression: string;
  advanced_expression: string;
  translation_uz: string;
  translation_ru: string;
  definition_en: string;
  basic_example_en: string;
  example_en: string;
  usage_context: string;
  cefr_level: string;
  category: string;
  original_generation_date: string;
  options: string[];
  correct_option: number;
}

export interface AdminQuizSubmitResponse {
  ok: boolean;
  question_count: number;
  correct_count: number;
  accuracy: number;
  wrong_archive_ids: number[];
  details: Array<{
    archive_id: number;
    basic_expression: string;
    advanced_expression: string;
    selected_text: string;
    is_correct: boolean;
    translation_uz: string;
    translation_ru: string;
    definition_en: string;
    example_en: string;
  }>;
}

export interface MockTestMaterialItem {
  id: number;
  file_type: string;
  material_role: string;
  title: string;
  telegram_file_id?: string | null;
  file_name?: string | null;
  mime_type?: string | null;
  text_content?: string | null;
  position: number;
}

export interface MockTestItem {
  id: number;
  title: string;
  category: string;
  description: string;
  price_uzs: number;
  price_formatted: string;
  duration_minutes: number;
  questions_count: number;
  instructions: string;
  preview_image_file_id?: string | null;
  is_published: boolean;
  is_active: boolean;
  materials_count?: number;
  material_types?: string[];
  is_unlocked?: boolean;
  access_expires_at?: string | null;
  access_duration_label?: string | null;
  support_username?: string;
  support_url?: string;
  active_users_count?: number;
  files?: MockTestMaterialItem[];
}

export interface MockTestsCatalogResponse {
  ok: boolean;
  categories: string[];
  tests: MockTestItem[];
  my_tests: MockTestItem[];
  support_username: string;
  support_url: string;
}

export interface AdminMockTestHolder {
  user_id: number;
  username: string;
  full_name: string;
  mock_test_id: number;
  test_title: string;
  category: string;
  duration_label: string;
  granted_by: number;
  granted_at: string;
  expires_at?: string | null;
}

export interface AdminMockTestsResponse {
  ok: boolean;
  admin_role: string;
  tests: MockTestItem[];
  holders: AdminMockTestHolder[];
  users: Array<{
    user_id: number;
    username: string;
    full_name: string;
    xp: number;
    streak: number;
  }>;
}
