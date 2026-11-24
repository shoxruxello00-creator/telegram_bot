import React, { useState } from 'react';
import { motion } from 'framer-motion';
import confetti from 'canvas-confetti';
import {
  Check,
  RotateCcw,
  Sparkles,
  Volume2,
  X,
  Zap,
} from 'lucide-react';
import { submitFlashcardAction } from '../lib/api';
import { t } from '../lib/i18n';
import {
  hapticImpact,
  hapticNotification,
  speakEnglishExpression,
} from '../lib/telegram';
import { useAppStore } from '../store/useAppStore';
import { VoxyMascot } from './VoxyMascot';

interface FlashcardsModalProps {
  onSynced: () => void;
}

export const FlashcardsModal: React.FC<FlashcardsModalProps> = ({
  onSynced,
}) => {
  const {
    lang,
    flashcardWords,
    flashcardTitle,
    closeModal,
    openQuiz,
    setVoxyMood,
  } = useAppStore();

  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [memorizedCount, setMemorizedCount] = useState(0);
  const [earnedXpTotal, setEarnedXpTotal] = useState(0);
  const [finished, setFinished] = useState(false);

  const words = flashcardWords;
  const total = words.length;
  const currentWord = words[currentIndex];

  if (!words.length) {
    return null;
  }

  const handleCardDecision = async (action: 'memorized' | 'review') => {
    if (!currentWord) return;
    if (action === 'memorized') {
      hapticNotification('success');
      setMemorizedCount((c) => c + 1);
      setVoxyMood('celebrate');
    } else {
      hapticImpact('light');
      setVoxyMood('encourage');
    }

    const isLast = currentIndex >= total - 1;
    try {
      const res = await submitFlashcardAction({
        vocabulary_id: currentWord.id,
        action,
        all_memorized: isLast,
      });
      if (res.xp_gained > 0) {
        setEarnedXpTotal((x) => x + res.xp_gained);
      }
      onSynced();
    } catch {
      // resilient offline continue
    }

    setIsFlipped(false);
    if (isLast) {
      setFinished(true);
      setVoxyMood('complete');
      try {
        confetti({ particleCount: 55, spread: 65, origin: { y: 0.65 } });
      } catch {
        // ignore
      }
    } else {
      setCurrentIndex((i) => i + 1);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-voxy-bg/95 backdrop-blur-xl flex flex-col justify-between p-4 overflow-y-auto">
      {/* Top Header & Progress Bar */}
      <div className="max-w-md w-full mx-auto space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-voxy-blue">
              {t(lang, 'flashcards_title')}
            </span>
            <h2 className="text-base font-display font-bold text-voxy-text truncate max-w-[240px]">
              {flashcardTitle}
            </h2>
          </div>
          <button
            type="button"
            aria-label="Close Flashcards"
            onClick={() => {
              hapticImpact('light');
              closeModal();
            }}
            className="w-9 h-9 rounded-xl bg-voxy-card border border-voxy-border flex items-center justify-center text-voxy-muted hover:text-voxy-text"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Progress Bar */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-2.5 bg-voxy-secondary rounded-full overflow-hidden p-0.5 border border-voxy-border">
            <motion.div
              animate={{
                width: `${finished ? 100 : Math.round(((currentIndex + 1) / total) * 100)}%`,
              }}
              className="h-full rounded-full bg-gradient-to-r from-voxy-purple to-voxy-blue"
            />
          </div>
          <span className="text-xs font-extrabold text-voxy-text">
            {finished ? total : currentIndex + 1}/{total}
          </span>
        </div>
      </div>

      {/* Main Content Area: Either 3D Flip Card OR Completion Screen */}
      {finished ? (
        <motion.div
          initial={{ scale: 0.92, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="max-w-md w-full mx-auto my-auto bg-voxy-card border border-voxy-purple/50 rounded-3xl p-6 text-center space-y-5 shadow-purpleGlow"
        >
          <div className="flex justify-center">
            <VoxyMascot mood="complete" size="lg" />
          </div>
          <div>
            <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-voxy-green/20 text-voxy-green">
              +{earnedXpTotal} XP EARNED
            </span>
            <h3 className="text-xl font-display font-bold text-voxy-text mt-3">
              {t(lang, 'voxy_complete')}
            </h3>
            <p className="text-xs text-voxy-muted mt-1">
              Memorized: {memorizedCount}/{total} expressions
            </p>
          </div>

          <div className="space-y-2.5 pt-2">
            <button
              type="button"
              onClick={() => {
                hapticImpact('heavy');
                openQuiz({
                  mode: 'daily',
                  title: flashcardTitle,
                  words,
                  timedSeconds: 20,
                });
              }}
              className="w-full py-3.5 px-4 rounded-2xl bg-gradient-to-r from-voxy-purple to-indigo-600 text-white font-bold text-sm flex items-center justify-center gap-2 shadow-purpleGlow"
            >
              <Zap className="w-4 h-4" />
              {t(lang, 'flashcard_finish_quiz')}
            </button>
            <button
              type="button"
              onClick={closeModal}
              className="w-full py-3 px-4 rounded-2xl bg-voxy-secondary border border-voxy-border text-voxy-muted font-bold text-xs"
            >
              {t(lang, 'quiz_back_home')}
            </button>
          </div>
        </motion.div>
      ) : (
        <div className="max-w-md w-full mx-auto my-4 flex-1 flex flex-col justify-center">
          {/* 3D Perspective Container */}
          <div className="perspective-1000 w-full">
            <motion.div
              key={currentWord.id}
              drag="x"
              dragConstraints={{ left: 0, right: 0 }}
              onDragEnd={(_, info) => {
                if (info.offset.x > 85) {
                  handleCardDecision('memorized');
                } else if (info.offset.x < -85) {
                  handleCardDecision('review');
                }
              }}
              onClick={() => {
                hapticImpact('light');
                setIsFlipped((f) => !f);
              }}
              animate={{ rotateY: isFlipped ? 180 : 0 }}
              transition={{ type: 'spring', stiffness: 260, damping: 24 }}
              className="relative w-full min-h-[370px] cursor-pointer preserve-3d select-none"
            >
              {/* FRONT SIDE: Everyday Basic English */}
              <div
                className={`absolute inset-0 backface-hidden rounded-3xl bg-gradient-to-b from-voxy-card to-voxy-secondary border-2 border-voxy-purple/40 p-6 flex flex-col justify-between shadow-glass ${
                  isFlipped ? 'pointer-events-none' : ''
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="px-3 py-1 rounded-full text-[11px] font-bold bg-voxy-purple/20 text-voxy-blue border border-voxy-purple/30">
                    {currentWord.category.replace('_', ' ').toUpperCase()}
                  </span>
                  <span className="px-2.5 py-1 rounded-xl text-xs font-extrabold bg-voxy-gold/20 text-voxy-gold">
                    📊 {currentWord.cefr_level}
                  </span>
                </div>

                <div className="my-auto text-center space-y-4">
                  <span className="text-[11px] font-extrabold uppercase tracking-widest text-voxy-muted">
                    🔤 {t(lang, 'flashcard_basic_label')}
                  </span>
                  <h3 className="text-2xl sm:text-3xl font-display font-extrabold text-voxy-text leading-tight">
                    {currentWord.simple_word}
                  </h3>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      speakEnglishExpression(currentWord.simple_word);
                    }}
                    className="mx-auto inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-voxy-bg/80 border border-voxy-border text-xs font-bold text-voxy-blue hover:bg-voxy-bg"
                  >
                    <Volume2 className="w-4 h-4" /> Pronounce
                  </button>

                  <div className="bg-voxy-bg/60 border border-voxy-border rounded-2xl p-3.5 text-left">
                    <div className="text-[10px] font-bold uppercase text-voxy-muted mb-1">
                      ✍️ BASIC SENTENCE
                    </div>
                    <p className="text-xs sm:text-sm text-voxy-text italic">
                      "{currentWord.basic_example_en}"
                    </p>
                  </div>
                </div>

                <div className="text-center text-[11px] font-semibold text-voxy-blue flex items-center justify-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5" />
                  {t(lang, 'flashcard_tap_flip')}
                </div>
              </div>

              {/* BACK SIDE: Advanced IELTS Upgrade + Translations + Usage */}
              <div
                className={`absolute inset-0 backface-hidden rotate-y-180 rounded-3xl bg-gradient-to-b from-[#1E1B4B] via-voxy-card to-voxy-secondary border-2 border-voxy-green/50 p-5 flex flex-col justify-between shadow-greenGlow ${
                  !isFlipped ? 'pointer-events-none' : ''
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="px-2.5 py-1 rounded-full text-[10px] font-extrabold bg-voxy-green/20 text-voxy-green border border-voxy-green/40">
                    💎 {t(lang, 'flashcard_adv_label')}
                  </span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      speakEnglishExpression(currentWord.advanced_word);
                    }}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-white/10 text-xs font-bold text-voxy-blue"
                  >
                    <Volume2 className="w-3.5 h-3.5" /> Audio
                  </button>
                </div>

                <div className="space-y-2.5 my-auto">
                  <div className="text-xs text-slate-400 font-semibold">
                    🔤 BASIC: <span className="line-through">{currentWord.simple_word}</span>
                  </div>
                  <h3 className="text-xl sm:text-2xl font-display font-extrabold text-voxy-green leading-snug">
                    💎 {currentWord.advanced_word}
                  </h3>

                  {/* Trilingual Translations & Formality Note */}
                  <div className="bg-black/30 border border-white/10 rounded-2xl p-3 space-y-1 text-xs">
                    <div>
                      <span className="font-bold text-voxy-blue">🇺🇿 Tarjima: </span>
                      <span className="text-slate-100">{currentWord.translation_uz}</span>
                    </div>
                    <div>
                      <span className="font-bold text-voxy-purple">🇷🇺 Перевод: </span>
                      <span className="text-slate-100">{currentWord.translation_ru}</span>
                    </div>
                    <div className="pt-1 text-[11px] text-slate-300 italic">
                      💡 {currentWord.definition_en}
                    </div>
                  </div>

                  {/* Basic vs Advanced Example Contrast */}
                  <div className="bg-black/30 border border-white/10 rounded-2xl p-3 space-y-1 text-xs">
                    <div className="text-slate-400">
                      <span className="font-bold">✍️ BASIC:</span> "{currentWord.basic_example_en}"
                    </div>
                    <div className="text-voxy-green font-medium">
                      <span className="font-bold">🎓 ADVANCED:</span> "{currentWord.example_en}"
                    </div>
                    <div className="text-[11px] text-slate-300 italic pt-0.5">
                      📝{' '}
                      {lang === 'ru'
                        ? currentWord.example_ru
                        : currentWord.example_uz}
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] font-bold pt-1">
                  <span className="text-voxy-gold">
                    📚 IELTS Usage: {currentWord.ielts_usage}
                  </span>
                  <span className="text-slate-300">📊 {currentWord.cefr_level}</span>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      )}

      {/* Bottom Swipe / Action Controls */}
      {!finished && (
        <div className="max-w-md w-full mx-auto grid grid-cols-2 gap-3 pt-2">
          <button
            type="button"
            onClick={() => handleCardDecision('review')}
            className="py-3.5 px-4 rounded-2xl bg-voxy-card border border-amber-500/40 text-amber-300 font-bold text-xs sm:text-sm flex items-center justify-center gap-2 active:scale-95 transition-transform"
          >
            <RotateCcw className="w-4 h-4" />
            {t(lang, 'flashcard_swipe_left')}
          </button>
          <button
            type="button"
            onClick={() => handleCardDecision('memorized')}
            className="py-3.5 px-4 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-600 text-slate-950 font-extrabold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-greenGlow active:scale-95 transition-transform"
          >
            <Check className="w-4 h-4 stroke-[3]" />
            {t(lang, 'flashcard_swipe_right')}
          </button>
        </div>
      )}
    </div>
  );
};
