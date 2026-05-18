/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        terminal: { bg: '#0a0e17', surface: '#111827', border: '#1e293b', accent: '#3b82f6', success: '#10b981', danger: '#ef4444', warning: '#f59e0b', muted: '#64748b', text: '#e2e8f0', 'text-dim': '#94a3b8' },
      },
      fontFamily: { mono: ['JetBrains Mono', 'Fira Code', 'monospace'], sans: ['Inter', 'system-ui', 'sans-serif'] },
      animation: { 'pulse-slow': 'pulse 3s ease-in-out infinite', 'slide-up': 'slideUp 0.3s ease-out', 'fade-in': 'fadeIn 0.2s ease-out' },
      keyframes: { slideUp: { '0%': { transform: 'translateY(10px)', opacity: '0' }, '100%': { transform: 'translateY(0)', opacity: '1' } }, fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } } },
    },
  },
  plugins: [],
}
