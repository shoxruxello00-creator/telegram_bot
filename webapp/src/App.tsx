import React, { Suspense, lazy, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { BottomNav } from './components/BottomNav';
import { VoxyMascot } from './components/VoxyMascot';
import { fetchBootstrap, updateSettings } from './lib/api';
import { configureBackButton, initTelegramWebApp } from './lib/telegram';
import { HomeDashboard } from './pages/HomeDashboard';
import { useAppStore } from './store/useAppStore';
import { LanguageCode } from './types/miniapp';

const JourneyMapPage = lazy(() =>
  import('./pages/JourneyMapPage').then((m) => ({ default: m.JourneyMapPage }))
);
const GameCenterPage = lazy(() =>
  import('./pages/GameCenterPage').then((m) => ({ default: m.GameCenterPage }))
);
const LeaderboardPage = lazy(() =>
  import('./pages/LeaderboardPage').then((m) => ({ default: m.LeaderboardPage }))
);
const ProfileAnalyticsPage = lazy(() =>
  import('./pages/ProfileAnalyticsPage').then((m) => ({
    default: m.ProfileAnalyticsPage,
  }))
);
const FlashcardsModal = lazy(() =>
  import('./components/FlashcardsModal').then((m) => ({
    default: m.FlashcardsModal,
  }))
);
const QuizEngineModal = lazy(() =>
  import('./components/QuizEngineModal').then((m) => ({
    default: m.QuizEngineModal,
  }))
);
const GamePlayModal = lazy(() =>
  import('./components/GamePlayModal').then((m) => ({
    default: m.GamePlayModal,
  }))
);
const ReferralsModal = lazy(() =>
  import('./components/ReferralsModal').then((m) => ({
    default: m.ReferralsModal,
  }))
);

export const App: React.FC = () => {
  const queryClient = useQueryClient();
  const {
    activeTab,
    activeModal,
    setLang,
    closeModal,
    setActiveTab,
  } = useAppStore();

  useEffect(() => {
    initTelegramWebApp();
  }, []);

  useEffect(() => {
    if (activeModal !== null) {
      return configureBackButton(true, () => closeModal());
    }
    if (activeTab !== 'home') {
      return configureBackButton(true, () => setActiveTab('home'));
    }
    return configureBackButton(false);
  }, [activeModal, activeTab, closeModal, setActiveTab]);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['bootstrap'],
    queryFn: fetchBootstrap,
  });

  useEffect(() => {
    if (data?.user?.language_code) {
      setLang(data.user.language_code);
    }
  }, [data?.user?.language_code, setLang]);

  const handleLanguageChange = async (newLang: LanguageCode) => {
    setLang(newLang);
    try {
      await updateSettings({ language_code: newLang });
      await queryClient.invalidateQueries({ queryKey: ['bootstrap'] });
      await queryClient.invalidateQueries({ queryKey: ['referrals'] });
    } catch {
      // keep local state responsive
    }
  };

  const handleRefreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ['bootstrap'] });
    queryClient.invalidateQueries({ queryKey: ['leaderboard'] });
    queryClient.invalidateQueries({ queryKey: ['referrals'] });
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-voxy-bg text-voxy-text flex flex-col items-center justify-center p-6 text-center space-y-5">
        <VoxyMascot mood="loading" size="lg" />
        <div className="space-y-1.5 max-w-xs">
          <h1 className="text-lg font-display font-bold text-voxy-text">
            Voxy IELTS Arena
          </h1>
          <p className="text-xs text-voxy-muted">
            Synchronizing your Everyday → Advanced IELTS vocabulary, streak & league rank...
          </p>
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="min-h-screen bg-voxy-bg text-voxy-text flex flex-col items-center justify-center p-6 text-center space-y-4">
        <VoxyMascot mood="encourage" size="md" />
        <h2 className="text-base font-display font-bold">
          Connection Interrupted
        </h2>
        <button
          type="button"
          onClick={() => refetch()}
          className="px-5 py-2.5 rounded-2xl bg-voxy-purple text-white text-xs font-bold"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-voxy-bg text-voxy-text relative overflow-x-hidden">
      <div className="pointer-events-none fixed inset-0 overflow-hidden z-0">
        <div className="absolute -top-28 -left-24 w-72 h-72 rounded-full bg-voxy-purple/12 blur-3xl" />
        <div className="absolute top-1/3 -right-28 w-72 h-72 rounded-full bg-voxy-blue/10 blur-3xl" />
      </div>

      <main className="relative z-10 max-w-md mx-auto px-3.5 pt-3.5">
        <Suspense
          fallback={
            <div className="py-20 flex justify-center">
              <VoxyMascot mood="loading" size="md" />
            </div>
          }
        >
          {activeTab === 'home' && (
            <HomeDashboard
              data={data}
              onLanguageChange={handleLanguageChange}
            />
          )}
          {activeTab === 'journey' && <JourneyMapPage worlds={data.journey} />}
          {activeTab === 'play' && <GameCenterPage />}
          {activeTab === 'ranks' && <LeaderboardPage />}
          {activeTab === 'profile' && (
            <ProfileAnalyticsPage
              data={data}
              onLanguageChange={handleLanguageChange}
              onRefetch={handleRefreshAll}
            />
          )}
        </Suspense>
      </main>

      <BottomNav />

      <Suspense fallback={null}>
        {activeModal === 'flashcards' && (
          <FlashcardsModal onSynced={handleRefreshAll} />
        )}
        {activeModal === 'quiz' && (
          <QuizEngineModal onCompleted={handleRefreshAll} />
        )}
        {activeModal === 'game' && (
          <GamePlayModal onCompleted={handleRefreshAll} />
        )}
        {activeModal === 'referrals' && <ReferralsModal />}
      </Suspense>
    </div>
  );
};
