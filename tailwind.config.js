/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#0058bc",
        "primary-container": "#0070eb",
        secondary: "#405e96",
        "secondary-container": "#a1befd",
        tertiary: "#9e3d00",
        "tertiary-container": "#c64f00",
        error: "#ba1a1a",
        "error-container": "#ffdad6",
        background: "#faf9fe",
        surface: "#faf9fe",
        "surface-dim": "#dad9df",
        "surface-bright": "#faf9fe",
        "surface-variant": "#e3e2e7",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#f4f3f8",
        "surface-container": "#eeedf3",
        "surface-container-high": "#e9e7ed",
        "surface-container-highest": "#e3e2e7",
        outline: "#717786",
        "outline-variant": "#c1c6d7",
        "on-primary": "#ffffff",
        "on-primary-container": "#fefcff",
        "on-secondary": "#ffffff",
        "on-secondary-container": "#2d4c83",
        "on-tertiary": "#ffffff",
        "on-tertiary-container": "#fffbff",
        "on-error": "#ffffff",
        "on-error-container": "#93000a",
        "on-background": "#1a1b1f",
        "on-surface": "#1a1b1f",
        "on-surface-variant": "#414755",
        "inverse-surface": "#2f3034",
        "inverse-on-surface": "#f1f0f5",
        "inverse-primary": "#adc6ff",
        emerald: {
          500: "#50C878",
          600: "#45b36b"
        }
      },
      borderRadius: {
        xl: "1.5rem"
      },
      fontFamily: {
        headline: ["Inter", "system-ui", "sans-serif"],
        body: ["Inter", "system-ui", "sans-serif"],
        label: ["Inter", "system-ui", "sans-serif"]
      }
    },
  },
  plugins: [],
}
