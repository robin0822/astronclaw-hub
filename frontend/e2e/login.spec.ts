import { test } from '@playwright/test';
import { loginByUi, mockAstronClawApi } from './support/mock-api';

test.beforeEach(async ({ page }) => {
  await mockAstronClawApi(page);
});

test('登录页可以完成真实路由跳转', async ({ page }) => {
  await loginByUi(page, '/models');
});
