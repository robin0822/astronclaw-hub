import { expect, test, type Page } from '@playwright/test';
import { mockAstronClawApi } from './support/mock-api';

test.setTimeout(120_000);

const appRoutes = ['/agents', '/org', '/monitoring', '/models', '/ops', '/skills', '/knowledge', '/memory', '/seats', '/sharing', '/channels', '/security', '/diagnosis'];

const surfaceSelector = [
  '.toolbar-card',
  '.entity-card',
  '.device-card',
  '.form-card',
  '.summary-card',
  '.table-card',
  '.chart-card',
  '.hero-card',
  '.feature-card',
  '.memory-block',
  '.stat-card',
  '.target-card',
  '.bulk-bar',
  '.info-banner',
  '.empty-state',
  '.arch-layer',
  '.arch-block',
  '.org-node',
  '.perm-group',
  '.selector-item',
  '.switch-row',
].join(', ');

async function enableDarkMode(page: Page) {
  await page.addInitScript(() => window.localStorage.setItem('astronclaw-theme', 'dark'));
}

function parseRgb(value: string) {
  const match = value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
  if (!match) return null;
  const [, red, green, blue, alpha = '1'] = match;
  return {
    red: Number(red),
    green: Number(green),
    blue: Number(blue),
    alpha: Number(alpha),
  };
}

test('theme toggle switches and persists dark mode', async ({ page }) => {
  await mockAstronClawApi(page);
  await page.goto('/login');

  const html = page.locator('html');
  const toggle = page.getByRole('button', { name: '切换到深色模式' });
  await expect(toggle).toBeVisible();

  const lightBackground = await page.locator('.login-page').evaluate((node) => getComputedStyle(node).backgroundImage);
  await toggle.click();

  await expect(html).toHaveAttribute('data-theme', 'dark');
  await expect(page.getByRole('button', { name: '切换到浅色模式' })).toBeVisible();

  const darkBackground = await page.locator('.login-page').evaluate((node) => getComputedStyle(node).backgroundImage);
  expect(darkBackground).not.toBe(lightBackground);

  await page.goto('/agents');
  await expect(html).toHaveAttribute('data-theme', 'dark');
  await expect(page.getByRole('button', { name: '切换到浅色模式' })).toBeVisible();

  const topbarBackground = await page.locator('.topbar').evaluate((node) => getComputedStyle(node).backgroundColor);
  expect(topbarBackground).not.toBe('rgba(0, 0, 0, 0)');
});

test('dark mode covers shared surfaces across app routes', async ({ page }) => {
  await mockAstronClawApi(page);
  await enableDarkMode(page);

  for (const route of appRoutes) {
    await page.goto(route, { waitUntil: 'domcontentloaded' });
    await expect(page).toHaveURL(new RegExp(`${route}(?:$|[?#])`));
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await expect(page.getByRole('button', { name: '切换到浅色模式' })).toBeVisible();
    await expect(page.locator('.page').first()).toBeVisible({ timeout: 15_000 });
    await expect(page.locator(surfaceSelector).first()).toBeVisible({ timeout: 15_000 });

    const audit = await page.evaluate((selector) => {
      const nodes = Array.from(document.querySelectorAll(selector));
      const visibleNodes = nodes.filter((node) => {
        const element = node as HTMLElement;
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
      });

      const lightSurfaces = visibleNodes
        .map((node) => {
          const element = node as HTMLElement;
          const style = getComputedStyle(element);
          const background = style.backgroundColor;
          const image = style.backgroundImage;
          const match = background.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
          const alpha = match?.[4] ? Number(match[4]) : 1;
          const luminance = match ? 0.2126 * Number(match[1]) + 0.7152 * Number(match[2]) + 0.0722 * Number(match[3]) : 0;
          const hasLightGradient = /rgb\(\s*255,\s*255,\s*255\s*\)|#fff/i.test(image);
          const hasLightSolid = alpha > 0.55 && luminance > 165;
          return hasLightGradient || hasLightSolid ? `${element.className} -> ${background} ${image}` : null;
        })
        .filter(Boolean);

      return { count: visibleNodes.length, lightSurfaces };
    }, surfaceSelector);

    expect(audit.count, `${route} should render shared surfaces`).toBeGreaterThan(0);
    expect(audit.lightSurfaces, `${route} has light surfaces in dark mode`).toEqual([]);
  }
});

test('dark mode keeps common form controls dark', async ({ page }) => {
  await mockAstronClawApi(page);
  await enableDarkMode(page);
  await page.goto('/agents', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.search-row input').first()).toBeVisible();

  const controls = await page
    .locator('input, textarea, select, .app-select.ant-select-single, .app-select .ant-select-selector, .app-select .ant-select-content')
    .evaluateAll((nodes) =>
      nodes
        .filter((node) => {
          const element = node as HTMLElement;
          const rect = element.getBoundingClientRect();
          const style = getComputedStyle(element);
          return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
        })
        .map((node) => {
          const element = node as HTMLElement;
          const style = getComputedStyle(element);
          return { className: String(element.className), background: style.backgroundColor, color: style.color };
        }),
    );

  expect(controls.length).toBeGreaterThan(0);
  const lightControls = controls.filter(({ background }) => {
    const color = parseRgb(background);
    if (!color || color.alpha < 0.55) return false;
    const luminance = 0.2126 * color.red + 0.7152 * color.green + 0.0722 * color.blue;
    return luminance > 165;
  });

  expect(lightControls).toEqual([]);
});
