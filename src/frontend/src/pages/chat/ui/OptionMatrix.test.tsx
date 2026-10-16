// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { CurrentComparison } from "../../../shared/api";
import { PreferencesProvider } from "../../../shared/preferences";
import { OptionMatrix } from "./OptionMatrix";

afterEach(cleanup);

const evidence = { url: "", method: "", observed_at: "", record_ref: "" };

function tour(id: string, price: number | null) {
  return {
    id,
    supplier: "Example Travel",
    name: `Tour ${id}`,
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
    exclusions: "",
    cancellation_policy: "",
    surcharges: "",
    child_policy: "",
    evidence,
    observed_at: "",
    verification: "provider_claimed",
    offers: [
      {
        id: `${id}-offer`,
        tour_id: id,
        departure_date: "2026-11-11",
        price,
        currency: "VND",
        price_basis: "exact" as const,
        departure_freshness: "unknown" as const,
        availability: "unknown",
        conditions: "",
        evidence,
      },
    ],
  };
}

function profile(id: string, groupTotal: number | null, unpriced: number) {
  return {
    tour_id: id,
    offer_id: `${id}-offer`,
    cost: {
      listed_price: 5_000_000,
      price_basis: "exact" as const,
      currency: "VND",
      group_total_calculated: groupTotal,
      group_total_scope: "",
      priced_extras: [],
      unpriced_exclusions: Array.from({ length: unpriced }, (_, i) => ({
        name: `Khoản ${i}`,
        obligation: "mandatory" as const,
        amount: null,
        currency: "",
        unit: "unknown" as const,
        applies_when: "",
        source_field: "exclusions",
        quote: "",
        calculated_total: null,
      })),
      optional_or_conditional: [],
      state: "partial" as const,
    },
    preference_fit: [],
    metrics: {},
    inclusions: [],
    exclusions: [],
    cancellation_rules: [],
    family_facts: [],
  };
}

function metric(key: string, value: number | null, relation: "favorable" | "tradeoff" | "similar" | "unknown", currency = "VND", unit = "") {
  return {
    key,
    value,
    reference_median: null,
    unit,
    currency,
    scope: "",
    state: "observed" as const,
    relation,
    higher_is_better: null,
    evidence: [],
  };
}

const comparison = {
  id: "cmp_matrix",
  requirement: { id: "req", conditions: [], missing: [], raw_text: "", travelers: 1 },
  ranked: [],
  near_miss: [],
  tour_snapshots: [tour("tour-a", 5_000_000), tour("tour-b", 7_000_000), tour("tour-c", null)],
  evaluations: [],
  analysis: { hidden_costs: [], conditions: [], risks: [], benefits: [] },
  candidates_considered: 3,
  metric_profiles: [profile("tour-a", 5_000_000, 0), profile("tour-b", 7_500_000, 2), profile("tour-c", null, 1)],
  decision_options: [
    {
      tour_id: "tour-a",
      offer_id: "tour-a-offer",
      objective: "cheapest",
      title: "Giá thấp nhất",
      reason: "",
      tradeoffs: [],
      metric_comparisons: [
        metric("group_total", 5_000_000, "favorable"),
        metric("preference_fit", 80, "similar"),
      ],
    },
    {
      tour_id: "tour-b",
      offer_id: "tour-b-offer",
      objective: "balanced",
      title: "Cân bằng",
      reason: "",
      tradeoffs: [],
      metric_comparisons: [
        metric("group_total", 7_500_000, "tradeoff"),
        metric("preference_fit", null, "unknown"),
      ],
    },
    {
      tour_id: "tour-c",
      offer_id: "tour-c-offer",
      objective: "balanced",
      title: "Cân bằng",
      reason: "",
      tradeoffs: [],
      metric_comparisons: [metric("group_total", null, "unknown")],
    },
  ],
} satisfies CurrentComparison;

describe("OptionMatrix", () => {
  it("renders one column per option with chips and honest unknowns", () => {
    render(
      <PreferencesProvider>
        <OptionMatrix comparison={comparison} />
      </PreferencesProvider>,
    );
    expect(screen.getByText("Phương án 1")).toBeTruthy();
    expect(screen.getByText("Phương án 2")).toBeTruthy();
    expect(screen.getByText("Phương án 3")).toBeTruthy();

    const table = document.querySelector("table");
    expect(table).not.toBeNull();
    const favorable = within(table as HTMLElement).getByText("Thuận lợi hơn trung vị");
    expect(favorable.getAttribute("data-relation")).toBe("favorable");

    const unknowns = within(table as HTMLElement).getAllByText("Chưa rõ");
    expect(unknowns.length).toBeGreaterThan(0);
  });

  it("renders nothing without options", () => {
    const { container } = render(
      <PreferencesProvider>
        <OptionMatrix comparison={{ ...comparison, decision_options: [] }} />
      </PreferencesProvider>,
    );
    expect(container.querySelector("table")).toBeNull();
  });
});
