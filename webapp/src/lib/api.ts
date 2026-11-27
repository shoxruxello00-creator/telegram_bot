import {
  AdminArchiveItem,
  AdminLibraryResponse,
  AdminQuizQuestion,
  AdminQuizSubmitResponse,
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

export async function fetchAdminLibrary(params: {
  mode?: string;
  q?: string;
  category?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}): Promise<AdminLibraryResponse> {
  const qs = new URLSearchParams();
  if (params.mode) qs.set('mode', params.mode);
  if (params.q) qs.set('q', params.q);
  if (params.category) qs.set('category', params.category);
  if (params.date_from) qs.set('date_from', params.date_from);
  if (params.date_to) qs.set('date_to', params.date_to);
  if (params.page) qs.set('page', String(params.page));
  if (params.page_size) qs.set('page_size', String(params.page_size));

  const res = await fetch(`/api/miniapp/admin/library?${qs.toString()}`, {
    method: 'GET',
    headers: buildHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Admin authorization required (${res.status})`);
  }
  return res.json();
}

export async function startAdminSession(payload: {
  mode: string;
  session_size: string;
  q?: string;
  category?: string;
  date_from?: string;
  date_to?: string;
}): Promise<{
  ok: boolean;
  session: { mode: string; archive_ids: number[]; current_index: number; total: number };
  items: AdminArchiveItem[];
}> {
  const res = await fetch('/api/miniapp/admin/session', {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error('Failed to start admin learning session');
  }
  return res.json();
}

export async function submitAdminFlashcard(payload: {
  action: 'memorized' | 'difficult' | 'later' | 'nav';
  archive_id?: number;
  session_index?: number;
  mode?: string;
  archive_ids?: number[];
}): Promise<{
  ok: boolean;
  status?: string;
  interval_days?: number;
}> {
  const res = await fetch('/api/miniapp/admin/flashcard', {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error('Failed to save admin flashcard progress');
  }
  return res.json();
}

export async function fetchAdminQuiz(params: {
  mode?: string;
  count?: number;
  retry_ids?: number[];
  q?: string;
  category?: string;
  date_from?: string;
  date_to?: string;
}): Promise<{
  ok: boolean;
  questions: AdminQuizQuestion[];
  total: number;
}> {
  const qs = new URLSearchParams();
  if (params.retry_ids && params.retry_ids.length > 0) {
    qs.set('retry_ids', params.retry_ids.join(','));
  } else {
    if (params.mode) qs.set('mode', params.mode);
    if (params.count) qs.set('count', String(params.count));
    if (params.q) qs.set('q', params.q);
    if (params.category) qs.set('category', params.category);
    if (params.date_from) qs.set('date_from', params.date_from);
    if (params.date_to) qs.set('date_to', params.date_to);
  }

  const res = await fetch(`/api/miniapp/admin/quiz?${qs.toString()}`, {
    method: 'GET',
    headers: buildHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to generate admin quiz');
  }
  return res.json();
}

export async function submitAdminQuiz(payload: {
  mode: string;
  submissions: Array<{ archive_id: number; selected_text: string }>;
}): Promise<AdminQuizSubmitResponse> {
  const res = await fetch('/api/miniapp/admin/quiz/submit', {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error('Failed to submit admin quiz');
  }
  return res.json();
}

export async function downloadAdminExport(params: {
  format: 'csv' | 'xlsx' | 'pdf';
  scope: 'all' | 'filtered';
  mode?: string;
  q?: string;
  category?: string;
  date_from?: string;
  date_to?: string;
}): Promise<void> {
  const qs = new URLSearchParams();
  qs.set('format', params.format);
  qs.set('scope', params.scope);
  if (params.mode) qs.set('mode', params.mode);
  if (params.q) qs.set('q', params.q);
  if (params.category) qs.set('category', params.category);
  if (params.date_from) qs.set('date_from', params.date_from);
  if (params.date_to) qs.set('date_to', params.date_to);

  const res = await fetch(`/api/miniapp/admin/export?${qs.toString()}`, {
    method: 'GET',
    headers: buildHeaders(),
  });
  if (!res.ok) {
    throw new Error('Export failed');
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `shoxrux_ai_vocabulary.${params.format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
}
