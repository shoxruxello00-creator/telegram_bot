import React from 'react';
import { motion } from 'framer-motion';
import {
  Award,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Flame,
  Gift,
  Layers,
  Moon,
  Play,
  Sparkles,
  Sun,
  Swords,
  Target,
  Zap,
} from 'lucide-react';
import { LeagueBadge } from '../components/LeagueBadge';
import { VoxyMascot } from '../components/VoxyMascot';
import { t } from '../lib/i18n';
import { hapticImpact, hapticSelection } from '../lib/telegram';
import { useAppStore } from '../store/useAppStore';
import { BootstrapPayload, LanguageCode } from '../types/miniapp';

interface HomeDashboardProps {
  data: BootstrapPayload;
  onLanguageChange: (lang: LanguageCode) => void;
}

export const HomeDashboard: React.FC<HomeDashboardProps> = ({
  data,
  onLanguageChange,
}) => {
  const {
    lang,
    theme,
    toggleTheme,
    voxyMood,
    openFlashcards,
    openQuiz,
    openGameMode,
    openReferrals,
    setActiveTab,
  } = useAppStore();

  const { user, daily_lesson, missions, weekly_calendar, achievements, referral_preview } =
    data;

  const initials = (user.full_name || 'Learner')
    .split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const quickGames = [
    {
      id: 'word_battle' as const,
      title: t(lang, 'game_word_battle_title'),
      tag: 'PvE Duel',
      Icon: Swords,
      gradient: 'from-violet-600/30 to-indigo-600/15 border-violet-500/40',
      iconColor: 'text-violet-400',
    },
    {
      id: 'brain_rush' as const,
      title: t(lang, 'game_brain_rush_title'),
      tag: '60s Blitz',
      Icon: Zap,
      gradient: 'from-sky-500/30 to-blue-600/15 border-sky-400/40',
      iconColor: 'text-sky-400',
    },
    {
      id: 'word_match' as const,
      title: t(lang, 'game_word_match_title'),
      tag: 'Pairs',
      Icon: Layers,
      gradient: 'from-emerald-500/30 to-teal-600/15 border-emerald-400/40',
      iconColor: 'text-emerald-400',
    },
    {
      id: 'ielts_arena' as const,
      title: t(lang, 'game_ielts_arena_title'),
      tag: 'Band 8+',
      Icon: Target,
      gradient: 'from-amber-500/30 to-orange-600/15 border-amber-400/40',
      iconColor: 'text-amber-400',
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32 }}
      className="space-y-4 pb-24"
    >
      {/* Top Profile Header Bar */}
      <div className="bg-voxy-secondary/90 backdrop-blur-md border border-voxy-border rounded-3xl p-4 shadow-glass">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-3 min-w-0">
            <div className="relative w-12 h-12 rounded-2xl bg-gradient-to-tr from-voxy-purple to-voxy-blue flex items-center justify-center text-white font-display font-bold text-lg shadow-purpleGlow shrink-0">
              {initials}
              <span className="absolute -bottom-1 -right-1 bg-voxy-gold text-slate-950 text-[10px] font-extrabold px-1.5 py-0.2 rounded-full border border-voxy-bg">
                L{user.level}
              </span>
            </div>
            <div className="min-w-0">
              <p className="text-xs text-voxy-muted font-medium truncate">
                {t(lang, 'greeting_prefix')}
              </p>
              <h1 className="text-base sm:text-lg font-display font-bold text-voxy-text truncate">
                {user.full_name}
              </h1>
              <div className="flex items-center gap-2 mt-0.5">
                <LeagueBadge leagueId={user.league.id} size="sm" />
                <span className="text-[11px] text-voxy-muted font-medium truncate">
                  • {user.level_title}
                </span>
              </div>
            </div>
          </div>

          {/* Language Pill & Theme Toggle */}
          <div className="flex items-center gap-1.5 shrink-0">
            <div className="bg-voxy-card border border-voxy-border rounded-xl p-0.5 flex items-center">
              {(['uz', 'ru', 'en'] as LanguageCode[]).map((l) => (
                <button
                  key={l}
                  type="button"
                  onClick={() => {
                    hapticSelection();
                    onLanguageChange(l);
                  }}
                  className={`px-2 py-1 rounded-lg text-[11px] font-bold uppercase transition-colors ${
                    lang === l
                      ? 'bg-voxy-purple text-white shadow'
                      : 'text-voxy-muted hover:text-voxy-text'
                  }`}
                >
                  {l}
                </button>
              ))}
            </div>
            <button
              type="button"
              aria-label="Toggle theme"
              onClick={() => {
                hapticImpact('light');
                toggleTheme();
              }}
              className="p-2 rounded-xl bg-voxy-card border border-voxy-border text-voxy-muted hover:text-voxy-text"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4 text-voxy-gold" /> : <Moon className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* XP, Streak & Level Progress Strip */}
        <div className="grid grid-cols-3 gap-2 mt-4">
          <div className="bg-voxy-card/90 border border-voxy-border rounded-2xl px-3 py-2 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-voxy-gold shrink-0" />
            <div>
              <div className="text-xs font-extrabold text-voxy-text">
                {user.xp.toLocaleString()} XP
              </div>
              <div className="text-[10px] text-voxy-muted">Total Score</div>
            </div>
          </div>

          <div className="bg-voxy-card/90 border border-voxy-border rounded-2xl px-3 py-2 flex items-center gap-2">
            <Flame className="w-4 h-4 text-orange-400 shrink-0" />
            <div>
              <div className="text-xs font-extrabold text-voxy-text">
                {user.streak} Days
              </div>
              <div className="text-[10px] text-voxy-muted">
                Best: {user.best_streak}d
              </div>
            </div>
          </div>

          <div className="bg-voxy-card/90 border border-voxy-border rounded-2xl px-3 py-2 flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-voxy-blue shrink-0" />
            <div>
              <div className="text-xs font-extrabold text-voxy-text">
                {user.learned_count}
              </div>
              <div className="text-[10px] text-voxy-muted">Upgrades</div>
            </div>
          </div>
        </div>

        {/* Animated Level Progress Bar */}
        <div className="mt-3.5">
          <div className="flex items-center justify-between text-[11px] font-semibold mb-1">
            <span className="text-voxy-blue">
              Level {user.level} • {user.level_title}
            </span>
            <span className="text-voxy-muted">
              {user.xp_in_level} / {user.xp_for_next_level} XP
            </span>
          </div>
          <div className="h-2.5 w-full bg-voxy-bg rounded-full overflow-hidden p-0.5 border border-voxy-border">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${user.progress_pct}%` }}
              transition={{ duration: 0.7, ease: 'easeOut' }}
              className="h-full rounded-full bg-gradient-to-r from-voxy-purple via-indigo-500 to-voxy-blue"
            />
          </div>
        </div>
      </div>

      {/* Voxy AI Mascot Interactive Banner */}
      <VoxyMascot
        mood={voxyMood}
        size="md"
        message={t(lang, 'voxy_welcome')}
      />

      {/* Daily IELTS 4+2+2+2 Vocabulary Mission Hero Card */}
      <motion.div
        whileHover={{ scale: 1.005 }}
        className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#1E1B4B] via-[#19243D] to-[#0F172A] border border-voxy-purple/40 p-5 shadow-purpleGlow"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-voxy-purple/25 text-voxy-blue border border-voxy-purple/40">
              <Sparkles className="w-3 h-3" />
              {daily_lesson.lesson_date} • 4+2+2+2 FORMULA
            </span>
            <h2 className="text-lg sm:text-xl font-display font-bold text-white mt-2">
              {t(lang, 'daily_mission_title')}
            </h2>
            <p className="text-xs text-slate-300 mt-0.5">
              {t(lang, 'daily_mission_sub')}
            </p>
          </div>
          <div className="bg-slate-900/80 border border-white/10 rounded-2xl px-3 py-2 text-center shrink-0">
            <div className="text-base font-display font-extrabold text-voxy-green">
              {daily_lesson.memorized_count}/{daily_lesson.total_words}
            </div>
            <div className="text-[10px] text-slate-400 font-semibold">Cards</div>
          </div>
        </div>

        {/* 4+2+2+2 Category Chips */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 mt-3.5">
          <div className="bg-white/5 border border-white/10 rounded-xl px-2.5 py-1.5 text-[11px] text-slate-200 font-semibold">
            🔤 4 Everyday → Adv
          </div>
          <div className="bg-white/5 border border-white/10 rounded-xl px-2.5 py-1.5 text-[11px] text-slate-200 font-semibold">
            🎓 2 Academic Verbs
          </div>
          <div className="bg-white/5 border border-white/10 rounded-xl px-2.5 py-1.5 text-[11px] text-slate-200 font-semibold">
            💎 2 Collocations
          </div>
          <div className="bg-white/5 border border-white/10 rounded-xl px-2.5 py-1.5 text-[11px] text-slate-200 font-semibold">
            🚀 2 Phrasal Verbs
          </div>
        </div>

        {/* Action Buttons: 3D Flashcards & Daily 10-Question Quiz */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mt-4">
          <button
            type="button"
            onClick={() => {
              hapticImpact('medium');
              openFlashcards(daily_lesson.words, t(lang, 'daily_mission_title'));
            }}
            className="w-full py-3 px-4 rounded-2xl bg-gradient-to-r from-voxy-purple to-indigo-600 hover:from-voxy-purple/90 hover:to-indigo-500 text-white font-bold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-lg active:scale-[0.98] transition-transform"
          >
            <Play className="w-4 h-4 fill-current" />
            {t(lang, 'btn_continue_learning')}
          </button>

          <button
            type="button"
            onClick={() => {
              hapticImpact('medium');
              openQuiz({
                mode: 'daily',
                title: t(lang, 'daily_mission_title'),
                words: daily_lesson.words,
                timedSeconds: 20,
              });
            }}
            className="w-full py-3 px-4 rounded-2xl bg-voxy-blue/20 hover:bg-voxy-blue/30 border border-voxy-blue/50 text-voxy-blue font-bold text-xs sm:text-sm flex items-center justify-center gap-2 active:scale-[0.98] transition-transform"
          >
            <Zap className="w-4 h-4" />
            {t(lang, 'btn_take_daily_quiz')}
          </button>
        </div>
      </motion.div>

      {/* Weekly Activity Calendar Strip */}
      <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 shadow-glass">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs sm:text-sm font-display font-bold text-voxy-text flex items-center gap-2">
            <Flame className="w-4 h-4 text-orange-400" />
            {t(lang, 'sec_weekly_activity')}
          </h3>
          <span className="text-[11px] font-bold text-voxy-green">
            {user.streak}d Active Streak
          </span>
        </div>
        <div className="grid grid-cols-7 gap-1.5">
          {weekly_calendar.map((day) => (
            <div
              key={day.date}
              className={`rounded-2xl py-2 px-1 flex flex-col items-center border transition-all ${
                day.is_today
                  ? 'bg-voxy-purple/25 border-voxy-purple text-voxy-text'
                  : day.active
                  ? 'bg-voxy-secondary border-voxy-green/35 text-voxy-text'
                  : 'bg-voxy-secondary/50 border-voxy-border text-voxy-muted'
              }`}
            >
              <span className="text-[10px] font-bold uppercase opacity-75">
                {day.day_name}
              </span>
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-extrabold my-1 ${
                  day.active
                    ? 'bg-voxy-green text-slate-950'
                    : 'bg-voxy-bg text-voxy-muted'
                }`}
              >
                {day.active ? '✓' : day.day_num}
              </div>
              <span className="text-[9px] font-semibold text-voxy-gold">
                +{day.xp}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Access to Game Modes */}
      <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 shadow-glass">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs sm:text-sm font-display font-bold text-voxy-text">
            {t(lang, 'sec_quick_games')}
          </h3>
          <button
            type="button"
            onClick={() => setActiveTab('play')}
            className="text-xs font-bold text-voxy-blue flex items-center gap-0.5"
          >
            All 8 Modes <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2.5">
          {quickGames.map(({ id, title, tag, Icon, gradient, iconColor }) => (
            <button
              key={id}
              type="button"
              onClick={() => {
                hapticImpact('light');
                openGameMode(id);
              }}
              className={`text-left p-3.5 rounded-2xl bg-gradient-to-br ${gradient} border transition-transform active:scale-95 flex flex-col justify-between`}
            >
              <div className="flex items-center justify-between">
                <Icon className={`w-5 h-5 ${iconColor}`} />
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-black/30 text-slate-200">
                  {tag}
                </span>
              </div>
              <div className="mt-2.5">
                <div className="text-xs sm:text-sm font-display font-bold text-voxy-text">
                  {title}
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Daily Missions & Deterministic Reward Chests */}
      <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 shadow-glass">
        <h3 className="text-xs sm:text-sm font-display font-bold text-voxy-text mb-3 flex items-center gap-2">
          <Target className="w-4 h-4 text-voxy-purple" />
          {t(lang, 'sec_daily_missions')}
        </h3>
        <div className="space-y-2.5">
          {missions.daily.map((m) => {
            const pct = Math.min(100, Math.round((m.current / m.target) * 100));
            const title =
              lang === 'uz' ? m.title_uz : lang === 'ru' ? m.title_ru : m.title_en;
            return (
              <div
                key={m.id}
                className="bg-voxy-secondary/80 border border-voxy-border rounded-2xl p-3"
              >
                <div className="flex items-center justify-between text-xs font-bold mb-1.5">
                  <span className="text-voxy-text flex items-center gap-1.5">
                    {m.completed ? (
                      <CheckCircle2 className="w-4 h-4 text-voxy-green shrink-0" />
                    ) : (
                      <span className="w-2 h-2 rounded-full bg-voxy-purple shrink-0" />
                    )}
                    {title}
                  </span>
                  <span className="text-voxy-gold font-extrabold shrink-0">
                    +{m.xp_reward} XP
                  </span>
                </div>
                <div className="flex items-center gap-2.5">
                  <div className="flex-1 h-2 bg-voxy-bg rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        m.completed ? 'bg-voxy-green' : 'bg-voxy-purple'
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="text-[11px] font-bold text-voxy-muted">
                    {m.current}/{m.target}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Achievements Preview Strip */}
      <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 shadow-glass">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs sm:text-sm font-display font-bold text-voxy-text flex items-center gap-2">
            <Award className="w-4 h-4 text-voxy-gold" />
            {t(lang, 'sec_achievements')}
          </h3>
          <button
            type="button"
            onClick={() => setActiveTab('profile')}
            className="text-xs font-bold text-voxy-blue flex items-center gap-0.5"
          >
            View All <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {achievements.slice(0, 3).map((ach) => {
            const title =
              lang === 'uz'
                ? ach.title_uz
                : lang === 'ru'
                ? ach.title_ru
                : ach.title_en;
            return (
              <div
                key={ach.id}
                className={`rounded-2xl p-2.5 border text-center ${
                  ach.unlocked
                    ? 'bg-voxy-secondary border-voxy-gold/40'
                    : 'bg-voxy-secondary/40 border-voxy-border opacity-60'
                }`}
              >
                <div className="w-8 h-8 mx-auto rounded-xl bg-voxy-gold/20 text-voxy-gold flex items-center justify-center font-bold text-sm mb-1.5">
                  {ach.unlocked ? '🏆' : '🔒'}
                </div>
                <div className="text-[11px] font-bold text-voxy-text truncate">
                  {title}
                </div>
                <div className="text-[10px] text-voxy-gold font-semibold mt-0.5">
                  +{ach.xp_bonus} XP
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Referral Rewards Banner */}
      <button
        type="button"
        onClick={() => {
          hapticImpact('medium');
          openReferrals();
        }}
        className="w-full text-left bg-gradient-to-r from-voxy-purple/25 via-voxy-card to-voxy-gold/20 border border-voxy-gold/40 rounded-3xl p-4 shadow-glass flex items-center justify-between gap-3 active:scale-[0.99] transition-transform"
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-11 h-11 rounded-2xl bg-voxy-gold/20 border border-voxy-gold/40 flex items-center justify-center text-voxy-gold shrink-0">
            <Gift className="w-6 h-6" />
          </div>
          <div className="min-w-0">
            <div className="text-xs sm:text-sm font-display font-bold text-voxy-text truncate">
              {t(lang, 'sec_referral_card')}
            </div>
            <div className="text-[11px] text-voxy-muted mt-0.5 truncate">
              ✅ {referral_preview.confirmed} Confirmed • Next:{' '}
              {referral_preview.next_reward_title}
            </div>
          </div>
        </div>
        <ChevronRight className="w-5 h-5 text-voxy-gold shrink-0" />
      </button>
    </motion.div>
  );
};
