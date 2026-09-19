module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: { sans: ['var(--font-sans)'] },
      colors: {
        primary: { DEFAULT: 'var(--brand)', soft: 'var(--brand-soft)', foreground: 'var(--on-brand)' },
        accent:  { DEFAULT: 'var(--accent)', foreground: 'var(--on-accent)' },
        success: { DEFAULT: 'var(--ok)', foreground: '#ffffff' },
        warning: { DEFAULT: 'var(--accent)', foreground: '#1a1a1a' },
        info: { DEFAULT: 'var(--info)', foreground: '#ffffff' },
        sidebar: { DEFAULT: 'var(--sidebar-bg)', foreground: 'var(--sidebar-text)', accent: 'var(--sidebar-hover)', border: 'var(--sidebar-border)' },
        muted: { DEFAULT: 'var(--surface-2)', foreground: 'var(--text-muted)' },
        border: 'var(--border)',
        card: 'var(--surface)',
      },
      borderRadius: { lg: '0.75rem', xl: '1rem', '2xl': '1.25rem' },
    },
  },
  plugins: [],
};
