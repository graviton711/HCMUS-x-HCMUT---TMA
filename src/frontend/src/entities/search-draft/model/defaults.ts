import type { SearchDraft } from './types';

export const emptySearchDraft: SearchDraft = {
  mode: 'structured',
  text: '',
  destinations: [],
  departureOrigin: '',
  departureDate: '',
  returnDate: '',
  adults: 0,
  budget: '',
  durationDays: '',
  transport: [],
  accommodation: '',
};
