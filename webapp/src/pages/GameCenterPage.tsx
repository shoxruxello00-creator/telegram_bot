import React from 'react';
import { motion } from 'framer-motion';
import {
  Brain,
  CalendarCheck,
  FileQuestion,
  Gamepad2,
  Grid,
  Layers,
  Play,
  Sparkles,
  Swords,
  Target,
  Zap,
} from 'lucide-react';
import { VoxyMascot } from '../components/VoxyMascot';
import { t } from '../lib/i18n';
import { hapticImpact } from '../lib/telegram';
import { useAppStore } from '../store/useAppStore';
import { GameModeId } from '../types/miniapp';

export const GameCenterPage: React.FC = () => {
  const { lang, openGameMode } = useAppStore();

  const gameModes: Array<{
    id: GameModeId;
    titleKey: string;
    descKey: string;
    difficulty: string;
    reward: string;
    Icon: React.ElementType;
    accent: string;
    badgeBg: string;
  }> = [
    {
      id: 'word_battle',
      titleKey: 'game_word_battle_title',
      descKey: 'game_word_battle_desc',
      difficulty: 'B2–C2 Duel',
      reward: '+120 XP',
      Icon: Swords,
      accent: 'from-violet-600/30 via-indigo-900/30 to-voxy-card border-violet-500/50',
      badgeBg: 'bg-violet-500/20 text-violet-300',
    },
    {
      id: 'brain_rush',
      titleKey: 'game_brain_rush_title',
      descKey: 'game_brain_rush_desc',
      difficulty: '60s Speed',
      reward: '+100 XP',
      Icon: Zap,
      accent: 'from-sky-500/30 via-blue-900/30 to-voxy-card border-sky-400/50',
      badgeBg: 'bg-sky-500/20 text-sky-300',
    },
    {
      id: 'word_match',
      titleKey: 'game_word_match_title',
      descKey: 'game_word_match_desc',
      difficulty: 'B2–C1 Pairs',
      reward: '+80 XP',
      Icon: Layers,
      accent: 'from-emerald-500/30 via-teal-900/30 to-voxy-card border-emerald-400/50',
      badgeBg: 'bg-emerald-500/20 text-emerald-300',
    },
    {
      id: 'missing_word',
      titleKey: 'game_missing_word_title',
      descKey: 'game_missing_word_desc',
      difficulty: 'C1 Context',
      reward: '+90 XP',
      Icon: FileQuestion,
      accent: 'from-amber-500/30 via-orange-900/30 to-voxy-card border-amber-400/50',
      badgeBg: 'bg-amber-500/20 text-amber-300',
    },
    {
      id: 'synonym_master',
      titleKey: 'game_synonym_master_title',
      descKey: 'game_synonym_master_desc',
      difficulty: 'C1 Nuance',
      reward: '+90 XP',
      Icon: Brain,
      accent: 'from-fuchsia-500/30 via-purple-900/30 to-voxy-card border-fuchsia-400/50',
      badgeBg: 'bg-fuchsia-500/20 text-fuchsia-300',
    },
    {
      id: 'ielts_arena',
      titleKey: 'game_ielts_arena_title',
      descKey: 'game_ielts_arena_desc',
      difficulty: 'Band 8.0+',
      reward: '+150 XP',
      Icon: Target,
      accent: 'from-rose-500/30 via-red-900/30 to-voxy-card border-rose-400/50',
      badgeBg: 'bg-rose-500/20 text-rose-300',
    },
    {
      id: 'memory_challenge',
      titleKey: 'game_memory_title',
      descKey: 'game_memory_desc',
      difficulty: 'Recall Grid',
      reward: '+85 XP',
      Icon: Grid,
      accent: 'from-cyan-500/30 via-sky-900/30 to-voxy-card border-cyan-400/50',
      badgeBg: 'bg-cyan-500/20 text-cyan-300',
    },
    {
      id: 'daily_challenge',
      titleKey: 'game_daily_title',
      descKey: 'game_daily_desc',
      difficulty: '4+2+2+2 Mix',
      reward: '+110 XP',
      Icon: CalendarCheck,
      accent: 'from-yellow-500/30 via-amber-900/30 to-voxy-card border-yellow-400/50',
      badgeBg: 'bg-yellow-500/20 text-yellow-300',
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-4 pb-24"
    >
      {/* Header Banner */}
      <div className="bg-voxy-secondary border border-voxy-border rounded-3xl p-4 shadow-glass">
        <div className="flex items-center justify-between gap-3">
          <div>
            <span className="inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-voxy-purple">
              <Gamepad2 className="w-3.5 h-3.5" /> 8 Active Modes
            </span>
            <h1 className="text-lg sm:text-xl font-display font-bold text-voxy-text mt-0.5">
              {t(lang, 'games_header')}
            </h1>
            <p className="text-xs text-voxy-muted mt-0.5">
              {t(lang, 'games_sub')}
            </p>
          </div>
          <VoxyMascot mood="celebrate" size="sm" />
        </div>
      </div>

      {/* 8 Game Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {gameModes.map((mode, idx) => {
          const Icon = mode.Icon;
          return (
            <motion.div
              key={mode.id}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.04 }}
              className={`rounded-3xl bg-gradient-to-br ${mode.accent} border p-4 shadow-glass flex flex-col justify-between`}
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <div className="w-11 h-11 rounded-2xl bg-black/30 border border-white/10 flex items-center justify-center text-white">
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold ${mode.badgeBg}`}
                    >
                      {mode.difficulty}
                    </span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-voxy-gold/20 text-voxy-gold">
                      {mode.reward}
                    </span>
                  </div>
                </div>

                <h2 className="text-base font-display font-bold text-voxy-text mt-3">
                  {t(lang, mode.titleKey)}
                </h2>
                <p className="text-xs text-voxy-muted mt-1 leading-relaxed">
                  {t(lang, mode.descKey)}
                </p>
              </div>

              <button
                type="button"
                onClick={() => {
                  hapticImpact('medium');
                  openGameMode(mode.id);
                }}
                className="mt-4 w-full py-2.5 px-3.5 rounded-2xl bg-white/10 hover:bg-white/20 border border-white/15 text-white font-bold text-xs flex items-center justify-center gap-1.5 active:scale-98 transition-all"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                Play {t(lang, mode.titleKey)}
                <Sparkles className="w-3.5 h-3.5 text-voxy-gold ml-0.5" />
              </button>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
};
