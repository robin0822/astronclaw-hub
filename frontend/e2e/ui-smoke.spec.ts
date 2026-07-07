import { expect, test } from '@playwright/test';
import { appRouteExpectations, loginByUi, mockAstronClawApi } from './support/mock-api';

test.beforeEach(async ({ page }) => {
  await mockAstronClawApi(page);
});

test('登录后可以通过侧边栏访问主要功能页面', async ({ page }) => {
  await loginByUi(page, '/agents');

  for (const route of appRouteExpectations) {
    await page.locator(`.nav-item[href="${route.path}"]`).click();
    await expect(page).toHaveURL(new RegExp(`${route.path}(?:$|[?#])`));
    await expect(page.getByRole('heading', { name: route.heading, level: 1 }).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.locator('.page').first()).toBeVisible({ timeout: 15_000 });
  }

  await page.getByRole('button', { name: '通知中心' }).click();
  const dialog = page.getByRole('dialog', { name: '通知中心' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('待处理告警')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
});

test('智能体列表可以搜索、打开详情并刷新日志', async ({ page }) => {
  await loginByUi(page, '/agents');
  await expect(page.getByText('寿险业务助手').first()).toBeVisible({ timeout: 15_000 });

  await page.getByPlaceholder('按名称、部门、负责人、模型搜索').fill('寿险');
  await expect(page.getByText('寿险业务助手').first()).toBeVisible();
  await page.getByRole('button', { name: '查看详情' }).first().click();

  const dialog = page.getByRole('dialog', { name: /寿险业务助手 实例详情/ });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('远程运行参数')).toBeVisible();

  await dialog.getByRole('button', { name: '手动同步状态' }).click();
  await expect(page.getByText('实例状态已同步')).toBeVisible();

  await dialog.getByRole('button', { name: '查询日志' }).click();
  await expect(dialog.getByText('模型调用正常')).toBeVisible();
});

test('公开分享页可以展示后端授权资源', async ({ page }) => {
  await page.goto('/share/ac-agent-001?token=share-token');

  await expect(page.getByRole('heading', { name: '寿险业务助手', level: 1 })).toBeVisible();
  await expect(page.getByText('后端授权分享')).toBeVisible();
  await expect(page.getByText('合同条款抽取')).toBeVisible();
  await expect(page.getByText('寿险事业部')).toBeVisible();
});
