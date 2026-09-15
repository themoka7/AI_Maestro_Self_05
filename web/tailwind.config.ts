import type { Config } from "tailwindcss";

export default {
  darkMode: ["class", '[data-theme="dark"]'],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "var(--surface-1)",
        plane: "var(--plane)",
        ink: "var(--text-primary)",
        "ink-2": "var(--text-secondary)",
        muted: "var(--text-muted)",
        grid: "var(--gridline)",
        hairline: "var(--border)",
        watchdog: "var(--watchdog)",
        neutralcat: "var(--neutral-cat)",
        dependent: "var(--dependent)",
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', '"Segoe UI"', '"Apple SD Gothic Neo"',
               '"Malgun Gothic"', 'sans-serif'],
      },
    },
  },
  plugins: [],
} satisfies Config;
