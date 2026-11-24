import React from 'react';
import { LeagueId } from '../types/miniapp';

interface LeagueBadgeProps {
  leagueId: LeagueId | string;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

const LEAGUE_PALETTES: Record<
  string,
  { primary: string; secondary: string; border: string; label: string }
> = {
  bronze: {
    primary: '#D97706',
    secondary: '#92400E',
    border: '#F59E0B',
    label: 'Bronze',
  },
  silver: {
    primary: '#E2E8F0',
    secondary: '#64748B',
    border: '#F8FAFC',
    label: 'Silver',
  },
  gold: {
    primary: '#FBBF24',
    secondary: '#B45309',
    border: '#FDE68A',
    label: 'Gold',
  },
  platinum: {
    primary: '#38BDF8',
    secondary: '#0369A1',
    border: '#BAE6FD',
    label: 'Platinum',
  },
  diamond: {
    primary: '#A78BFA',
    secondary: '#5B21B6',
    border: '#DDD6FE',
    label: 'Diamond',
  },
  master: {
    primary: '#F43F5E',
    secondary: '#881337',
    border: '#FDA4AF',
    label: 'Master',
  },
};

export const LeagueBadge: React.FC<LeagueBadgeProps> = ({
  leagueId,
  size = 'md',
  showLabel = true,
}) => {
  const key = (leagueId || 'gold').toLowerCase();
  const palette = LEAGUE_PALETTES[key] || LEAGUE_PALETTES.gold;
  const px = size === 'sm' ? 22 : size === 'lg' ? 42 : 30;

  return (
    <div className="inline-flex items-center gap-1.5">
      <svg
        width={px}
        height={px}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="shrink-0 drop-shadow"
      >
        <defs>
          <linearGradient id={`lg_${key}`} x1="6" y1="4" x2="34" y2="36" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor={palette.primary} />
            <stop offset="100%" stopColor={palette.secondary} />
          </linearGradient>
        </defs>
        {/* Crystalline hexagonal shield */}
        <path
          d="M20 3L34 10V23C34 30.5 27.8 35.8 20 38C12.2 35.8 6 30.5 6 23V10L20 3Z"
          fill={`url(#lg_${key})`}
          stroke={palette.border}
          strokeWidth="2"
        />
        {/* Inner crystal facet */}
        <path
          d="M20 8L28 12.5V22C28 26.8 24.5 30.3 20 32C15.5 30.3 12 26.8 12 22V12.5L20 8Z"
          fill="#080D1E"
          fillOpacity="0.28"
        />
        {/* Star crest */}
        <path
          d="M20 12.5L22.1 17L27 17.6L23.4 21L24.3 25.8L20 23.4L15.7 25.8L16.6 21L13 17.6L17.9 17L20 12.5Z"
          fill={palette.border}
        />
      </svg>
      {showLabel && (
        <span
          className="text-xs font-bold tracking-wide"
          style={{ color: palette.primary }}
        >
          {palette.label}
        </span>
      )}
    </div>
  );
};
