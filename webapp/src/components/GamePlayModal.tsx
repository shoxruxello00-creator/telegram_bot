import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import confetti from 'canvas-confetti';
import {
  CheckCircle2,
  Clock,
  Layers,
  Swords,
  Trophy,
  X,
} from 'lucide-react';
import { fetchGameSession, submitQuizAnswers } from '../lib/api';
import { t } from '../lib/i18n';
import { hapticImpact, hapticNotification } from '../lib/telegram';
import { useAppStore } from '../store/useAppStore';
import { GameSessionPayload, VocabularyItem } from '../types/miniapp';
import { VoxyMascot } from './VoxyMascot';

interface GamePlayModalProps {
  onCompleted: () => void;
}

interface MemoryTile {
  uid: string;
  vocabId: number;
  side: 'basic' | 'advanced';
  text: string;
}

export const GamePlayModal: React.FC<GamePlayModalProps> = ({
  onCompleted,
}) => {
  const { lang, activeGameMode, closeModal, setVoxyMood } = useAppStore();
  const [session, setSession] = useState<GameSessionPayload | null>(null);
  const [loading, setLoading] = useState(true);

  // Shared Question Mode State (word_battle, brain_rush, missing_word, synonym_master, ielts_arena, daily_challenge)
  const [qIndex, setQIndex] = useState(0);
  const [selectedOpt, setSelectedOpt] = useState<number | null>(null);
  const [playerScore, setPlayerScore] = useState(0);
  const [botScore, setBotScore] = useState(0);
  const [timeLeft, setTimeLeft] = useState(60);
  const [answersLog, setAnswersLog] = useState<
    Array<{ vocab_id: number; selected_option: number; time_ms: number }>
  >([]);

  // Word Match State
  const [selectedBasicId, setSelectedBasicId] = useState<number | null>(null);
  const [matchedIds, setMatchedIds] = useState<number[]>([]);
  const [wrongPairFlash, setWrongPairFlash] = useState(false);

  // Memory Challenge State
  const [flippedTileUids, setFlippedTileUids] = useState<string[]>([]);
  const [solvedVocabIds, setSolvedVocabIds] = useState<number[]>([]);

  // Final Result State
  const [earnedXp, setEarnedXp] = useState<number | null>(null);

  useEffect(() => {
    if (!activeGameMode) return;
    setLoading(true);
    fetchGameSession(activeGameMode)
      .then((data) => {
        setSession(data);
        setTimeLeft(data.time_limit_sec || 30);
      })
      .finally(() => setLoading(false));
  }, [activeGameMode]);

  // Countdown for Brain Rush
  useEffect(() => {
    if (
      !session ||
      activeGameMode !== 'brain_rush' ||
      earnedXp !== null ||
      loading
    )
      return;
    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          finalizeGameSession(answersLog);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [session, activeGameMode, earnedXp, loading]);

  const matchItems: VocabularyItem[] = useMemo(() => {
    return (session?.items || []).slice(0, 5);
  }, [session]);

  const shuffledAdvancedItems: VocabularyItem[] = useMemo(() => {
    const arr = [...matchItems];
    return arr.reverse();
  }, [matchItems]);

  const memoryTiles: MemoryTile[] = useMemo(() => {
    const subset = (session?.items || []).slice(0, 4);
    const tiles: MemoryTile[] = [];
    subset.forEach((w) => {
      tiles.push({
        uid: `b_${w.id}`,
        vocabId: w.id,
        side: 'basic',
        text: w.simple_word,
      });
      tiles.push({
        uid: `a_${w.id}`,
        vocabId: w.id,
        side: 'advanced',
        text: w.advanced_word,
      });
    });
    // Deterministic interleave shuffle
    return tiles.sort((a, b) => a.text.localeCompare(b.text));
  }, [session]);

  if (!activeGameMode) return null;

  const finalizeGameSession = async (
    finalAnswers: Array<{
      vocab_id: number;
      selected_option: number;
      time_ms: number;
    }>
  ) => {
    try {
      const res = await submitQuizAnswers({
        mode: 'game',
        game_type: activeGameMode,
        answers: finalAnswers,
      });
      setEarnedXp(res.earned_xp);
      setVoxyMood('complete');
      onCompleted();
      try {
        confetti({ particleCount: 60, spread: 70, origin: { y: 0.6 } });
      } catch {
        // ignore
      }
    } catch {
      setEarnedXp(playerScore * 10);
    }
  };

  // Word Match tap handlers
  const handleSelectAdvancedMatch = (advWord: VocabularyItem) => {
    if (selectedBasicId === null) return;
    if (selectedBasicId === advWord.id) {
      hapticNotification('success');
      const nextMatched = [...matchedIds, advWord.id];
      setMatchedIds(nextMatched);
      setSelectedBasicId(null);
      setPlayerScore((s) => s + 1);

      if (nextMatched.length >= matchItems.length) {
        const syntheticAnswers = matchItems.map((w) => ({
          vocab_id: w.id,
          selected_option: w.correct_option,
          time_ms: 1500,
        }));
        finalizeGameSession(syntheticAnswers);
      }
    } else {
      hapticNotification('error');
      setWrongPairFlash(true);
      setTimeout(() => {
        setWrongPairFlash(false);
        setSelectedBasicId(null);
      }, 450);
    }
  };

  // Memory Challenge tap handler
  const handleFlipMemoryTile = (tile: MemoryTile) => {
    if (
      solvedVocabIds.includes(tile.vocabId) ||
      flippedTileUids.includes(tile.uid) ||
      flippedTileUids.length >= 2
    ) {
      return;
    }
    hapticImpact('light');
    const nextFlipped = [...flippedTileUids, tile.uid];
    setFlippedTileUids(nextFlipped);

    if (nextFlipped.length === 2) {
      const t1 = memoryTiles.find((x) => x.uid === nextFlipped[0]);
      const t2 = memoryTiles.find((x) => x.uid === nextFlipped[1]);
      if (t1 && t2 && t1.vocabId === t2.vocabId && t1.side !== t2.side) {
        hapticNotification('success');
        const nextSolved = [...solvedVocabIds, t1.vocabId];
        setSolvedVocabIds(nextSolved);
        setPlayerScore((s) => s + 1);
        setFlippedTileUids([]);

        if (nextSolved.length >= 4) {
          const subset = (session?.items || []).slice(0, 4);
          finalizeGameSession(
            subset.map((w) => ({
              vocab_id: w.id,
              selected_option: w.correct_option,
              time_ms: 2000,
            }))
          );
        }
      } else {
        setTimeout(() => setFlippedTileUids([]), 700);
      }
    }
  };

  // Standard Question Mode answer handler
  const items = session?.items || [];
  const currentItem = items[qIndex];

  const handleQuestionAnswer = (optIdx: number) => {
    if (selectedOpt !== null || !currentItem) return;
    setSelectedOpt(optIdx);
    const isCorrect = optIdx === currentItem.correct_option;
    if (isCorrect) {
      hapticNotification('success');
      setPlayerScore((s) => s + 1);
    } else {
      hapticNotification('warning');
    }
    if (activeGameMode === 'word_battle') {
      // Simulate Cambridge AI opponent accuracy
      if (qIndex % 4 !== 2) {
        setBotScore((b) => b + 1);
      }
    }

    const updatedLog = [
      ...answersLog,
      {
        vocab_id: currentItem.id,
        selected_option: optIdx,
        time_ms: 1800,
      },
    ];
    setAnswersLog(updatedLog);

    setTimeout(() => {
      if (qIndex < items.length - 1) {
        setSelectedOpt(null);
        setQIndex((i) => i + 1);
      } else {
        finalizeGameSession(updatedLog);
      }
    }, 850);
  };

  return (
    <div className="fixed inset-0 z-50 bg-voxy-bg/98 backdrop-blur-xl flex flex-col justify-between p-4 overflow-y-auto">
      {/* Header */}
      <div className="max-w-md w-full mx-auto flex items-center justify-between">
        <div>
          <span className="text-[11px] font-extrabold uppercase tracking-wider text-voxy-blue">
            IELTS ARENA MODE
          </span>
          <h2 className="text-base font-display font-bold text-voxy-text uppercase">
            {activeGameMode.replace('_', ' ')}
          </h2>
        </div>

        <div className="flex items-center gap-2">
          {activeGameMode === 'brain_rush' && earnedXp === null && (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-sky-500/20 border border-sky-400 text-sky-300 text-xs font-extrabold">
              <Clock className="w-3.5 h-3.5" /> {timeLeft}s
            </span>
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

      {/* Body */}
      <div className="max-w-md w-full mx-auto my-auto py-4">
        {loading ? (
          <div className="text-center py-12 space-y-3">
            <VoxyMascot mood="loading" size="md" />
            <p className="text-xs text-voxy-muted font-bold">
              Loading Arena Challenge...
            </p>
          </div>
        ) : earnedXp !== null ? (
          <motion.div
            initial={{ scale: 0.92, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="bg-voxy-card border border-voxy-purple/50 rounded-3xl p-6 text-center space-y-4 shadow-purpleGlow"
          >
            <div className="flex justify-center">
              <VoxyMascot mood="complete" size="lg" />
            </div>
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-voxy-gold/20 text-voxy-gold text-xs font-extrabold">
              <Trophy className="w-4 h-4" /> +{earnedXp} XP REWARDED
            </div>
            <h3 className="text-xl font-display font-extrabold text-voxy-text">
              {t(lang, 'quiz_result_title')}
            </h3>
            {activeGameMode === 'word_battle' && (
              <p className="text-sm font-bold text-voxy-blue">
                You {playerScore} — {botScore} Cambridge Bot AI
              </p>
            )}
            <button
              type="button"
              onClick={closeModal}
              className="w-full py-3.5 px-4 rounded-2xl bg-gradient-to-r from-voxy-purple to-indigo-600 text-white font-bold text-sm"
            >
              {t(lang, 'quiz_back_home')}
            </button>
          </motion.div>
        ) : activeGameMode === 'word_match' ? (
          /* MODE 3: WORD MATCH BOARD */
          <div className="space-y-4">
            <div className="bg-voxy-card border border-voxy-border rounded-2xl p-3 text-xs text-voxy-muted flex items-center justify-between">
              <span className="flex items-center gap-1.5 font-bold text-voxy-text">
                <Layers className="w-4 h-4 text-voxy-green" />
                Tap Basic on left, then matching IELTS Upgrade on right
              </span>
              <span className="font-extrabold text-voxy-green">
                {matchedIds.length}/{matchItems.length}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {/* Left Column: Basic */}
              <div className="space-y-2.5">
                <div className="text-[10px] font-extrabold uppercase text-voxy-muted px-1">
                  🔤 Everyday Basic
                </div>
                {matchItems.map((item) => {
                  const isDone = matchedIds.includes(item.id);
                  const isSelected = selectedBasicId === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      disabled={isDone}
                      onClick={() => {
                        hapticImpact('light');
                        setSelectedBasicId(item.id);
                      }}
                      className={`w-full p-3 rounded-2xl border text-left text-xs font-bold transition-all ${
                        isDone
                          ? 'bg-emerald-500/15 border-voxy-green/40 text-voxy-green opacity-50'
                          : isSelected
                          ? 'bg-voxy-purple/30 border-voxy-purple text-white shadow-purpleGlow'
                          : 'bg-voxy-card border-voxy-border text-voxy-text'
                      }`}
                    >
                      {item.simple_word}
                    </button>
                  );
                })}
              </div>

              {/* Right Column: Advanced */}
              <div className="space-y-2.5">
                <div className="text-[10px] font-extrabold uppercase text-voxy-blue px-1">
                  💎 IELTS Upgrade
                </div>
                {shuffledAdvancedItems.map((item) => {
                  const isDone = matchedIds.includes(item.id);
                  return (
                    <button
                      key={item.id}
                      type="button"
                      disabled={isDone}
                      onClick={() => handleSelectAdvancedMatch(item)}
                      className={`w-full p-3 rounded-2xl border text-left text-xs font-bold transition-all ${
                        isDone
                          ? 'bg-emerald-500/15 border-voxy-green/40 text-voxy-green opacity-50'
                          : wrongPairFlash
                          ? 'bg-rose-500/20 border-rose-500 text-rose-200'
                          : 'bg-voxy-card border-voxy-border text-voxy-blue hover:border-voxy-blue/60'
                      }`}
                    >
                      {item.advanced_word}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        ) : activeGameMode === 'memory_challenge' ? (
          /* MODE 7: MEMORY CHALLENGE 8-TILE GRID */
          <div className="space-y-4">
            <div className="bg-voxy-card border border-voxy-border rounded-2xl p-3 text-xs flex items-center justify-between">
              <span className="font-bold text-voxy-text">
                Flip cards to match Basic ↔ Advanced pairs
              </span>
              <span className="font-extrabold text-voxy-green">
                {solvedVocabIds.length}/4 Pairs
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              {memoryTiles.map((tile) => {
                const isSolved = solvedVocabIds.includes(tile.vocabId);
                const isFlipped =
                  isSolved || flippedTileUids.includes(tile.uid);
                return (
                  <button
                    key={tile.uid}
                    type="button"
                    onClick={() => handleFlipMemoryTile(tile)}
                    className={`h-24 rounded-2xl border-2 p-3 flex flex-col items-center justify-center text-center transition-all ${
                      isSolved
                        ? 'bg-emerald-500/20 border-voxy-green text-voxy-green'
                        : isFlipped
                        ? 'bg-voxy-purple/25 border-voxy-purple text-white'
                        : 'bg-voxy-card border-voxy-border text-voxy-muted hover:border-voxy-blue/40'
                    }`}
                  >
                    {isFlipped ? (
                      <>
                        <span className="text-[9px] font-extrabold uppercase opacity-75 mb-1">
                          {tile.side === 'basic' ? '🔤 Basic' : '💎 IELTS'}
                        </span>
                        <span className="text-xs font-bold leading-tight">
                          {tile.text}
                        </span>
                      </>
                    ) : (
                      <span className="text-lg font-display font-extrabold text-voxy-purple">
                        ?
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          /* MODES 1, 2, 4, 5, 6, 8: INTERACTIVE ARENA & CONTEXT CHALLENGE */
          currentItem && (
            <div className="space-y-4">
              {activeGameMode === 'word_battle' && (
                <div className="bg-voxy-secondary border border-violet-500/40 rounded-2xl p-3 flex items-center justify-between text-xs font-bold">
                  <div className="text-voxy-green">YOU: {playerScore}</div>
                  <div className="flex items-center gap-1 text-violet-300">
                    <Swords className="w-4 h-4" /> VS
                  </div>
                  <div className="text-rose-400">
                    CAMBRIDGE AI: {botScore}
                  </div>
                </div>
              )}

              <div className="bg-voxy-card border border-voxy-border rounded-3xl p-5 space-y-3 shadow-glass">
                <div className="flex items-center justify-between text-xs font-bold">
                  <span className="text-voxy-blue">
                    Question {qIndex + 1}/{items.length}
                  </span>
                  <span className="text-voxy-gold">
                    📊 {currentItem.cefr_level} • {currentItem.ielts_usage}
                  </span>
                </div>

                {activeGameMode === 'missing_word' ? (
                  <>
                    <div className="text-xs font-semibold text-voxy-muted">
                      Complete the sentence for:{' '}
                      <b className="text-voxy-text">{currentItem.simple_word}</b>
                    </div>
                    <h3 className="text-base sm:text-lg font-display font-bold text-voxy-text leading-relaxed">
                      "{currentItem.sentence_with_blank}"
                    </h3>
                  </>
                ) : (
                  <>
                    <div className="text-xs font-semibold text-voxy-muted">
                      🔤 Everyday English:
                    </div>
                    <h3 className="text-xl font-display font-extrabold text-voxy-text">
                      "{currentItem.simple_word}"
                    </h3>
                    <p className="text-xs text-voxy-muted">
                      🇺🇿 {currentItem.translation_uz}
                    </p>
                  </>
                )}
              </div>

              <div className="space-y-2.5">
                {currentItem.options.map((opt, idx) => {
                  const isAnswered = selectedOpt !== null;
                  const isRight = idx === currentItem.correct_option;
                  const isPicked = selectedOpt === idx;
                  return (
                    <button
                      key={idx}
                      type="button"
                      disabled={isAnswered}
                      onClick={() => handleQuestionAnswer(idx)}
                      className={`w-full p-3.5 rounded-2xl border-2 text-left text-xs sm:text-sm font-bold flex items-center justify-between transition-all ${
                        isAnswered && isRight
                          ? 'bg-emerald-500/20 border-voxy-green text-white shadow-greenGlow'
                          : isAnswered && isPicked
                          ? 'bg-rose-500/20 border-rose-500 text-rose-200'
                          : 'bg-voxy-card border-voxy-border text-voxy-text hover:border-voxy-purple'
                      }`}
                    >
                      <span>{opt}</span>
                      {isAnswered && isRight && (
                        <CheckCircle2 className="w-4 h-4 text-voxy-green" />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )
        )}
      </div>

      <div className="h-4" />
    </div>
  );
};
