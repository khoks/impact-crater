/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // App-specific accents land here as the design language firms up.
        // M0 ships with Tailwind's default palette only.
      },
    },
  },
  plugins: [],
};
