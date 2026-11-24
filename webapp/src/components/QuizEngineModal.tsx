import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import confetti from 'canvas-confetti';
import {
  CheckCircle2,
  Clock,
  Flame,
  Sparkles,
  Trophy,
  X,
  XCircle,
} from 'lucide-react';
import { submitQuizAnswers } from '../lib/api';
import { t } from '../lib/i18n';
import { hapticImpact, hapticNotification } from '../lib/telegram';
import { useAppStore } from '../store/useAppStore';
import { VoxyMascot } from './VoxyMascot';

interface QuizEngineModalProps {
  onCompleted: () => void;
}

export const QuizEngineModal: React.FC<QuizEngineModalProps> = ({
  onCompleted,
}) => {
  const { lang, quizConfig, closeModal, setVoxyMood } = useAppStore();

  const words = quizConfig?.words || [];
  const total = words.length;
  const timePerQuestion = quizConfig?.timedSeconds || 20;

  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [combo, setCombo] = useState(0);
  const [timeLeft, setTimeLeft] = useState(timePerQuestion);
  const [questionStartMs, setQuestionStartMs] = useState(Date.now());
  const [answersLog, setAnswersLog] = useState<
    Array<{ vocab_id: number; selected_option: number; time_ms: number }>
  >([]);
  const [submitting, setSubmitting] = useState(false);
  const [finalResult, setFinalResult] = useState<Awaited<
    ReturnType<typeof submitQuizAnswers>
  > | null>(null);

  const currentWord = words[currentIndex];

  useEffect(() => {
    if (finalResult || selectedOption !== null || !currentWord) return;
    setTimeLeft(timePerQuestion);
    setQuestionStartMs(Date.now());

    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          handleSelectOption(-1);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [currentIndex, finalResult, selectedOption]);

  if (!quizConfig || !words.length) return null;

  const handleSelectOption = (optIdx: number) => {
    if (selectedOption !== null || !currentWord) return;
    const elapsed = Math.max(200, Date.now() - questionStartMs);
    setSelectedOption(optIdx);

    const isCorrect = optIdx === currentWord.correct_option;
    if (isCorrect) {
      hapticNotification('success');
      setCombo((c) => c + 1);
      setVoxyMood('celebrate');
    } else {
      hapticNotification('warning');
      setCombo(0);
      setVoxyMood('encourage');
    }

    setAnswersLog((prev) => [
      ...prev,
      {
        vocab_id: currentWord.id,
        selected_option: optIdx,
        time_ms: elapsed,
      },
    ]);
  };

  const handleNextOrFinish = async () => {
    hapticImpact('medium');
    if (currentIndex < total - 1) {
      setSelectedOption(null);
      setCurrentIndex((i) => i + 1);
      return;
    }

    setSubmitting(true);
    try {
      const res = await submitQuizAnswers({
        mode: quizConfig.mode,
        node_id: quizConfig.nodeId,
        answers: answersLog,
      });
      setFinalResult(res);
      setVoxyMood(res.leveled_up ? 'levelup' : 'complete');
      onCompleted();
      if (res.accuracy >= 60) {
        try {
          confetti({ particleCount: 70, spread: 75, origin: { y: 0.6 } });
        } catch {
          // ignore
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const questionPrompt =
    lang === 'uz'
      ? currentWord?.quiz_question_uz ||
        `«${currentWord?.simple_word}» ifodasining tabiiy IELTS upgrade variantini tanlang:`
      : lang === 'ru'
      ? currentWord?.quiz_question_ru ||
        `Выберите продвинутый IELTS эквивалент для «${currentWord?.simple_word}»:`
      : currentWord?.quiz_question_en ||
        `Which advanced IELTS expression best upgrades "${currentWord?.simple_word}"?`;

  return (
    <div className="fixed inset-0 z-50 bg-voxy-bg/98 backdrop-blur-xl flex flex-col justify-between p-4 overflow-y-auto">
      {/* Top Bar */}
      <div className="max-w-md w-full mx-auto space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-voxy-purple">
              IELTS MASTERY QUIZ
            </span>
            <h2 className="text-sm sm:text-base font-display font-bold text-voxy-text truncate max-w-[210px]">
              {quizConfig.title}
            </h2>
          </div>

          <div className="flex items-center gap-2">
            {combo >= 2 && !finalResult && (
              <motion.span
                initial={{ scale: 0.7 }}
                animate={{ scale: 1 }}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-orange-500/20 border border-orange-400/50 text-orange-300 text-xs font-extrabold"
              >
                <Flame className="w-3.5 h-3.5 fill-current" />
                {combo}x {t(lang, 'quiz_combo')}
              </motion.span>
            )}
            {!finalResult && (
              <div
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-xl border text-xs font-extrabold ${
                  timeLeft <= 5
                    ? 'bg-rose-500/20 border-rose-500 text-rose-300 animate-pulse'
                    : 'bg-voxy-card border-voxy-border text-voxy-blue'
                }`}
              >
                <Clock className="w-3.5 h-3.5" />
                {timeLeft}s
              </div>
            )}
            <button
              type="button"
              onClick={closeModal}
              className="w-9 h-9 rounded-xl bg-voxy-card border border-voxy-border flex items-center justify-center text-voxy-muted"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Question Progress Bar */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-2.5 bg-voxy-secondary rounded-full overflow-hidden p-0.5 border border-voxy-border">
            <motion.div
              animate={{
                width: `${
                  finalResult
                    ? 100
                    : Math.round(((currentIndex + 1) / total) * 100)
                }%`,
              }}
              className="h-full rounded-full bg-gradient-to-r from-voxy-purple to-voxy-green"
            />
          </div>
          <span className="text-xs font-extrabold text-voxy-text">
            {finalResult ? total : currentIndex + 1}/{total}
          </span>
        </div>
      </div>

      {/* Main Quiz Body or Final Performance Screen */}
      {finalResult ? (
        <motion.div
          initial={{ opacity: 0, scale: 0.94 }}
          animate={{ opacity: 1, scale: 1 }}
          className="max-w-md w-full mx-auto my-4 bg-voxy-card border border-voxy-purple/50 rounded-3xl p-5 space-y-4 shadow-purpleGlow"
        >
          <div className="flex items-center justify-between">
            <VoxyMascot
              mood={finalResult.leveled_up ? 'levelup' : 'complete'}
              size="md"
              message={t(lang, 'voxy_complete')}
            />
          </div>

          <div className="text-center pt-1">
            <h3 className="text-xl font-display font-extrabold text-voxy-text">
              {t(lang, 'quiz_result_title')}
            </h3>
            {finalResult.leveled_up && (
              <div className="mt-1 inline-flex items-center gap-1 px-3 py-1 rounded-full bg-voxy-gold/20 border border-voxy-gold text-voxy-gold text-xs font-extrabold">
                <Trophy className="w-3.5 h-3.5" /> LEVEL UP! Level{' '}
                {finalResult.level_info.level}
              </div>
            )}
          </div>

          {/* 3 Metric Cards */}
          <div className="grid grid-cols-3 gap-2.5">
            <div className="bg-voxy-secondary border border-voxy-border rounded-2xl p-3 text-center">
              <div className="text-lg font-display font-extrabold text-voxy-green">
                {finalResult.score}/{finalResult.total}
              </div>
              <div className="text-[10px] text-voxy-muted font-bold uppercase">
                Score
              </div>
            </div>
            <div className="bg-voxy-secondary border border-voxy-border rounded-2xl p-3 text-center">
              <div className="text-lg font-display font-extrabold text-voxy-blue">
                {finalResult.accuracy}%
              </div>
              <div className="text-[10px] text-voxy-muted font-bold uppercase">
                {t(lang, 'quiz_accuracy')}
              </div>
            </div>
            <div className="bg-voxy-secondary border border-voxy-border rounded-2xl p-3 text-center">
              <div className="text-lg font-display font-extrabold text-voxy-gold">
                +{finalResult.earned_xp}
              </div>
              <div className="text-[10px] text-voxy-muted font-bold uppercase">
                {t(lang, 'quiz_earned_xp')}
              </div>
            </div>
          </div>

          {/* Answer Breakdown List */}
          <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1">
            {finalResult.results.map((r, idx) => (
              <div
                key={idx}
                className={`p-2.5 rounded-xl border text-xs flex items-center justify-between ${
                  r.is_correct
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
                    : 'bg-rose-500/10 border-rose-500/30 text-rose-200'
                }`}
              >
                <span className="truncate max-w-[45%]">{r.simple_word}</span>
                <span className="font-bold truncate max-w-[50%]">
                  {r.is_correct ? '✓' : '✗'} {r.advanced_word}
                </span>
              </div>
            ))}
          </div>

          <button
            type="button"
            onClick={closeModal}
            className="w-full py-3.5 px-4 rounded-2xl bg-gradient-to-r from-voxy-purple to-indigo-600 text-white font-bold text-sm shadow-purpleGlow"
          >
            {t(lang, 'quiz_back_home')}
          </button>
        </motion.div>
      ) : (
        <div className="max-w-md w-full mx-auto my-auto space-y-4 py-3">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentWord.id}
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -24 }}
              transition={{ duration: 0.22 }}
              className="space-y-4"
            >
              {/* Question Card */}
              <div className="bg-voxy-card border border-voxy-border rounded-3xl p-5 shadow-glass space-y-3">
                <div className="flex items-center justify-between">
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-voxy-purple/25 text-voxy-blue">
                    🔤 BASIC: {currentWord.simple_word}
                  </span>
                  <span className="text-[11px] font-bold text-voxy-gold">
                    📊 {currentWord.cefr_level}
                  </span>
                </div>

                <h3 className="text-base sm:text-lg font-display font-bold text-voxy-text leading-snug">
                  {questionPrompt}
                </h3>

                <div className="bg-voxy-secondary/70 border border-voxy-border rounded-2xl p-3 text-xs text-voxy-muted italic">
                  ✍️ Basic: "{currentWord.basic_example_en}"
                </div>
              </div>

              {/* 4 Answer Buttons */}
              <div className="space-y-2.5">
                {currentWord.options.map((optionText, idx) => {
                  const letters = ['A', 'B', 'C', 'D'];
                  const isAnswered = selectedOption !== null;
                  const isCorrectOption = idx === currentWord.correct_option;
                  const isSelected = selectedOption === idx;

                  let btnStyle =
                    'bg-voxy-card border-voxy-border text-voxy-text hover:border-voxy-purple/60';
                  if (isAnswered) {
                    if (isCorrectOption) {
                      btnStyle =
                        'bg-emerald-500/20 border-voxy-green text-white shadow-greenGlow';
                    } else if (isSelected) {
                      btnStyle =
                        'bg-rose-500/20 border-rose-500 text-rose-200';
                    } else {
                      btnStyle =
                        'bg-voxy-secondary/50 border-voxy-border text-voxy-muted opacity-60';
                    }
                  }

                  return (
                    <motion.button
                      key={idx}
                      type="button"
                      disabled={isAnswered}
                      whileTap={{ scale: isAnswered ? 1 : 0.98 }}
                      onClick={() => handleSelectOption(idx)}
                      className={`w-full p-3.5 rounded-2xl border-2 text-left flex items-center justify-between gap-3 transition-all ${btnStyle}`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <span
                          className={`w-8 h-8 rounded-xl flex items-center justify-center font-display font-extrabold text-xs shrink-0 ${
                            isAnswered && isCorrectOption
                              ? 'bg-voxy-green text-slate-950'
                              : isAnswered && isSelected
                              ? 'bg-rose-500 text-white'
                              : 'bg-voxy-secondary text-voxy-blue'
                          }`}
                        >
                          {letters[idx]}
                        </span>
                        <span className="text-xs sm:text-sm font-bold truncate">
                          {optionText}
                        </span>
                      </div>

                      {isAnswered && isCorrectOption && (
                        <CheckCircle2 className="w-5 h-5 text-voxy-green shrink-0" />
                      )}
                      {isAnswered && isSelected && !isCorrectOption && (
                        <XCircle className="w-5 h-5 text-rose-400 shrink-0" />
                      )}
                    </motion.button>
                  );
                })}
              </div>

              {/* Constructive Feedback & Formality Explanation Box */}
              {selectedOption !== null && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`rounded-2xl p-3.5 border text-xs space-y-1.5 ${
                    selectedOption === currentWord.correct_option
                      ? 'bg-emerald-950/60 border-voxy-green/50 text-emerald-100'
                      : 'bg-slate-900/90 border-voxy-blue/40 text-slate-200'
                  }`}
                >
                  <div className="font-extrabold flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-voxy-gold" />
                    💎 {currentWord.advanced_word} —{' '}
                    {lang === 'ru'
                      ? currentWord.translation_ru
                      : currentWord.translation_uz}
                  </div>
                  <p className="text-[11px] opacity-90">
                    💡 {currentWord.definition_en}
                  </p>
                  <p className="text-[11px] text-voxy-green italic">
                    🎓 "{currentWord.example_en}" ({currentWord.ielts_usage})
                  </p>
                </motion.div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      )}

      {/* Bottom Next Button */}
      {!finalResult && (
        <div className="max-w-md w-full mx-auto pt-2">
          <button
            type="button"
            disabled={selectedOption === null || submitting}
            onClick={handleNextOrFinish}
            className={`w-full py-3.5 px-4 rounded-2xl font-extrabold text-sm transition-all ${
              selectedOption !== null
                ? 'bg-gradient-to-r from-voxy-purple to-voxy-blue text-white shadow-purpleGlow'
                : 'bg-voxy-secondary text-voxy-muted opacity-50 cursor-not-allowed'
            }`}
          >
            {submitting
              ? 'Validating Score...'
              : currentIndex < total - 1
              ? t(lang, 'quiz_next')
              : t(lang, 'quiz_finish')}
          </button>
        </div>
      )}
    </div>
  );
};
