import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  BookOpen,
  Check,
  Copy,
  Gift,
  Lock,
  Send,
  Sparkles,
  Users,
  X,
  Zap,
} from 'lucide-react';
import { fetchReferrals } from '../lib/api';
import { t } from '../lib/i18n';
import {
  hapticImpact,
  hapticNotification,
  shareViaTelegram,
} from '../lib/telegram';
import { useAppStore } from '../store/useAppStore';

export const ReferralsModal: React.FC = () => {
  const { lang, closeModal, openFlashcards, openQuiz } = useAppStore();
  const [copied, setCopied] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['referrals'],
    queryFn: fetchReferrals,
  });

  const handleCopyLink = async () => {
    if (!data?.referral_link) return;
    hapticNotification('success');
    try {
      await navigator.clipboard.writeText(data.referral_link);
    } catch {
      // Fallback
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2200);
  };

  return (
    <div className="fixed inset-0 z-50 bg-voxy-bg/98 backdrop-blur-xl flex flex-col justify-between p-4 overflow-y-auto">
      <div className="max-w-md w-full mx-auto space-y-4 pb-8">
        {/* Top Header */}
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-voxy-gold flex items-center gap-1">
              <Gift className="w-3.5 h-3.5" /> IELTS Ambassador Rewards
            </span>
            <h2 className="text-base sm:text-lg font-display font-bold text-voxy-text mt-0.5">
              {t(lang, 'referral_title')}
            </h2>
          </div>
          <button
            type="button"
            onClick={closeModal}
            className="w-9 h-9 rounded-xl bg-voxy-card border border-voxy-border flex items-center justify-center text-voxy-muted"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {isLoading || !data ? (
          <div className="space-y-3 py-8">
            <div className="h-32 rounded-3xl bg-voxy-card animate-pulse" />
            <div className="h-48 rounded-3xl bg-voxy-card animate-pulse" />
          </div>
        ) : (
          <>
            {/* Stats Summary Card */}
            <div className="grid grid-cols-3 gap-2.5">
              <div className="bg-voxy-card border border-voxy-border rounded-2xl p-3 text-center">
                <div className="text-lg font-display font-extrabold text-voxy-text">
                  {data.invited}
                </div>
                <div className="text-[10px] text-voxy-muted font-bold">
                  {t(lang, 'referral_invited')}
                </div>
              </div>
              <div className="bg-voxy-card border border-voxy-green/40 rounded-2xl p-3 text-center">
                <div className="text-lg font-display font-extrabold text-voxy-green">
                  {data.confirmed}
                </div>
                <div className="text-[10px] text-voxy-muted font-bold">
                  {t(lang, 'referral_confirmed')}
                </div>
              </div>
              <div className="bg-voxy-card border border-voxy-gold/40 rounded-2xl p-3 text-center">
                <div className="text-lg font-display font-extrabold text-voxy-gold">
                  {data.unlocked_count}/5
                </div>
                <div className="text-[10px] text-voxy-muted font-bold">
                  {t(lang, 'referral_unlocked')}
                </div>
              </div>
            </div>

            {/* Personal Link & Share Box */}
            <div className="bg-gradient-to-br from-voxy-purple/25 via-voxy-card to-voxy-secondary border border-voxy-purple/40 rounded-3xl p-4 space-y-3 shadow-purpleGlow">
              <div className="flex items-center justify-between text-xs font-bold">
                <span className="text-voxy-blue flex items-center gap-1.5">
                  <Users className="w-4 h-4" /> Personal Referral Link
                </span>
                <span className="text-voxy-gold">
                  Progress: {data.confirmed}/{data.next_reward_target}
                </span>
              </div>

              <div className="bg-voxy-bg/90 border border-voxy-border rounded-2xl p-2.5 flex items-center justify-between gap-2">
                <code className="text-[11px] text-voxy-text truncate select-all">
                  {data.referral_link}
                </code>
                <button
                  type="button"
                  onClick={handleCopyLink}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1 shrink-0 transition-all ${
                    copied
                      ? 'bg-voxy-green text-slate-950'
                      : 'bg-voxy-purple text-white'
                  }`}
                >
                  {copied ? (
                    <>
                      <Check className="w-3.5 h-3.5" />
                      {t(lang, 'referral_copied')}
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      {t(lang, 'referral_copy')}
                    </>
                  )}
                </button>
              </div>

              <button
                type="button"
                onClick={() => shareViaTelegram(data.share_url)}
                className="w-full py-3 px-4 rounded-2xl bg-gradient-to-r from-sky-500 to-indigo-600 text-white font-extrabold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-lg active:scale-98"
              >
                <Send className="w-4 h-4" />
                {t(lang, 'referral_share_tg')}
              </button>
            </div>

            {/* 5-Milestone Timeline (1, 3, 5, 10, 20) */}
            <div className="space-y-2.5">
              <h3 className="text-xs sm:text-sm font-display font-bold text-voxy-text flex items-center gap-1.5 px-1">
                <Sparkles className="w-4 h-4 text-voxy-gold" />
                {t(lang, 'referral_timeline')}
              </h3>

              {data.milestones.map((m, idx) => {
                const pct = Math.min(
                  100,
                  Math.round((m.progress / m.required_referrals) * 100)
                );
                return (
                  <motion.div
                    key={m.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.05 }}
                    className={`rounded-3xl p-4 border ${
                      m.unlocked
                        ? 'bg-voxy-card border-voxy-green/50 shadow-glass'
                        : 'bg-voxy-secondary/70 border-voxy-border'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-extrabold ${
                            m.unlocked
                              ? 'bg-voxy-green/20 text-voxy-green'
                              : 'bg-voxy-bg text-voxy-muted'
                          }`}
                        >
                          {m.unlocked ? '✓ UNLOCKED' : `🔒 ${m.required_referrals} Referrals`}
                        </span>
                        <h4 className="text-sm sm:text-base font-display font-bold text-voxy-text mt-1.5">
                          {m.title}
                        </h4>
                      </div>
                      <span className="text-xs font-extrabold text-voxy-gold">
                        {m.progress}/{m.required_referrals}
                      </span>
                    </div>

                    <div className="mt-2.5 h-2 bg-voxy-bg rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          m.unlocked ? 'bg-voxy-green' : 'bg-voxy-purple'
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>

                    {m.unlocked ? (
                      <div className="grid grid-cols-2 gap-2 mt-3">
                        <button
                          type="button"
                          onClick={() => {
                            hapticImpact('light');
                            openFlashcards(m.words, m.title);
                          }}
                          className="py-2 px-3 rounded-xl bg-voxy-secondary border border-voxy-border text-voxy-text font-bold text-xs flex items-center justify-center gap-1.5"
                        >
                          <BookOpen className="w-3.5 h-3.5 text-voxy-blue" />
                          3D Cards
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            hapticImpact('medium');
                            openQuiz({
                              mode: 'pack',
                              title: m.title,
                              words: m.words,
                              timedSeconds: 20,
                            });
                          }}
                          className="py-2 px-3 rounded-xl bg-voxy-green/20 border border-voxy-green/40 text-voxy-green font-bold text-xs flex items-center justify-center gap-1.5"
                        >
                          <Zap className="w-3.5 h-3.5" />
                          Pack Quiz
                        </button>
                      </div>
                    ) : (
                      <div className="mt-2.5 flex items-center gap-1.5 text-[11px] text-voxy-muted">
                        <Lock className="w-3.5 h-3.5" /> Invite{' '}
                        {Math.max(0, m.required_referrals - data.confirmed)} more
                        confirmed friend(s) to unlock
                      </div>
                    )}
                  </motion.div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
};
