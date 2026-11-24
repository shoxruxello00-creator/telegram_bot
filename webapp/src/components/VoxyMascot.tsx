import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import Lottie from 'lottie-react';
import { VoxyMood } from '../types/miniapp';

// Lightweight embedded Lottie JSON pulse ring for Voxy's futuristic core aura
const VOXY_PULSE_LOTTIE = {
  v: '5.7.4',
  fr: 30,
  ip: 0,
  op: 60,
  w: 120,
  h: 120,
  nm: 'VoxyAura',
  ddd: 0,
  assets: [],
  layers: [
    {
      ddd: 0,
      ind: 1,
      ty: 4,
      nm: 'Ring',
      sr: 1,
      ks: {
        o: {
          a: 1,
          k: [
            { t: 0, s: [45] },
            { t: 30, s: [15] },
            { t: 60, s: [45] },
          ],
        },
        r: { a: 0, k: 0 },
        p: { a: 0, k: [60, 60, 0] },
        a: { a: 0, k: [0, 0, 0] },
        s: {
          a: 1,
          k: [
            { t: 0, s: [88, 88, 100] },
            { t: 30, s: [108, 108, 100] },
            { t: 60, s: [88, 88, 100] },
          ],
        },
      },
      ao: 0,
      shapes: [
        {
          ty: 'el',
          p: { a: 0, k: [0, 0] },
          s: { a: 0, k: [96, 96] },
          nm: 'Ellipse',
        },
        {
          ty: 'st',
          c: { a: 0, k: [0.545, 0.361, 0.965, 1] },
          o: { a: 0, k: 100 },
          w: { a: 0, k: 3 },
          lc: 2,
          lj: 2,
          nm: 'Stroke',
        },
      ],
      ip: 0,
      op: 60,
      st: 0,
    },
  ],
};

interface VoxyMascotProps {
  mood?: VoxyMood;
  size?: 'sm' | 'md' | 'lg';
  message?: string;
  className?: string;
}

export const VoxyMascot: React.FC<VoxyMascotProps> = ({
  mood = 'idle',
  size = 'md',
  message,
  className = '',
}) => {
  const [isBlinking, setIsBlinking] = useState(false);

  // Automatic natural blinking every 3.6 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setIsBlinking(true);
      setTimeout(() => setIsBlinking(false), 160);
    }, 3600);
    return () => clearInterval(interval);
  }, []);

  const dims = size === 'sm' ? 64 : size === 'lg' ? 116 : 86;

  const isHappy =
    mood === 'celebrate' ||
    mood === 'complete' ||
    mood === 'levelup' ||
    mood === 'achievement' ||
    mood === 'welcome';

  const isEncouraging = mood === 'encourage';
  const isLoading = mood === 'loading';

  const eyeColor =
    mood === 'celebrate' || mood === 'complete'
      ? '#34D399'
      : mood === 'levelup' || mood === 'achievement'
      ? '#FBBF24'
      : mood === 'encourage'
      ? '#38BDF8'
      : '#38BDF8';

  return (
    <div className={`flex items-center gap-3.5 ${className}`}>
      <div
        className="relative flex items-center justify-center shrink-0 select-none"
        style={{ width: dims, height: dims }}
      >
        {/* Lightweight Lottie energy aura */}
        <div className="absolute inset-0 pointer-events-none opacity-75">
          <Lottie animationData={VOXY_PULSE_LOTTIE} loop={true} />
        </div>

        {/* Original Voxy Futuristic Educational Robot SVG */}
        <motion.svg
          width={dims}
          height={dims}
          viewBox="0 0 120 120"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          animate={
            isHappy
              ? { y: [0, -6, 0], rotate: [0, -3, 3, 0] }
              : isLoading
              ? { rotate: [0, 360] }
              : { y: [0, -3.5, 0] }
          }
          transition={{
            duration: isHappy ? 1.4 : isLoading ? 2.4 : 2.8,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        >
          <defs>
            <linearGradient id="voxyHeadGrad" x1="20" y1="20" x2="100" y2="100" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#8B5CF6" />
              <stop offset="55%" stopColor="#4F46E5" />
              <stop offset="100%" stopColor="#38BDF8" />
            </linearGradient>
            <linearGradient id="voxyVisorGrad" x1="30" y1="40" x2="90" y2="80" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#080D1E" />
              <stop offset="100%" stopColor="#111B32" />
            </linearGradient>
          </defs>

          {/* Antenna */}
          <line x1="60" y1="14" x2="60" y2="26" stroke="#8B5CF6" strokeWidth="4" strokeLinecap="round" />
          <motion.circle
            cx="60"
            cy="12"
            r="5.5"
            fill={eyeColor}
            animate={{ scale: [1, 1.25, 1], opacity: [0.85, 1, 0.85] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />

          {/* Side Ear Pods */}
          <rect x="14" y="46" width="9" height="24" rx="4.5" fill="#38BDF8" />
          <rect x="97" y="46" width="9" height="24" rx="4.5" fill="#38BDF8" />

          {/* Main Rounded Futuristic Robot Head/Chassis */}
          <rect
            x="22"
            y="25"
            width="76"
            height="66"
            rx="24"
            fill="url(#voxyHeadGrad)"
            stroke="#F8FAFC"
            strokeOpacity="0.22"
            strokeWidth="2"
          />

          {/* Top Specular Highlight */}
          <path
            d="M38 31H82C86 31 89 33 90 35"
            stroke="#F8FAFC"
            strokeOpacity="0.35"
            strokeWidth="2.5"
            strokeLinecap="round"
          />

          {/* Glass Visor Screen */}
          <rect
            x="30"
            y="37"
            width="60"
            height="40"
            rx="15"
            fill="url(#voxyVisorGrad)"
            stroke="#38BDF8"
            strokeOpacity="0.4"
            strokeWidth="1.5"
          />

          {/* Expressive LED Eyes */}
          {isBlinking || mood === 'blink' ? (
            <>
              <line x1="41" y1="54" x2="53" y2="54" stroke={eyeColor} strokeWidth="3.5" strokeLinecap="round" />
              <line x1="67" y1="54" x2="79" y2="54" stroke={eyeColor} strokeWidth="3.5" strokeLinecap="round" />
            </>
          ) : isHappy ? (
            <>
              <path
                d="M41 56C43 50 51 50 53 56"
                stroke={eyeColor}
                strokeWidth="3.8"
                strokeLinecap="round"
              />
              <path
                d="M67 56C69 50 77 50 79 56"
                stroke={eyeColor}
                strokeWidth="3.8"
                strokeLinecap="round"
              />
            </>
          ) : isEncouraging ? (
            <>
              <circle cx="47" cy="54" r="5.5" fill={eyeColor} />
              <circle cx="73" cy="54" r="5.5" fill={eyeColor} />
              <line x1="41" y1="46" x2="52" y2="48" stroke={eyeColor} strokeWidth="2" strokeLinecap="round" />
              <line x1="79" y1="46" x2="68" y2="48" stroke={eyeColor} strokeWidth="2" strokeLinecap="round" />
            </>
          ) : (
            <>
              <circle cx="47" cy="53" r="6" fill={eyeColor} />
              <circle cx="49" cy="51" r="2" fill="#F8FAFC" />
              <circle cx="73" cy="53" r="6" fill={eyeColor} />
              <circle cx="75" cy="51" r="2" fill="#F8FAFC" />
            </>
          )}

          {/* Expressive Mouth LED */}
          {isHappy ? (
            <path
              d="M52 65C55 70 65 70 68 65"
              stroke="#34D399"
              strokeWidth="3"
              strokeLinecap="round"
            />
          ) : isEncouraging ? (
            <path
              d="M54 67H66"
              stroke="#38BDF8"
              strokeWidth="2.8"
              strokeLinecap="round"
            />
          ) : (
            <path
              d="M54 65C57 68 63 68 66 65"
              stroke="#38BDF8"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
          )}

          {/* Floating Mini Shoulder Core */}
          <path
            d="M42 96C42 93 48 92 60 92C72 92 78 93 78 96C78 101 70 104 60 104C50 104 42 101 42 96Z"
            fill="#19243D"
            stroke="#8B5CF6"
            strokeWidth="2"
          />
          <circle cx="60" cy="98" r="3" fill="#34D399" />
        </motion.svg>

        {/* Levelup / Achievement Crown Sparkle Badge */}
        {(mood === 'levelup' || mood === 'achievement') && (
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute -top-1 -right-1 bg-voxy-gold text-slate-950 text-[10px] font-extrabold px-1.5 py-0.5 rounded-full shadow-goldGlow"
          >
            ★ UP!
          </motion.div>
        )}
      </div>

      {message && (
        <motion.div
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          className="relative flex-1 bg-voxy-card/90 backdrop-blur-md border border-voxy-purple/30 rounded-2xl px-3.5 py-2.5 shadow-glass"
        >
          <div className="flex items-center gap-1.5 mb-0.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-voxy-blue">
              VOXY AI COACH
            </span>
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-voxy-green animate-pulse" />
          </div>
          <p className="text-xs sm:text-sm text-voxy-text leading-snug font-medium">
            {message}
          </p>
        </motion.div>
      )}
    </div>
  );
};
