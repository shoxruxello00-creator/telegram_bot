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
