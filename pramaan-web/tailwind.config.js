/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'bg-base':   '#1b1f2b',
        'bg-raised': '#1f2433',
        'bg-inset':  '#171a24',
        accent: { DEFAULT: '#6f8cff', dim: '#5570cc' },
        st: {
          green:     '#3ddc97',
          amber:     '#ffb84d',
          red:       '#ff5c6c',
          nodata:    '#8b93a7',
          pending:   '#7da2d6',
          uncertain: '#b49cff',
          swap:      '#ff7ad9',
          ghost:     '#ff9f6b',
        },
        text: {
          primary:   '#e8ecf6',
          secondary: '#a3acc2',
          disabled:  '#6b7390',
        },
      },
      fontFamily: {
        ui:         ['Inter', 'system-ui', 'sans-serif'],
        mono:       ['JetBrains Mono', 'Fira Code', 'monospace'],
        devanagari: ['Noto Sans Devanagari', 'sans-serif'],
      },
      fontSize: {
        xs:   ['0.75rem',  { lineHeight: '1rem' }],
        sm:   ['0.875rem', { lineHeight: '1.25rem' }],
        base: ['1rem',     { lineHeight: '1.5rem' }],
        lg:   ['1.25rem',  { lineHeight: '1.75rem' }],
        xl:   ['1.75rem',  { lineHeight: '2.25rem' }],
        '2xl':['2.25rem',  { lineHeight: '2.75rem' }],
      },
      borderRadius: {
        sm: '10px',
        md: '16px',
        lg: '24px',
      },
      boxShadow: {
        'raised-sm': '4px 4px 10px rgba(0,0,0,0.60), -4px -4px 10px rgba(255,255,255,0.045)',
        'raised-md': '8px 8px 20px rgba(0,0,0,0.60), -8px -8px 20px rgba(255,255,255,0.045)',
        'raised-lg': '14px 14px 32px rgba(0,0,0,0.60), -14px -14px 32px rgba(255,255,255,0.045)',
        'inset-sm':  'inset 3px 3px 7px rgba(0,0,0,0.60), inset -3px -3px 7px rgba(255,255,255,0.045)',
        'inset-md':  'inset 6px 6px 14px rgba(0,0,0,0.60), inset -6px -6px 14px rgba(255,255,255,0.045)',
        'accent-glow': '0 0 0 1px rgba(111,140,255,.55), 0 0 18px rgba(111,140,255,.28)',
      },
      transitionDuration: { fast: '150ms', base: '200ms' },
      spacing: { 18: '4.5rem' },
    },
  },
  plugins: [],
};
