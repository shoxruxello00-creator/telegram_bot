import React from 'react';
import { motion } from 'framer-motion';
import { Compass, Gamepad2, Home, Trophy, User } from 'lucide-react';
import { t } from '../lib/i18n';
import { hapticSelection } from '../lib/telegram';
import { useAppStore } from '../store/useAppStore';
import { TabId } from '../types/miniapp';

export const BottomNav: React.FC = () => {
  const { activeTab, setActiveTab, lang } = useAppStore();

  const tabs: Array<{ id: TabId; labelKey: string; Icon: React.ElementType }> = [
    { id: 'home', labelKey: 'nav_home', Icon: Home },
    { id: 'journey', labelKey: 'nav_journey', Icon: Compass },
    { id: 'play', labelKey: 'nav_play', Icon: Gamepad2 },
    { id: 'ranks', labelKey: 'nav_ranks', Icon: Trophy },
    { id: 'profile', labelKey: 'nav_profile', Icon: User },
  ];

  return (
    <div className="fixed bottom-0 inset-x-0 z-40 px-3 pb-3 pt-1 pointer-events-none">
      <nav
        aria-label="Main Navigation"
        className="pointer-events-auto max-w-md mx-auto bg-voxy-secondary/95 backdrop-blur-xl border border-voxy-border rounded-2xl shadow-glass px-2 py-1.5 flex items-center justify-between"
      >
        {tabs.map(({ id, labelKey, Icon }) => {
          const isActive = activeTab === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => {
                hapticSelection();
                setActiveTab(id);
              }}
              className={`relative flex-1 flex flex-col items-center justify-center py-1.5 rounded-xl transition-colors select-none ${
                isActive ? 'text-voxy-text' : 'text-voxy-muted hover:text-voxy-text'
              }`}
            >
              {isActive && (
                <motion.div
                  layoutId="bottomNavActivePill"
                  transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                  className="absolute inset-0 bg-gradient-to-tr from-voxy-purple/25 to-voxy-blue/20 border border-voxy-purple/40 rounded-xl"
                />
              )}
              <Icon
                className={`relative z-10 w-5 h-5 transition-transform duration-200 ${
                  isActive ? 'scale-110 text-voxy-blue' : ''
                }`}
              />
              <span className="relative z-10 text-[10px] font-bold mt-1 truncate max-w-[62px]">
                {t(lang, labelKey)}
              </span>
            </button>
          );
        })}
      </nav>
    </div>
  );
};
