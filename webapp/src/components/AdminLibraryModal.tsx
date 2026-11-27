import React, { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import confetti from 'canvas-confetti';
import { AnimatePresence, motion } from 'framer-motion';
import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  Brain,
  Calendar,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Download,
  FileSpreadsheet,
  FileText,
  Filter,
  HelpCircle,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  Sparkles,
  Volume2,
  X,
} from 'lucide-react';
import {
  downloadAdminExport,
  fetchAdminLibrary,
  fetchAdminQuiz,
  startAdminSession,
  submitAdminFlashcard,
  submitAdminQuiz,
} from '../lib/api';
import { t } from '../lib/i18n';
import {
  hapticImpact,
  hapticNotification,
  hapticSelection,
  speakEnglishExpression,
} from '../lib/telegram';
import { useAppStore } from '../store/useAppStore';
import {
  AdminArchiveItem,
  AdminQuizQuestion,
  AdminQuizSubmitResponse,
  LanguageCode,
} from '../types/miniapp';

type AdminSubTab = 'browse' | 'memorize' | 'quiz' | 'revision' | 'stats';

const LOCAL_LABELS: Record<LanguageCode, Record<string, string>> = {
  uz: {
    archived_total: 'Jami Arxiv So‘zlari',
    added_today: 'Bugun',
    added_week: 'Shu hafta',
    added_month: 'Shu oy',
    memorized: 'Yodlangan',
    unmemorized: 'Yodlanmagan',
    difficult: 'Qiyin',
    revision_due: 'Takrorlash kerak',
    completion: 'O‘zlashtirish',
    quiz_acc: 'Test aniqligi',
    resume_session: 'Oxirgi sessiyani davom ettirish',
    session_size: 'Sessiya hajmi',
    start_flashcards: '3D Flashcard sessiyasini boshlash',
    mode_all: 'Barcha so‘zlar',
    mode_unmemorized: 'Yodlanmagan so‘zlar',
    mode_memorized: 'Yodlangan so‘zlar',
    mode_difficult: 'Qiyin so‘zlar',
    mode_incorrect: 'Testda xato qilinganlar',
    mode_today: 'Bugungi so‘zlar',
    mode_last_7d: 'Oxirgi 7 kun',
    mode_last_30d: 'Oxirgi 30 kun',
    mode_srs_due: 'Takrorlash vaqti kelganlar',
    custom_dates: 'Maxsus sana oralig‘i',
    all_categories: 'Barcha turkumlar',
    quiz_pool: 'Test uchun so‘zlar manbasi',
    quiz_count: 'Savollar soni',
    custom_count: 'Maxsus son',
    start_quiz: 'ABCD Testni boshlash',
    retry_wrong: 'Xatolarni qayta ishlash',
    wrong_review: 'Xato javoblar tahlili',
    export_title: 'Eksport qilish (CSV • XLSX • PDF)',
    export_all: 'Barcha arxivni yuklab olish',
    export_filtered: 'Joriy filtr natijasini yuklab olish',
    srs_title: 'Aqlli Takrorlash (Spaced Repetition)',
    srs_desc: 'Intervallar: 1 kun • 3 kun • 7 kun • 14 kun • 30 kun. Qiyin va xato qilingan so‘zlar birinchi chiqadi.',
    tap_flip: 'Kartani aylantirish uchun bosing',
  },
  ru: {
    archived_total: 'Всего слов в архиве',
    added_today: 'Сегодня',
    added_week: 'За неделю',
    added_month: 'За месяц',
    memorized: 'Выучено',
    unmemorized: 'Не выучено',
    difficult: 'Сложные',
    revision_due: 'К повторению',
    completion: 'Прогресс',
    quiz_acc: 'Точность тестов',
    resume_session: 'Продолжить прошлую сессию',
    session_size: 'Размер сессии',
    start_flashcards: 'Начать 3D карточки',
    mode_all: 'Все слова',
    mode_unmemorized: 'Невыученные слова',
    mode_memorized: 'Выученные слова',
    mode_difficult: 'Сложные слова',
    mode_incorrect: 'Ошибки в тестах',
    mode_today: 'Слова за сегодня',
    mode_last_7d: 'Последние 7 дней',
    mode_last_30d: 'Последние 30 дней',
    mode_srs_due: 'Пора повторить (SRS)',
    custom_dates: 'Произвольный период дат',
    all_categories: 'Все категории',
    quiz_pool: 'Источник слов для теста',
    quiz_count: 'Количество вопросов',
    custom_count: 'Своё число',
    start_quiz: 'Начать ABCD тест',
    retry_wrong: 'Повторить ошибки',
    wrong_review: 'Разбор неверных ответов',
    export_title: 'Экспорт словаря (CSV • XLSX • PDF)',
    export_all: 'Скачать весь архив',
    export_filtered: 'Скачать текущий фильтр',
    srs_title: 'Умное интервальное повторение (SRS)',
    srs_desc: 'Интервалы: 1 дн • 3 дн • 7 дн • 14 дн • 30 дн. Приоритет сложным словам и ошибкам.',
    tap_flip: 'Нажмите на карточку для переворота',
  },
  en: {
    archived_total: 'Total Archived Words',
    added_today: 'Today',
    added_week: 'This Week',
    added_month: 'This Month',
    memorized: 'Memorized',
    unmemorized: 'Unmemorized',
    difficult: 'Difficult',
    revision_due: 'Due for Revision',
    completion: 'Completion',
    quiz_acc: 'Quiz Accuracy',
    resume_session: 'Resume Interrupted Session',
    session_size: 'Session Size',
    start_flashcards: 'Start 3D Flashcards Session',
    mode_all: 'All Vocabulary',
    mode_unmemorized: 'Unmemorized Vocabulary',
    mode_memorized: 'Previously Memorized',
    mode_difficult: 'Difficult Vocabulary',
    mode_incorrect: 'Incorrectly Answered',
    mode_today: "Today's Vocabulary",
    mode_last_7d: 'Last 7 Days',
    mode_last_30d: 'Last 30 Days',
    mode_srs_due: 'Due for Revision (SRS)',
    custom_dates: 'Custom Date Range',
    all_categories: 'All Categories',
    quiz_pool: 'Vocabulary Source Pool',
    quiz_count: 'Question Count',
    custom_count: 'Custom',
    start_quiz: 'Start Interactive ABCD Quiz',
    retry_wrong: 'Retry Incorrect Answers',
    wrong_review: 'Incorrect Answer Review',
    export_title: 'Export Vocabulary (CSV • XLSX • PDF)',
    export_all: 'Export Full Archive',
    export_filtered: 'Export Filtered Selection',
    srs_title: 'Smart Spaced Repetition (SRS)',
    srs_desc: 'Intervals: 1d • 3d • 7d • 14d • 30d. Prioritizes difficult & missed expressions.',
    tap_flip: 'Tap card to flip • Swipe left/right',
  },
};

const ProgressRing: React.FC<{
  percentage: number;
  color: string;
  label: string;
  sub: string;
}> = ({ percentage, color, label, sub }) => {
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.min(100, Math.max(0, percentage));
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div className="bg-voxy-card/90 border border-voxy-border rounded-2xl p-2.5 flex items-center gap-2.5">
      <div className="relative w-14 h-14 flex items-center justify-center shrink-0">
        <svg className="w-14 h-14 -rotate-90" viewBox="0 0 64 64">
          <circle
            cx="32"
            cy="32"
            r={radius}
            stroke="currentColor"
            strokeWidth="5"
            fill="transparent"
            className="text-voxy-secondary"
          />
          <motion.circle
            cx="32"
            cy="32"
            r={radius}
            stroke={color}
            strokeWidth="5"
            strokeLinecap="round"
            fill="transparent"
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
            style={{ strokeDasharray: circumference }}
          />
        </svg>
        <span className="absolute text-[11px] font-extrabold text-voxy-text">
          {Math.round(clamped)}%
        </span>
      </div>
      <div className="min-w-0">
        <div className="text-xs font-bold text-voxy-text truncate">{label}</div>
        <div className="text-[10px] text-voxy-muted truncate">{sub}</div>
      </div>
    </div>
  );
};

export const AdminLibraryModal: React.FC = () => {
  const queryClient = useQueryClient();
  const { lang, closeModal } = useAppStore();
  const L = LOCAL_LABELS[lang] || LOCAL_LABELS.uz;

  const [subTab, setSubTab] = useState<AdminSubTab>('browse');
  const [filterMode, setFilterMode] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [category, setCategory] = useState<string>('');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [showFilters, setShowFilters] = useState<boolean>(false);

  // Animated counter state
  const [animatedTotal, setAnimatedTotal] = useState<number>(0);

  // Flashcard session state
  const [sessionSize, setSessionSize] = useState<string>('10');
  const [fcDeck, setFcDeck] = useState<AdminArchiveItem[]>([]);
  const [fcIndex, setFcIndex] = useState<number>(0);
  const [fcFlipped, setFcFlipped] = useState<boolean>(false);
  const [fcActiveMode, setFcActiveMode] = useState<string>('all');
  const [fcCompletedBanner, setFcCompletedBanner] = useState<boolean>(false);
  const [busyAction, setBusyAction] = useState<boolean>(false);

  // Quiz state
  const [quizPoolMode, setQuizPoolMode] = useState<string>('all');
  const [quizCountChoice, setQuizCountChoice] = useState<string>('10');
  const [customQuizCount, setCustomQuizCount] = useState<string>('25');
  const [quizQuestions, setQuizQuestions] = useState<AdminQuizQuestion[]>([]);
  const [quizIdx, setQuizIdx] = useState<number>(0);
  const [quizSelectedIdx, setQuizSelectedIdx] = useState<number | null>(null);
  const [quizSubmissions, setQuizSubmissions] = useState<
    Array<{ archive_id: number; selected_text: string }>
  >([]);
  const [quizResult, setQuizResult] = useState<AdminQuizSubmitResponse | null>(
    null
  );
  const [exportStatus, setExportStatus] = useState<string>('');

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: [
      'admin_library',
      filterMode,
      searchQuery,
      category,
      dateFrom,
      dateTo,
      page,
    ],
    queryFn: () =>
      fetchAdminLibrary({
        mode: filterMode,
        q: searchQuery,
        category,
        date_from: dateFrom,
        date_to: dateTo,
        page,
        page_size: 15,
      }),
  });

  // Smooth animated vocabulary counter
  useEffect(() => {
    const target = data?.stats?.total_archived ?? 0;
    if (target <= 0) {
      setAnimatedTotal(0);
      return;
    }
    let current = 0;
    const step = Math.max(1, Math.ceil(target / 24));
    const timer = window.setInterval(() => {
      current += step;
      if (current >= target) {
        setAnimatedTotal(target);
        window.clearInterval(timer);
      } else {
        setAnimatedTotal(current);
      }
    }, 22);
    return () => window.clearInterval(timer);
  }, [data?.stats?.total_archived]);

  const refreshLibrary = () => {
    queryClient.invalidateQueries({ queryKey: ['admin_library'] });
  };

  // Start a new Flashcard Session
  const handleStartSession = async (overrideMode?: string) => {
    const targetMode = overrideMode || filterMode;
    setBusyAction(true);
    hapticImpact('medium');
    try {
      const res = await startAdminSession({
        mode: targetMode,
        session_size: sessionSize,
        q: searchQuery,
        category,
        date_from: dateFrom,
        date_to: dateTo,
      });
      if (res.items.length > 0) {
        setFcDeck(res.items);
        setFcIndex(0);
        setFcFlipped(false);
        setFcActiveMode(targetMode);
        setFcCompletedBanner(false);
        setSubTab('memorize');
      }
      refreshLibrary();
    } finally {
      setBusyAction(false);
    }
  };

  // Resume interrupted session
  const handleResumeSession = () => {
    const saved = data?.saved_session;
    if (!saved?.items || saved.items.length === 0) return;
    hapticImpact('medium');
    setFcDeck(saved.items);
    setFcIndex(Math.min(saved.current_index, saved.items.length - 1));
    setFcFlipped(false);
    setFcActiveMode(saved.mode);
    setFcCompletedBanner(false);
    setSubTab('memorize');
  };

  // Handle YODLADIM | QIYIN | KEYINROQ
  const handleCardDecision = async (
    action: 'memorized' | 'difficult' | 'later'
  ) => {
    const currentCard = fcDeck[fcIndex];
    if (!currentCard || busyAction) return;
    setBusyAction(true);
    if (action === 'memorized') {
      hapticNotification('success');
    } else {
      hapticImpact('light');
    }

    try {
      await submitAdminFlashcard({
        action,
        archive_id: currentCard.id,
        session_index: fcIndex,
      });
      refreshLibrary();

      if (fcIndex >= fcDeck.length - 1) {
        setFcCompletedBanner(true);
        confetti({ particleCount: 70, spread: 65, origin: { y: 0.65 } });
      } else {
        setFcFlipped(false);
        setFcIndex((prev) => prev + 1);
      }
    } finally {
      setBusyAction(false);
    }
  };

  // Handle OLDINGI SO'Z / KEYINGI SO'Z
  const handleCardNav = async (delta: -1 | 1) => {
    if (fcDeck.length === 0) return;
    const nextIdx = Math.max(0, Math.min(fcDeck.length - 1, fcIndex + delta));
    if (nextIdx === fcIndex) return;
    hapticSelection();
    setFcFlipped(false);
    setFcIndex(nextIdx);
    try {
      await submitAdminFlashcard({
        action: 'nav',
        session_index: nextIdx,
        mode: fcActiveMode,
        archive_ids: fcDeck.map((x) => x.id),
      });
    } catch {
      // keep navigation instant
    }
  };

  // Start ABCD Quiz
  const handleStartQuiz = async (retryIds?: number[]) => {
    setBusyAction(true);
    hapticImpact('medium');
    try {
      const countNum =
        quizCountChoice === 'custom'
          ? Math.max(1, parseInt(customQuizCount || '10', 10) || 10)
          : parseInt(quizCountChoice, 10);

      const res = await fetchAdminQuiz(
        retryIds && retryIds.length > 0
          ? { retry_ids: retryIds }
          : {
              mode: quizPoolMode,
              count: countNum,
              q: searchQuery,
              category,
              date_from: dateFrom,
              date_to: dateTo,
            }
      );
      if (res.questions.length > 0) {
        setQuizQuestions(res.questions);
        setQuizIdx(0);
        setQuizSelectedIdx(null);
        setQuizSubmissions([]);
        setQuizResult(null);
        setSubTab('quiz');
      }
    } finally {
      setBusyAction(false);
    }
  };

  const handleSelectQuizOption = (optIndex: number) => {
    if (quizSelectedIdx !== null) return;
    const q = quizQuestions[quizIdx];
    if (!q) return;

    setQuizSelectedIdx(optIndex);
    const chosenText = q.options[optIndex];
    const isCorrect = optIndex === q.correct_option;
    if (isCorrect) {
      hapticNotification('success');
    } else {
      hapticNotification('error');
    }

    setQuizSubmissions((prev) => [
      ...prev,
      { archive_id: q.archive_id, selected_text: chosenText },
    ]);
  };

  const handleNextOrFinishQuiz = async () => {
    if (quizIdx < quizQuestions.length - 1) {
      hapticSelection();
      setQuizIdx((prev) => prev + 1);
      setQuizSelectedIdx(null);
      return;
    }
    setBusyAction(true);
    try {
      const res = await submitAdminQuiz({
        mode: quizPoolMode,
        submissions: quizSubmissions,
      });
      setQuizResult(res);
      setQuizQuestions([]);
      refreshLibrary();
      if (res.accuracy >= 70) {
        confetti({ particleCount: 85, spread: 70, origin: { y: 0.6 } });
      }
    } finally {
      setBusyAction(false);
    }
  };

  const handleExport = async (
    format: 'csv' | 'xlsx' | 'pdf',
    scope: 'all' | 'filtered'
  ) => {
    hapticImpact('medium');
    setExportStatus(`⏳ ${format.toUpperCase()}...`);
    try {
      await downloadAdminExport({
        format,
        scope,
        mode: filterMode,
        q: searchQuery,
        category,
        date_from: dateFrom,
        date_to: dateTo,
      });
      setExportStatus(`✅ ${format.toUpperCase()} downloaded!`);
      setTimeout(() => setExportStatus(''), 2500);
    } catch {
      setExportStatus('⚠️ Export failed');
    }
  };

  const stats = data?.stats;
  const activeCard = fcDeck[fcIndex];
  const activeQuizQ = quizQuestions[quizIdx];

  const modeOptions = [
    { id: 'all', label: L.mode_all, count: stats?.total_archived ?? 0 },
    { id: 'unmemorized', label: L.mode_unmemorized, count: stats?.unmemorized_count ?? 0 },
    { id: 'memorized', label: L.mode_memorized, count: stats?.memorized_count ?? 0 },
    { id: 'difficult', label: L.mode_difficult, count: stats?.difficult_count ?? 0 },
    { id: 'incorrect', label: L.mode_incorrect, count: stats?.incorrect_count ?? 0 },
    { id: 'today', label: L.mode_today, count: stats?.added_today ?? 0 },
    { id: 'last_7d', label: L.mode_last_7d, count: stats?.added_this_week ?? 0 },
    { id: 'last_30d', label: L.mode_last_30d, count: stats?.added_this_month ?? 0 },
    { id: 'srs_due', label: L.mode_srs_due, count: stats?.revision_due_count ?? 0 },
  ];

  return (
    <div className="fixed inset-0 z-50 bg-voxy-bg/98 backdrop-blur-xl flex flex-col overflow-hidden">
      {/* Top Sticky Bar */}
      <div className="px-4 pt-3.5 pb-3 border-b border-voxy-border bg-voxy-secondary/90 flex items-center justify-between gap-2 shrink-0">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-voxy-gold/20 text-voxy-gold border border-voxy-gold/40">
              👑 ADMIN ARCHIVE
            </span>
            {stats && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-voxy-green/15 text-voxy-green border border-voxy-green/30">
                +{stats.added_today} {L.added_today}
              </span>
            )}
          </div>
          <h2 className="text-sm sm:text-base font-display font-bold text-voxy-text truncate mt-1">
            {t(lang, 'admin_lib_btn')}
          </h2>
        </div>

        <button
          type="button"
          onClick={() => {
            hapticImpact('light');
            closeModal();
          }}
          className="p-2 rounded-2xl bg-voxy-card border border-voxy-border text-voxy-muted hover:text-voxy-text"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Sub-Navigation Pills */}
      <div className="px-3.5 py-2.5 bg-voxy-bg border-b border-voxy-border flex items-center gap-1.5 overflow-x-auto shrink-0">
        {(
          [
            { id: 'browse', label: t(lang, 'admin_tab_all'), Icon: BookOpen },
            { id: 'memorize', label: t(lang, 'admin_tab_memorize'), Icon: Brain },
            { id: 'quiz', label: t(lang, 'admin_tab_quiz'), Icon: HelpCircle },
            { id: 'revision', label: t(lang, 'admin_tab_revision'), Icon: RefreshCw },
            { id: 'stats', label: t(lang, 'admin_tab_stats'), Icon: BarChart3 },
          ] as const
        ).map(({ id, label, Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => {
              hapticSelection();
              setSubTab(id);
            }}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1.5 whitespace-nowrap transition-all ${
              subTab === id
                ? 'bg-gradient-to-r from-voxy-purple to-indigo-600 text-white shadow'
                : 'bg-voxy-card border border-voxy-border text-voxy-muted hover:text-voxy-text'
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Scrollable Content Area */}
      <div className="flex-1 overflow-y-auto px-3.5 py-3.5 max-w-md w-full mx-auto space-y-3.5 pb-12">
        {isLoading && !data && (
          <div className="py-16 text-center text-xs text-voxy-muted">
            Synchronizing permanent vocabulary archive...
          </div>
        )}

        {isError && (
          <div className="bg-rose-500/15 border border-rose-500/40 rounded-3xl p-5 text-center space-y-3">
            <AlertTriangle className="w-8 h-8 text-rose-400 mx-auto" />
            <p className="text-xs font-bold text-voxy-text">
              Admin authorization required or connection interrupted.
            </p>
            <button
              type="button"
              onClick={() => refetch()}
              className="px-4 py-2 rounded-xl bg-voxy-purple text-white text-xs font-bold"
            >
              Retry
            </button>
          </div>
        )}

        {data && stats && (
          <>
            {/* Hero Counter & Progress Rings */}
            <div className="bg-gradient-to-br from-[#1E1B4B] via-[#19243D] to-[#0F172A] border border-voxy-purple/40 rounded-3xl p-4 shadow-purpleGlow space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-[11px] text-slate-300 font-semibold">
                    {L.archived_total}
                  </div>
                  <div className="text-2xl sm:text-3xl font-display font-extrabold text-white tracking-tight flex items-baseline gap-2">
                    <span>{animatedTotal.toLocaleString()}</span>
                    <span className="text-xs font-bold text-voxy-green">
                      +{stats.added_this_week} {L.added_week}
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-white/10 text-voxy-gold text-[11px] font-bold">
                    <Sparkles className="w-3.5 h-3.5" />
                    Auto-Sync Active
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <ProgressRing
                  percentage={stats.completion_percentage}
                  color="#34D399"
                  label={L.completion}
                  sub={`${stats.memorized_count}/${stats.total_archived}`}
                />
                <ProgressRing
                  percentage={stats.quiz_accuracy}
                  color="#38BDF8"
                  label={L.quiz_acc}
                  sub={`${stats.revision_due_count} SRS`}
                />
              </div>

              {data.saved_session && fcDeck.length === 0 && (
                <button
                  type="button"
                  onClick={handleResumeSession}
                  className="w-full py-2.5 px-3.5 rounded-2xl bg-voxy-gold text-slate-950 font-extrabold text-xs flex items-center justify-between shadow"
                >
                  <span className="flex items-center gap-2">
                    <Play className="w-4 h-4 fill-current" />
                    {L.resume_session}
                  </span>
                  <span>
                    {Math.min(
                      data.saved_session.current_index + 1,
                      data.saved_session.total
                    )}
                    /{data.saved_session.total}
                  </span>
                </button>
              )}
            </div>

            {/* ============================================================ */}
            {/* TAB 1: BROWSE, SEARCH, CATEGORY & DATE FILTERS               */}
            {/* ============================================================ */}
            {subTab === 'browse' && (
              <div className="space-y-3">
                {/* Search Bar + Filter Toggle */}
                <div className="flex items-center gap-2">
                  <div className="relative flex-1">
                    <Search className="w-4 h-4 text-voxy-muted absolute left-3.5 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => {
                        setSearchQuery(e.target.value);
                        setPage(1);
                      }}
                      placeholder={t(lang, 'admin_search_placeholder')}
                      className="w-full pl-9 pr-8 py-2.5 rounded-2xl bg-voxy-card border border-voxy-border text-xs text-voxy-text placeholder:text-voxy-muted focus:outline-none focus:border-voxy-purple"
                    />
                    {searchQuery && (
                      <button
                        type="button"
                        onClick={() => {
                          setSearchQuery('');
                          setPage(1);
                        }}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-voxy-muted"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowFilters((v) => !v)}
                    className={`p-2.5 rounded-2xl border ${
                      showFilters || category || dateFrom || dateTo
                        ? 'bg-voxy-purple text-white border-voxy-purple'
                        : 'bg-voxy-card border-voxy-border text-voxy-muted'
                    }`}
                  >
                    <Filter className="w-4 h-4" />
                  </button>
                </div>

                {/* Mode Filter Chips */}
                <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
                  {modeOptions.map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => {
                        hapticSelection();
                        setFilterMode(m.id);
                        setPage(1);
                      }}
                      className={`px-2.5 py-1.5 rounded-xl text-[11px] font-bold whitespace-nowrap border ${
                        filterMode === m.id
                          ? 'bg-voxy-purple/25 border-voxy-purple text-voxy-blue'
                          : 'bg-voxy-card border-voxy-border text-voxy-muted'
                      }`}
                    >
                      {m.label} ({m.count})
                    </button>
                  ))}
                </div>

                {/* Expandable Category & Custom Date Range Drawer */}
                {showFilters && (
                  <div className="bg-voxy-card border border-voxy-border rounded-2xl p-3 space-y-2.5">
                    <div>
                      <label className="text-[10px] font-bold text-voxy-muted uppercase">
                        Category
                      </label>
                      <div className="flex flex-wrap gap-1.5 mt-1">
                        <button
                          type="button"
                          onClick={() => {
                            setCategory('');
                            setPage(1);
                          }}
                          className={`px-2.5 py-1 rounded-lg text-[11px] font-bold ${
                            !category
                              ? 'bg-voxy-purple text-white'
                              : 'bg-voxy-secondary text-voxy-muted'
                          }`}
                        >
                          {L.all_categories}
                        </button>
                        {Object.entries(stats.categories).map(([cat, cnt]) => (
                          <button
                            key={cat}
                            type="button"
                            onClick={() => {
                              setCategory(cat);
                              setPage(1);
                            }}
                            className={`px-2.5 py-1 rounded-lg text-[11px] font-bold ${
                              category === cat
                                ? 'bg-voxy-purple text-white'
                                : 'bg-voxy-secondary text-voxy-muted'
                            }`}
                          >
                            {cat} ({cnt})
                          </button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <label className="text-[10px] font-bold text-voxy-muted uppercase flex items-center gap-1">
                        <Calendar className="w-3 h-3" /> {L.custom_dates}
                      </label>
                      <div className="grid grid-cols-2 gap-2 mt-1">
                        <input
                          type="date"
                          value={dateFrom}
                          onChange={(e) => {
                            setDateFrom(e.target.value);
                            setPage(1);
                          }}
                          className="px-2.5 py-1.5 rounded-xl bg-voxy-secondary border border-voxy-border text-xs text-voxy-text"
                        />
                        <input
                          type="date"
                          value={dateTo}
                          onChange={(e) => {
                            setDateTo(e.target.value);
                            setPage(1);
                          }}
                          className="px-2.5 py-1.5 rounded-xl bg-voxy-secondary border border-voxy-border text-xs text-voxy-text"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Quick Study Action Bar for Filtered Results */}
                {data.total_filtered > 0 && (
                  <div className="flex items-center justify-between bg-voxy-secondary/80 border border-voxy-border rounded-2xl px-3 py-2">
                    <span className="text-[11px] font-bold text-voxy-muted">
                      {data.total_filtered} expressions found
                    </span>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => handleStartSession(filterMode)}
                        className="px-2.5 py-1 rounded-xl bg-voxy-purple text-white text-[11px] font-bold"
                      >
                        🧠 Flashcards
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setQuizPoolMode(filterMode);
                          setSubTab('quiz');
                        }}
                        className="px-2.5 py-1 rounded-xl bg-voxy-blue/20 text-voxy-blue border border-voxy-blue/40 text-[11px] font-bold"
                      >
                        📝 Quiz
                      </button>
                    </div>
                  </div>
                )}

                {/* Vocabulary Cards List */}
                <div className="space-y-2">
                  {data.items.map((item) => (
                    <div
                      key={item.id}
                      className="bg-voxy-card border border-voxy-border rounded-2xl p-3.5 space-y-1.5"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="text-xs text-voxy-muted font-medium">
                            🔤 {item.basic_expression}
                          </div>
                          <div className="text-sm font-display font-bold text-voxy-green flex items-center gap-1.5 mt-0.5">
                            <span>💎 {item.advanced_expression}</span>
                            <button
                              type="button"
                              onClick={() =>
                                speakEnglishExpression(item.advanced_expression)
                              }
                              className="p-1 rounded-lg bg-voxy-secondary text-voxy-blue"
                            >
                              <Volume2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                        <span
                          className={`px-2 py-0.5 rounded-lg text-[10px] font-bold shrink-0 ${
                            item.admin_status === 'memorized'
                              ? 'bg-voxy-green/20 text-voxy-green'
                              : item.admin_status === 'difficult'
                              ? 'bg-amber-500/20 text-amber-400'
                              : 'bg-voxy-secondary text-voxy-muted'
                          }`}
                        >
                          {item.admin_status.toUpperCase()}
                        </span>
                      </div>

                      <div className="text-xs text-voxy-text">
                        🇺🇿 {item.translation_uz}
                        {item.translation_ru ? ` • 🇷🇺 ${item.translation_ru}` : ''}
                      </div>
                      <div className="text-[11px] text-voxy-muted italic">
                        “{item.example_en}”
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-voxy-muted pt-1 border-t border-voxy-border">
                        <span>
                          🏷 {item.category} • {item.cefr_level}
                        </span>
                        <span>📅 {item.original_generation_date}</span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Pagination Controls */}
                {data.total_pages > 1 && (
                  <div className="flex items-center justify-between pt-1">
                    <button
                      type="button"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      className="px-3.5 py-2 rounded-xl bg-voxy-card border border-voxy-border text-xs font-bold disabled:opacity-40 flex items-center gap-1"
                    >
                      <ChevronLeft className="w-4 h-4" /> Prev
                    </button>
                    <span className="text-xs font-bold text-voxy-muted">
                      {data.page} / {data.total_pages}
                    </span>
                    <button
                      type="button"
                      disabled={page >= data.total_pages}
                      onClick={() =>
                        setPage((p) => Math.min(data.total_pages, p + 1))
                      }
                      className="px-3.5 py-2 rounded-xl bg-voxy-card border border-voxy-border text-xs font-bold disabled:opacity-40 flex items-center gap-1"
                    >
                      Next <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* ============================================================ */}
            {/* TAB 2: MEMORIZATION MODES & 3D INTERACTIVE FLASHCARDS        */}
            {/* ============================================================ */}
            {subTab === 'memorize' && (
              <div className="space-y-3.5">
                {fcDeck.length === 0 || fcCompletedBanner ? (
                  <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 space-y-4">
                    {fcCompletedBanner && (
                      <div className="bg-voxy-green/15 border border-voxy-green/40 rounded-2xl p-3.5 text-center space-y-1">
                        <CheckCircle2 className="w-7 h-7 text-voxy-green mx-auto" />
                        <div className="text-sm font-display font-bold text-voxy-text">
                          🎉 Session Completed!
                        </div>
                        <div className="text-xs text-voxy-muted">
                          All progress & spaced repetition intervals saved to database.
                        </div>
                      </div>
                    )}

                    <div>
                      <div className="text-xs font-bold text-voxy-text mb-2">
                        1. {t(lang, 'admin_tab_memorize')}
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        {modeOptions.map((m) => (
                          <button
                            key={m.id}
                            type="button"
                            onClick={() => {
                              hapticSelection();
                              setFilterMode(m.id);
                            }}
                            className={`p-2.5 rounded-2xl border text-left transition-all ${
                              filterMode === m.id
                                ? 'bg-voxy-purple/25 border-voxy-purple text-voxy-text'
                                : 'bg-voxy-secondary/70 border-voxy-border text-voxy-muted'
                            }`}
                          >
                            <div className="text-xs font-bold truncate">
                              {m.label}
                            </div>
                            <div className="text-[11px] text-voxy-gold font-extrabold mt-0.5">
                              {m.count} words
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <div className="text-xs font-bold text-voxy-text mb-2">
                        2. {L.session_size}
                      </div>
                      <div className="grid grid-cols-5 gap-1.5">
                        {(['10', '20', '50', '100', 'all'] as const).map((sz) => (
                          <button
                            key={sz}
                            type="button"
                            onClick={() => setSessionSize(sz)}
                            className={`py-2 rounded-xl text-xs font-extrabold uppercase border ${
                              sessionSize === sz
                                ? 'bg-voxy-purple text-white border-voxy-purple'
                                : 'bg-voxy-secondary border-voxy-border text-voxy-muted'
                            }`}
                          >
                            {sz}
                          </button>
                        ))}
                      </div>
                    </div>

                    <button
                      type="button"
                      disabled={busyAction}
                      onClick={() => handleStartSession()}
                      className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-voxy-purple to-indigo-600 text-white font-extrabold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-lg"
                    >
                      <Play className="w-4 h-4 fill-current" />
                      {L.start_flashcards}
                    </button>
                  </div>
                ) : (
                  activeCard && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between text-xs font-bold text-voxy-muted">
                        <span>
                          Card {fcIndex + 1} / {fcDeck.length}
                        </span>
                        <button
                          type="button"
                          onClick={() => setFcDeck([])}
                          className="text-voxy-blue underline"
                        >
                          Change Mode
                        </button>
                      </div>

                      {/* 3D Interactive Flashcard with Swipe Gestures */}
                      <motion.div
                        key={activeCard.id}
                        drag="x"
                        dragConstraints={{ left: 0, right: 0 }}
                        onDragEnd={(_, info) => {
                          if (info.offset.x > 85) {
                            handleCardDecision('memorized');
                          } else if (info.offset.x < -85) {
                            handleCardDecision('difficult');
                          }
                        }}
                        onClick={() => {
                          hapticSelection();
                          setFcFlipped((f) => !f);
                        }}
                        className="perspective-1000 cursor-pointer select-none"
                      >
                        <motion.div
                          animate={{ rotateY: fcFlipped ? 180 : 0 }}
                          transition={{ duration: 0.45, ease: 'easeOut' }}
                          className="relative w-full min-h-[270px] preserve-3d"
                        >
                          {/* FRONT: Basic Expression */}
                          <div className="absolute inset-0 backface-hidden rounded-3xl bg-gradient-to-br from-voxy-card via-voxy-secondary to-voxy-bg border border-voxy-purple/40 p-5 flex flex-col justify-between shadow-glass">
                            <div className="flex items-center justify-between text-[11px] text-voxy-muted font-bold">
                              <span>
                                🏷 {activeCard.category} • {activeCard.cefr_level}
                              </span>
                              <span>📅 {activeCard.original_generation_date}</span>
                            </div>

                            <div className="my-auto text-center space-y-2.5 py-4">
                              <span className="text-[10px] font-extrabold uppercase tracking-wider text-voxy-blue">
                                BASIC ENGLISH EXPRESSION
                              </span>
                              <h3 className="text-xl sm:text-2xl font-display font-extrabold text-voxy-text">
                                {activeCard.basic_expression}
                              </h3>
                              <p className="text-xs text-voxy-muted italic">
                                “{activeCard.basic_example_en}”
                              </p>
                            </div>

                            <div className="text-center text-[11px] text-voxy-muted flex items-center justify-center gap-1.5">
                              <RotateCcw className="w-3.5 h-3.5 text-voxy-purple" />
                              {L.tap_flip}
                            </div>
                          </div>

                          {/* BACK: Advanced Equivalent, Translation, Example, Usage */}
                          <div className="absolute inset-0 backface-hidden rotate-y-180 rounded-3xl bg-gradient-to-br from-[#1E1B4B] via-[#19243D] to-[#0F172A] border border-voxy-green/50 p-5 flex flex-col justify-between shadow-greenGlow">
                            <div className="flex items-center justify-between">
                              <span className="text-[10px] font-extrabold uppercase tracking-wider text-voxy-green">
                                ADVANCED IELTS EQUIVALENT
                              </span>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  speakEnglishExpression(
                                    activeCard.advanced_expression
                                  );
                                }}
                                className="p-1.5 rounded-xl bg-white/10 text-voxy-blue"
                              >
                                <Volume2 className="w-4 h-4" />
                              </button>
                            </div>

                            <div className="space-y-2 my-auto py-2">
                              <h3 className="text-lg sm:text-xl font-display font-extrabold text-white">
                                💎 {activeCard.advanced_expression}
                              </h3>
                              <div className="text-xs text-amber-300 font-semibold">
                                🇺🇿 {activeCard.translation_uz}
                                {activeCard.translation_ru
                                  ? ` • 🇷🇺 ${activeCard.translation_ru}`
                                  : ''}
                              </div>
                              <p className="text-[11px] text-slate-300 leading-relaxed">
                                📖 {activeCard.definition_en}
                              </p>
                              <div className="bg-white/5 border border-white/10 rounded-xl p-2.5 text-[11px] text-slate-200 italic">
                                🎓 “{activeCard.example_en}”
                              </div>
                            </div>

                            <div className="text-[10px] font-bold text-voxy-blue">
                              📚 IELTS Usage: {activeCard.usage_context}
                            </div>
                          </div>
                        </motion.div>
                      </motion.div>

                      {/* 5 Required Action & Navigation Buttons */}
                      <div className="grid grid-cols-3 gap-2">
                        <button
                          type="button"
                          disabled={busyAction}
                          onClick={() => handleCardDecision('memorized')}
                          className="py-3 rounded-2xl bg-voxy-green text-slate-950 font-extrabold text-xs shadow"
                        >
                          ✅ YODLADIM
                        </button>
                        <button
                          type="button"
                          disabled={busyAction}
                          onClick={() => handleCardDecision('difficult')}
                          className="py-3 rounded-2xl bg-amber-500/20 border border-amber-400/50 text-amber-300 font-extrabold text-xs"
                        >
                          ⚠️ QIYIN
                        </button>
                        <button
                          type="button"
                          disabled={busyAction}
                          onClick={() => handleCardDecision('later')}
                          className="py-3 rounded-2xl bg-voxy-card border border-voxy-border text-voxy-text font-extrabold text-xs"
                        >
                          ⏳ KEYINROQ
                        </button>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <button
                          type="button"
                          disabled={fcIndex <= 0}
                          onClick={() => handleCardNav(-1)}
                          className="py-2.5 rounded-2xl bg-voxy-secondary border border-voxy-border text-xs font-bold text-voxy-text disabled:opacity-40 flex items-center justify-center gap-1"
                        >
                          <ChevronLeft className="w-4 h-4" /> OLDINGI SO‘Z
                        </button>
                        <button
                          type="button"
                          disabled={fcIndex >= fcDeck.length - 1}
                          onClick={() => handleCardNav(1)}
                          className="py-2.5 rounded-2xl bg-voxy-secondary border border-voxy-border text-xs font-bold text-voxy-text disabled:opacity-40 flex items-center justify-center gap-1"
                        >
                          KEYINGI SO‘Z <ChevronRight className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  )
                )}
              </div>
            )}

            {/* ============================================================ */}
            {/* TAB 3: ALL VOCABULARY ABCD QUIZ & RETRY WRONG ANSWERS        */}
            {/* ============================================================ */}
            {subTab === 'quiz' && (
              <div className="space-y-3.5">
                {quizQuestions.length === 0 && !quizResult && (
                  <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 space-y-4">
                    <div>
                      <div className="text-xs font-bold text-voxy-text mb-2">
                        1. {L.quiz_pool}
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        {modeOptions.slice(0, 6).map((m) => (
                          <button
                            key={m.id}
                            type="button"
                            onClick={() => setQuizPoolMode(m.id)}
                            className={`p-2.5 rounded-2xl border text-left ${
                              quizPoolMode === m.id
                                ? 'bg-voxy-blue/20 border-voxy-blue text-voxy-text'
                                : 'bg-voxy-secondary/70 border-voxy-border text-voxy-muted'
                            }`}
                          >
                            <div className="text-xs font-bold truncate">
                              {m.label}
                            </div>
                            <div className="text-[10px] text-voxy-gold font-bold">
                              {m.count} available
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <div className="text-xs font-bold text-voxy-text mb-2">
                        2. {L.quiz_count}
                      </div>
                      <div className="grid grid-cols-5 gap-1.5">
                        {(['10', '20', '50', '100', 'custom'] as const).map(
                          (cnt) => (
                            <button
                              key={cnt}
                              type="button"
                              onClick={() => setQuizCountChoice(cnt)}
                              className={`py-2 rounded-xl text-xs font-extrabold border ${
                                quizCountChoice === cnt
                                  ? 'bg-voxy-blue text-slate-950 border-voxy-blue'
                                  : 'bg-voxy-secondary border-voxy-border text-voxy-muted'
                              }`}
                            >
                              {cnt === 'custom' ? L.custom_count : cnt}
                            </button>
                          )
                        )}
                      </div>
                      {quizCountChoice === 'custom' && (
                        <input
                          type="number"
                          min={1}
                          max={500}
                          value={customQuizCount}
                          onChange={(e) => setCustomQuizCount(e.target.value)}
                          className="mt-2 w-full px-3.5 py-2 rounded-xl bg-voxy-secondary border border-voxy-border text-xs text-voxy-text"
                          placeholder="Enter custom question count (e.g. 35)"
                        />
                      )}
                    </div>

                    <button
                      type="button"
                      disabled={busyAction}
                      onClick={() => handleStartQuiz()}
                      className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-voxy-blue to-indigo-600 text-white font-extrabold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-lg"
                    >
                      <Play className="w-4 h-4 fill-current" />
                      {L.start_quiz}
                    </button>
                  </div>
                )}

                {activeQuizQ && (
                  <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 space-y-3.5">
                    <div className="flex items-center justify-between text-xs font-bold">
                      <span className="text-voxy-blue">
                        Question {quizIdx + 1} / {quizQuestions.length}
                      </span>
                      <span className="text-voxy-muted">
                        {activeQuizQ.cefr_level} • {activeQuizQ.category}
                      </span>
                    </div>

                    <div className="bg-voxy-secondary rounded-2xl p-3.5 space-y-1">
                      <div className="text-sm font-display font-bold text-voxy-text">
                        🔤 “{activeQuizQ.basic_expression}”
                      </div>
                      <div className="text-xs text-voxy-muted">
                        🇺🇿 {activeQuizQ.translation_uz}
                      </div>
                    </div>

                    <div className="space-y-2">
                      {activeQuizQ.options.map((opt, idx) => {
                        const letters = ['A', 'B', 'C', 'D'];
                        const isChosen = quizSelectedIdx === idx;
                        const isCorrect = idx === activeQuizQ.correct_option;
                        let style =
                          'bg-voxy-secondary border-voxy-border text-voxy-text';
                        if (quizSelectedIdx !== null) {
                          if (isCorrect) {
                            style =
                              'bg-voxy-green/20 border-voxy-green text-voxy-green';
                          } else if (isChosen) {
                            style =
                              'bg-rose-500/20 border-rose-500 text-rose-300';
                          }
                        }
                        return (
                          <button
                            key={idx}
                            type="button"
                            disabled={quizSelectedIdx !== null}
                            onClick={() => handleSelectQuizOption(idx)}
                            className={`w-full p-3 rounded-2xl border text-left text-xs font-bold flex items-center gap-2.5 transition-all ${style}`}
                          >
                            <span className="w-6 h-6 rounded-lg bg-voxy-bg flex items-center justify-center text-[11px] font-extrabold shrink-0">
                              {letters[idx]}
                            </span>
                            <span>{opt}</span>
                          </button>
                        );
                      })}
                    </div>

                    <AnimatePresence>
                      {quizSelectedIdx !== null && (
                        <motion.div
                          initial={{ opacity: 0, y: 6 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="bg-voxy-bg border border-voxy-border rounded-2xl p-3 space-y-1.5 text-xs"
                        >
                          <div className="font-bold text-voxy-green">
                            ✅ {activeQuizQ.advanced_expression} —{' '}
                            {activeQuizQ.translation_uz}
                          </div>
                          <div className="text-[11px] text-voxy-muted">
                            {activeQuizQ.definition_en}
                          </div>
                          <div className="text-[11px] text-voxy-text italic">
                            “{activeQuizQ.example_en}”
                          </div>
                          <button
                            type="button"
                            disabled={busyAction}
                            onClick={handleNextOrFinishQuiz}
                            className="mt-2 w-full py-2.5 rounded-xl bg-voxy-purple text-white font-extrabold text-xs"
                          >
                            {quizIdx < quizQuestions.length - 1
                              ? t(lang, 'quiz_next')
                              : t(lang, 'quiz_finish')}
                          </button>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )}

                {quizResult && (
                  <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 space-y-4">
                    <div className="text-center space-y-1">
                      <div className="text-2xl font-display font-extrabold text-voxy-green">
                        {quizResult.correct_count} / {quizResult.question_count}{' '}
                        ({quizResult.accuracy}%)
                      </div>
                      <div className="text-xs text-voxy-muted">
                        {t(lang, 'quiz_result_title')}
                      </div>
                    </div>

                    {quizResult.wrong_archive_ids.length > 0 && (
                      <>
                        <button
                          type="button"
                          onClick={() =>
                            handleStartQuiz(quizResult.wrong_archive_ids)
                          }
                          className="w-full py-3 rounded-2xl bg-amber-500 text-slate-950 font-extrabold text-xs flex items-center justify-center gap-2"
                        >
                          <RotateCcw className="w-4 h-4" />
                          {L.retry_wrong} ({quizResult.wrong_archive_ids.length})
                        </button>

                        <div className="space-y-2">
                          <div className="text-xs font-bold text-voxy-text">
                            🧐 {L.wrong_review}
                          </div>
                          {quizResult.details
                            .filter((d) => !d.is_correct)
                            .map((d) => (
                              <div
                                key={d.archive_id}
                                className="bg-voxy-secondary border border-rose-500/30 rounded-2xl p-3 text-xs space-y-1"
                              >
                                <div className="text-voxy-muted">
                                  🔤 {d.basic_expression} (❌ {d.selected_text})
                                </div>
                                <div className="font-bold text-voxy-green">
                                  ✅ {d.advanced_expression} — {d.translation_uz}
                                </div>
                                <div className="text-[11px] text-voxy-muted italic">
                                  “{d.example_en}”
                                </div>
                              </div>
                            ))}
                        </div>
                      </>
                    )}

                    <button
                      type="button"
                      onClick={() => setQuizResult(null)}
                      className="w-full py-2.5 rounded-2xl bg-voxy-secondary border border-voxy-border text-xs font-bold text-voxy-text"
                    >
                      New Quiz
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* ============================================================ */}
            {/* TAB 4: SMART SPACED REPETITION (SRS 1/3/7/14/30 DAYS)        */}
            {/* ============================================================ */}
            {subTab === 'revision' && (
              <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 space-y-4">
                <div className="flex items-start gap-3">
                  <div className="p-2.5 rounded-2xl bg-voxy-purple/20 text-voxy-purple">
                    <Clock className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-display font-bold text-voxy-text">
                      {L.srs_title}
                    </h3>
                    <p className="text-xs text-voxy-muted mt-0.5">
                      {L.srs_desc}
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="bg-voxy-secondary rounded-2xl p-3">
                    <div className="text-lg font-extrabold text-voxy-gold">
                      {stats.revision_due_count}
                    </div>
                    <div className="text-[10px] text-voxy-muted">
                      {L.revision_due}
                    </div>
                  </div>
                  <div className="bg-voxy-secondary rounded-2xl p-3">
                    <div className="text-lg font-extrabold text-amber-400">
                      {stats.difficult_count}
                    </div>
                    <div className="text-[10px] text-voxy-muted">
                      {L.difficult}
                    </div>
                  </div>
                  <div className="bg-voxy-secondary rounded-2xl p-3">
                    <div className="text-lg font-extrabold text-rose-400">
                      {stats.incorrect_count}
                    </div>
                    <div className="text-[10px] text-voxy-muted">
                      Missed Quiz
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <button
                    type="button"
                    disabled={stats.revision_due_count === 0 || busyAction}
                    onClick={() => handleStartSession('srs_due')}
                    className="py-3 rounded-2xl bg-voxy-purple text-white font-extrabold text-xs disabled:opacity-40"
                  >
                    🧠 SRS Flashcards ({stats.revision_due_count})
                  </button>
                  <button
                    type="button"
                    disabled={stats.revision_due_count === 0 || busyAction}
                    onClick={() => {
                      setQuizPoolMode('srs_due');
                      setSubTab('quiz');
                    }}
                    className="py-3 rounded-2xl bg-voxy-blue/20 border border-voxy-blue/40 text-voxy-blue font-extrabold text-xs disabled:opacity-40"
                  >
                    📝 SRS Quiz ({stats.revision_due_count})
                  </button>
                </div>
              </div>
            )}

            {/* ============================================================ */}
            {/* TAB 5: REAL ADMIN STATISTICS & CSV / XLSX / PDF EXPORT       */}
            {/* ============================================================ */}
            {subTab === 'stats' && (
              <div className="space-y-3.5">
                <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 space-y-3">
                  <h3 className="text-sm font-display font-bold text-voxy-text">
                    📊 {t(lang, 'admin_tab_stats')}
                  </h3>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-voxy-secondary rounded-2xl p-3">
                      <div className="text-voxy-muted">{L.archived_total}</div>
                      <div className="text-base font-extrabold text-voxy-text mt-0.5">
                        {stats.total_archived}
                      </div>
                    </div>
                    <div className="bg-voxy-secondary rounded-2xl p-3">
                      <div className="text-voxy-muted">
                        {L.added_today} / {L.added_week} / {L.added_month}
                      </div>
                      <div className="text-base font-extrabold text-voxy-green mt-0.5">
                        +{stats.added_today} / +{stats.added_this_week} / +
                        {stats.added_this_month}
                      </div>
                    </div>
                    <div className="bg-voxy-secondary rounded-2xl p-3">
                      <div className="text-voxy-muted">
                        {L.memorized} / {L.unmemorized}
                      </div>
                      <div className="text-base font-extrabold text-voxy-blue mt-0.5">
                        {stats.memorized_count} / {stats.unmemorized_count}
                      </div>
                    </div>
                    <div className="bg-voxy-secondary rounded-2xl p-3">
                      <div className="text-voxy-muted">
                        {L.difficult} / {L.revision_due}
                      </div>
                      <div className="text-base font-extrabold text-amber-400 mt-0.5">
                        {stats.difficult_count} / {stats.revision_due_count}
                      </div>
                    </div>
                    <div className="bg-voxy-secondary rounded-2xl p-3">
                      <div className="text-voxy-muted">{L.quiz_acc}</div>
                      <div className="text-base font-extrabold text-voxy-purple mt-0.5">
                        {stats.quiz_accuracy}%
                      </div>
                    </div>
                    <div className="bg-voxy-secondary rounded-2xl p-3">
                      <div className="text-voxy-muted">{L.completion}</div>
                      <div className="text-base font-extrabold text-voxy-gold mt-0.5">
                        {stats.completion_percentage}%
                      </div>
                    </div>
                  </div>
                </div>

                {/* Gemini Free Tier API Monitoring Dashboard (Requirement 15) */}
                {data.ai_monitoring && (
                  <div className="bg-voxy-card border border-voxy-green/35 rounded-3xl p-4 space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="text-sm font-display font-bold text-voxy-text flex items-center gap-1.5">
                        <Sparkles className="w-4 h-4 text-voxy-green" />
                        Gemini Free Tier API Monitor
                      </h3>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-voxy-green/20 text-voxy-green border border-voxy-green/40">
                        $0.00 FREE TIER ONLY
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="bg-voxy-secondary rounded-2xl p-2.5">
                        <div className="text-[10px] text-voxy-muted">
                          Active Free Model
                        </div>
                        <div className="font-mono font-bold text-voxy-blue truncate mt-0.5">
                          {data.ai_monitoring.active_model}
                        </div>
                      </div>
                      <div className="bg-voxy-secondary rounded-2xl p-2.5">
                        <div className="text-[10px] text-voxy-muted">
                          Requests Today / RPD Left
                        </div>
                        <div className="font-extrabold text-voxy-green mt-0.5">
                          {data.ai_monitoring.total_requests_today} used •{' '}
                          {data.ai_monitoring.active_model_quota.rpd_remaining} left
                        </div>
                      </div>
                      <div className="bg-voxy-secondary rounded-2xl p-2.5">
                        <div className="text-[10px] text-voxy-muted">
                          PostgreSQL Unused Reserve
                        </div>
                        <div className="font-extrabold text-voxy-gold mt-0.5">
                          {data.ai_monitoring.reserve.unused_count} /{' '}
                          {data.ai_monitoring.reserve.target_min}–
                          {data.ai_monitoring.reserve.target_max}
                        </div>
                      </div>
                      <div className="bg-voxy-secondary rounded-2xl p-2.5">
                        <div className="text-[10px] text-voxy-muted">
                          API Errors (404 / 429)
                        </div>
                        <div className="font-extrabold text-voxy-text mt-0.5">
                          404: {data.ai_monitoring.errors.errors_404} • 429:{' '}
                          {data.ai_monitoring.errors.errors_429}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Export Card */}
                <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-display font-bold text-voxy-text flex items-center gap-2">
                      <Download className="w-4 h-4 text-voxy-gold" />
                      {L.export_title}
                    </h3>
                    {exportStatus && (
                      <span className="text-[11px] font-bold text-voxy-green">
                        {exportStatus}
                      </span>
                    )}
                  </div>

                  <div className="text-[11px] text-voxy-muted font-semibold">
                    {L.export_all} ({stats.total_archived})
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      type="button"
                      onClick={() => handleExport('csv', 'all')}
                      className="py-2.5 rounded-xl bg-voxy-secondary border border-voxy-border text-xs font-bold flex items-center justify-center gap-1.5"
                    >
                      <FileText className="w-3.5 h-3.5 text-voxy-blue" /> CSV
                    </button>
                    <button
                      type="button"
                      onClick={() => handleExport('xlsx', 'all')}
                      className="py-2.5 rounded-xl bg-voxy-secondary border border-voxy-border text-xs font-bold flex items-center justify-center gap-1.5"
                    >
                      <FileSpreadsheet className="w-3.5 h-3.5 text-voxy-green" />{' '}
                      XLSX
                    </button>
                    <button
                      type="button"
                      onClick={() => handleExport('pdf', 'all')}
                      className="py-2.5 rounded-xl bg-voxy-secondary border border-voxy-border text-xs font-bold flex items-center justify-center gap-1.5"
                    >
                      <FileText className="w-3.5 h-3.5 text-rose-400" /> PDF
                    </button>
                  </div>

                  <div className="text-[11px] text-voxy-muted font-semibold pt-1">
                    {L.export_filtered} ({data.total_filtered})
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      type="button"
                      onClick={() => handleExport('csv', 'filtered')}
                      className="py-2.5 rounded-xl bg-voxy-purple/15 border border-voxy-purple/40 text-xs font-bold"
                    >
                      CSV
                    </button>
                    <button
                      type="button"
                      onClick={() => handleExport('xlsx', 'filtered')}
                      className="py-2.5 rounded-xl bg-voxy-purple/15 border border-voxy-purple/40 text-xs font-bold"
                    >
                      XLSX
                    </button>
                    <button
                      type="button"
                      onClick={() => handleExport('pdf', 'filtered')}
                      className="py-2.5 rounded-xl bg-voxy-purple/15 border border-voxy-purple/40 text-xs font-bold"
                    >
                      PDF
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
