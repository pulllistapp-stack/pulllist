import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Theme-reactive tokens driven by CSS variables in globals.css.
        // Same class works in both modes — the variable swap happens via .dark.
        bg: {
          DEFAULT: "rgb(var(--bg) / <alpha-value>)",
          surface: "rgb(var(--bg-surface) / <alpha-value>)",
          elevated: "rgb(var(--bg-elevated) / <alpha-value>)",
        },
        border: {
          DEFAULT: "rgb(var(--border) / <alpha-value>)",
        },
        text: {
          primary: "rgb(var(--text-primary) / <alpha-value>)",
          secondary: "rgb(var(--text-secondary) / <alpha-value>)",
          tertiary: "rgb(var(--text-tertiary) / <alpha-value>)",
        },
        // Brand accents — fixed (look intentional in both modes).
        accent: {
          yellow: "#FFCB05",
          blue: "#3D7DFF",
          green: "#16C784",
          red: "#E5484D",
        },
        retailer: {
          target: "#CC0000",
          walmart: "#0071CE",
          bestbuy: "#0046BE",
          gamestop: "#1A1A1A",
          costco: "#E32018",
          pokemoncenter: "#FFCB05",
          amazon: "#FF9900",
          samsclub: "#0067A0",
        },
      },
      fontFamily: {
        sans: ["var(--font-dm-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "ui-monospace", "monospace"],
        noto: ["var(--font-noto-sans)", "system-ui", "sans-serif"],
      },
      borderRadius: {
        card: "12px",
        btn: "8px",
        chip: "6px",
      },
      keyframes: {
        // Mascot bobs up + down with a slight squash. Slower than a typical
        // bounce so it reads as 'breathing' rather than impatient.
        "mascot-bounce": {
          "0%, 100%": { transform: "translateY(0) scale(1)" },
          "50%": { transform: "translateY(-8px) scale(1.02)" },
        },
        // Phrase fade-in when it rotates — re-keyed on the React side so
        // each new phrase plays this once.
        "mascot-fade": {
          "0%": { opacity: "0", transform: "translateY(2px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "mascot-bounce": "mascot-bounce 1.8s ease-in-out infinite",
        "mascot-fade": "mascot-fade 0.35s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
