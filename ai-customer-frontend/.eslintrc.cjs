/* ESLint 配置 — Vue3 + TypeScript */
module.exports = {
  root: true,
  env: { browser: true, es2023: true, node: true },
  extends: [
    'eslint:recommended',
    'plugin:vue/vue3-recommended',
    '@vue/eslint-config-typescript',
    '@vue/eslint-config-prettier',
  ],
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
  rules: {
    // 调试语句管控：允许 warn/error，禁止 log/debugger
    'no-console': ['warn', { allow: ['warn', 'error'] }],
    'no-debugger': 'error',

    // 类型安全：any 是 Blocker（对应审查标准 4.1）
    '@typescript-eslint/no-explicit-any': 'error',
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],

    // Vue 规范
    'vue/multi-word-component-names': 'off',
    'vue/no-unused-vars': 'error',

    // import 排序
    'import/order': [
      'error',
      {
        groups: ['builtin', 'external', 'internal', 'parent', 'sibling', 'index'],
        'newlines-between': 'always',
      },
    ],
  },
  overrides: [
    {
      // vite.config.ts 等构建配置文件放宽
      files: ['*.config.js', '*.config.ts', 'vite.config.ts'],
      rules: { 'import/order': 'off' },
    },
  ],
}
