import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import {
  comparison as validateComparison,
  record,
  requirement as validateRequirement,
} from '../api/contracts';
import { formFromRequirement } from '../api/form';
import type { Comparison, Evidence, Requirement } from '../api/types';
import type { LocalSession, SessionAccess } from '../app/storage';

const screenshots = resolve(import.meta.dirname, '../../../artifacts/frontend');
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
    await page.getByRole('button', { name: 'Tùy chọn hiển thị', exact: true }).click();
    const preferencesBox = await page.locator('.preferences-panel').boundingBox();
    expect(preferencesBox).not.toBeNull();
    if (preferencesBox) {
      expect(preferencesBox.x).toBeGreaterThanOrEqual(0);
      expect(preferencesBox.x + preferencesBox.width).toBeLessThanOrEqual(width);
    }
    await page.getByRole('button', { name: 'English', exact: true }).click();
    await page.getByRole('button', { name: 'Dark', exact: true }).click();
    await page.getByRole('button', { name: 'Display preferences', exact: true }).click();
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
    await page.getByRole('button', { name: 'Display preferences', exact: true }).click();
    await page.getByRole('button', { name: 'Tiếng Việt', exact: true }).click();
    await page.getByRole('button', { name: 'Sáng', exact: true }).click();
    await page.getByRole('button', { name: 'Tùy chọn hiển thị', exact: true }).click();
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
