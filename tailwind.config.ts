import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        obsidian: {
          DEFAULT: '#05060A',
          950: '#030408',
          900: '#070810',
          800: '#0B0D16',
          700: '#11131E',
          600: '#171A26',
        },
        graphite: {
          DEFAULT: '#22262F',
          100: '#3A404D',
          200: '#2C313B',
          300: '#22262F',
          400: '#171A21',
        },
        titanium: {
          light: '#B8BFCB',
          DEFAULT: '#8B93A3',
          dark: '#5A6070',
        },
        platinum: {
          DEFAULT: '#E6E8EE',
          soft: '#C9CDD8',
          dim: '#8F95A3',
        },
        champagne: {
          DEFAULT: '#D8C39A',
          bright: '#EFDCB6',
          deep: '#A8916A',
          faint: '#6E5F44',
        },
        ion: {
          DEFAULT: '#6EA8FF',
          bright: '#9CC6FF',
          deep: '#2F5DA8',
          faint: '#16233D',
        },
      },
      fontFamily: {
        sans: ['"Inter"', '"SF Pro Display"', 'system-ui', 'sans-serif'],
        display: ['"Inter"', '"SF Pro Display"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"SF Mono"', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.9rem', letterSpacing: '0.16em' }],
        '3xs': ['0.5625rem', { lineHeight: '0.8rem', letterSpacing: '0.2em' }],
      },
      letterSpacing: {
        widest2: '0.28em',
        widest3: '0.42em',
      },
      backgroundImage: {
        'grain':
          "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)' opacity='0.5'/%3E%3C/svg%3E\")",
      },
      boxShadow: {
        glass: '0 24px 80px -32px rgba(0,0,0,0.9), inset 0 1px 0 0 rgba(255,255,255,0.05)',
        'glass-lg':
          '0 48px 140px -48px rgba(0,0,0,0.95), inset 0 1px 0 0 rgba(255,255,255,0.06)',
        aura: '0 0 80px -10px rgba(110,168,255,0.25)',
        'aura-gold': '0 0 60px -12px rgba(216,195,154,0.35)',
      },
      transitionTimingFunction: {
        cinematic: 'cubic-bezier(0.16, 1, 0.3, 1)',
        silk: 'cubic-bezier(0.22, 0.61, 0.36, 1)',
      },
      keyframes: {
        breathe: {
          '0%, 100%': { transform: 'scale(1)', opacity: '0.85' },
          '50%': { transform: 'scale(1.04)', opacity: '1' },
        },
        'slow-spin': {
          to: { transform: 'rotate(360deg)' },
        },
        'slow-spin-reverse': {
          to: { transform: 'rotate(-360deg)' },
        },
        shimmer: {
          '0%': { transform: 'translateX(-120%)' },
          '100%': { transform: 'translateX(220%)' },
        },
        'pulse-ring': {
          '0%': { transform: 'scale(0.85)', opacity: '0.5' },
          '100%': { transform: 'scale(1.6)', opacity: '0' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        'scan-line': {
          '0%': { transform: 'translateY(-100%)', opacity: '0' },
          '50%': { opacity: '0.8' },
          '100%': { transform: 'translateY(100%)', opacity: '0' },
        },
      },
      animation: {
        breathe: 'breathe 6s ease-in-out infinite',
        'slow-spin': 'slow-spin 38s linear infinite',
        'slow-spin-reverse': 'slow-spin-reverse 54s linear infinite',
        shimmer: 'shimmer 2.6s ease-in-out infinite',
        'pulse-ring': 'pulse-ring 3.2s ease-out infinite',
        float: 'float 7s ease-in-out infinite',
        'scan-line': 'scan-line 4.5s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};

export default config;