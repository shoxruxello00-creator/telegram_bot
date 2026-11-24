import {
  BootstrapPayload,
  GameModeId,
  GameSessionPayload,
  LanguageCode,
  LeaderboardPayload,
  ReferralsPayload,
} from '../types/miniapp';
import { getTelegramInitData, getTelegramUser } from './telegram';

function buildHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const initData = getTelegramInitData();
  if (initData) {
    headers['X-Telegram-Init-Data'] = initData;
  }
  const tgUser = getTelegramUser();
  if (tgUser?.id) {
    headers['X-Telegram-User-Id'] = String(tgUser.id);
  }
  return headers;
}

export async function fetchBootstrap(): Promise<BootstrapPayload> {
  const res = await fetch('/api/miniapp/bootstrap', {
    method: 'GET',
    headers: buildHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch bootstrap data (${res.status})`);
  }
  return res.json();
}

export async function submitFlashcardAction(payload: {
  vocabulary_id: number;
  action: 'memorized' | 'review';
  all_memorized?: boolean;
}): Promise<{
  ok: boolean;
  xp_gained: number;
  total_xp: number;
  memorized_count: number;
  is_memorized: boolean;
}> {
  const res = await fetch('/api/miniapp/flashcard/action', {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error('Failed to sync flashcard action');
  }
  return res.json();
}

export async function submitQuizAnswers(payload: {
  mode: 'daily' | 'journey' | 'game' | 'pack';
  node_id?: string;
  game_type?: string;
  answers: Array<{ vocab_id: number; selected_option: number; time_ms: number }>;
}): Promise<{
  ok: boolean;
  score: number;
  total: number;
  accuracy: number;
  max_combo: number;
  combo_bonus: number;
  earned_xp: number;
  total_xp: number;
  streak: number;
  best_streak: number;
  leveled_up: boolean;
  level_info: {
    level: number;
    level_title: string;
    xp_in_level: number;
    xp_for_next_level: number;
    progress_pct: number;
  };
  results: Array<{
    vocab_id: number;
    selected_option: number;
    correct_option: number;
    is_correct: boolean;
    simple_word: string;
    advanced_word: string;
    definition_en: string;
    translation_uz: string;
    translation_ru: string;
  }>;
}> {
  const res = await fetch('/api/miniapp/quiz/submit', {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error('Failed to submit quiz answers');
  }
  return res.json();
}

export async function fetchGameSession(
  mode: GameModeId
): Promise<GameSessionPayload> {
  const res = await fetch(`/api/miniapp/games/session?mode=${encodeURIComponent(mode)}`, {
    method: 'GET',
    headers: buildHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to load game session');
  }
  return res.json();
}

export async function fetchLeaderboard(): Promise<LeaderboardPayload> {
  const res = await fetch('/api/miniapp/leaderboard', {
    method: 'GET',
    headers: buildHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to load leaderboard');
  }
  return res.json();
}

export async function fetchReferrals(): Promise<ReferralsPayload> {
  const res = await fetch('/api/miniapp/referrals', {
    method: 'GET',
    headers: buildHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to load referrals');
  }
  return res.json();
}

export async function updateSettings(payload: {
  language_code?: LanguageCode;
  reminders_enabled?: boolean;
  broadcast_enabled?: boolean;
  daily_goal?: number;
}): Promise<{
  ok: boolean;
  language_code: LanguageCode;
  reminders_enabled: boolean;
  broadcast_enabled: boolean;
  daily_goal: number;
}> {
  const res = await fetch('/api/miniapp/settings', {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error('Failed to update settings');
  }
  return res.json();
}
