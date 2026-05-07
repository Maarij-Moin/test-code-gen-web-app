/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        surface: "hsl(var(--surface))",
        panel: "hsl(var(--panel))",
        panel2: "hsl(var(--panel-2))",
        text: "hsl(var(--text))",
        muted: "hsl(var(--muted))",
        brand: "hsl(var(--brand))",
        brand2: "hsl(var(--brand-2))",
        border: "hsl(var(--border))",
        success: "hsl(var(--success))",
        warning: "hsl(var(--warning))",
        danger: "hsl(var(--danger))"
      },
      boxShadow: {
        card: "0 12px 40px rgba(0, 0, 0, 0.25)",
        glow: "0 0 30px rgba(56, 189, 248, 0.3)"
      }
    }
  },
  plugins: []
};
