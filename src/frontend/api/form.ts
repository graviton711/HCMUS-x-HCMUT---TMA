import type {
  Catalog,
  Condition,
  ConditionValue,
  CreateRequirementRequest,
  FormCondition,
  Party,
  PreferenceDimension,
  Preferences,
  Requirement,
  Strength,
  TypedEdit,
} from './types';
import {
  directMonthReason,
  editMonths,
  localToday,
  monthConditions,
  monthsFromRequirement,
  treesWithMonths,
  validMonth,
} from './travelFilters';

export interface FormValues {
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
  budgetMeasure: 'listed' | 'payable';
  durationDays: string;
  hotelStars: string;
  shopping: 'any' | 'few' | 'none';
  transport: string[];
  includedServices: string[];
  referenceUrls: string[];
  notes: string;
  preferenceLevels: Record<PreferenceDimension, number>;
  preferenceOrigins?: Partial<Record<PreferenceDimension, 'user' | 'system_default'>>;
  strengths: Record<string, 'hard' | 'soft'>;
}
export const emptyForm: FormValues = {
  mode: 'structured',
  text: '',
  destinations: [],
  departureOrigin: '',
  departureDate: '',
  departureMonths: [],
  returnDate: '',
  adults: 0,
  childAges: [],
  budget: '',
  budgetMin: '',
  budgetBasis: 'per_adult',
  budgetMeasure: 'listed',
  durationDays: '',
  hotelStars: '',
  shopping: 'any',
  transport: [],
  includedServices: [],
  referenceUrls: [],
  notes: '',
  preferenceLevels: { cost: 3, comfort: 3, pace: 3, culture: 3 },
  strengths: {},
};
export class FormValidationError extends Error {
  readonly name = 'FormValidationError';
  constructor(readonly fields: Record<string, string>) {
    super(Object.values(fields)[0] ?? 'Kiểm tra các trường của yêu cầu.');
  }
}
const dimensions: PreferenceDimension[] = ['cost', 'comfort', 'pace', 'culture'];
const copy = <T>(v: T): T => structuredClone(v);
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
const items = (condition: Condition | undefined): string[] => {
  if (!condition) return [];
  if (condition.value.kind === 'set') return condition.value.items;
  if (condition.value.kind === 'entities')
    return condition.value.members.flatMap((m) => (m.entity_id ? [m.entity_id] : []));
  return [];
};
const numeric = (condition: Condition | undefined) =>
  condition?.value.kind === 'number' ? String(condition.value.amount) : '';
const date = (condition: Condition | undefined) =>
  condition?.value.kind === 'date'
    ? condition.value.value
    : condition?.value.kind === 'temporal'
      ? (condition.value.resolved_date ?? '')
      : '';

export function formFromRequirement(requirement: Requirement): FormValues {
  const result = copy(emptyForm);
  const field = (name: string) => requirement.conditions.find((c) => c.field === name);
  result.mode = requirement.input_kind;
  result.destinations = [...items(field('destinations'))];
  result.departureOrigin = items(field('departure_origin'))[0] ?? '';
  result.departureDate = date(field('departure_date'));
  result.departureMonths = monthsFromRequirement(requirement);
  if (result.departureMonths.length) result.departureDate = '';
  result.returnDate = date(field('return_date'));
  result.adults = requirement.party.adults ?? 0;
  result.childAges = requirement.party.children.map((c) => c.age);
  const budget = field('estimated_cost')?.value;
  if (budget?.kind === 'budget') {
    result.budget = String(budget.upper ?? budget.amount);
    result.budgetMin = budget.upper != null ? String(budget.amount) : '';
    result.budgetBasis = budget.basis ?? 'per_adult';
    result.budgetMeasure = budget.measure ?? 'payable';
  }
  result.durationDays = numeric(field('duration_days'));
  result.hotelStars = numeric(field('hotel_stars_min'));
  const shopping = field('shopping_stops');
  result.shopping =
    shopping?.value.kind === 'number' &&
    shopping.value.amount === 0 &&
    shopping.strength === 'hard' &&
    shopping.operator === 'eq'
      ? 'none'
      : shopping
        ? 'few'
        : 'any';
  result.transport = [...items(field('transport'))];
  result.includedServices = [...items(field('included_services'))];
  result.referenceUrls = [...requirement.reference_urls];
  result.notes = requirement.notes;
  result.preferenceOrigins = {};
  for (const dimension of dimensions) {
    const level = requirement.preference_levels?.[dimension];
    result.preferenceLevels[dimension] = level?.level ?? 3;
    if (level) result.preferenceOrigins[dimension] = level.origin;
  }
  for (const condition of requirement.conditions)
    if (condition.strength !== 'unresolved') result.strengths[condition.field] = condition.strength;
  return result;
}
export const fromRequirement = formFromRequirement;

export function canonicalUrls(urls: string[], limit = 5): string[] {
  const values = urls.map((url) => url.trim()).filter(Boolean);
  const errors: Record<string, string> = {};
  if (values.length > limit) errors.referenceUrls = `Tối đa ${limit} URL tour.`;
  const normalized = values.map((url, i) => {
    try {
      const parsed = new URL(url);
      if (
        !['http:', 'https:'].includes(parsed.protocol) ||
        !parsed.hostname ||
        parsed.username ||
        parsed.password ||
        !['', '80', '443'].includes(parsed.port) ||
        /[\s\\]/u.test(url) ||
        url.length > 2048
      )
        throw new Error();
      parsed.hash = '';
      return parsed.href;
    } catch {
      errors[`referenceUrls.${i}`] =
        'Nhập URL HTTP/HTTPS hợp lệ, không có mật khẩu hoặc cổng riêng.';
      return url;
    }
  });
  if (Object.keys(errors).length) throw new FormValidationError(errors);
  return [...new Set(normalized)];
}

function validateStructured(values: FormValues, requireCore: boolean, catalog?: Catalog): void {
  const errors: Record<string, string> = {};
  if (requireCore) {
    if (!values.destinations.length) errors.destinations = 'Chọn điểm đến.';
    if (!values.departureOrigin) errors.departureOrigin = 'Chọn nơi khởi hành.';
    if (!values.departureDate && !values.departureMonths.length)
      errors.departureMonths = 'Chọn ít nhất một tháng khởi hành.';
    if (!Number.isInteger(values.adults) || values.adults < 1 || values.adults > 100)
      errors.adults = 'Số người lớn từ 1 đến 100.';
    if (!values.budget) errors.budget = 'Nhập ngân sách.';
  } else if (
    values.adults !== 0 &&
    (!Number.isInteger(values.adults) || values.adults < 1 || values.adults > 100)
  )
    errors.adults = 'Số người lớn từ 1 đến 100.';
  if (
    values.budget &&
    (!/^\d+$/u.test(values.budget) ||
      !Number.isSafeInteger(Number(values.budget)) ||
      Number(values.budget) > 10 ** 15)
  )
    errors.budget = 'Ngân sách VND phải là số nguyên không âm.';
  if (
    values.budgetMin &&
    (!/^\d+$/u.test(values.budgetMin) ||
      !Number.isSafeInteger(Number(values.budgetMin)) ||
      Number(values.budgetMin) > 10 ** 15 ||
      !values.budget ||
      Number(values.budgetMin) > Number(values.budget))
  )
    errors.budgetMin = 'Khoảng ngân sách phải là số nguyên không âm, đáy không vượt trần.';
  if (
    values.departureMonths.length > 12 ||
    values.departureMonths.some((month) => !validMonth(month))
  )
    errors.departureMonths = 'Chọn tối đa 12 tháng, có tháng và năm hợp lệ.';
  const today = localToday();
  if (values.departureMonths.some((month) => validMonth(month) && month < today.slice(0, 7)))
    errors.departureMonths = 'Tháng khởi hành đã qua. Chọn lại tháng và năm.';
  if (values.departureDate && values.departureDate < today)
    errors.departureDate = 'Ngày khởi hành đã qua. Chọn lại ngày.';
  for (const key of ['departureDate', 'returnDate'] as const)
    if (
      values[key] &&
      (!/^\d{4}-\d{2}-\d{2}$/u.test(values[key]) ||
        !Number.isFinite(Date.parse(values[key])) ||
        new Date(values[key]).toISOString().slice(0, 10) !== values[key])
    )
      errors[key] = 'Ngày không hợp lệ.';
  if (values.returnDate && values.departureDate && values.returnDate < values.departureDate)
    errors.returnDate = 'Ngày về phải từ ngày khởi hành.';
  if (
    values.childAges.length > 20 ||
    values.childAges.some((age) => age !== null && (!Number.isInteger(age) || age < 0 || age > 17))
  )
    errors.childAges = 'Mỗi trẻ từ 0 đến 17 tuổi; tối đa 20 trẻ.';
  if (
    values.durationDays &&
    (!/^\d+$/u.test(values.durationDays) ||
      Number(values.durationDays) < 1 ||
      Number(values.durationDays) > 10 ** 15)
  )
    errors.durationDays = 'Số ngày phải là số nguyên dương.';
  if (values.hotelStars && !/^[1-5]$/u.test(values.hotelStars))
    errors.hotelStars = 'Hạng khách sạn từ 1 đến 5 sao.';
  if (values.notes.length > 8000) errors.notes = 'Ghi chú tối đa 8.000 ký tự.';
  for (const dimension of dimensions)
    if (
      !Number.isInteger(values.preferenceLevels[dimension]) ||
      values.preferenceLevels[dimension] < 0 ||
      values.preferenceLevels[dimension] > 5
    )
      errors[`preferenceLevels.${dimension}`] = 'Mức sở thích từ 0 đến 5.';
  if (catalog) {
    if (values.destinations.some((id) => !catalog.destinations.some((d) => d.id === id)))
      errors.destinations = 'Điểm đến chưa có trong danh mục backend.';
    if (values.departureOrigin && !catalog.origins.some((o) => o.id === values.departureOrigin))
      errors.departureOrigin = 'Nơi khởi hành chưa có trong danh mục backend.';
    if (values.transport.some((id) => !catalog.transports.some((t) => t.id === id)))
      errors.transport = 'Phương tiện chưa có trong danh mục backend.';
  }
  if (Object.keys(errors).length) throw new FormValidationError(errors);
}

function preferences(values: FormValues, catalog?: Catalog): Preferences {
  return Object.fromEntries(
    dimensions.map((dimension) => {
      const level = values.preferenceLevels[dimension];
      const defaultLevel =
        catalog?.preference_dimensions.find((d) => d.id === dimension)?.default.level ?? 3;
      const origin =
        values.preferenceOrigins?.[dimension] ??
        (level === defaultLevel ? 'system_default' : 'user');
      return [dimension, { level, origin }];
    }),
  ) as Preferences;
}

function conditions(values: FormValues): FormCondition[] {
  const result: FormCondition[] = [];
  const add = (
    field: string,
    operator: string,
    value: ConditionValue,
    strength: Strength = 'hard',
  ) =>
    result.push({
      id: `condition_${field}`,
      field,
      operator,
      value,
      strength: values.strengths[field] ?? strength,
    });
  if (values.destinations.length)
    add('destinations', values.destinations.length === 1 ? 'contains' : 'contains_any', {
      kind: 'set',
      items: [...new Set(values.destinations)],
    });
  if (values.departureOrigin)
    add('departure_origin', 'in', { kind: 'set', items: [values.departureOrigin] });
  if (values.departureMonths.length)
    result.push(
      ...monthConditions(values.departureMonths, values.strengths.departure_date ?? 'hard'),
    );
  else if (values.departureDate)
    add('departure_date', 'eq', { kind: 'date', value: values.departureDate });
  if (values.returnDate) add('return_date', 'lte', { kind: 'date', value: values.returnDate });
  if (values.budget)
    add(
      'estimated_cost',
      values.budgetMin === '' ? 'lte' : 'between',
      {
        kind: 'budget',
        measure: values.budgetMeasure,
        amount: Number(values.budgetMin === '' ? values.budget : values.budgetMin),
        ...(values.budgetMin === '' ? {} : { upper: Number(values.budget) }),
        currency: 'VND',
        basis: values.budgetBasis,
        coverage: 'tour_price',
        coverage_origin: 'system_default',
      },
      'hard',
    );
  if (values.durationDays)
    add(
      'duration_days',
      values.strengths.duration_days === 'hard' ? 'eq' : 'near',
      { kind: 'number', amount: Number(values.durationDays) },
      'soft',
    );
  if (values.hotelStars)
    add('hotel_stars_min', 'gte', { kind: 'number', amount: Number(values.hotelStars) }, 'soft');
  if (values.shopping !== 'any')
    result.push({
      id: 'condition_shopping_stops',
      field: 'shopping_stops',
      operator: values.shopping === 'none' ? 'eq' : 'prefer_low',
      value: { kind: 'number', amount: 0 },
      strength: values.shopping === 'none' ? 'hard' : 'soft',
    });
  if (values.transport.length)
    add('transport', 'in', { kind: 'set', items: [...new Set(values.transport)] });
  if (values.includedServices.length)
    add(
      'included_services',
      'contains_all',
      { kind: 'set', items: [...new Set(values.includedServices)] },
      'soft',
    );
  return result;
}

function party(values: FormValues, previous?: Party): Party {
  return {
    adults: values.adults || null,
    children: values.childAges.map((age, i) => ({
      id: previous?.children[i]?.id ?? `child_${i + 1}`,
      age,
    })),
    ...(previous?.rooming ? { rooming: previous.rooming } : {}),
  };
}

export function buildCreateRequirement(
  values: FormValues,
  catalog?: Catalog,
): CreateRequirementRequest {
  const reference_urls = canonicalUrls(values.referenceUrls, catalog?.limits.reference_urls);
  if (values.mode === 'urls') {
    if (!reference_urls.length)
      throw new FormValidationError({ referenceUrls: 'Nhập ít nhất một URL tour.' });
    return { input: { kind: 'urls' }, reference_urls, timezone: 'Asia/Ho_Chi_Minh' };
  }
  if (values.mode === 'text') {
    const text = values.text.trim();
    if (!text || text.length > (catalog?.limits.text_characters ?? 2000))
      throw new FormValidationError({ text: 'Mô tả nhu cầu từ 1 đến 2.000 ký tự.' });
    return { input: { kind: 'text', text }, reference_urls, timezone: 'Asia/Ho_Chi_Minh' };
  }
  validateStructured(values, true, catalog);
  const formConditions = conditions(values);
  return {
    input: {
      kind: 'structured',
      form: {
        conditions: formConditions,
        ...(values.departureMonths.length ? treesWithMonths(formConditions) : {}),
        party: party(values),
        preference_levels: preferences(values, catalog),
        notes: values.notes.trim(),
      },
    },
    reference_urls,
    timezone: 'Asia/Ho_Chi_Minh',
  };
}

const controls: { field: string; keys: (keyof FormValues)[] }[] = [
  { field: 'destinations', keys: ['destinations'] },
  { field: 'departure_origin', keys: ['departureOrigin'] },
  { field: 'return_date', keys: ['returnDate'] },
  { field: 'estimated_cost', keys: ['budget', 'budgetMin', 'budgetBasis'] },
  { field: 'duration_days', keys: ['durationDays'] },
  { field: 'hotel_stars_min', keys: ['hotelStars'] },
  { field: 'shopping_stops', keys: ['shopping'] },
  { field: 'transport', keys: ['transport'] },
  { field: 'included_services', keys: ['includedServices'] },
];

export function directBudgetReason(requirement: Requirement): string | null {
  const budgets = requirement.conditions.filter(
    (condition) => condition.field === 'estimated_cost',
  );
  if (budgets.length > 1)
    return 'Ngân sách có nhiều nhánh. Sửa qua hội thoại để giữ đúng nhóm điều kiện.';
  const value = budgets[0]?.value;
  if (!value) return null;
  if (
    value.kind !== 'budget' ||
    value.currency !== 'VND' ||
    value.basis !== 'per_adult' ||
    value.coverage !== 'tour_price' ||
    !['lte', 'between'].includes(budgets[0].operator)
  ) {
    return 'Ngân sách này có đơn vị, phạm vi hoặc khoảng tiền khác. Sửa qua hội thoại để giữ đúng ý nghĩa.';
  }
  return null;
}
export const canEditBudget = (requirement: Requirement) => directBudgetReason(requirement) === null;

/** Edit only controls the user changed; other predicates and their AND/OR tree stay on BE. */
export function buildEdits(
  values: FormValues,
  requirement: Requirement,
  catalog?: Catalog,
): TypedEdit[] {
  // Existing semantic IDs absent from the current catalog must remain editable elsewhere.
  const before = formFromRequirement(requirement);
  validateStructured(
    {
      ...values,
      ...(same(values.departureMonths, before.departureMonths) ? { departureMonths: [] } : {}),
      ...(values.departureDate === before.departureDate ? { departureDate: '' } : {}),
      ...(values.budget === before.budget && values.budgetMin === before.budgetMin
        ? { budget: '', budgetMin: '' }
        : {}),
    },
    false,
  );
  const desired = conditions(values);
  const edits: TypedEdit[] = [];
  for (const control of controls) {
    if (
      control.keys.every((key) => same(values[key], before[key])) &&
      same(values.strengths[control.field], before.strengths[control.field])
    )
      continue;
    const existing = requirement.conditions.filter((c) => c.field === control.field);
    if (existing.length > 1)
      throw new FormValidationError({
        [control.keys[0]]:
          'Điều kiện này có nhiều nhánh. Dùng hội thoại để sửa và giữ đúng nhóm AND/OR.',
      });
    const old = existing[0],
      next = desired.find((c) => c.field === control.field);
    const budgetReason =
      control.field === 'estimated_cost' ? directBudgetReason(requirement) : null;
    if (budgetReason) throw new FormValidationError({ budget: budgetReason });
    if (!next) {
      if (old) edits.push({ op: 'remove_condition', condition_id: old.id });
      continue;
    }
    if (!old) {
      edits.push({ op: 'upsert_condition', condition: next });
      continue;
    }
    const strength =
      control.field === 'shopping_stops'
        ? next.strength
        : (values.strengths[control.field] ?? old.strength);
    const operator =
      ['shopping_stops', 'estimated_cost'].includes(control.field) ||
      (control.field === 'duration_days' &&
        ['eq', 'near'].includes(old.operator) &&
        values.strengths.duration_days !== before.strengths.duration_days)
        ? next.operator
        : old.operator;
    if (
      control.field === 'estimated_cost' &&
      next.value.kind === 'budget' &&
      old.value.kind === 'budget'
    ) {
      next.value.coverage_origin = old.value.coverage_origin;
      next.value.coverage = old.value.coverage;
      next.value.measure = old.value.measure ?? 'payable';
    }
    const updated = {
      ...next,
      id: old.id,
      operator,
      strength,
      ...(old.scope ? { scope: old.scope } : {}),
    };
    if (old.operator === operator && old.strength === strength)
      edits.push({ op: 'replace_condition_value', condition_id: old.id, value: next.value });
    else edits.push({ op: 'upsert_condition', condition: updated });
  }
  if (
    !same(values.departureMonths, before.departureMonths) ||
    values.departureDate !== before.departureDate
  ) {
    const reason = directMonthReason(requirement);
    if (reason) throw new FormValidationError({ departureMonths: reason });
    if (values.departureMonths.length || !values.departureDate)
      edits.push(...editMonths(values.departureMonths, requirement, edits));
    else
      throw new FormValidationError({
        departureMonths: 'Chọn tháng để sửa lịch, hoặc sửa ngày chính xác qua hội thoại.',
      });
  }
  if (!same(values.childAges, before.childAges) || values.adults !== before.adults)
    edits.push({ op: 'replace_party', party: party(values, requirement.party) });
  for (const dimension of dimensions)
    if (values.preferenceLevels[dimension] !== before.preferenceLevels[dimension])
      edits.push({
        op: 'set_preference_level',
        dimension,
        level: values.preferenceLevels[dimension],
      });
  const urls = canonicalUrls(values.referenceUrls, catalog?.limits.reference_urls);
  if (!same(urls, requirement.reference_urls))
    edits.push({ op: 'replace_reference_urls', reference_urls: urls });
  if (values.notes.trim() !== requirement.notes)
    edits.push({ op: 'set_notes', notes: values.notes.trim() });
  if (edits.length > 30)
    throw new FormValidationError({ form: 'Tối đa 30 thay đổi mỗi lần xác nhận.' });
  return edits;
}
