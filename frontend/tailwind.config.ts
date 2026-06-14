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
      },
      borderRadius: {
        card: "12px",
        btn: "8px",
        chip: "6px",
      },
    },
  },
  plugins: [],
};

export default config;
