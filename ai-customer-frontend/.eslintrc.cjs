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

    // import 排序：依赖 eslint-plugin-import 插件。
    // 插件安装受网络/沙箱限制暂时失败，先停用该规则以解锁 lint:check；
    // 后续装好 eslint-plugin-import 后重新启用（恢复下方 'import/order' 配置块）。
    // 'import/order': [
    //   'error',
    //   {
    //     groups: ['builtin', 'external', 'internal', 'parent', 'sibling', 'index'],
    //     'newlines-between': 'always',
    //   },
    // ],
  },
  overrides: [
    {
      // vite.config.ts 等构建配置文件放宽
      files: ['*.config.js', '*.config.ts', 'vite.config.ts'],
      rules: {},
    },
  ],
}
