import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import {
  comparison as validateComparison,
  record,
  requirement as validateRequirement,
  whatIf as validateWhatIf,
} from '../api/contracts';
import { formFromRequirement } from '../api/form';
import type { Comparison, Evidence, Requirement, WhatIf } from '../api/types';
import type { LocalSession, SessionAccess } from '../app/storage';

const screenshots = resolve(import.meta.dirname, '../../../artifacts/frontend');
test('Account profile: personal edits, round avatar, photo upload/removal and responsive sections', async ({
  page,
}) => {
  test.skip(process.env.E2E_AUTH_STUB !== '1', 'Uses isolated Auth/Storage only.');
  const root = resolve(import.meta.dirname, '../../..');
  const python = resolve(root, '.venv/Scripts/python.exe');
  const image = execFileSync(python, [
    '-c',
    "from PIL import Image; import sys; Image.new('RGB',(320,240),(50,90,60)).save(sys.stdout.buffer,format='JPEG')",
  ]);
  await page.route('https://browser-auth.example.test/storage/**', (route) =>
    route.fulfill({ status: 200, contentType: 'image/jpeg', body: image }),
  );
  await page.goto('/auth');
  await page.getByLabel('Email', { exact: true }).fill('browser@example.test');
  await page.getByLabel('Mật khẩu', { exact: true }).fill('test-password');
  await page.locator('.auth-submit').click();
  await expect(page).toHaveURL(/\/tours/);
  await page.goto('/account');
  await expect(page.locator('.account-nav')).toHaveCount(1);
  await expect(page.locator('.account-avatar-link .profile-avatar')).toBeVisible();
  await capture(page, 'account-new-overview-desktop');
  await page.getByRole('button', { name: 'Hồ sơ', exact: true }).click();
  await page.getByLabel('Tên hiển thị').fill('Nguyễn An');
  await page.getByLabel('Số điện thoại').fill('+84 123456789');
  await page.getByLabel('Thành phố bạn sống').fill('Hồ Chí Minh');
  await page.getByLabel('Giới thiệu ngắn').fill('Thích đi chậm và gần thiên nhiên.');
  await page.getByRole('button', { name: 'Lưu hồ sơ', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Đã lưu hồ sơ.');
  await expect(page.locator('.account-avatar-link')).toHaveText('NA');
  await page
    .getByLabel('Chọn ảnh đại diện')
    .setInputFiles({ name: 'portrait.jpg', mimeType: 'image/jpeg', buffer: image });
  await expect(page.locator('.profile-photo-editor img')).toBeVisible();
  await page.getByRole('button', { name: 'Lưu ảnh', exact: true }).click();
  await expect(page.locator('.account-avatar-link img')).toBeVisible();
  await expect(page.locator('.account-avatar-link img')).toHaveJSProperty('naturalWidth', 320);
  await page.reload();
  await expect(page.getByLabel('Thành phố bạn sống')).toHaveValue('Hồ Chí Minh');
  await expect(page.locator('.account-avatar-link img')).toBeVisible();
  await page.evaluate(() => {
    (document.activeElement as HTMLElement)?.blur();
    window.scrollTo(0, 0);
  });
  await capture(page, 'account-new-profile-desktop');
  await noOverflow(page);
  await page.getByRole('button', { name: 'Tour lưu', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Hồ sơ cá nhân' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Tour đã lưu 0' })).toBeVisible();
  await page.getByRole('button', { name: 'Cài đặt', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Cài đặt tài khoản' })).toBeVisible();
  await capture(page, 'account-new-settings-desktop');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Hồ sơ', exact: true }).click();
  await capture(page, 'account-new-profile-mobile');
  await noOverflow(page);
  await page.setViewportSize({ width: 320, height: 780 });
  await expect(page.locator('.account-avatar-link img')).toBeVisible();
  await capture(page, 'account-new-profile-320');
  await noOverflow(page);
  await page.getByRole('button', { name: 'Chọn ngôn ngữ', exact: true }).first().click();
  await page.getByRole('button', { name: 'English', exact: true }).click();
  await page.getByRole('button', { name: 'Switch to dark mode', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'Personal profile' })).toBeVisible();
  await capture(page, 'account-new-profile-dark-en-320');
  await noOverflow(page);
  await page.getByRole('button', { name: 'Remove photo', exact: true }).click();
  await expect(page.locator('.account-avatar-link img')).toHaveCount(0);
  await expect(page.locator('.account-avatar-link')).toHaveText('NA');
  await page.reload();
  await expect(page.locator('.account-avatar-link')).toHaveText('NA');
});
test('Profile Hub saves preferences and explicitly starts a fresh draft on desktop/mobile', async ({
  page,
}) => {
  test.skip(
    process.env.E2E_AUTH_STUB !== '1',
    'Uses loopback Auth and personal REST harness only.',
  );
  await page.goto('/auth');
  await page.getByLabel('Email', { exact: true }).fill('browser@example.test');
  await page.getByLabel('Mật khẩu', { exact: true }).fill('test-password');
  await page.locator('.auth-submit').click();
  await expect(page).toHaveURL(/\/tours/);
  await page.goto('/account');
  await page.getByRole('button', { name: 'Sở thích', exact: true }).click();
  await expect(page.getByLabel('Khách sạn mong muốn')).toBeVisible();
  await page.getByLabel('Khách sạn mong muốn').selectOption('4');
  await page.getByLabel('Ưu tiên giá tour niêm yết thấp hơn trong nhóm đạt điều kiện').check();
  await page.getByRole('button', { name: 'Lưu sở thích', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Lưu sở thích', exact: true })).toBeEnabled();
  await page.reload();
  await expect(page.getByLabel('Khách sạn mong muốn')).toHaveValue('4');
  await page.evaluate(() => window.scrollTo(0, 0));
  await capture(page, 'profile-hub-desktop-vi');
  await noOverflow(page);
  await page.getByRole('button', { name: 'Dùng cho chuyến mới', exact: true }).click();
  await expect(page).toHaveURL(/\/tours\?session=/);
  await expect(page.getByText('Đã tạo bản nháp mới.', { exact: false })).toBeVisible();
  const draft = await page.evaluate(() => {
    const key = Object.keys(localStorage).find((k) => k.startsWith('di-cung:history:v1:user:'))!;
    return JSON.parse(localStorage.getItem(key)!)[0].draft;
  });
  expect(draft.hotelStars).toBe('4');
  expect(draft.adults).toBe(0);
  expect(draft.budget).toBe('');
  expect(draft.departureMonths).toEqual([]);
  await page.goto('/account');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Sở thích', exact: true }).click();
  await capture(page, 'profile-hub-mobile-vi');
  await noOverflow(page);
  await page.getByRole('button', { name: 'Chọn ngôn ngữ', exact: true }).first().click();
  await page.getByRole('button', { name: 'English', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Travel preferences', exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Switch to dark mode', exact: true }).first().click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await capture(page, 'profile-hub-mobile-dark-en');
  await noOverflow(page);
  await page.getByRole('button', { name: 'Delete saved preferences', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Delete', exact: true }).click();
  await expect(page.getByLabel('Desired hotel standard')).toHaveValue('');
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page).toHaveURL(/\/auth/);
  await page.goto('/account');
  await expect(
    page.getByRole('heading', { name: 'Take your plans with you', exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel('Desired hotel standard')).toHaveCount(0);
});
// Public help checks are isolated from real tickets, auth accounts and tour sources.
async function isolateHelp(page: Page) {
  await page.route('**/v2/**', (route) => route.abort());
  await page.route('**/auth/**', (route) => route.abort());
}
async function capture(page: Page, name: string, fullPage = true) {
  await mkdir(screenshots, { recursive: true });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(
      document
        .getAnimations()
        .filter(
          (animation) =>
            animation.playState === 'running' &&
            Number.isFinite(animation.effect?.getComputedTiming().endTime),
        )
        .map((animation) => animation.finished.catch(() => undefined)),
    );
  });
  await page.screenshot({ path: resolve(screenshots, `${name}.png`), fullPage });
}
async function noOverflow(page: Page) {
  const sizes = await page.evaluate(() => ({
    width: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }));
  expect(sizes.scroll, `Document overflow at ${sizes.width}px`).toBeLessThanOrEqual(
    sizes.width + 1,
  );
}
async function begin(page: Page) {
  await page.goto('/auth');
  await expect(
    page.getByRole('button', { name: 'Tiếp tục bằng Google', exact: true }),
  ).toBeDisabled();
  await page.getByRole('button', { name: 'Tiếp tục với phiên ẩn danh', exact: true }).click();
  await expect(page.getByRole('combobox', { name: 'Điểm đến', exact: true })).toBeVisible();
}

test('footer help links preserve route, focus, keyboard FAQ and contact draft intent', async ({
  page,
}) => {
  await isolateHelp(page);
  await page.goto('/');
  const footer = page.getByRole('contentinfo');
  for (const id of ['compare', 'faq', 'sources', 'privacy', 'security', 'scope']) {
    await footer.locator(`a[href="/support#${id}"]`).click();
    await expect(page).toHaveURL(new RegExp(`/support#${id}$`));
    const heading = page.locator(`#${id}`);
    await expect(heading).toBeFocused();
    const position = await heading.boundingBox();
    const header = await page.locator('.site-header').boundingBox();
    expect(position!.y).toBeGreaterThanOrEqual(header!.y + header!.height);
  }
  await page.goBack();
  await expect(page.locator('#security')).toBeFocused();
  await page.goForward();
  await expect(page.locator('#scope')).toBeFocused();
  await footer.locator('a[href="/support#faq"]').click();
  // Re-entering the same anchor must scroll and focus after the footer was reached.
  await footer.locator('a[href="/support#faq"]').click();
  await expect(page.locator('#faq')).toBeFocused();
  const summary = page.locator('.support-faq summary').first();
  await page.keyboard.press('Tab');
  await expect(summary).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('.support-faq details').first()).toHaveAttribute('open', '');
  await expect(page.locator('.support-faq details').first().locator('p')).toBeVisible();
  await page.keyboard.press('Space');
  await expect(page.locator('.support-faq details').first()).not.toHaveAttribute('open', '');
  await page.keyboard.press('Enter');
  await page.getByRole('button', { name: 'Chọn ngôn ngữ', exact: true }).click();
  await page.getByRole('button', { name: 'English', exact: true }).click();
  await expect(page.locator('.support-faq details').first()).toHaveAttribute('open', '');
  await expect(summary).toHaveText('Why are there no recommendations?');
  await page.getByRole('button', { name: 'Choose language', exact: true }).click();
  await page.getByRole('button', { name: 'Tiếng Việt', exact: true }).click();
  await footer.locator('a[href="/contact?category=data_issue"]').click();
  await expect(page.getByRole('combobox')).toHaveValue('data_issue');
  const message = page.getByRole('textbox', { name: 'Bạn muốn nhắn điều gì?' });
  const email = page.getByRole('textbox', { name: 'Email liên hệ (tùy chọn)' });
  await message.fill('Kiểm tra https://example.test/tour, lịch và giá hiển thị.');
  await email.fill('browser@example.test');
  await footer.locator('a[href="/contact"]').click();
  await expect(page.getByRole('combobox')).toHaveValue('feedback');
  await expect(message).toHaveValue('Kiểm tra https://example.test/tour, lịch và giá hiển thị.');
  await expect(email).toHaveValue('browser@example.test');
  await page.goBack();
  await expect(page.getByRole('combobox')).toHaveValue('data_issue');
  await expect(message).toHaveValue('Kiểm tra https://example.test/tour, lịch và giá hiển thị.');
  await page.goto('/contact?category=admin');
  await expect(page.getByRole('combobox')).toHaveValue('feedback');
  await page.goto('/support#privacy');
  await expect(page.locator('#privacy')).toBeFocused();
  await page.reload();
  await expect(page.locator('#privacy')).toBeFocused();
  await noOverflow(page);
});

test('footer help layout stays usable in VI/EN, both themes and desktop/mobile widths', async ({
  page,
}) => {
  test.setTimeout(90_000);
  await isolateHelp(page);
  await mkdir(screenshots, { recursive: true });
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  for (const width of [1440, 1280, 390, 320]) {
    await page.setViewportSize({ width, height: 960 });
    for (const locale of ['vi', 'en']) {
      for (const theme of ['light', 'dark']) {
        await page.goto('/');
        await page.evaluate(
          ({ locale, theme }) => {
            localStorage.setItem('di-cung-display-v1', JSON.stringify({ locale, theme }));
          },
          { locale, theme },
        );
        await page.goto('/support#faq');
        await expect(page.locator('html')).toHaveAttribute('lang', locale);
        await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
        await page.locator('.support-faq summary').first().click();
        await noOverflow(page);
        const footer = page.getByRole('contentinfo');
        await expect(footer.getByRole('navigation')).toHaveCount(3);
        for (const anchor of await footer.locator('a').all()) {
          const box = await anchor.boundingBox();
          expect(box!.height).toBeGreaterThanOrEqual(44);
          expect(box!.x).toBeGreaterThanOrEqual(0);
          expect(box!.x + box!.width).toBeLessThanOrEqual(width);
        }
        await footer.scrollIntoViewIfNeeded();
        await footer.screenshot({
          path: resolve(screenshots, `footer-help-${width}-${theme}-${locale}.png`),
        });
        if (width === 1440 || width === 390) {
          await page.locator('#faq').scrollIntoViewIfNeeded();
          await capture(page, `support-faq-${width}-${theme}-${locale}`, false);
        }
      }
    }
  }
  expect(errors).toEqual([]);
});
async function fillTrip(page: Page) {
  await page.getByRole('combobox', { name: 'Điểm đến', exact: true }).selectOption('country:jp');
  await page
    .getByRole('combobox', { name: 'Khởi hành từ', exact: true })
    .selectOption('city:vn:hcmc');
  await chooseMonth(page, '2026-11');
  await chooseMonth(page, '2027-01');
  await page.getByLabel('Người lớn', { exact: true }).fill('2');
  await page
    .getByRole('spinbutton', { name: 'Giá tối thiểu (VND/người lớn)', exact: true })
    .fill('10000000');
  await page
    .getByRole('spinbutton', { name: 'Giá tối đa (VND/người lớn)', exact: true })
    .fill('35000000');
  await page.locator('.optional-fields summary').click();
  await page.getByRole('spinbutton', { name: 'Thời lượng khoảng (ngày)', exact: true }).fill('5');
}
async function chooseMonth(page: Page, month: string) {
  const target = Number(month.slice(0, 4));
  const picker = page.locator('.month-picker');
  let year = Number(await picker.locator('.month-year output').textContent());
  while (year !== target) {
    await picker
      .getByRole('button', { name: year < target ? 'Năm tiếp theo' : 'Năm trước', exact: true })
      .click();
    year = Number(await picker.locator('.month-year output').textContent());
  }
  await picker
    .getByRole('button', { name: `tháng ${Number(month.slice(5))} năm ${target}`, exact: true })
    .click();
}
async function backendRequirement(page: Page): Promise<Requirement> {
  const saved = await page.evaluate(() => {
    const id = new URLSearchParams(location.search).get('session');
    const sessions: unknown = JSON.parse(localStorage.getItem('di-cung:history:v1') ?? '[]');
    const entries: unknown = JSON.parse(sessionStorage.getItem('di-cung:access:v1') ?? '{}');
    if (!Array.isArray(sessions) || !entries || typeof entries !== 'object' || !id)
      throw new Error('Session was not persisted');
    const session: unknown = sessions.find(
      (candidate: unknown) =>
        candidate && typeof candidate === 'object' && 'id' in candidate && candidate.id === id,
    );
    const access: unknown = (entries as Record<string, unknown>)[id];
    if (
      !session ||
      typeof session !== 'object' ||
      !('requirementId' in session) ||
      typeof session.requirementId !== 'string' ||
      !access ||
      typeof access !== 'object' ||
      !('token' in access) ||
      typeof access.token !== 'string'
    )
      throw new Error('Backend access was not persisted');
    return { requirementId: session.requirementId, token: access.token };
  });
  const response = await page.request.get(`/v2/requirements/${saved.requirementId}`, {
    headers: { Authorization: `Bearer ${saved.token}` },
  });
  expect(response.ok()).toBe(true);
  const raw: unknown = await response.json();
  const data = record(raw).data;
  validateRequirement(data);
  return data as Requirement;
}

test('responsive public pages and workspace stay within the viewport in both languages and themes', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  for (const width of [1440, 1280, 390, 320]) {
    await page.setViewportSize({ width, height: 960 });
    for (const route of ['/', '/auth', '/contact', '/support']) {
      await page.goto(route);
      await expect(page.getByRole('main')).toBeVisible();
      await noOverflow(page);
      if (route === '/') await capture(page, `landing-${width}-light-vi`);
      if (route === '/auth' && width === 320) await capture(page, 'auth-320-light-vi');
    }
    await begin(page);
    await noOverflow(page);
    if (width === 1440) await capture(page, 'workspace-desktop-light-vi');
    if (width === 390) await capture(page, 'workspace-mobile-light-vi');
    await expect(
      page.getByRole('button', { name: 'Chuyển sang giao diện tối', exact: true }),
    ).toBeVisible();
    await page
      .locator('.site-header')
      .screenshot({ path: resolve(screenshots, `header-controls-${width}-light-vi.png`) });
    const languageButton = page.getByRole('button', { name: 'Chọn ngôn ngữ', exact: true });
    await languageButton.click();
    const preferencesBox = await page.locator('.preferences-panel').boundingBox();
    expect(preferencesBox).not.toBeNull();
    if (preferencesBox) {
      expect(preferencesBox.x).toBeGreaterThanOrEqual(0);
      expect(preferencesBox.x + preferencesBox.width).toBeLessThanOrEqual(width);
    }
    if (width === 1440 || width === 390)
      await capture(page, `language-menu-${width}-light-vi`, false);
    await page.keyboard.press('Escape');
    await expect(page.locator('.preferences-panel')).toHaveCount(0);
    await expect(languageButton).toBeFocused();
    await languageButton.click();
    await page.getByRole('button', { name: 'English', exact: true }).click();
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
    await expect(page.locator('.preferences-panel')).toHaveCount(0);
    await page.getByRole('button', { name: 'Choose language', exact: true }).click();
    await page.getByRole('button', { name: 'Switch to dark mode', exact: true }).click();
    await expect(page.locator('.preferences-panel')).toHaveCount(0);
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await noOverflow(page);
    await capture(page, `workspace-${width}-dark-en`);
    for (const route of ['/', '/auth', '/contact', '/support']) {
      await page.goto(route);
      await expect(page.getByRole('main')).toBeVisible();
      await noOverflow(page);
      if (route === '/' && width === 320) await capture(page, 'landing-320-dark-en');
    }
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await page.getByRole('button', { name: 'Choose language', exact: true }).click();
    await page.getByRole('button', { name: 'Tiếng Việt', exact: true }).click();
    await page.getByRole('button', { name: 'Chuyển sang giao diện sáng', exact: true }).click();
  }
  expect(errors).toEqual([]);
});

test('auth is explicit about missing service and anonymous drafts survive switching and reload', async ({
  page,
}) => {
  await page.goto('/auth');
  await expect(
    page.getByText(
      'Đăng nhập tài khoản chưa khả dụng. Bạn vẫn có thể tìm tour bằng phiên ẩn danh.',
      { exact: true },
    ),
  ).toBeVisible();
  await expect(page.locator('.auth-submit')).toBeDisabled();
  await page.getByRole('button', { name: 'Tạo tài khoản', exact: true }).first().click();
  await expect(page.getByLabel('Họ và tên', { exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Tiếp tục với phiên ẩn danh', exact: true }).click();
  await page
    .getByRole('textbox', { name: 'Ghi chú', exact: true })
    .fill('E2E: bản nháp chuyến đi đầu tiên');
  const firstUrl = page.url();
  await page.getByRole('button', { name: 'Phiên mới', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Ghi chú', exact: true })).toHaveValue('');
  await page
    .getByRole('textbox', { name: 'Ghi chú', exact: true })
    .fill('E2E: bản nháp chuyến đi thứ hai');
  await page.goto(firstUrl);
  await expect(page.getByRole('textbox', { name: 'Ghi chú', exact: true })).toHaveValue(
    'E2E: bản nháp chuyến đi đầu tiên',
  );
  await page.reload();
  await expect(page.getByRole('textbox', { name: 'Ghi chú', exact: true })).toHaveValue(
    'E2E: bản nháp chuyến đi đầu tiên',
  );
  await expect(page.locator('.session-item:visible')).toHaveCount(2);
  await expect(page.locator('.account-link')).toHaveText('Đăng nhập');
  await page.getByRole('button', { name: 'Đổi tên phiên', exact: true }).first().click();
  await page.getByLabel('Tên phiên', { exact: true }).fill('E2E Nhật Bản');
  await page.getByRole('button', { name: 'Lưu tên', exact: true }).click();
  await expect(page.locator('.session-list:visible')).toContainText('E2E Nhật Bản');
  await capture(page, 'sidebar-draft-desktop');
});

test('sidebar rail, resizing, price sliders and footer anchors work on desktop and mobile', async ({
  page,
}) => {
  await begin(page);
  const sidebar = page.locator('.session-sidebar');
  await expect(
    page.getByRole('button', { name: 'Thu gọn lịch sử phiên', exact: true }),
  ).toHaveCount(1);
  await expect(page.locator('.history-toggle')).toBeHidden();
  const separator = page.getByRole('separator', { name: 'Độ rộng lịch sử phiên' });
  await separator.focus();
  await page.keyboard.press('ArrowRight');
  await expect(separator).toHaveAttribute('aria-valuenow', '316');
  const box = await separator.boundingBox();
  if (!box) throw new Error('Missing resize handle');
  await page.mouse.move(box.x + 3, box.y + 150);
  await page.mouse.down();
  await page.mouse.move(420, box.y + 150, { steps: 8 });
  await page.mouse.up();
  await expect(separator).toHaveAttribute('aria-valuenow', '420');
  await capture(page, 'sidebar-resized-420', false);

  const track = page.locator('.budget-track');
  await track.scrollIntoViewIfNeeded();
  const trackBox = await track.boundingBox();
  if (!trackBox) throw new Error('Missing price slider track');
  await page.mouse.move(trackBox.x + trackBox.width / 2, trackBox.y + 20);
  await page.mouse.down();
  await page.mouse.move(trackBox.x + 9 + (trackBox.width - 18) * 0.7, trackBox.y + 20, {
    steps: 8,
  });
  await page.mouse.up();
  expect(
    Number(
      await page
        .getByRole('spinbutton', { name: 'Giá tối đa (VND/người lớn)', exact: true })
        .inputValue(),
    ),
  ).toBeGreaterThan(65_000_000);
  await page
    .getByRole('spinbutton', { name: 'Giá tối đa (VND/người lớn)', exact: true })
    .fill('50000000');

  const minimum = page.getByRole('slider', { name: 'Kéo giá tối thiểu', exact: true });
  const maximum = page.getByRole('slider', { name: 'Kéo giá tối đa', exact: true });
  await minimum.focus();
  await page.keyboard.press('End');
  await expect(
    page.getByRole('spinbutton', { name: 'Giá tối thiểu (VND/người lớn)', exact: true }),
  ).toHaveValue('50000000');
  await maximum.focus();
  await page.keyboard.press('Home');
  await expect(
    page.getByRole('spinbutton', { name: 'Giá tối đa (VND/người lớn)', exact: true }),
  ).toHaveValue('50000000');
  await minimum.focus();
  await page.keyboard.press('Home');
  await page.keyboard.press('ArrowRight');
  await expect(
    page.getByRole('spinbutton', { name: 'Giá tối thiểu (VND/người lớn)', exact: true }),
  ).toHaveValue('500000');
  await page
    .getByRole('spinbutton', { name: 'Giá tối đa (VND/người lớn)', exact: true })
    .fill('123456789');
  await expect(maximum).toHaveValue('123456789');
  await minimum.focus();
  await page.keyboard.press('ArrowRight');
  await expect(
    page.getByRole('spinbutton', { name: 'Giá tối đa (VND/người lớn)', exact: true }),
  ).toHaveValue('123456789');
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));

  await page.getByRole('button', { name: 'Thu gọn lịch sử phiên', exact: true }).click();
  expect((await sidebar.boundingBox())?.width).toBe(64);
  await capture(page, 'sidebar-collapsed-rail', false);
  await page.reload();
  const rail = page.getByRole('button', { name: 'Mở lịch sử phiên', exact: true });
  await expect(rail).toBeVisible();
  await rail.click({ position: { x: 32, y: 350 } });
  await expect(separator).toHaveAttribute('aria-valuenow', '420');
  await page.getByRole('button', { name: 'Thu gọn lịch sử phiên', exact: true }).click();
  await rail.focus();
  await page.keyboard.press('Enter');
  await expect(separator).toBeVisible();
  await noOverflow(page);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(sidebar).toBeHidden();
  await page.getByRole('button', { name: 'Ẩn / hiện lịch sử phiên', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Lịch sử phiên', exact: true })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', { name: 'Lịch sử phiên', exact: true })).toBeHidden();
  await page.reload();
  await page.setViewportSize({ width: 1440, height: 960 });
  await expect(separator).toHaveAttribute('aria-valuenow', '420');
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .locator('.page-footer')
    .getByRole('link', { name: 'Dữ liệu & quyền riêng tư', exact: true })
    .click();
  await expect(page).toHaveURL(/\/support#privacy$/);
  await expect(page.locator('#privacy')).toBeVisible();
  await noOverflow(page);
});

test('actual backend structured review/edit/confirm works and synthetic provider cannot publish a search', async ({
  page,
}) => {
  const health: unknown = await (await page.request.get('/health')).json();
  test.skip(
    record(health).data_origin !== 'synthetic',
    'This gate test requires the fixture provider and never calls a live search.',
  );
  const comparisonPosts: string[] = [];
  page.on('request', (request) => {
    if (request.method() === 'POST' && new URL(request.url()).pathname === '/v2/comparisons')
      comparisonPosts.push(request.url());
  });
  await begin(page);
  await fillTrip(page);
  await page
    .getByRole('textbox', { name: 'Ghi chú', exact: true })
    .fill('E2E: structured requirement integration');
  await page.getByRole('button', { name: 'Xem lại nhu cầu', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Xác nhận nhu cầu chuyến đi' })).toBeVisible();
  await page.getByRole('button', { name: 'Xác nhận nhu cầu', exact: true }).click();
  await expect(page.getByText('Nhu cầu đã được xác nhận', { exact: true })).toBeVisible();
  const committed = await backendRequirement(page);
  expect(committed.revision).toBe(1);
  expect(committed.party.adults).toBe(2);
  expect(committed.notes).toBe('E2E: structured requirement integration');
  expect(committed.conditions.find((c) => c.field === 'duration_days')).toMatchObject({
    operator: 'near',
    strength: 'soft',
    value: { amount: 5 },
  });
  expect(
    committed.conditions.filter((c) => c.field === 'departure_date').map((c) => c.value),
  ).toMatchObject([
    { value: '2026-11-01', upper: '2026-11-30' },
    { value: '2027-01-01', upper: '2027-01-31' },
  ]);
  expect(committed.hard_tree.children).toContainEqual({
    kind: 'any',
    condition_id: null,
    children: [
      { kind: 'predicate', condition_id: 'condition_departure_month_2026_11', children: [] },
      { kind: 'predicate', condition_id: 'condition_departure_month_2027_01', children: [] },
    ],
  });
  await page.getByRole('button', { name: 'Sửa nhiều mục', exact: true }).click();
  await page
    .getByRole('spinbutton', { name: 'Giá tối đa (VND/người lớn)', exact: true })
    .fill('32000000');
  await chooseMonth(page, '2027-03');
  await chooseMonth(page, '2026-11');
  await page.getByRole('spinbutton', { name: 'Thời lượng khoảng (ngày)', exact: true }).fill('7');
  await page.getByRole('button', { name: 'Xem thay đổi', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Kiểm tra thay đổi', exact: true })).toBeVisible();
  expect((await backendRequirement(page)).revision).toBe(1);
  await capture(page, 'proposal-desktop-light-vi');
  await page.getByRole('button', { name: 'Xác nhận tất cả', exact: true }).click();
  await expect(page.getByText('Nhu cầu đã được xác nhận', { exact: true })).toBeVisible();
  const updated = await backendRequirement(page);
  expect(updated.revision).toBe(2);
  expect(updated.conditions.find((c) => c.field === 'duration_days')).toMatchObject({
    operator: 'near',
    strength: 'soft',
    value: { amount: 7 },
  });
  expect(updated.conditions.find((c) => c.field === 'estimated_cost')?.value).toMatchObject({
    amount: 10000000,
    upper: 32000000,
  });
  expect(
    updated.conditions.filter((c) => c.field === 'departure_date').map((c) => c.value),
  ).toMatchObject([
    { value: '2027-01-01', upper: '2027-01-31' },
    { value: '2027-03-01', upper: '2027-03-31' },
  ]);
  await page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Nguồn tour chưa được kết nối');
  expect(comparisonPosts).toEqual([]);
  await expect(page.locator('.compare-table')).toHaveCount(0);
  await expect(page.locator('.tour-card')).toHaveCount(0);
  await noOverflow(page);
  await capture(page, 'confirmed-provider-gate-desktop');
  await page.reload();
  await expect(page.getByText('Nhu cầu đã được xác nhận', { exact: true })).toBeVisible();
  expect((await backendRequirement(page)).revision).toBe(2);
});

test('contact submits one real ticket without representing it as an email send', async ({
  page,
}) => {
  await page.goto('/contact');
  await page.getByRole('combobox', { name: 'Loại liên hệ', exact: true }).selectOption('support');
  await page
    .getByRole('textbox', { name: 'Bạn muốn nhắn điều gì?', exact: true })
    .fill('E2E: browser contact integration, no email requested.');
  const received = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === '/v2/contacts' && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Gửi liên hệ', exact: true }).click();
  const response = await received;
  expect(response.status()).toBe(201);
  const raw: unknown = await response.json(),
    data = record(record(raw).data);
  expect(typeof data.ticket_id).toBe('string');
  await expect(page.getByRole('status')).toContainText(String(data.ticket_id));
  expect(response.request().postDataJSON()).toMatchObject({
    category: 'support',
    reply_to: null,
    message: 'E2E: browser contact integration, no email requested.',
  });
  await expect(
    page.getByRole('textbox', { name: 'Bạn muốn nhắn điều gì?', exact: true }),
  ).toHaveValue('');
  await noOverflow(page);
  await capture(page, 'contact-ticket-desktop');
});

test('URL-only notes remain a pending proposal until explicit confirmation through actual backend', async ({
  page,
}) => {
  await begin(page);
  await page.getByRole('button', { name: 'So sánh URL', exact: true }).click();
  await page
    .getByRole('textbox', { name: /^URL tour cần đối chiếu/ })
    .fill('https://tour-demo.invalid/tour-a');
  await page
    .getByRole('textbox', { name: 'Ghi chú', exact: true })
    .fill('E2E: retain URL-only notes until confirmation.');
  await page.getByRole('button', { name: 'Xem lại nhu cầu', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Kiểm tra thay đổi', exact: true })).toBeVisible();
  const draft = await backendRequirement(page);
  expect(draft.revision).toBe(0);
  expect(draft.notes).toBe('');
  await expect(page.locator('.notes-copy')).toHaveText(
    'E2E: retain URL-only notes until confirmation.',
  );
  await page.getByRole('button', { name: 'Xác nhận tất cả', exact: true }).click();
  await expect(page.getByText('Nhu cầu đã được xác nhận', { exact: true })).toBeVisible();
  const confirmed = await backendRequirement(page);
  expect(confirmed.revision).toBe(1);
  expect(confirmed.notes).toBe('E2E: retain URL-only notes until confirmation.');
  expect(confirmed.party.adults).toBeNull();
  expect(confirmed.preference_levels).toBeNull();
});

test('comparison contract example keeps eight columns within its own scroll region and opens evidence', async ({
  page,
}) => {
  test.setTimeout(45_000);
  const root = resolve(import.meta.dirname, '../../..');
  const python = resolve(
    root,
    process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python',
  );
  const raw: unknown = JSON.parse(
    execFileSync(python, [resolve(root, 'src/frontend/api/verify_backend.py')], {
      cwd: root,
      encoding: 'utf8',
      timeout: 30_000,
      maxBuffer: 4 * 1024 * 1024,
    }),
  );
  if (!Array.isArray(raw)) throw new Error('Invalid isolated backend response capture');
  const captured = raw.map((entry) => record(entry));
  const responseFor = (name: string) =>
    record(captured.find((entry) => entry.name === name)?.response);
  const comparisonResponse = responseFor('published comparison');
  validateComparison(comparisonResponse.data);
  const comparison = structuredClone(comparisonResponse.data) as Comparison;
  const result = comparison.result;
  if (!result) throw new Error('Missing completed contract result');
  result.origin = 'source'; // Test copy only; production synthetic results remain blocked.
  result.recommendations.truncated = true;
  result.analysis.retrieval = {
    runs: [{ scanned_count: 1000, retained_count: result.columns.length, scan_truncated: true }],
  }; // Test-only bounded retrieval for diagnosis layout at each viewport.
  const requirement = result.requirement_snapshot;
  for (const column of result.columns) {
    column.origin = 'discovery';
    column.target_ids = [];
  }
  requirement.targets = Array.from({ length: 5 }, (_, i) => ({
    target_id: `target_layout_${i}`,
    url: `https://example.invalid/reference-${i}`,
  }));
  requirement.reference_urls = requirement.targets.map((target) => target.url);
  for (const target of requirement.targets) {
    result.columns.push({
      id: target.target_id,
      candidate_id: null,
      tour_id: null,
      tour_snapshot_id: null,
      offer_snapshot_id: null,
      selected_offer_snapshot_id: null,
      title: null,
      title_reason: 'TITLE_NOT_PROVIDED',
      supplier: null,
      canonical_url: target.url,
      origin: 'reference',
      target_ids: [target.target_id],
      source_ids: [],
      offer_reason: 'TARGET_RESULT_MISSING',
      offer_options: [],
      eligible_offer_snapshot_ids: [],
      offer_assessments: [],
      offers_complete: false,
    });
    for (const row of result.rows)
      result.cells.push({
        row_id: row.id,
        column_id: target.target_id,
        value: null,
        raw_value: [],
        data_state: 'missing',
        verification: 'unverified',
        completeness: 'unknown',
        observed_at: null,
        freshness: {
          state: 'unknown',
          checked_at: result.evaluated_at,
          expires_at: null,
          policy_version: 'decision-v1',
        },
        evidence_ids: [],
        reason_code: 'TARGET_RESULT_MISSING',
        evaluation_ids: [],
      });
  }
  validateComparison(comparison);
  const evidenceResponse = responseFor('evidence deep link');
  const evidence = structuredClone(evidenceResponse.data) as Evidence;
  evidence.quality.origin = 'source'; // Test copy only, for the drawer's layout branch.
  const time = new Date().toISOString(),
    sessionId = 'contract_layout_session';
  const session: LocalSession = {
    id: sessionId,
    title: 'Contract layout test',
    pinned: false,
    createdAt: time,
    updatedAt: time,
    draft: formFromRequirement(requirement),
    requirementId: requirement.id,
    proposalId: null,
    comparisonId: comparison.id,
    pendingComparisonId: null,
    jobId: null,
    pendingMessageId: null,
    runs: [{ id: comparison.id, revision: requirement.revision, createdAt: time }],
    chat: [],
  };
  const access: SessionAccess = {
    token: 'test_contract_token',
    backendId: 'session_contract_test',
    expiresAt: '2099-01-01T00:00:00Z',
  };
  await page.addInitScript(
    ({ session, access }) => {
      localStorage.setItem('di-cung:history:v1', JSON.stringify([session]));
      sessionStorage.setItem('di-cung:access:v1', JSON.stringify({ [session.id]: access }));
    },
    { session, access },
  );
  await page.route(`**/v2/requirements/${requirement.id}`, (route) =>
    route.fulfill({
      json: {
        ...comparisonResponse,
        data: {
          ...requirement,
          active_proposal: null,
          latest_job_id: null,
          latest_comparison_id: comparison.id,
          latest_comparison_job_id: null,
        },
      },
    }),
  );
  await page.route(`**/v2/comparisons/${comparison.id}`, (route) =>
    route.fulfill({ json: { ...comparisonResponse, data: comparison } }),
  );
  await page.route(`**/v2/evidence/${evidence.id}`, (route) =>
    route.fulfill({ json: { ...evidenceResponse, data: evidence } }),
  );
  const pageErrors: string[] = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  await page.goto(`/tours?session=${sessionId}`);
  await expect(page.locator('.compare-table')).toBeVisible();
  await expect(page.getByRole('region', { name: 'Chi tiết kết quả tìm kiếm' })).toContainText(
    'kết quả này chưa đại diện toàn bộ kho tour',
  );
  await expect(page.locator('.compare-table thead th')).toHaveCount(9);
  for (const width of [1440, 1280, 390, 320]) {
    await page.setViewportSize({ width, height: 960 });
    await noOverflow(page);
    const scroll = await page.locator('.compare-wrap').evaluate((element) => ({
      width: element.clientWidth,
      scroll: element.scrollWidth,
      overflow: getComputedStyle(element).overflowX,
    }));
    expect(scroll.scroll).toBeGreaterThan(scroll.width);
    expect(scroll.overflow).toBe('auto');
    await capture(page, `comparison-contract-test-${width}-facts`);
  }
  const cell = result.cells.find((cell) => cell.evidence_ids.includes(evidence.id));
  if (!cell) throw new Error('Evidence has no captured cell binding');
  const rows = [...result.rows].sort((a, b) => a.order - b.order);
  await page
    .locator('.compare-table tbody tr')
    .nth(rows.findIndex((row) => row.id === cell.row_id))
    .locator('td')
    .nth(result.columns.findIndex((column) => column.id === cell.column_id))
    .locator('.evidence-button')
    .nth(cell.evidence_ids.indexOf(evidence.id))
    .click();
  await expect(page.getByRole('dialog', { name: 'Dữ kiện và nguồn', exact: true })).toBeVisible();
  await expect(page.getByRole('dialog').locator('blockquote')).toHaveText(evidence.raw_quote);
  await capture(page, 'comparison-contract-test-320-evidence', false);
  await page.getByRole('button', { name: 'Đóng hộp thoại', exact: true }).click();
  await page.getByRole('tab', { name: 'Phân tích AI', exact: true }).click();
  await expect(page.getByRole('tabpanel', { name: 'Phân tích AI', exact: true })).toBeVisible();
  await noOverflow(page);
  await capture(page, 'comparison-contract-test-320-analysis');
  expect(pageErrors).toEqual([]);
});

test('hosted identity adapter: confirmation, cross-browser account history, profile and archive', async ({
  page,
  browser,
}) => {
  test.skip(process.env.E2E_AUTH_STUB !== '1', 'Uses the loopback test Auth provider only.');
  const title = `E2E account Japan ${Date.now()}`;
  await page.goto('/auth');
  await page.getByRole('button', { name: 'Tạo tài khoản', exact: true }).first().click();
  await page.getByLabel('Họ và tên', { exact: true }).fill('Browser tester');
  await page.getByLabel('Email', { exact: true }).fill('browser@example.test');
  await page.getByLabel('Mật khẩu', { exact: true }).fill('test-password');
  await page.getByLabel('Xác nhận mật khẩu', { exact: true }).fill('test-password');
  await page.locator('.auth-submit').click();
  await expect(page.getByRole('status')).toContainText('Kiểm tra email');
  await expect(page.locator('.account-link')).toHaveText('Đăng nhập');
  async function login(target: Page) {
    await target.goto('/auth');
    await target.getByLabel('Email', { exact: true }).fill('browser@example.test');
    await target.getByLabel('Mật khẩu', { exact: true }).fill('test-password');
    await expect(target.locator('.auth-submit')).toBeEnabled();
    await target.locator('.auth-submit').click();
    await expect(target).toHaveURL(/\/tours/);
    await expect(target.locator('.account-link')).not.toHaveText('Đăng nhập');
  }
  await login(page);
  await page.getByRole('button', { name: 'Phiên mới', exact: true }).first().click();
  await fillTrip(page);
  await page.getByRole('button', { name: 'Xem lại nhu cầu', exact: true }).click();
  await page.getByRole('button', { name: 'Xác nhận nhu cầu', exact: true }).click();
  await expect(page.getByText('Nhu cầu đã được xác nhận', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Đổi tên phiên', exact: true }).first().click();
  await page.getByLabel('Tên phiên', { exact: true }).fill(title);
  await page.getByRole('button', { name: 'Lưu tên', exact: true }).click();
  await expect(page.locator('.session-list:visible')).toContainText(title);
  const second = await browser.newContext();
  try {
    const other = await second.newPage();
    await login(other);
    await expect(other.locator('.session-list:visible')).toContainText(title);
    await expect(other.getByText('Nhu cầu đã được xác nhận', { exact: true })).toBeVisible();
    expect(
      await other.evaluate(() => JSON.parse(localStorage.getItem('di-cung:history:v1') ?? '[]')),
    ).toEqual([]);
    await other.goto('/account');
    await other.getByRole('button', { name: 'Hồ sơ', exact: true }).click();
    await other.getByLabel('Tên hiển thị', { exact: true }).fill('Updated browser tester');
    await other.getByRole('button', { name: 'Lưu hồ sơ', exact: true }).click();
    await expect(other.getByRole('status')).toContainText('Đã lưu');
    await noOverflow(other);
    await capture(other, 'account-auth-stub-desktop');
    await other.setViewportSize({ width: 390, height: 900 });
    await noOverflow(other);
    await capture(other, 'account-auth-stub-mobile');
    await other.setViewportSize({ width: 1440, height: 960 });
    await other.goto('/tours');
    await other
      .getByRole('button', { name: 'Xóa phiên khỏi lịch sử', exact: true })
      .first()
      .click();
    await other.getByRole('button', { name: 'Xóa bản lưu', exact: true }).click();
    await expect(other.locator('.session-list:visible')).not.toContainText(title);
    await page.getByRole('button', { name: 'Tải lại lịch sử tài khoản', exact: true }).click();
    await expect(page.locator('.session-list:visible')).not.toContainText(title);
  } finally {
    await second.close();
  }
});

test('what-if contract: measured scenarios open a review proposal without confirming or searching', async ({
  page,
}) => {
  const root = resolve(import.meta.dirname, '../../..');
  const raw = JSON.parse(
    execFileSync(
      resolve(root, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python'),
      [resolve(root, 'src/frontend/api/verify_backend.py')],
      { cwd: root, encoding: 'utf8', timeout: 30_000 },
    ),
  );
  const captured = (raw as unknown[]).map((entry) => record(entry));
  const responseFor = (name: string) =>
    record(captured.find((entry) => entry.name === name)?.response);
  const compEnvelope = responseFor('hard comparison');
  const comparison = structuredClone(compEnvelope.data) as Comparison;
  comparison.result!.origin = 'source'; // Layout test copy; production synthetic gate stays enabled.
  const requirement = comparison.result!.requirement_snapshot;
  const analysisEnvelope = responseFor('hard what-if result');
  const analysis = structuredClone(analysisEnvelope.data) as WhatIf;
  analysis.result!.origin = 'source';
  validateComparison(comparison);
  validateWhatIf(analysis);
  const accepted = responseFor('hard what-if acceptance');
  const reviewEnvelope = responseFor('what-if review proposal');
  const review = record(reviewEnvelope.data);
  const scenario = analysis.result!.scenarios.find((s) => s.edits.length > 0);
  if (!scenario || scenario.state !== 'measured')
    throw new Error('Expected a measured fixture scenario');
  const id = 'what-if-browser-contract';
  const time = new Date().toISOString();
  const session: LocalSession = {
    id,
    title: 'What-if contract test',
    pinned: false,
    createdAt: time,
    updatedAt: time,
    draft: formFromRequirement(requirement),
    requirementId: requirement.id,
    proposalId: null,
    comparisonId: comparison.id,
    pendingComparisonId: null,
    jobId: null,
    pendingMessageId: null,
    runs: [],
    chat: [],
  };
  await page.addInitScript(
    ({ session }) => {
      localStorage.setItem('di-cung:history:v1', JSON.stringify([session]));
      sessionStorage.setItem(
        'di-cung:access:v1',
        JSON.stringify({
          [session.id]: {
            token: 'test-only',
            backendId: 'test-only',
            expiresAt: '2099-01-01T00:00:00Z',
          },
        }),
      );
    },
    { session },
  );
  const wrap = (data: unknown) => ({ ...compEnvelope, data });
  await page.route(`**/v2/requirements/${requirement.id}`, (route) =>
    route.fulfill({ json: wrap(requirement) }),
  );
  await page.route(`**/v2/comparisons/${comparison.id}`, (route) =>
    route.fulfill({ json: wrap(comparison) }),
  );
  await page.route(`**/v2/comparisons/${comparison.id}/what-if`, (route) =>
    route.fulfill({ json: accepted, status: 202 }),
  );
  const jobId = String(record(accepted.data).job_id);
  const job = record(responseFor('terminal comparison job').data);
  await page.route(`**/v2/jobs/${jobId}`, (route) =>
    route.fulfill({
      json: wrap({ ...job, id: jobId, kind: 'v2_what_if', resource_id: analysis.id }),
    }),
  );
  await page.route(`**/v2/jobs/${jobId}/events?*`, (route) =>
    route.fulfill({ json: wrap({ items: [], next_seq: 0, has_more: false }) }),
  );
  await page.route(`**/v2/what-if/${analysis.id}`, (route) =>
    route.fulfill({ json: wrap(analysis) }),
  );
  await page.route(`**/v2/what-if/${analysis.id}/scenarios/${scenario.id}/proposals`, (route) =>
    route.fulfill({ json: reviewEnvelope }),
  );
  await page.route(`**/v2/proposals/${String(review.id)}`, (route) =>
    route.fulfill({ json: reviewEnvelope }),
  );
  const forbidden: string[] = [];
  page.on('request', (request) => {
    if (
      request.method() === 'POST' &&
      (/\/confirm$/.test(new URL(request.url()).pathname) ||
        new URL(request.url()).pathname === '/v2/comparisons')
    )
      forbidden.push(request.url());
  });
  await page.goto(`/tours?session=${id}`);
  await page.getByRole('button', { name: 'Phân tích tác động điều kiện', exact: true }).click();
  await expect(page.locator('.what-if-scenario')).toHaveCount(analysis.result!.scenarios.length);
  const first = page
    .locator('.what-if-scenario')
    .filter({ has: page.locator('summary', { hasText: scenario.label }) })
    .first();
  await first.locator('summary').click();
  await expect(first).toContainText('Bị điều kiện gốc loại, nay đạt');
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await noOverflow(page);
    await page.locator('.what-if-panel').screenshot({
      path: resolve(screenshots, `what-if-contract-test-${width}.png`),
      style: '.site-header, .workspace-toolbar, .skip-link { visibility: hidden !important; }',
    });
  }
  await first.getByRole('button', { name: 'Xem đề xuất sửa nhu cầu', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Kiểm tra thay đổi', exact: true })).toBeVisible();
  expect(forbidden).toEqual([]);
  await expect(
    page.getByRole('button', { name: 'Phân tích tác động điều kiện', exact: true }),
  ).toBeDisabled();
});
