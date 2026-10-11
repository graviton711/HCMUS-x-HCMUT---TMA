import type { CurrentCatalog } from '../../../shared/api';

export interface SlotPrompt {
  question: [string, string];
  options: { label: string; value: string }[];
  hint?: [string, string];
}

/** One missing slot → one question with tappable answers (values are text fragments). */
export function slotPrompt(slot: string, catalog: CurrentCatalog | null): SlotPrompt | null {
  switch (slot) {
    case 'destination':
      return {
        question: ['Bạn muốn đi đâu?', 'Where to?'],
        options: (catalog?.destinations ?? []).slice(0, 4).map((place) => ({
          label: place,
          value: place,
        })),
      };
    case 'date_from':
      return {
        question: ['Đi từ ngày nào?', 'Leaving when?'],
        options: [],
        hint: ['VD: 27/12 âm, 20/12/2026', 'E.g. lunar Dec 27, 2026-12-20'],
      };
    case 'date_to':
      return {
        question: ['Về ngày nào?', 'Returning when?'],
        options: [],
        hint: ['VD: mùng 4 Tết, 25/12/2026', 'E.g. Tet day 4, 2026-12-25'],
      };
    case 'budget_max':
      return {
        question: ['Ngân sách tối đa mỗi người?', 'Max budget per person?'],
        options: ['5 triệu', '8 triệu', '12 triệu', '20 triệu'].map((amount) => ({
          label: `${amount}/người`,
          value: `tối đa ${amount} mỗi người`,
        })),
      };
    case 'duration_days':
      return {
        question: ['Đi mấy ngày?', 'How many days?'],
        options: ['3 ngày', '4 ngày', '5 ngày', '7 ngày'].map((days) => ({
          label: days,
          value: `đi ${days}`,
        })),
      };
    case 'departure_city':
      return {
        question: ['Khởi hành từ đâu?', 'Departing from?'],
        options: ['Hà Nội', 'TP.HCM', 'Hải Phòng', 'Đà Nẵng'].map((city) => ({
          label: city,
          value: `đi từ ${city}`,
        })),
      };
    case 'transport':
      return {
        question: ['Đi bằng phương tiện gì?', 'By what transport?'],
        options: [
          ['Ô tô', 'đi bằng xe ô tô'],
          ['Máy bay', 'đi bằng máy bay'],
          ['Tàu hỏa', 'đi bằng tàu hỏa'],
        ].map(([label, value]) => ({ label, value })),
      };
    case 'accommodation':
      return {
        question: ['Muốn ở loại nào?', 'What accommodation?'],
        options: [
          ['Khách sạn 3 sao', 'ở khách sạn 3 sao'],
          ['Khách sạn 4 sao', 'ở khách sạn 4 sao'],
          ['Resort', 'ở resort'],
        ].map(([label, value]) => ({ label, value })),
      };
    default:
      return null;
  }
}
