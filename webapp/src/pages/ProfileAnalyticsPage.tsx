import React from 'react';
import { motion } from 'framer-motion';
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from 'recharts';
import {
  Award,
  Bell,
  BookOpen,
  Calendar,
  Globe,
  Info,
  Play,
  RotateCcw,
  Settings,
  Target,
  TrendingUp,
} from 'lucide-react';
import { LeagueBadge } from '../components/LeagueBadge';
import { updateSettings } from '../lib/api';
import { t } from '../lib/i18n';
import { hapticImpact, hapticSelection } from '../lib/telegram';
import { useAppStore } from '../store/useAppStore';
import { BootstrapPayload, LanguageCode } from '../types/miniapp';

interface ProfileAnalyticsPageProps {
  data: BootstrapPayload;
  onLanguageChange: (lang: LanguageCode) => void;
  onRefetch: () => void;
}

export const ProfileAnalyticsPage: React.FC<ProfileAnalyticsPageProps> = ({
  data,
  onLanguageChange,
  onRefetch,
}) => {
  const { lang, openFlashcards } = useAppStore();
  const {
    user,
    weekly_calendar,
    heatmap_28,
    category_mastery,
    achievements,
    words_for_revision,
  } = data;

  const handleToggleSetting = async (
    field: 'reminders_enabled' | 'broadcast_enabled',
    currentVal: boolean
  ) => {
    hapticImpact('light');
    await updateSettings({ [field]: !currentVal });
    onRefetch();
  };

  // Animated SVG Circle Progress helper
  const radius = 32;
  const circumference = 2 * Math.PI * radius;
  const accuracyOffset =
    circumference - (Math.min(100, user.accuracy) / 100) * circumference;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-4 pb-24"
    >
      {/* Profile Hero Card */}
      <div className="bg-voxy-secondary border border-voxy-border rounded-3xl p-5 shadow-glass">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3.5 min-w-0">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-voxy-purple to-voxy-blue flex items-center justify-center font-display font-extrabold text-xl text-white shadow-purpleGlow shrink-0">
              {user.full_name.slice(0, 2).toUpperCase()}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-display font-bold text-voxy-text truncate">
                  {user.full_name}
                </h1>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-voxy-gold/20 text-voxy-gold shrink-0">
                  {user.badge}
                </span>
              </div>
              <p className="text-xs text-voxy-muted">
                @{user.username} • Level {user.level} {user.level_title}
              </p>
              <div className="mt-1">
                <LeagueBadge leagueId={user.league.id} size="sm" />
              </div>
            </div>
          </div>

          {/* Animated SVG Accuracy Progress Ring */}
          <div className="relative w-20 h-20 flex items-center justify-center shrink-0">
            <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
              <circle
                cx="40"
                cy="40"
                r={radius}
                stroke="rgba(148,163,184,0.18)"
                strokeWidth="7"
                fill="none"
              />
              <motion.circle
                cx="40"
                cy="40"
                r={radius}
                stroke="#34D399"
                strokeWidth="7"
                strokeLinecap="round"
                fill="none"
                strokeDasharray={circumference}
                initial={{ strokeDashoffset: circumference }}
                animate={{ strokeDashoffset: accuracyOffset }}
                transition={{ duration: 0.9, ease: 'easeOut' }}
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-xs font-display font-extrabold text-voxy-green">
                {user.accuracy}%
              </span>
              <span className="text-[9px] text-voxy-muted font-bold">
                Accuracy
              </span>
            </div>
          </div>
        </div>

        {/* 4 Key Stats Grid */}
        <div className="grid grid-cols-4 gap-2 mt-4">
          <div className="bg-voxy-card border border-voxy-border rounded-2xl p-2.5 text-center">
            <div className="text-sm font-display font-extrabold text-voxy-text">
              {user.learned_count}
            </div>
            <div className="text-[10px] text-voxy-muted">Words</div>
          </div>
          <div className="bg-voxy-card border border-voxy-border rounded-2xl p-2.5 text-center">
            <div className="text-sm font-display font-extrabold text-voxy-gold">
              {user.xp}
            </div>
            <div className="text-[10px] text-voxy-muted">Total XP</div>
          </div>
          <div className="bg-voxy-card border border-voxy-border rounded-2xl p-2.5 text-center">
            <div className="text-sm font-display font-extrabold text-orange-400">
              {user.streak}d
            </div>
            <div className="text-[10px] text-voxy-muted">Streak</div>
          </div>
          <div className="bg-voxy-card border border-voxy-border rounded-2xl p-2.5 text-center">
            <div className="text-sm font-display font-extrabold text-voxy-blue">
              {user.total_quizzes}
            </div>
            <div className="text-[10px] text-voxy-muted">Quizzes</div>
          </div>
        </div>

        {user.is_admin && (
          <button
            type="button"
            onClick={() => {
              hapticImpact('medium');
              useAppStore.getState().openAdminLibrary();
            }}
            className="mt-3.5 w-full py-3 px-4 rounded-2xl bg-gradient-to-r from-amber-500/20 via-voxy-purple/25 to-voxy-blue/20 border border-voxy-gold/45 text-xs font-extrabold text-voxy-gold flex items-center justify-between"
          >
            <span>👑 {t(lang, 'admin_lib_btn')}</span>
            <span>Open →</span>
          </button>
        )}
      </div>

      {/* Vocabulary Category Mastery (4+2+2+2 Breakdown) */}
      <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 shadow-glass space-y-3">
        <h2 className="text-xs sm:text-sm font-display font-bold text-voxy-text flex items-center gap-2">
          <Target className="w-4 h-4 text-voxy-purple" />
          {t(lang, 'profile_category_mastery')}
        </h2>

        <div className="space-y-3">
          {category_mastery.map((cat) => (
            <div key={cat.category} className="space-y-1">
              <div className="flex items-center justify-between text-xs font-bold">
                <span className="text-voxy-text">{cat.label}</span>
                <span style={{ color: cat.color }}>{cat.percentage}%</span>
              </div>
              <div className="h-2.5 w-full bg-voxy-bg rounded-full overflow-hidden p-0.5 border border-voxy-border">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${cat.percentage}%` }}
                  transition={{ duration: 0.7 }}
                  className="h-full rounded-full"
                  style={{ backgroundColor: cat.color }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Weekly XP Velocity Bar Chart (Recharts) */}
      <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 shadow-glass">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs sm:text-sm font-display font-bold text-voxy-text flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-voxy-blue" />
            {t(lang, 'profile_xp_chart')}
          </h2>
          <span className="text-[11px] font-bold text-voxy-gold">
            Goal: {user.daily_goal} words/day
          </span>
        </div>

        <div className="h-40 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={weekly_calendar}>
              <XAxis
                dataKey="day_name"
                stroke="#94A3B8"
                fontSize={11}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                cursor={{ fill: 'rgba(139, 92, 246, 0.12)' }}
                contentStyle={{
                  backgroundColor: '#111B32',
                  borderColor: 'rgba(139,92,246,0.4)',
                  borderRadius: '12px',
                  fontSize: '12px',
                  color: '#F8FAFC',
                }}
              />
              <Bar
                dataKey="xp"
                fill="#8B5CF6"
                radius={[8, 8, 4, 4]}
                maxBarSize={28}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 28-Day Streak Calendar Heatmap */}
      <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 shadow-glass">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs sm:text-sm font-display font-bold text-voxy-text flex items-center gap-2">
            <Calendar className="w-4 h-4 text-voxy-green" />
            {t(lang, 'profile_heatmap')}
          </h2>
          <span className="text-[11px] text-voxy-muted font-semibold">
            Last 28 Days
          </span>
        </div>
        <div className="grid grid-cols-7 gap-1.5">
          {heatmap_28.map((day) => {
            const bgClass =
              day.intensity === 3
                ? 'bg-voxy-green border-voxy-green'
                : day.intensity === 2
                ? 'bg-voxy-green/60 border-voxy-green/70'
                : day.intensity === 1
                ? 'bg-voxy-green/30 border-voxy-green/40'
                : 'bg-voxy-secondary border-voxy-border';
            return (
              <div
                key={day.date}
                title={`${day.date}: ${day.xp} XP`}
                className={`h-7 rounded-lg border ${bgClass} flex items-center justify-center text-[9px] font-bold text-slate-950`}
              >
                {day.intensity > 0 ? '✓' : ''}
              </div>
            );
          })}
        </div>
      </div>

      {/* Words Requiring Revision */}
      <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 shadow-glass space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs sm:text-sm font-display font-bold text-voxy-text flex items-center gap-2">
            <RotateCcw className="w-4 h-4 text-amber-400" />
            {t(lang, 'profile_revision_words')}
          </h2>
          <button
            type="button"
            onClick={() => {
              hapticImpact('medium');
              openFlashcards(
                words_for_revision,
                t(lang, 'profile_revision_words')
              );
            }}
            className="px-3 py-1 rounded-xl bg-voxy-purple/25 border border-voxy-purple/40 text-voxy-blue text-xs font-bold flex items-center gap-1"
          >
            <Play className="w-3 h-3 fill-current" /> Review Cards
          </button>
        </div>

        <div className="space-y-2">
          {words_for_revision.slice(0, 4).map((w) => (
            <div
              key={w.id}
              className="bg-voxy-secondary/80 border border-voxy-border rounded-2xl p-3 flex items-center justify-between gap-2 text-xs"
            >
              <div className="min-w-0">
                <div className="text-voxy-muted truncate">
                  🔤 {w.simple_word}
                </div>
                <div className="font-bold text-voxy-green truncate mt-0.5">
                  💎 {w.advanced_word}
                </div>
              </div>
              <span className="px-2 py-0.5 rounded-lg bg-voxy-bg text-[10px] font-bold text-voxy-gold shrink-0">
                {w.cefr_level}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Full Achievements Grid */}
      <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 shadow-glass">
        <h2 className="text-xs sm:text-sm font-display font-bold text-voxy-text mb-3 flex items-center gap-2">
          <Award className="w-4 h-4 text-voxy-gold" />
          {t(lang, 'sec_achievements')}
        </h2>
        <div className="grid grid-cols-2 gap-2.5">
          {achievements.map((ach) => {
            const title =
              lang === 'uz'
                ? ach.title_uz
                : lang === 'ru'
                ? ach.title_ru
                : ach.title_en;
            const desc =
              lang === 'uz'
                ? ach.desc_uz
                : lang === 'ru'
                ? ach.desc_ru
                : ach.desc_en;
            const pct = Math.min(
              100,
              Math.round((ach.progress / ach.target) * 100)
            );
            return (
              <div
                key={ach.id}
                className={`rounded-2xl p-3 border ${
                  ach.unlocked
                    ? 'bg-voxy-secondary border-voxy-gold/40'
                    : 'bg-voxy-secondary/50 border-voxy-border opacity-75'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-base">
                    {ach.unlocked ? '🏆' : '🔒'}
                  </span>
                  <span className="text-[10px] font-extrabold text-voxy-gold">
                    +{ach.xp_bonus} XP
                  </span>
                </div>
                <div className="text-xs font-bold text-voxy-text truncate">
                  {title}
                </div>
                <p className="text-[10px] text-voxy-muted mt-0.5 line-clamp-2">
                  {desc}
                </p>
                <div className="mt-2 h-1.5 bg-voxy-bg rounded-full overflow-hidden">
                  <div
                    className="h-full bg-voxy-gold rounded-full"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Language & Notification Settings */}
      <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 shadow-glass space-y-3">
        <h2 className="text-xs sm:text-sm font-display font-bold text-voxy-text flex items-center gap-2">
          <Settings className="w-4 h-4 text-voxy-blue" />
          {t(lang, 'profile_settings')}
        </h2>

        {/* Language Selector */}
        <div className="flex items-center justify-between bg-voxy-secondary rounded-2xl p-3 border border-voxy-border">
          <span className="text-xs font-bold text-voxy-text flex items-center gap-2">
            <Globe className="w-4 h-4 text-voxy-purple" /> Interface Language
          </span>
          <div className="flex items-center gap-1">
            {(
              [
                { code: 'uz', label: '🇺🇿 UZ' },
                { code: 'ru', label: '🇷🇺 RU' },
                { code: 'en', label: '🇬🇧 EN' },
              ] as const
            ).map((item) => (
              <button
                key={item.code}
                type="button"
                onClick={() => {
                  hapticSelection();
                  onLanguageChange(item.code);
                }}
                className={`px-2.5 py-1 rounded-xl text-xs font-bold ${
                  lang === item.code
                    ? 'bg-voxy-purple text-white'
                    : 'bg-voxy-card text-voxy-muted'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {/* Evening Reminders Toggle */}
        <div className="flex items-center justify-between bg-voxy-secondary rounded-2xl p-3 border border-voxy-border">
          <span className="text-xs font-bold text-voxy-text flex items-center gap-2">
            <Bell className="w-4 h-4 text-voxy-gold" /> 20:00 Evening Reminders
          </span>
          <button
            type="button"
            onClick={() =>
              handleToggleSetting('reminders_enabled', user.reminders_enabled)
            }
            className={`px-3 py-1 rounded-xl text-xs font-extrabold transition-colors ${
              user.reminders_enabled
                ? 'bg-voxy-green/20 text-voxy-green border border-voxy-green/40'
                : 'bg-voxy-card text-voxy-muted border border-voxy-border'
            }`}
          >
            {user.reminders_enabled ? 'ON ✓' : 'OFF'}
          </button>
        </div>

        {/* Admin Broadcast Announcements Toggle */}
        <div className="flex items-center justify-between bg-voxy-secondary rounded-2xl p-3 border border-voxy-border">
          <span className="text-xs font-bold text-voxy-text flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-voxy-blue" /> Broadcast Announcements
          </span>
          <button
            type="button"
            onClick={() =>
              handleToggleSetting('broadcast_enabled', user.broadcast_enabled)
            }
            className={`px-3 py-1 rounded-xl text-xs font-extrabold transition-colors ${
              user.broadcast_enabled
                ? 'bg-voxy-green/20 text-voxy-green border border-voxy-green/40'
                : 'bg-voxy-card text-voxy-muted border border-voxy-border'
            }`}
          >
            {user.broadcast_enabled ? 'ON ✓' : 'OFF'}
          </button>
        </div>
      </div>

      {/* Transparent Analytics Disclaimer */}
      <div className="bg-voxy-secondary/60 border border-voxy-border rounded-2xl p-3 flex items-start gap-2.5 text-[11px] text-voxy-muted">
        <Info className="w-4 h-4 text-voxy-blue shrink-0 mt-0.5" />
        <p>{t(lang, 'profile_disclaimer')}</p>
      </div>
    </motion.div>
  );
};
