// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { CurrentComparison } from "../../../shared/api";
import { PreferencesProvider } from "../../../shared/preferences";
import { ResultCards } from "./ResultCards";

const evidence = { url: "", method: "", observed_at: "", record_ref: "" };
const comparison = {
  id: "cmp_test",
  requirement: {
    id: "req_test",
    conditions: [],
    missing: [],
    raw_text: "Mộc Châu",
    travelers: 1,
  },
  ranked: [
    { tour_id: "tour-a", offer_id: "offer-a-1", score: 1 },
    { tour_id: "tour-a", offer_id: "offer-a-2", score: 1 },
  ],
  near_miss: [],
  tour_snapshots: [
    {
      id: "tour-a",
      supplier: "Example Travel",
      name: "Tour Mộc Châu",
      url: "",
      destinations: ["Mộc Châu"],
      raw_destinations: ["Mộc Châu"],
      route: [],
      departure_city: "Hà Nội",
      duration_days: 3,
      transport: "bus",
      accommodation: "",
      itinerary: "",
      inclusions: "",
      exclusions: "Không bao gồm vé tham quan",
      cancellation_policy: "",
      surcharges: "",
      child_policy: "",
      evidence,
      observed_at: "",
      verification: "provider_claimed",
      offers: ["offer-a-1", "offer-a-2"].map((id, index) => ({
        id,
        tour_id: "tour-a",
        departure_date: index === 0 ? "2026-11-11" : "2026-11-25",
        price: 5_000_000,
        currency: "VND",
        price_basis: "exact" as const,
        departure_freshness: "unknown" as const,
        availability: "unknown",
        conditions: "",
        evidence,
      })),
    },
  ],
  evaluations: [],
  analysis: { hidden_costs: [], conditions: [], risks: [], benefits: [] },
  candidates_considered: 1,
} satisfies CurrentComparison;

const decisionComparison = {
  ...comparison,
  decision_views: [
    {
      kind: "cheapest" as const,
      candidates: [{ tour_id: "tour-a", offer_id: "offer-a-1", score: 0 }],
      currencies: ["VND"],
      note: "Only numeric published prices in one currency.",
    },
    {
      kind: "best_fit" as const,
      candidates: [{ tour_id: "tour-a", offer_id: "offer-a-1", score: 80 }],
      currencies: ["VND"],
      note: "Add a preference.",
    },
    {
      kind: "experience_rich" as const,
      candidates: [],
      currencies: [],
      note: "No activity data.",
    },
    {
      kind: "fewest_legs" as const,
      candidates: [],
      currencies: [],
      note: "No route data.",
    },
    {
      kind: "cancellation_flexible" as const,
      candidates: [],
      currencies: [],
      note: "No cancellation data.",
    },
    {
      kind: "included_value" as const,
      candidates: [],
      currencies: [],
      note: "No inclusion data.",
    },
    {
      kind: "balanced" as const,
      candidates: [{ tour_id: "tour-a", offer_id: "offer-a-1", score: 0 }],
      currencies: ["VND"],
      note: "Pareto options.",
    },
  ],
  metric_profiles: [
    {
      tour_id: "tour-a",
      offer_id: "offer-a-1",
      cost: {
        listed_price: 5_000_000,
        price_basis: "exact",
        currency: "VND",
        group_total_calculated: 5_000_000,
        group_total_scope: "Tổng theo giá niêm yết; chưa xác nhận exclusions.",
        priced_extras: [],
        unpriced_exclusions: [
          {
            name: "Vé tham quan",
            obligation: "mandatory",
            amount: null,
            currency: "",
            unit: "unknown",
            applies_when: "",
            source_field: "exclusions",
            quote: "Không bao gồm vé tham quan",
            calculated_total: null,
          },
        ],
        optional_or_conditional: [],
        state: "partial",
      },
      preference_fit: [],
      metrics: {
        preference_fit: {
          value: null,
          lower_bound: 0.8,
          upper_bound: 0.8,
          unit: "score",
          state: "observed",
          evidence: [],
          method_version: "test",
        },
        experience_density: {
          value: { activity_count: 3 },
          lower_bound: null,
          upper_bound: null,
          unit: "activities",
          state: "observed",
          evidence: [
            {
              source_field: "itinerary",
              quote: "Tham quan ba điểm",
              observed_at: "",
              url: "",
            },
          ],
          method_version: "test",
        },
        route_complexity: {
          value: null,
          lower_bound: null,
          upper_bound: null,
          unit: "legs",
          state: "unknown",
          evidence: [],
          method_version: "test",
        },
        included_coverage: {
          value: null,
          lower_bound: null,
          upper_bound: null,
          unit: "ratio",
          state: "unknown",
          evidence: [],
          method_version: "test",
        },
        cancellation_flexibility: {
          value: null,
          lower_bound: null,
          upper_bound: null,
          unit: "days",
          state: "unknown",
          evidence: [],
          method_version: "test",
        },
        unpriced_cost_exposures: {
          value: { count: 1 },
          lower_bound: null,
          upper_bound: null,
          unit: "items",
          state: "observed",
          evidence: [],
          method_version: "test",
        },
      },
      inclusions: [],
      exclusions: [],
      cancellation_rules: [],
      family_facts: [],
    },
  ],
} satisfies CurrentComparison;

const heroComparison = {
  ...decisionComparison,
  requirement: {
    id: "req_test",
    conditions: [
      {
        id: "cond-budget",
        field: "budget_max",
        operator: "lte",
        value: 8_000_000,
        strength: "hard",
        quote: "8 triệu",
      },
      {
        id: "cond-pref",
        field: "preference",
        operator: "contains",
        value: "chèo thuyền",
        strength: "soft",
        priority: "high",
        quote: "thích chèo thuyền",
      },
    ],
    missing: [],
    raw_text: "Mộc Châu",
    travelers: 1,
  },
  ranked: [
    { tour_id: "tour-a", offer_id: "offer-a-1", score: 90 },
    { tour_id: "tour-b", offer_id: "offer-b-1", score: 70 },
  ],
  tour_snapshots: [
    comparison.tour_snapshots[0],
    {
      ...comparison.tour_snapshots[0],
      id: "tour-b",
      name: "Tour Mộc Châu 2 ngày",
      offers: [
        {
          ...comparison.tour_snapshots[0].offers[0],
          id: "offer-b-1",
          tour_id: "tour-b",
          price: 6_200_000,
        },
      ],
    },
  ],
  evaluations: [
    {
      offer_id: "offer-a-1",
      condition_id: "cond-budget",
      state: "pass",
      quote: "5.000.000đ trọn gói",
      reason_code: "ok",
      reason: "Trong ngân sách",
    },
    {
      offer_id: "offer-a-1",
      condition_id: "cond-pref",
      state: "pass",
      quote: "Có chèo thuyền Kayak",
      reason_code: "ok",
      reason: "Khớp",
    },
    {
      offer_id: "offer-b-1",
      condition_id: "cond-budget",
      state: "pass",
      quote: "6.200.000đ trọn gói",
      reason_code: "ok",
      reason: "Trong ngân sách",
    },
    {
      offer_id: "offer-b-1",
      condition_id: "cond-pref",
      state: "unknown",
      quote: "",
      reason_code: "no_evidence",
      reason: "Chưa rõ",
    },
  ],
  decision_views: decisionComparison.decision_views.map((view) =>
    view.kind === "best_fit" || view.kind === "cheapest" || view.kind === "balanced"
      ? {
          ...view,
          candidates: [
            { tour_id: "tour-a", offer_id: "offer-a-1", score: 90 },
            { tour_id: "tour-b", offer_id: "offer-b-1", score: 70 },
          ],
        }
      : view,
  ),
  metric_profiles: [
    decisionComparison.metric_profiles[0],
    {
      ...decisionComparison.metric_profiles[0],
      tour_id: "tour-b",
      offer_id: "offer-b-1",
      cost: {
        ...decisionComparison.metric_profiles[0].cost,
        listed_price: 6_200_000,
        group_total_calculated: 6_200_000,
      },
    },
  ],
} satisfies CurrentComparison;

afterEach(cleanup);

describe("ResultCards", () => {
  it("renders one card and counts one tour when ranked offers share a tour ID", () => {
    render(
      <PreferencesProvider>
        <ResultCards comparison={comparison} busy={false} onRelax={() => {}} />
      </PreferencesProvider>,
    );

    expect(screen.getAllByRole("article")).toHaveLength(1);
    expect(screen.getByRole("status").textContent).toContain("1 tour đạt đủ");
    expect(screen.getByText(/Tour khuyên cho bạn:/)).toBeTruthy();
    expect(screen.getByText(/Xếp đầu theo yêu cầu của bạn/)).toBeTruthy();
    expect(screen.getByText("Không khai báo điều kiện bắt buộc")).toBeTruthy();
  });

  it("renders the decision workspace and source-backed cost exposure for the eight metric views", () => {
    render(
      <PreferencesProvider>
        <ResultCards
          comparison={decisionComparison}
          busy={false}
          onRelax={() => {}}
        />
      </PreferencesProvider>,
    );

    expect(
      screen
        .getByRole("tab", { name: /Giá thấp nhất/ })
        .getAttribute("aria-selected"),
    ).toBe("true");
    expect(screen.getByRole("tab", { name: /Hợp ưu tiên nhất/ })).toBeTruthy();
    expect(
      screen
        .getByRole("tab", { name: /Nhiều trải nghiệm/ })
        .hasAttribute("disabled"),
    ).toBe(true);
    expect(screen.getAllByText("Tour Mộc Châu")).toHaveLength(3);
    expect(screen.getByText(/Tour khuyên cho bạn:/)).toBeTruthy();
    expect(
      screen.getByText(/Giá công bố thấp nhất trong nhóm đạt điều kiện/),
    ).toBeTruthy();
    expect(screen.getByText("Không khai báo điều kiện bắt buộc")).toBeTruthy();
    expect(screen.getByText(/Chấp nhận: 1 khoản chưa định giá/)).toBeTruthy();
    expect(screen.getByText("Được")).toBeTruthy();
    expect(screen.getByText(/Mất \/ Chấp nhận/)).toBeTruthy();
    expect(
      screen.getAllByText(/1 khoản chưa định giá — không cộng vào tổng/).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/1 tour đã quét/)).toBeTruthy();
    expect(screen.getByText("Đánh đổi và chi phí cần kiểm tra")).toBeTruthy();
    expect(
      screen.getByText("Đánh đổi và chi phí cần kiểm tra").closest("details")?.open,
    ).toBe(false);
    expect(screen.getByText("Khoản chưa định giá / có điều kiện")).toBeTruthy();
    fireEvent.click(screen.getByText(/Loại trừ, phụ thu/));
    expect(screen.getAllByText("Không bao gồm vé tham quan")).toHaveLength(2);

    fireEvent.click(screen.getByRole("tab", { name: /Cân bằng/ }));
    expect(screen.getByText("Pareto options.")).toBeTruthy();
  });

  it("shows the recommended tour with plain status and gain/loss checklists", () => {
    render(
      <PreferencesProvider>
        <ResultCards comparison={heroComparison} busy={false} onRelax={() => {}} />
      </PreferencesProvider>,
    );

    expect(screen.getByText(/Tour khuyên cho bạn:/)).toBeTruthy();
    expect(screen.getByText(/Khớp các ưu tiên của bạn nhất/)).toBeTruthy();
    expect(screen.getByText("Điều kiện bắt buộc: đạt 1/1")).toBeTruthy();
    expect(screen.getByText("Ưu tiên: khớp 1/1 · mức Cao 1/1")).toBeTruthy();
    expect(screen.getByText(/Chấp nhận: 1 khoản chưa định giá/)).toBeTruthy();

    expect(screen.getByText("Hợp nhất")).toBeTruthy();
    expect(screen.getAllByText(/5.000.000đ trọn gói/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Có chèo thuyền Kayak/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Cao").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/6.200.000đ trọn gói/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Giá cao hơn tour dẫn đầu 1.200.000 VND/)).toBeTruthy();
  });
});
