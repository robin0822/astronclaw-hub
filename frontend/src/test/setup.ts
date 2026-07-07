import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { clearAstronClawAccessToken, setAuthRedirectHandler } from '../api/request';
import { server } from './server';

class TestResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// jsdom 不实现 ResizeObserver，Ant Design 下拉组件渲染时需要这个浏览器 API。
if (!globalThis.ResizeObserver) {
  Object.defineProperty(globalThis, 'ResizeObserver', { value: TestResizeObserver, writable: true });
}
beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
});

afterEach(() => {
  cleanup();
  server.resetHandlers();
  setAuthRedirectHandler(undefined);
  clearAstronClawAccessToken();
});

afterAll(() => {
  server.close();
});
