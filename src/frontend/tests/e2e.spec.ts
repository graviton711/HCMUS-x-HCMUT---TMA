import { expect, test, type Page } from '@playwright/test';

async function startGuestSearch(page: Page) {
  await page.goto('/tours');
  await page.getByRole('main').getByRole('button', { name: 'Phiên mới', exact: true }).click();
  await expect(page.getByLabel('Mô tả chuyến đi')).toBeVisible();
}

test('guest interprets, compares, and restores the persisted current-backend result', async ({
  page,
}) => {
  await startGuestSearch(page);
  await page.getByLabel('Mô tả chuyến đi').fill('Đà Lạt 3 ngày, tối đa 8 triệu/người');
  await page.getByLabel('Điểm đến trong catalog').fill('Đà Lạt');
  await page.getByRole('button', { name: 'Diễn giải nhu cầu', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Backend đã hiểu' })).toBeVisible();
  await page.getByRole('button', { name: 'Tìm và so sánh tour', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Các tour có thể đối chiếu' })).toBeVisible();
  await expect(page.locator('.current-tour-card').first()).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => {
        const saved = JSON.parse(localStorage.getItem('di-cung:history:v1') ?? '[]') as {
          comparisonId?: string;
        }[];
        return saved.some(
          (item) => typeof item.comparisonId === 'string' && item.comparisonId.length > 0,
        );
      }),
    )
    .toBe(true);

  await page.reload();
  await expect(page.getByRole('heading', { name: 'Các tour có thể đối chiếu' })).toBeVisible();
  await expect(page.locator('.current-tour-card').first()).toBeVisible();
});

test('account and contact routes clearly report that their backend features are not ported', async ({
  page,
}) => {
  await page.goto('/account');
  await expect(page.getByRole('heading', { name: 'Tài khoản chưa khả dụng.' })).toBeVisible();
  await page.getByRole('button', { name: 'Tiếp tục với guest' }).click();
  await expect(page.getByLabel('Mô tả chuyến đi')).toBeVisible();

  await page.goto('/contact');
  await expect(page.getByRole('heading', { name: 'Liên hệ chưa khả dụng.' })).toBeVisible();
});

test('guest workspace fits a narrow mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await startGuestSearch(page);
  const sizes = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }));
  expect(sizes.content).toBeLessThanOrEqual(sizes.viewport + 1);
});
