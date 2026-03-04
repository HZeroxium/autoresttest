import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        body: ["'IBM Plex Sans'", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
      },
      colors: {
        paper: "#f5f2e9",
        ink: "#12343b",
        inkSoft: "#365f64",
        accent: "#d28b36",
        accentSoft: "#f4d6a5",
        slate: "#5f6f72",
        panel: "#ffffff",
        line: "#d8d3c6",
      },
      boxShadow: {
        panel: "0 14px 40px rgba(18, 52, 59, 0.08)",
      },
      backgroundImage: {
        "paper-grid":
          "linear-gradient(rgba(18,52,59,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(18,52,59,0.04) 1px, transparent 1px)",
      },
    },
  },
  plugins: [],
} satisfies Config;
