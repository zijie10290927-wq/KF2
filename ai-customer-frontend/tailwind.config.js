/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#409eff',
        'primary-dark': '#337ecc',
        success: '#67c23a',
        warning: '#e6a23c',
        danger: '#f56c6c',
        info: '#909399',
      },
    },
  },
  plugins: [],
  corePlugins: {
    preflight: false, // 避免覆盖 Element Plus 基础样式
  },
}
