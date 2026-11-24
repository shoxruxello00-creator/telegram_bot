import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BookOpen,
  Check,
  Compass,
  Info,
  Lock,
  Play,
  ShieldAlert,
  Star,
  Zap,
} from 'lucide-react';
import { t } from '../lib/i18n';
import { hapticImpact } from '../lib/telegram';
import { useAppStore } from '../store/useAppStore';
import { JourneyNode, JourneyWorld } from '../types/miniapp';

interface JourneyMapPageProps {
  worlds: JourneyWorld[];
}

export const JourneyMapPage: React.FC<JourneyMapPageProps> = ({ worlds }) => {
  const { lang, openFlashcards, openQuiz } = useAppStore();
  const [selectedNode, setSelectedNode] = useState<JourneyNode | null>(null);

  const totalStars = worlds.reduce((acc, w) => acc + w.stars, 0);
  const maxTotalStars = worlds.reduce((acc, w) => acc + w.max_stars, 0);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-4 pb-24"
    >
      {/* Top Journey Banner */}
      <div className="bg-voxy-secondary border border-voxy-border rounded-3xl p-4 shadow-glass">
        <div className="flex items-center justify-between gap-2">
          <div>
            <span className="inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-voxy-blue">
              <Compass className="w-3.5 h-3.5" /> 6 Worlds • 18 Stages
            </span>
            <h1 className="text-lg sm:text-xl font-display font-bold text-voxy-text mt-0.5">
              {t(lang, 'journey_header')}
            </h1>
            <p className="text-xs text-voxy-muted mt-0.5">
              {t(lang, 'journey_sub')}
            </p>
          </div>
          <div className="bg-voxy-card border border-voxy-gold/40 rounded-2xl px-3.5 py-2 text-center shrink-0">
            <div className="flex items-center justify-center gap-1 text-voxy-gold font-display font-extrabold text-base">
              <Star className="w-4 h-4 fill-current" />
              {totalStars}/{maxTotalStars}
            </div>
            <div className="text-[10px] text-voxy-muted font-semibold">
              Stars Earned
            </div>
          </div>
        </div>
      </div>

      {/* 6 Adventure Worlds */}
      <div className="space-y-4">
        {worlds.map((world, wIdx) => {
          const title =
            lang === 'uz'
              ? world.title_uz
              : lang === 'ru'
              ? world.title_ru
              : world.title_en;
          const subtitle =
            lang === 'uz'
              ? world.subtitle_uz
              : lang === 'ru'
              ? world.subtitle_ru
              : world.subtitle_en;
          const isWorldLocked = world.status === 'locked';

          return (
            <motion.div
              key={world.id}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: wIdx * 0.05 }}
              className={`relative overflow-hidden rounded-3xl bg-gradient-to-br ${
                world.accent
              } bg-voxy-card border ${
                world.status === 'active'
                  ? 'border-voxy-blue/60 shadow-blueGlow'
                  : world.status === 'completed'
                  ? 'border-voxy-green/40'
                  : 'border-voxy-border opacity-80'
              } p-4`}
            >
              {/* World Header */}
              <div className="flex items-start justify-between gap-2 mb-4">
                <div className="flex items-center gap-3">
                  <div
                    className="w-11 h-11 rounded-2xl flex items-center justify-center font-display font-extrabold text-sm text-slate-950 shadow shrink-0"
                    style={{ backgroundColor: world.theme_color }}
                  >
                    {world.cefr}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-base font-display font-bold text-voxy-text">
                        {world.cefr} — {title}
                      </h2>
                      {world.status === 'completed' && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-voxy-green/20 text-voxy-green">
                          CLEAR
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-voxy-muted mt-0.5">{subtitle}</p>
                  </div>
                </div>
                <div className="flex items-center gap-1 bg-black/25 px-2.5 py-1 rounded-xl text-xs font-bold text-voxy-gold shrink-0">
                  <Star className="w-3.5 h-3.5 fill-current" />
                  {world.stars}/{world.max_stars}
                </div>
              </div>

              {/* Winding Adventure Path of 3 Nodes */}
              <div className="relative grid grid-cols-3 gap-2.5 pt-2 pb-1">
                {/* Connecting Path Line */}
                <div className="absolute top-9 left-[16%] right-[16%] h-1 bg-voxy-bg/80 rounded-full overflow-hidden pointer-events-none">
                  <div
                    className="h-full transition-all duration-500"
                    style={{
                      width:
                        world.status === 'completed'
                          ? '100%'
                          : world.status === 'active'
                          ? '55%'
                          : '0%',
                      backgroundColor: world.theme_color,
                    }}
                  />
                </div>

                {world.nodes.map((node) => {
                  const nodeTitle =
                    lang === 'uz'
                      ? node.title_uz
                      : lang === 'ru'
                      ? node.title_ru
                      : node.title_en;
                  const isCompleted = node.status === 'completed';
                  const isActive = node.status === 'active';
                  const isLocked = node.status === 'locked';

                  return (
                    <button
                      key={node.id}
                      type="button"
                      onClick={() => {
                        hapticImpact(isLocked ? 'light' : 'medium');
                        setSelectedNode(node);
                      }}
                      className="relative z-10 flex flex-col items-center text-center group focus:outline-none"
                    >
                      <motion.div
                        animate={
                          isActive
                            ? { scale: [1, 1.08, 1] }
                            : { scale: 1 }
                        }
                        transition={{
                          duration: 1.8,
                          repeat: isActive ? Infinity : 0,
                        }}
                        className={`w-14 h-14 rounded-2xl flex items-center justify-center border-2 transition-all ${
                          isCompleted
                            ? 'bg-voxy-green/20 border-voxy-green text-voxy-green shadow-greenGlow'
                            : isActive
                            ? 'bg-voxy-purple border-voxy-blue text-white shadow-purpleGlow'
                            : 'bg-voxy-secondary border-voxy-border text-voxy-muted'
                        }`}
                      >
                        {isCompleted ? (
                          <Check className="w-6 h-6 stroke-[2.5]" />
                        ) : isActive ? (
                          <Play className="w-6 h-6 fill-current ml-0.5" />
                        ) : (
                          <Lock className="w-5 h-5 opacity-70" />
                        )}
                      </motion.div>

                      {/* 3-Star Rating Display */}
                      <div className="flex items-center gap-0.5 mt-1.5">
                        {[1, 2, 3].map((s) => (
                          <Star
                            key={s}
                            className={`w-3 h-3 ${
                              s <= node.stars
                                ? 'text-voxy-gold fill-current'
                                : 'text-slate-600'
                            }`}
                          />
                        ))}
                      </div>

                      <span className="text-[11px] font-bold text-voxy-text mt-1 line-clamp-1">
                        {nodeTitle}
                      </span>
                      <span className="text-[9px] font-semibold text-voxy-gold">
                        +{node.xp_reward} XP
                      </span>
                    </button>
                  );
                })}
              </div>

              {isWorldLocked && (
                <div className="mt-2 flex items-center justify-center gap-1.5 text-[11px] text-voxy-muted font-medium">
                  <Lock className="w-3 h-3" /> Complete previous world checkpoint to unlock
                </div>
              )}
            </motion.div>
          );
        })}
      </div>

      {/* Selected Node Action Modal */}
      <AnimatePresence>
        {selectedNode && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSelectedNode(null)}
            className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center p-4"
          >
            <motion.div
              initial={{ y: 40, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 40, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md bg-voxy-card border border-voxy-purple/50 rounded-3xl p-5 shadow-glass space-y-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase bg-voxy-purple/25 text-voxy-blue">
                    {selectedNode.cefr} • {selectedNode.type}
                  </span>
                  <h3 className="text-lg font-display font-bold text-voxy-text mt-1.5">
                    {lang === 'uz'
                      ? selectedNode.title_uz
                      : lang === 'ru'
                      ? selectedNode.title_ru
                      : selectedNode.title_en}
                  </h3>
                </div>
                <div className="flex items-center gap-1 text-voxy-gold font-extrabold text-sm">
                  +{selectedNode.xp_reward} XP
                </div>
              </div>

              {/* Preview of Node Expressions */}
              <div className="bg-voxy-secondary/90 border border-voxy-border rounded-2xl p-3 space-y-1.5 max-h-44 overflow-y-auto">
                {selectedNode.words.map((w) => (
                  <div
                    key={w.id}
                    className="flex items-center justify-between text-xs py-1 border-b border-voxy-border last:border-0"
                  >
                    <span className="text-voxy-muted truncate max-w-[44%]">
                      {w.simple_word}
                    </span>
                    <span className="text-voxy-blue font-bold truncate max-w-[52%]">
                      → {w.advanced_word}
                    </span>
                  </div>
                ))}
              </div>

              {selectedNode.status === 'locked' ? (
                <div className="flex items-center gap-2 p-3 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-medium">
                  <ShieldAlert className="w-4 h-4 shrink-0" />
                  Complete the active stage first to unlock this challenge!
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2.5">
                  <button
                    type="button"
                    onClick={() => {
                      const node = selectedNode;
                      setSelectedNode(null);
                      openFlashcards(node.words, node.title_en);
                    }}
                    className="py-3 px-3 rounded-2xl bg-voxy-secondary border border-voxy-border text-voxy-text font-bold text-xs flex items-center justify-center gap-1.5"
                  >
                    <BookOpen className="w-4 h-4 text-voxy-blue" />
                    Study 3D Cards
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const node = selectedNode;
                      setSelectedNode(null);
                      openQuiz({
                        mode: 'journey',
                        nodeId: node.id,
                        title: node.title_en,
                        words: node.words,
                        timedSeconds: 20,
                      });
                    }}
                    className="py-3 px-3 rounded-2xl bg-gradient-to-r from-voxy-purple to-indigo-600 text-white font-bold text-xs flex items-center justify-center gap-1.5 shadow-purpleGlow"
                  >
                    <Zap className="w-4 h-4" />
                    Start Stage Quiz
                  </button>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Transparent Educational Disclaimer (Section 06 requirement) */}
      <div className="bg-voxy-secondary/60 border border-voxy-border rounded-2xl p-3 flex items-start gap-2.5 text-[11px] text-voxy-muted">
        <Info className="w-4 h-4 text-voxy-blue shrink-0 mt-0.5" />
        <p>{t(lang, 'journey_disclaimer')}</p>
      </div>
    </motion.div>
  );
};
