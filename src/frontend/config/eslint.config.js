import js from '@eslint/js';
import ts from 'typescript-eslint';
import boundaries from 'eslint-plugin-boundaries';
import hooks from 'eslint-plugin-react-hooks';
import globals from 'globals';

export default ts.config(
  { ignores: ['dist', 'node_modules'] },
  js.configs.recommended,
  ...ts.configs.recommended,
  {
    files: ['scripts/**/*.mjs'],
    languageOptions: { globals: { ...globals.node } },
  },
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    plugins: { 'react-hooks': hooks, boundaries },
    settings: {
      'import/resolver': {
        node: { extensions: ['.js', '.jsx', '.ts', '.tsx', '.json'] },
      },
      'boundaries/elements': [
        { type: 'app', pattern: 'src/app' },
        { type: 'page', pattern: 'src/pages/*', capture: ['slice'] },
        { type: 'pages-layer', pattern: 'src/pages' },
        { type: 'feature', pattern: 'src/features/*', capture: ['slice'] },
        { type: 'features-layer', pattern: 'src/features' },
        { type: 'entity', pattern: 'src/entities/*', capture: ['slice'] },
        { type: 'entities-layer', pattern: 'src/entities' },
        { type: 'shared', pattern: 'src/shared' },
        { type: 'test', pattern: 'tests' },
      ],
    },
    rules: {
      ...hooks.configs.recommended.rules,
      ...boundaries.configs.recommended.rules,
      'boundaries/dependencies': [
        'error',
        {
          default: 'allow',
          message:
            'Respect frontend layer boundaries: {{from.element.types}} cannot depend on {{to.element.types}}.',
          policies: [
            {
              from: { element: { type: 'page' } },
              disallow: { to: { element: { type: 'app' } } },
            },
            {
              from: { element: { type: 'feature' } },
              disallow: { to: { element: { types: ['app', 'page'] } } },
            },
            {
              from: { element: { type: 'entity' } },
              disallow: { to: { element: { types: ['app', 'page', 'feature'] } } },
            },
            {
              from: { element: { type: 'shared' } },
              disallow: { to: { element: { types: ['app', 'page', 'feature', 'entity'] } } },
            },
            {
              from: { element: { type: 'app' } },
              disallow: {
                to: {
                  element: {
                    types: ['page', 'feature', 'entity'],
                    fileInternalPath: '!index.ts',
                  },
                },
              },
            },
            {
              from: { element: { type: 'page' } },
              disallow: {
                to: {
                  element: {
                    types: ['feature', 'entity'],
                    fileInternalPath: '!index.ts',
                  },
                },
              },
            },
            {
              from: { element: { type: 'feature' } },
              disallow: {
                to: {
                  element: { type: 'entity', fileInternalPath: '!index.ts' },
                },
              },
            },
            {
              from: { element: { types: ['app', 'page', 'feature', 'entity'] } },
              disallow: {
                to: {
                  element: { type: 'shared', fileInternalPath: '!*/index.ts' },
                },
              },
            },
            {
              from: { element: { type: 'page' } },
              disallow: {
                to: {
                  element: {
                    type: 'page',
                    captured: { slice: '!{{ from.element.captured.slice }}' },
                  },
                },
              },
            },
            {
              from: { element: { type: 'feature' } },
              disallow: {
                to: {
                  element: {
                    type: 'feature',
                    captured: { slice: '!{{ from.element.captured.slice }}' },
                  },
                },
              },
            },
            {
              from: { element: { type: 'entity' } },
              disallow: {
                to: {
                  element: {
                    type: 'entity',
                    captured: { slice: '!{{ from.element.captured.slice }}' },
                  },
                },
              },
            },
          ],
        },
      ],
    },
  },
);
