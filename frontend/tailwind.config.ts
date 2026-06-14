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
        bg: {
          DEFAULT: "#0B0E14",
          surface: "#161B26",
          elevated: "#1E2533",
        },
        border: {
          DEFAULT: "#252D3D",
        },
        text: {
          primary: "#E6E9EF",
          secondary: "#8B92A5",
          tertiary: "#5A6275",
        },
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
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
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
