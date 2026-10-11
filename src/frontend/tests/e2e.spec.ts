import { expect, test, type Page } from '@playwright/test';

async function startChat(page: Page) {
  await page.goto('/');
  await expect(page.getByLabel('Nhắn cho TourLens')).toBeVisible();
}

test('guest chats, compares, and restores the persisted result', async ({ page }) => {
  const legacyRequests: string[] = [];
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/v2/')) legacyRequests.push(request.url());
  });
  await startChat(page);
  await page.getByLabel('Nhắn cho TourLens').fill('Đà Lạt 3 ngày, tối đa 8 triệu/người');
  await page.getByRole('button', { name: 'Gửi', exact: true }).click();
  await expect(page.getByText('Đã hiểu như sau')).toBeVisible();
  await page.getByRole('button', { name: 'Tìm và so sánh tour', exact: true }).click();
  await expect(page.getByText(/tour đạt đủ/)).toBeVisible();
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

  expect(legacyRequests).toEqual([]);
  await page.reload();
  await expect(page.getByText('Đã hiểu như sau')).toBeVisible();
  await expect(page.getByText(/tour đạt đủ/)).toBeVisible();
});

test('account and contact routes clearly report that their backend features are not ported', async ({
  page,
}) => {
  await page.goto('/account');
  await expect(page.getByRole('heading', { name: 'Tài khoản chưa khả dụng.' })).toBeVisible();
  await page.getByRole('button', { name: 'Tiếp tục với guest' }).click();
  await expect(page.getByLabel('Nhắn cho TourLens')).toBeVisible();

  await page.goto('/contact');
  await expect(page.getByRole('heading', { name: 'Liên hệ chưa khả dụng.' })).toBeVisible();
});

test('guest chat fits a narrow mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await startChat(page);
  const sizes = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }));
  expect(sizes.content).toBeLessThanOrEqual(sizes.viewport + 1);
});
