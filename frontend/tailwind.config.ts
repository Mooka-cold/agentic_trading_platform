import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/features/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        xiaohongshu: {
          red: '#FF2442',
          light: '#FFF0F3',
          bg: '#F5F5F5',
          card: '#FFFFFF',
          text: '#333333',
          textSecondary: '#666666',
        },
      },
      borderRadius: {
        'card': '16px',
        'btn': '24px',
      },
      boxShadow: {
        'card': '0 2px 12px rgba(0, 0, 0, 0.04)',
        'hover': '0 4px 16px rgba(0, 0, 0, 0.08)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
};
export default config;
