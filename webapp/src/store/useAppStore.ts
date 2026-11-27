import { create } from 'zustand';
import {
  GameModeId,
  LanguageCode,
  TabId,
  ThemeMode,
  VocabularyItem,
  VoxyMood,
} from '../types/miniapp';

export type ActiveModal =
  | 'flashcards'
  | 'quiz'
  | 'game'
  | 'referrals'
  | 'admin_library'
  | null;

interface QuizContextConfig {
  mode: 'daily' | 'journey' | 'game' | 'pack';
  title: string;
  words: VocabularyItem[];
  nodeId?: string;
  timedSeconds?: number;
}

interface AppState {
  activeTab: TabId;
  activeModal: ActiveModal;
  lang: LanguageCode;
  theme: ThemeMode;
  voxyMood: VoxyMood;
  flashcardWords: VocabularyItem[];
  flashcardTitle: string;
  quizConfig: QuizContextConfig | null;
  activeGameMode: GameModeId | null;
  setActiveTab: (tab: TabId) => void;
  setActiveModal: (modal: ActiveModal) => void;
  setLang: (lang: LanguageCode) => void;
  toggleTheme: () => void;
  setVoxyMood: (mood: VoxyMood) => void;
  openFlashcards: (words: VocabularyItem[], title?: string) => void;
  openQuiz: (config: QuizContextConfig) => void;
  openGameMode: (mode: GameModeId) => void;
  openReferrals: () => void;
  openAdminLibrary: () => void;
  closeModal: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeTab: 'home',
  activeModal: null,
  lang: 'uz',
  theme: 'dark',
  voxyMood: 'welcome',
  flashcardWords: [],
  flashcardTitle: 'Daily IELTS Upgrades',
  quizConfig: null,
  activeGameMode: null,

  setActiveTab: (tab) => set({ activeTab: tab, activeModal: null }),
  setActiveModal: (modal) => set({ activeModal: modal }),
  setLang: (lang) => set({ lang }),
  toggleTheme: () =>
    set((state) => {
      const next: ThemeMode = state.theme === 'dark' ? 'light' : 'dark';
      if (typeof document !== 'undefined') {
        document.documentElement.classList.remove('dark', 'light');
        document.documentElement.classList.add(next);
      }
      return { theme: next };
    }),
  setVoxyMood: (voxyMood) => set({ voxyMood }),
  openFlashcards: (words, title = '3D IELTS Flashcards') =>
    set({
      flashcardWords: words,
      flashcardTitle: title,
      activeModal: 'flashcards',
      voxyMood: 'idle',
    }),
  openQuiz: (config) =>
    set({
      quizConfig: config,
      activeModal: 'quiz',
      voxyMood: 'idle',
    }),
  openGameMode: (mode) =>
    set({
      activeGameMode: mode,
      activeModal: 'game',
      voxyMood: 'idle',
    }),
  openReferrals: () =>
    set({
      activeModal: 'referrals',
      voxyMood: 'celebrate',
    }),
  openAdminLibrary: () =>
    set({
      activeModal: 'admin_library',
      voxyMood: 'welcome',
    }),
  closeModal: () =>
    set({
      activeModal: null,
      quizConfig: null,
      activeGameMode: null,
      voxyMood: 'idle',
    }),
}));
