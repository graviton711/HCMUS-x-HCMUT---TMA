import { expect, test, type Page } from '@playwright/test';

const draft = 'Đà Lạt 3 ngày, tối đa 8 triệu/người, thích thiên nhiên';

function currentComparison() {
  const observedAt = '2026-10-13T10:00:00+07:00';
  const evidence = {
    url: 'https://travel.example/tour-da-lat',
    method: 'database_record',
    observed_at: observedAt,
    record_ref: 'offer-dalat',
  };
  const requirement = {
    id: 'req-e2e',
    conditions: [
      {
        id: 'budget',
        field: 'budget_max',
        operator: 'lte',
        value: 8_000_000,
        strength: 'hard',
        quote: 'tối đa 8 triệu/người',
      },
      {
        id: 'nature',
        field: 'preference',
        operator: 'contains',
        value: 'thiên nhiên',
        strength: 'soft',
        quote: 'thích thiên nhiên',
        weight_percent: 100,
      },
    ],
    missing: [],
    raw_text: draft,
    travelers: 1,
  };
  return {
    id: 'cmp-e2e',
    requirement,
    ranked: [{ tour_id: 'tour-dalat', offer_id: 'offer-dalat', score: 0 }],
    near_miss: [],
    tour_snapshots: [
      {
        id: 'tour-dalat',
        supplier: 'Travel Example',
        name: 'Tour Đà Lạt cuối tuần',
        url: evidence.url,
        destinations: ['Đà Lạt'],
        raw_destinations: ['Đà Lạt'],
        route: ['TP.HCM', 'Đà Lạt'],
        departure_city: 'TP.HCM',
        duration_days: 3,
        transport: 'bus',
        accommodation: 'Hotel',
        itinerary: '',
        inclusions: '',
        exclusions: '',
        cancellation_policy: '',
        surcharges: '',
        child_policy: '',
        evidence: { ...evidence, record_ref: 'tour-dalat' },
        observed_at: observedAt,
        verification: 'provider_claimed',
        offers: [
          {
            id: 'offer-dalat',
            tour_id: 'tour-dalat',
            departure_date: '2026-11-10',
            price: 6_500_000,
            currency: 'VND',
            price_basis: 'exact',
            departure_freshness: 'fresh',
            availability: 'available',
            conditions: '',
            evidence,
          },
        ],
      },
    ],
    evaluations: [
      {
        offer_id: 'offer-dalat',
        condition_id: 'budget',
        state: 'pass',
        quote: '',
        reason_code: '',
        reason: '',
      },
      {
        offer_id: 'offer-dalat',
        condition_id: 'nature',
        state: 'pass',
        quote: 'Rừng thông',
        reason_code: 'SOFT_PASS',
        reason: 'Lịch trình có cảnh quan rừng thông.',
      },
    ],
    analysis: { hidden_costs: [], conditions: [], risks: [], benefits: [] },
    candidates_considered: 1,
    decision_views: [
      {
        kind: 'cheapest',
        candidates: [{ tour_id: 'tour-dalat', offer_id: 'offer-dalat', score: 0 }],
        currencies: ['VND'],
        note: 'Chỉ so sánh giá exact trong cùng đơn vị tiền tệ.',
      },
      {
        kind: 'best_fit',
        candidates: [{ tour_id: 'tour-dalat', offer_id: 'offer-dalat', score: 100 }],
        currencies: ['VND'],
        note: 'Điểm là tổng trọng số của các sở thích được đánh giá là phù hợp.',
      },
      {
        kind: 'balanced',
        candidates: [{ tour_id: 'tour-dalat', offer_id: 'offer-dalat', score: 100 }],
        currencies: ['VND'],
        note: 'Pareto giữa giá exact và điểm ưu tiên.',
      },
    ],
  };
}

async function mockBackend(
  page: Page,
  expireFirstMessage = false,
  toolCalls: { name: string; status: string }[] = [],
  messageDelayMs = 0,
) {
  const messageCalls: { agentSessionId: string; text: string }[] = [];
  const decisionCalls: { agentSessionId: string; requirement: unknown }[] = [];
  let sessionsCreated = 0;
  let agentSessionsCreated = 0;

  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify(body),
      });

    if (url.pathname === '/sessions' && method === 'POST') {
      sessionsCreated += 1;
      return json(
        {
          id: `session-${sessionsCreated}`,
          session_id: `session-${sessionsCreated}`,
          token: `guest-token-${sessionsCreated}`,
          token_type: 'Bearer',
          expires_at: '2030-01-01T00:00:00+00:00',
        },
        201,
      );
    }
    if (url.pathname === '/health' && method === 'GET') {
      return json({ status: 'ok', version: 'e2e' });
    }
    if (url.pathname === '/agent/sessions' && method === 'POST') {
      agentSessionsCreated += 1;
      return json({ agent_session_id: `agent-${agentSessionsCreated}` }, 201);
    }
    if (url.pathname.startsWith('/agent/sessions/') && url.pathname.endsWith('/decisions')) {
      const agentSessionId = url.pathname.split('/')[3] ?? '';
      const body = request.postDataJSON() as { requirement: unknown };
      decisionCalls.push({ agentSessionId, requirement: body.requirement });
      return json({
        assistant_text: 'Đã đối chiếu theo các tiêu chí bạn xác nhận.',
        tool_calls: [
          { name: 'query_tours', status: 'completed' },
          { name: 'score_soft', status: 'completed' },
        ],
        requirement: currentComparison().requirement,
        comparison: currentComparison(),
      });
    }
    if (url.pathname.startsWith('/agent/sessions/') && url.pathname.endsWith('/messages')) {
      const agentSessionId = url.pathname.split('/')[3] ?? '';
      const body = request.postDataJSON() as { message: string };
      messageCalls.push({ agentSessionId, text: body.message });
      if (messageDelayMs > 0) await new Promise((resolve) => setTimeout(resolve, messageDelayMs));
      if (expireFirstMessage && messageCalls.length === 1) {
        return json({ error: { code: 'SESSION_EXPIRED', message: 'Guest session expired.' } }, 401);
      }
      return json({
        assistant_text: 'Mình đã chuẩn bị bản tiêu chí để bạn xem lại trước khi so tour.',
        tool_calls: toolCalls.length ? toolCalls : [{ name: 'draft_requirement', status: 'completed' }],
        requirement: currentComparison().requirement,
        decision_draft: currentComparison().requirement,
      });
    }
    return route.continue();
  });

  return {
    messageCalls,
    decisionCalls,
    get sessionsCreated() {
      return sessionsCreated;
    },
  };
}

async function startChat(page: Page) {
  await page.goto('/');
  await expect(page.getByLabel('Nhắn cho TourLens')).toBeVisible();
}

test('guest reviews a brief, compares decision views, and restores the result', async ({ page }) => {
  const backend = await mockBackend(page, false, [
    { name: 'catalog_facets', status: 'success' },
    { name: 'draft_requirement', status: 'completed' },
  ]);
  const legacyRequests: string[] = [];
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/v2/')) legacyRequests.push(request.url());
  });

  await startChat(page);
  await page.getByLabel('Nhắn cho TourLens').fill(draft);
  await page.getByRole('button', { name: 'Gửi', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Kiểm tra tiêu chí chuyến đi' })).toBeVisible();
  await expect(page.getByText('Đã phân bổ 100 / 100 điểm')).toBeVisible();
  await expect(page.getByRole('button', { name: 'So sánh tour' })).toBeEnabled();
  await page.getByRole('spinbutton', { name: 'ngân sách — Bắt buộc' }).fill('7000000');
  await page.getByRole('button', { name: 'So sánh tour' }).click();
  await expect(page.getByRole('heading', { name: 'Tour Đà Lạt cuối tuần' })).toBeVisible();
  await expect(page.getByRole('tab', { name: /Giá thấp nhất/ })).toBeVisible();
  await expect(page.getByText('1 tour đã quét')).toBeVisible();
  await expect(
    page.locator('details').filter({ hasText: 'Đã kiểm tra 2 bước' }),
  ).toHaveCount(2);

  await expect
    .poll(() =>
      page.evaluate(() => {
        const saved = JSON.parse(localStorage.getItem('di-cung:history:v1') ?? '[]') as {
          comparisonId?: string;
        }[];
        return saved.some((item) => item.comparisonId === 'cmp-e2e');
      }),
    )
    .toBe(true);
  expect(backend.messageCalls).toHaveLength(1);
  expect(backend.messageCalls[0]?.text).toBe(draft);
  expect(backend.decisionCalls).toHaveLength(1);
  const reviewedRequirement = backend.decisionCalls[0]?.requirement as {
    conditions: { field: string; value: unknown; quote: string }[];
    raw_text: string;
  };
  const reviewedBudget = reviewedRequirement.conditions.find((condition) => condition.field === 'budget_max');
  expect(reviewedBudget?.value).toBe(7_000_000);
  expect(reviewedBudget?.quote).toBe('7000000');
  expect(reviewedRequirement.raw_text).toContain('7000000');
  expect(legacyRequests).toEqual([]);

  await page.reload();
  await expect(page.getByRole('heading', { name: 'Tour Đà Lạt cuối tuần' })).toBeVisible();
  await expect(page.getByRole('tab', { name: /Giá thấp nhất/ })).toBeVisible();
  await expect(
    page.locator('details').filter({ hasText: 'Đã kiểm tra 2 bước' }),
  ).toHaveCount(2);
});

test('expired guest starts a new session and resends the draft once', async ({ page }) => {
  const backend = await mockBackend(page, true);
  await startChat(page);
  await page.getByLabel('Nhắn cho TourLens').fill(draft);
  await page.getByRole('button', { name: 'Gửi', exact: true }).click();

  await expect(page.getByRole('alert')).toContainText('Phiên hết hạn.');
  await expect(page.getByRole('button', { name: 'Thử lại' })).toHaveCount(0);
  await expect(page.getByLabel('Nhắn cho TourLens')).toBeDisabled();
  await page.getByRole('button', { name: 'Tạo phiên mới' }).click();
  await expect(page.getByRole('heading', { name: 'Kiểm tra tiêu chí chuyến đi' })).toBeVisible();

  expect(backend.sessionsCreated).toBe(2);
  expect(backend.messageCalls).toHaveLength(2);
  expect(backend.messageCalls.map((call) => call.text)).toEqual([draft, draft]);
  expect(backend.messageCalls[0]?.agentSessionId).not.toBe(backend.messageCalls[1]?.agentSessionId);
});

test('account and contact routes clearly report that their backend features are not ported', async ({
  page,
}) => {
  await mockBackend(page);
  await page.goto('/account');
  await expect(page.getByRole('heading', { name: 'Tài khoản chưa khả dụng.' })).toBeVisible();
  await page.getByRole('button', { name: 'Tiếp tục với guest' }).click();
  await expect(page.getByLabel('Nhắn cho TourLens')).toBeVisible();

  await page.goto('/contact');
  await expect(page.getByRole('heading', { name: 'Liên hệ chưa khả dụng.' })).toBeVisible();
});

test('guest chat fits a narrow mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockBackend(page, false, [
    { name: 'catalog_facets', status: 'success' },
    { name: 'draft_requirement', status: 'completed' },
  ]);
  await startChat(page);
  await page.getByLabel('Nhắn cho TourLens').fill(draft);
  await page.getByRole('button', { name: 'Gửi', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Kiểm tra tiêu chí chuyến đi' })).toBeVisible();
  await page.getByRole('button', { name: 'So sánh tour' }).click();
  await expect(page.getByRole('tab', { name: /Giá thấp nhất/ })).toBeVisible();
  const details = page.locator('details').filter({ hasText: 'Kiểm tra lựa chọn có trong dữ liệu' });
  await expect(details.locator('summary')).toBeVisible();
  await details.locator('summary').click();
  await expect(details.getByRole('listitem')).toHaveCount(2);
  const sizes = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }));
  expect(sizes.content).toBeLessThanOrEqual(sizes.viewport + 1);
});

test('tool progress expands by keyboard and respects dark mode and reduced motion', async ({
  page,
}) => {
  await mockBackend(
    page,
    false,
    [
      { name: 'catalog_facets', status: 'success' },
      { name: 'draft_requirement', status: 'completed' },
    ],
    3000,
  );
  await startChat(page);
  await page.getByLabel('Nhắn cho TourLens').fill(draft);
  await page.getByRole('button', { name: 'Gửi', exact: true }).click();

  const activeStatus = page.getByRole('status');
  await expect(activeStatus).toBeVisible();
  const regularMotionDuration = await activeStatus
    .locator('span')
    .evaluate((element) => getComputedStyle(element).animationDuration);
  const gradientClip = await activeStatus
    .locator('span')
    .evaluate((element) => getComputedStyle(element).backgroundClip);
  expect(regularMotionDuration).toBe('2.4s');
  expect(gradientClip).toBe('text');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const reducedMotionDuration = await activeStatus
    .locator('span')
    .evaluate((element) => getComputedStyle(element).animationDuration);
  expect(parseFloat(reducedMotionDuration)).toBeLessThan(0.001);

  await expect(page.getByRole('heading', { name: 'Kiểm tra tiêu chí chuyến đi' })).toBeVisible();

  const disclosure = page.locator('details').filter({ hasText: 'Kiểm tra lựa chọn có trong dữ liệu' });
  const summary = disclosure.locator('summary');
  await expect(summary).toBeVisible();
  await summary.focus();
  await page.keyboard.press('Enter');
  await expect(disclosure).toHaveAttribute('open', '');
  await expect(disclosure.getByRole('listitem')).toHaveCount(2);
  await expect(disclosure).toContainText('Kiểm tra lựa chọn có trong dữ liệu');
  await expect(disclosure).toContainText('Chuẩn bị bản tiêu chí để bạn xem');

  await page.getByRole('button', { name: 'So sánh tour' }).click();
  await expect(page.getByRole('heading', { name: 'Tour Đà Lạt cuối tuần' })).toBeVisible();

  const lightSurface = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue('--paper').trim(),
  );
  await page.getByRole('button', { name: 'Chuyển sang giao diện tối' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  const darkSurface = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue('--paper').trim(),
  );
  expect(darkSurface).not.toBe(lightSurface);
});

test('composer keeps top room for the caret and grows for multiline input', async ({ page }) => {
  await mockBackend(page);
  await startChat(page);
  const composer = page.getByLabel('Nhắn cho TourLens');
  await composer.focus();

  const placeholderMetrics = await composer.evaluate((element: HTMLTextAreaElement) => {
    const style = getComputedStyle(element);
    return {
      paddingTop: parseFloat(style.paddingTop),
      lineHeight: parseFloat(style.lineHeight),
      height: element.getBoundingClientRect().height,
    };
  });
  expect(placeholderMetrics.paddingTop).toBeGreaterThanOrEqual(8);
  expect(placeholderMetrics.lineHeight).toBeGreaterThanOrEqual(24);
  expect(placeholderMetrics.height).toBeGreaterThanOrEqual(40);

  await composer.fill('M');
  const oneLineHeight = await composer.evaluate(
    (element) => element.getBoundingClientRect().height,
  );
  await composer.fill('Dòng thứ nhất\nDòng thứ hai\nDòng thứ ba');
  const multilineMetrics = await composer.evaluate((element: HTMLTextAreaElement) => ({
    height: element.getBoundingClientRect().height,
    scrollHeight: element.scrollHeight,
  }));
  expect(multilineMetrics.height).toBeGreaterThan(oneLineHeight);
  expect(multilineMetrics.height).toBeLessThanOrEqual(200);
  expect(multilineMetrics.height).toBeGreaterThanOrEqual(multilineMetrics.scrollHeight - 1);
});
