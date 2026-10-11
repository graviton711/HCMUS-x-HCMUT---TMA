export interface SearchDraft {
  mode: 'structured' | 'text';
  text: string;
  destinations: string[];
  departureOrigin: string;
  departureDate: string;
  returnDate: string;
  adults: number;
  budget: string;
  durationDays: string;
  transport: string[];
  accommodation: string;
}
