/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        voxy: {
          bg: 'var(--bg-main)',
          secondary: 'var(--bg-secondary)',
          card: 'var(--bg-card)',
          border: 'var(--border-subtle)',
          purple: '#8B5CF6',
          blue: '#38BDF8',
          green: '#34D399',
          gold: '#FBBF24',
          text: 'var(--text-main)',
          muted: 'var(--text-secondary)',
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['"Space Grotesk"', '"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        glass: '0 8px 32px 0 rgba(8, 13, 30, 0.45)',
        purpleGlow: '0 0 24px rgba(139, 92, 246, 0.35)',
        blueGlow: '0 0 24px rgba(56, 189, 248, 0.35)',
        greenGlow: '0 0 24px rgba(52, 211, 153, 0.4)',
        goldGlow: '0 0 24px rgba(251, 191, 36, 0.38)',
      },
    },
  },
  plugins: [],
};
