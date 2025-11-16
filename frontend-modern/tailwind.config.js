/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border) / <alpha-value>)",
        input: "hsl(var(--input) / <alpha-value>)",
        ring: "hsl(var(--ring) / <alpha-value>)",
        background: "hsl(var(--background) / <alpha-value>)",
        foreground: "hsl(var(--foreground) / <alpha-value>)",
        card: "hsl(var(--card) / <alpha-value>)",
        muted: "hsl(var(--muted) / <alpha-value>)",
        accent: "hsl(var(--accent) / <alpha-value>)",
        destructive: "hsl(var(--destructive) / <alpha-value>)",
        popover: "hsl(var(--popover) / <alpha-value>)",
        primary: "hsl(var(--primary) / <alpha-value>)",
        secondary: "hsl(var(--secondary) / <alpha-value>)",
      },
      borderRadius: {
        "2xl": "1.25rem",
      },
      colors: {
        primary: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
          950: '#052e16',
        },
        accent: {
          emerald: '#10b981',
          teal: '#14b8a6',
          cyan: '#06b6d4',
          sky: '#0ea5e9',
          mint: '#99f6e4',
        },
        neso: {
          gold: '#ceb94b',
          lightgold: '#d9d97d',
          dark: '#241a06',
          gray: '#7c7874',
          light: '#e5e5e5',
        },
      },
      boxShadow: {
        'surface-dark': '0 24px 48px rgba(0, 12, 9, 0.55)',
        'surface-light': '0 28px 52px rgba(16, 185, 129, 0.18)',
      },
    },
  },
  plugins: [],
}

