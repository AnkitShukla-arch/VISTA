import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "var(--background)", surface: "var(--surface)", raised: "var(--raised)",
        border: "var(--border)", foreground: "var(--foreground)", muted: "var(--muted)", accent: "var(--accent)",
      },
      fontFamily: { sans: ["var(--font-inter)", "Inter", "sans-serif"], mono: ["var(--font-mono)", "monospace"] },
      fontSize: {
        title: "var(--text-title)", body: "var(--text-body)", meta: "var(--text-meta)",
        nav: "var(--text-nav)", "box-label": "var(--text-box-label)", input: "var(--text-input)",
        "result-title": "var(--text-result-title)", "preview-title": "var(--text-preview-title)",
        number: "var(--text-number)", overline: "var(--text-overline)",
        "sidebar-section": "var(--text-sidebar-section)", "crumb": "var(--text-crumb)",
        snippet: "var(--text-snippet)",
      },
      borderRadius: { xl: "12px" },
    },
  },
  plugins: [],
};
export default config;
