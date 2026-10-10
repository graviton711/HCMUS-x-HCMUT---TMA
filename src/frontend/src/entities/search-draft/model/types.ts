export interface SearchDraft {
  mode: 'structured' | 'text' | 'urls';
  text: string;
  destinations: string[];
  departureOrigin: string;
  departureDate: string;
  departureMonths: string[];
  returnDate: string;
  adults: number;
  childAges: (number | null)[];
  budget: string;
  budgetMin: string;
  budgetBasis: 'per_adult' | 'per_person' | 'group_total';
  durationDays: string;
  hotelStars: string;
  shopping: 'any' | 'few' | 'none';
  transport: string[];
  includedServices: string[];
  referenceUrls: string[];
  notes: string;
  preferenceLevels: Record<'cost' | 'comfort' | 'pace' | 'culture', number>;
  preferenceOrigins?: Partial<
    Record<'cost' | 'comfort' | 'pace' | 'culture', 'user' | 'system_default'>
  >;
  strengths: Record<string, 'hard' | 'soft'>;
}
