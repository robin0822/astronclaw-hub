import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';
import { loadEnv, type ProxyOptions } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const projectRoot = dirname(fileURLToPath(import.meta.url));

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backendTarget = (env.BACKEND_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');

  const configureProxy: NonNullable<ProxyOptions['configure']> = (proxy) => {
    proxy.on('proxyReq', (_proxyReq, req) => {
      console.info('[backend request]', req.method, req.url, { target: backendTarget });
    });

    proxy.on('proxyRes', (proxyRes, req) => {
      console.info('[backend response]', req.method, req.url, {
        statusCode: proxyRes.statusCode,
      });
    });
  };

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        react: resolve(projectRoot, 'node_modules/react'),
        'react/jsx-runtime': resolve(projectRoot, 'node_modules/react/jsx-runtime.js'),
        'react/jsx-dev-runtime': resolve(projectRoot, 'node_modules/react/jsx-dev-runtime.js'),
        'react-dom': resolve(projectRoot, 'node_modules/react-dom'),
        'react-dom/client': resolve(projectRoot, 'node_modules/react-dom/client.js'),
      },
      dedupe: ['react', 'react-dom'],
    },
    test: {
      environment: 'jsdom',
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
      exclude: ['node_modules/**', 'dist/**', 'e2e/**'],
      setupFiles: './src/test/setup.ts',
      css: true,
    },
    server: {
      host: '0.0.0.0',
      port: 5174,
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true,
          configure: configureProxy,
        },
      },
    },
  };
});
