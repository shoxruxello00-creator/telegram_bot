interface TelegramWebAppUser {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  photo_url?: string;
}

interface TelegramWebApp {
  initData?: string;
  initDataUnsafe?: {
    user?: TelegramWebAppUser;
    start_param?: string;
  };
  colorScheme?: 'light' | 'dark';
  isExpanded?: boolean;
  viewportHeight?: number;
  ready?: () => void;
  expand?: () => void;
  requestFullscreen?: () => void;
  openTelegramLink?: (url: string) => void;
  openLink?: (url: string) => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  BackButton?: {
    isVisible: boolean;
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  MainButton?: {
    text: string;
    isVisible: boolean;
    setText: (text: string) => void;
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  HapticFeedback?: {
    impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
    notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
    selectionChanged: () => void;
  };
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}

export function getTelegramWebApp(): TelegramWebApp | null {
  if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
    return window.Telegram.WebApp;
  }
  return null;
}

export function initTelegramWebApp(): void {
  const tg = getTelegramWebApp();
  if (!tg) return;
  try {
    tg.ready?.();
    tg.expand?.();
    tg.setHeaderColor?.('#080D1E');
    tg.setBackgroundColor?.('#080D1E');
  } catch {
    // Graceful fallback on older Telegram clients
  }
}

export function getTelegramInitData(): string {
  return getTelegramWebApp()?.initData || '';
}

export function getTelegramUser(): TelegramWebAppUser | null {
  return getTelegramWebApp()?.initDataUnsafe?.user || null;
}

export function hapticImpact(
  style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft' = 'light'
): void {
  try {
    getTelegramWebApp()?.HapticFeedback?.impactOccurred(style);
  } catch {
    // Fallback for standard browsers
  }
}

export function hapticNotification(
  type: 'error' | 'success' | 'warning' = 'success'
): void {
  try {
    getTelegramWebApp()?.HapticFeedback?.notificationOccurred(type);
  } catch {
    // Fallback
  }
}

export function hapticSelection(): void {
  try {
    getTelegramWebApp()?.HapticFeedback?.selectionChanged();
  } catch {
    // Fallback
  }
}

export function configureBackButton(
  visible: boolean,
  handler?: () => void
): () => void {
  const tg = getTelegramWebApp();
  const backBtn = tg?.BackButton;
  if (!backBtn) return () => {};

  try {
    if (visible && handler) {
      backBtn.show();
      backBtn.onClick(handler);
      return () => {
        try {
          backBtn.offClick(handler);
          backBtn.hide();
        } catch {
          // ignore
        }
      };
    } else {
      backBtn.hide();
    }
  } catch {
    // ignore
  }
  return () => {};
}

export function shareViaTelegram(shareUrl: string): void {
  hapticImpact('medium');
  const tg = getTelegramWebApp();
  try {
    if (tg?.openTelegramLink && shareUrl.startsWith('https://t.me/')) {
      tg.openTelegramLink(shareUrl);
      return;
    }
  } catch {
    // fallback to window.open
  }
  window.open(shareUrl, '_blank', 'noopener,noreferrer');
}

export function speakEnglishExpression(text: string): void {
  hapticImpact('light');
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
  try {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-GB';
    utterance.rate = 0.94;
    window.speechSynthesis.speak(utterance);
  } catch {
    // Speech synthesis unavailable
  }
}
