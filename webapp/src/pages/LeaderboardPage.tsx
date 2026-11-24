import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { ArrowUpRight, Crown, Flame, Trophy, Users } from 'lucide-react';
import { LeagueBadge } from '../components/LeagueBadge';
import { fetchLeaderboard } from '../lib/api';
import { t } from '../lib/i18n';
import { hapticSelection } from '../lib/telegram';
import { useAppStore } from '../store/useAppStore';
import { LeaderboardEntry } from '../types/miniapp';

export const LeaderboardPage: React.FC = () => {
  const { lang } = useAppStore();
  const [tab, setTab] = useState<'weekly' | 'all_time' | 'referrals'>('weekly');

  const { data, isLoading } = useQuery({
    queryKey: ['leaderboard'],
    queryFn: fetchLeaderboard,
  });

  const activeBoard = data?.[tab];
  const entries: LeaderboardEntry[] = activeBoard?.entries || [];
  const topThree = entries.slice(0, 3);
  const restEntries = entries.slice(3);

  const metricUnit = tab === 'referrals' ? 'refs' : 'XP';

  // Arrange podium as [#2, #1, #3]
  const podiumOrder = [topThree[1], topThree[0], topThree[2]].filter(
    Boolean
  ) as LeaderboardEntry[];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-4 pb-24"
    >
      {/* Header & Tabs */}
      <div className="bg-voxy-secondary border border-voxy-border rounded-3xl p-4 shadow-glass space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <span className="inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-voxy-gold">
              <Trophy className="w-3.5 h-3.5" /> Competitive Arena
            </span>
            <h1 className="text-lg sm:text-xl font-display font-bold text-voxy-text mt-0.5">
              {t(lang, 'ranks_header')}
            </h1>
          </div>
          {activeBoard && (
            <div className="bg-voxy-card border border-voxy-purple/40 rounded-2xl px-3 py-1.5 text-center">
              <div className="text-sm font-display font-extrabold text-voxy-blue">
                #{activeBoard.user_rank}
              </div>
              <div className="text-[10px] text-voxy-muted font-semibold">
                {t(lang, 'ranks_your_pos')}
              </div>
            </div>
          )}
        </div>

        {/* 3 Mode Tabs */}
        <div className="grid grid-cols-3 gap-1.5 bg-voxy-bg p-1 rounded-2xl border border-voxy-border">
          {(
            [
              { id: 'weekly', key: 'ranks_tab_weekly' },
              { id: 'all_time', key: 'ranks_tab_alltime' },
              { id: 'referrals', key: 'ranks_tab_referrals' },
            ] as const
          ).map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                hapticSelection();
                setTab(item.id);
              }}
              className={`py-2 px-2 rounded-xl text-xs font-bold transition-all ${
                tab === item.id
                  ? 'bg-gradient-to-r from-voxy-purple to-indigo-600 text-white shadow'
                  : 'text-voxy-muted hover:text-voxy-text'
              }`}
            >
              {t(lang, item.key)}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2.5">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-16 rounded-2xl bg-voxy-card/60 animate-pulse border border-voxy-border"
            />
          ))}
        </div>
      ) : (
        <>
          {/* Animated Top-Three Podium */}
          {podiumOrder.length > 0 && (
            <div className="bg-gradient-to-b from-voxy-secondary/90 to-voxy-card border border-voxy-border rounded-3xl p-4 pt-6 shadow-glass">
              <div className="grid grid-cols-3 gap-2 items-end">
                {podiumOrder.map((entry) => {
                  const isFirst = entry.rank === 1;
                  const isSecond = entry.rank === 2;
                  const initials = entry.full_name
                    .split(' ')
                    .map((p) => p[0])
                    .join('')
                    .slice(0, 2)
                    .toUpperCase();
                  const heightClass = isFirst
                    ? 'h-28 from-amber-500/35 to-yellow-600/10 border-voxy-gold'
                    : isSecond
                    ? 'h-22 from-slate-400/25 to-slate-600/10 border-slate-300/60'
                    : 'h-20 from-amber-700/30 to-orange-900/10 border-amber-500/50';

                  return (
                    <motion.div
                      key={entry.user_id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.4, delay: entry.rank * 0.08 }}
                      className="flex flex-col items-center text-center"
                    >
                      <div className="relative mb-2">
                        {isFirst && (
                          <Crown className="w-5 h-5 text-voxy-gold fill-current mx-auto -mt-3 mb-0.5 animate-bounce" />
                        )}
                        <div
                          className={`w-12 h-12 rounded-2xl flex items-center justify-center font-display font-extrabold text-sm text-white shadow ${
                            isFirst
                              ? 'bg-gradient-to-tr from-amber-500 to-yellow-400 text-slate-950 shadow-goldGlow'
                              : isSecond
                              ? 'bg-gradient-to-tr from-slate-500 to-slate-300 text-slate-950'
                              : 'bg-gradient-to-tr from-amber-700 to-orange-500'
                          }`}
                        >
                          {initials}
                        </div>
                        <span className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 px-2 py-0.2 rounded-full text-[10px] font-extrabold bg-voxy-bg border border-voxy-border text-voxy-text">
                          #{entry.rank}
                        </span>
                      </div>

                      <div className="text-xs font-bold text-voxy-text truncate max-w-[95px] mt-1">
                        {entry.full_name.split(' ')[0]}
                      </div>
                      <div className="text-[11px] font-extrabold text-voxy-gold mb-2">
                        {entry.metric_value.toLocaleString()} {metricUnit}
                      </div>

                      <div
                        className={`w-full rounded-t-2xl bg-gradient-to-b border-t-2 flex flex-col items-center justify-center p-2 ${heightClass}`}
                      >
                        <LeagueBadge
                          leagueId={entry.league_id}
                          size="sm"
                          showLabel={false}
                        />
                        <span className="text-[10px] font-bold text-voxy-muted mt-1">
                          🔥 {entry.streak}d
                        </span>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Ranks #4+ List */}
          <div className="space-y-2">
            {restEntries.map((entry, idx) => (
              <motion.div
                key={entry.user_id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.04 }}
                className={`rounded-2xl p-3.5 border flex items-center justify-between gap-3 ${
                  entry.is_current_user
                    ? 'bg-voxy-purple/20 border-voxy-purple shadow-purpleGlow'
                    : 'bg-voxy-card border-voxy-border'
                }`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="w-7 text-center font-display font-extrabold text-xs text-voxy-muted">
                    #{entry.rank}
                  </span>
                  <div className="w-10 h-10 rounded-xl bg-voxy-secondary border border-voxy-border flex items-center justify-center font-bold text-xs text-voxy-blue shrink-0">
                    {entry.full_name.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs sm:text-sm font-bold text-voxy-text truncate">
                        {entry.full_name}
                      </span>
                      {entry.is_current_user && (
                        <span className="px-1.5 py-0.2 rounded text-[9px] font-extrabold bg-voxy-purple text-white">
                          YOU
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <LeagueBadge leagueId={entry.league_id} size="sm" />
                      <span className="text-[10px] text-voxy-muted flex items-center gap-0.5">
                        <Flame className="w-3 h-3 text-orange-400" />
                        {entry.streak}d
                      </span>
                    </div>
                  </div>
                </div>

                <div className="text-right shrink-0">
                  <div className="text-xs sm:text-sm font-display font-extrabold text-voxy-gold flex items-center justify-end gap-1">
                    {entry.metric_value.toLocaleString()} {metricUnit}
                    <ArrowUpRight className="w-3.5 h-3.5 text-voxy-green" />
                  </div>
                  <div className="text-[10px] text-voxy-muted">
                    {tab === 'referrals' ? (
                      <span className="inline-flex items-center gap-0.5">
                        <Users className="w-3 h-3" /> Verified
                      </span>
                    ) : (
                      entry.badge
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </>
      )}
    </motion.div>
  );
};
