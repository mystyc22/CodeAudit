// CodeAudit: flat config for ESLint 9. Stored OUTSIDE scanned projects.
// No --fix and no eslint cache: analysis must not modify target projects.
import js from '@eslint/js';
import sonarjs from 'eslint-plugin-sonarjs';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';

const jsFiles = ['**/*.{js,jsx,mjs,cjs}'];
const reactFiles = [
  '**/*.jsx',
  'client-app/**/*.{js,jsx}',
  'hub-app/**/*.{js,jsx}',
  'courier-viz/**/*.{js,jsx}',
  'web-common/**/*.{js,jsx}',
];

export default [
  {
    ignores: [
      '**/node_modules/**', '**/dist/**', '**/build/**', '**/.next/**',
      '**/coverage/**', '**/.work/**', '**/.git/**', '**/vendor/**', '**/var/**',
      '**/*.min.js', '**/*.bundle.js',
    ],
  },
  {
    files: jsFiles,
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser, ...globals.node, ...globals.es2021 },
    },
    rules: {
      ...js.configs.recommended.rules,
      // Warnings for maintainability, not automatic refactoring.
      complexity: ['warn', { max: 15 }],
      'max-depth': ['warn', 4],
      'max-params': ['warn', 5],
      'max-statements': ['warn', 35],
    },
  },
  {
    files: jsFiles,
    ...sonarjs.configs.recommended,
    rules: {
      ...sonarjs.configs.recommended.rules,
      'sonarjs/cognitive-complexity': ['warn', 15],
    },
  },
  {
    files: reactFiles,
    ...react.configs.flat.recommended,
    settings: { react: { version: 'detect' } },
  },
  {
    files: reactFiles,
    ...react.configs.flat['jsx-runtime'],
  },
  {
    files: reactFiles,
    ...reactHooks.configs.flat.recommended,
  },
  {
    files: ['**/*.cjs'],
    languageOptions: { sourceType: 'commonjs' },
  },
];
