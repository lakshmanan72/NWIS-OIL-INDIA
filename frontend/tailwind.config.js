/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        petroleum: {
          navy: '#062B49',
          dark: '#082F49',
          deep: '#0B192C',
          slate: '#0F172A',
          orange: '#F97316',
          amber: '#F59E0B',
          gray: '#F4F7FA',
        },
      },
    },
  },
  plugins: [],
};
