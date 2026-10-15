import type { CurrentCondition, CurrentComparison } from "../../../shared/api";

export interface SavedTourEvaluation {
  condition: CurrentCondition;
  state: "pass" | "partial" | "fail" | "unknown";
  quote: string;
  reasonCode: string;
  reason: string;
}

export interface SavedTour {
  id: string;
  savedAt: string;
  tourId: string;
  offerId: string;
  name: string;
  supplier: string;
  destinations: string[];
  route: string[];
  departureCity: string;
  durationDays: number | null;
  transport: string;
  departureDate: string;
  price: number | null;
  currency: string;
  priceBasis: "exact" | "from" | "contact" | "unknown";
  availability: string;
  conditions: string;
  sourceUrl: string;
  observedAt: string;
  evaluations: SavedTourEvaluation[];
}

export function savedTourId(tourId: string, offerId: string) {
  return `${tourId}::${offerId}`;
}

export function savedTourFromComparison(
  comparison: CurrentComparison,
  tourId: string,
  offerId: string,
): SavedTour | null {
  const tour = comparison.tour_snapshots.find(
    (candidate) => candidate.id === tourId,
  );
  const offer = tour?.offers.find((candidate) => candidate.id === offerId);
  if (!tour || !offer) return null;
  const evaluations = new Map(
    comparison.evaluations
      .filter((evaluation) => evaluation.offer_id === offerId)
      .map((evaluation) => [evaluation.condition_id, evaluation]),
  );

  return {
    id: savedTourId(tourId, offerId),
    savedAt: new Date().toISOString(),
    tourId,
    offerId,
    name: tour.name || tour.id,
    supplier: tour.supplier || "",
    destinations: [...tour.destinations],
    route: [...tour.route],
    departureCity: tour.departure_city,
    durationDays: tour.duration_days,
    transport: tour.transport,
    departureDate: offer.departure_date,
    price: offer.price,
    currency: offer.currency,
    priceBasis: offer.price_basis,
    availability: offer.availability,
    conditions: offer.conditions,
    sourceUrl: offer.evidence.url || tour.url || tour.evidence.url,
    observedAt: offer.evidence.observed_at || tour.observed_at,
    evaluations: comparison.requirement.conditions.map((condition) => {
      const evaluation = evaluations.get(condition.id);
      return {
        condition: { ...condition },
        state: evaluation?.state ?? "unknown",
        quote: evaluation?.quote ?? "",
        reasonCode: evaluation?.reason_code ?? "",
        reason: evaluation?.reason ?? "",
      };
    }),
  };
}
