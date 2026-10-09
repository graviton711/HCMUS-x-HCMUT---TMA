import type { Condition, FormCondition, Requirement, Tree, TypedEdit } from './types';

export const validMonth = (month: string) => /^[1-9]\d{3}-(0[1-9]|1[0-2])$/u.test(month);
export function monthBounds(month: string) {
  const [year, number] = month.split('-').map(Number);
  const last = new Date(Date.UTC(year, number, 0)).getUTCDate();
  return { kind: 'date' as const, value: `${month}-01`, upper: `${month}-${last}` };
}
const monthOf = (condition: Condition) => {
  if (condition.operator !== 'between' || condition.value.kind !== 'date') return null;
  const month = condition.value.value.slice(0, 7);
  if (!validMonth(month)) return null;
  const bounds = monthBounds(month);
  return condition.value.value === bounds.value && condition.value.upper === bounds.upper
    ? month
    : null;
};
const dateConditions = (requirement: Requirement) =>
  requirement.conditions.filter((c) => c.field === 'departure_date');
const treeIds = (tree: Tree): string[] =>
  tree.kind === 'predicate' ? [tree.condition_id!] : (tree.children ?? []).flatMap(treeIds);
const sameIds = (tree: Tree, ids: string[]) => {
  const actual = treeIds(tree);
  return actual.length === ids.length && ids.every((id) => actual.includes(id));
};
function dateGroup(tree: Tree, ids: string[]): Tree | null {
  if (
    sameIds(tree, ids) &&
    (ids.length === 1
      ? tree.kind === 'predicate'
      : tree.kind === 'any' && tree.children?.every((child) => child.kind === 'predicate'))
  )
    return tree;
  for (const child of tree.children ?? []) {
    const group = dateGroup(child, ids);
    if (group) return group;
  }
  return null;
}

export function directMonthReason(requirement: Requirement): string | null {
  const dates = dateConditions(requirement);
  if (!dates.length) return null;
  if (
    dates.length > 12 ||
    dates.some((c) => c.value.kind !== 'date' || c.strength === 'unresolved') ||
    dates.some((c) => c.strength !== dates[0].strength) ||
    (dates.length > 1 && dates.some((c) => !monthOf(c)))
  )
    return 'Lịch này có điều kiện khác tháng dương lịch. Sửa qua hội thoại để giữ đúng ý nghĩa.';
  const tree = dates[0].strength === 'soft' ? requirement.preference_tree : requirement.hard_tree;
  return dateGroup(
    tree,
    dates.map((c) => c.id),
  )
    ? null
    : 'Các mốc ngày nằm trong nhóm điều kiện khác. Sửa qua hội thoại để giữ đúng AND/OR.';
}

export function monthsFromRequirement(requirement: Requirement): string[] {
  if (directMonthReason(requirement)) return [];
  const months = dateConditions(requirement).map(monthOf);
  return months.every((month): month is string => month !== null) ? months.sort() : [];
}
export function monthConditions(months: string[], strength: 'hard' | 'soft'): FormCondition[] {
  return [...new Set(months)].sort().map((month) => ({
    id: `condition_departure_month_${month.replace('-', '_')}`,
    field: 'departure_date',
    operator: 'between',
    value: monthBounds(month),
    strength,
  }));
}
const leaf = (id: string): Tree => ({ kind: 'predicate', condition_id: id });
const anyMonths = (ids: string[]): Tree =>
  ids.length === 1 ? leaf(ids[0]) : { kind: 'any', children: ids.map(leaf) };
export function treesWithMonths(conditions: FormCondition[]) {
  const tree = (soft: boolean): Tree => {
    const selected = conditions.filter((c) => (c.strength === 'soft') === soft);
    const dates = selected.filter((c) => c.field === 'departure_date');
    return {
      kind: 'all',
      children: [
        ...selected.filter((c) => c.field !== 'departure_date').map((c) => leaf(c.id)),
        ...(dates.length ? [anyMonths(dates.map((c) => c.id))] : []),
      ],
    };
  };
  return { hard_tree: tree(false), preference_tree: tree(true) };
}
function prune(tree: Tree, ids: string[]): Tree | null {
  if (tree.kind === 'predicate') return ids.includes(tree.condition_id!) ? null : tree;
  const children = (tree.children ?? []).flatMap((child) => {
    const remaining = prune(child, ids);
    return remaining ? [remaining] : [];
  });
  return children.length ? { ...tree, children } : null;
}
const append = (tree: Tree, child: Tree): Tree => ({ kind: 'all', children: [tree, child] });

/** Replace only an isolated calendar group, accounting for other edits in the same proposal. */
export function editMonths(
  months: string[],
  requirement: Requirement,
  otherEdits: TypedEdit[],
): TypedEdit[] {
  const old = dateConditions(requirement);
  const strength = old[0]?.strength === 'soft' ? 'soft' : 'hard';
  const treeKind = strength === 'soft' ? 'preference_tree' : 'hard_tree';
  let tree = structuredClone(requirement[treeKind]);
  const membership = new Map(requirement.conditions.map((c) => [c.id, c.strength]));
  for (const edit of otherEdits) {
    if (edit.op === 'remove_condition') {
      tree = prune(tree, [edit.condition_id]) ?? { kind: 'all', children: [] };
      membership.delete(edit.condition_id);
    } else if (edit.op === 'upsert_condition') {
      const c = edit.condition;
      if (!membership.has(c.id) || membership.get(c.id) !== c.strength) {
        tree = prune(tree, [c.id]) ?? { kind: 'all', children: [] };
        if ((c.strength === 'soft') === (strength === 'soft')) tree = append(tree, leaf(c.id));
      }
      membership.set(c.id, c.strength);
    }
  }
  const used = new Set(requirement.conditions.map((c) => c.id));
  const next = monthConditions(months, strength).map((c, index) => {
    const month = c.value.kind === 'date' ? c.value.value.slice(0, 7) : '';
    const existing =
      old.find((item) => monthOf(item) === month) ??
      (old.length === 1 && index === 0 && !months.includes(monthOf(old[0]) ?? '')
        ? old[0]
        : undefined);
    let id = existing?.id ?? c.id;
    if (!existing) {
      for (let suffix = 2; used.has(id); suffix++) id = `${c.id}_${suffix}`;
      used.add(id);
    }
    return { ...c, id, ...(existing?.scope ? { scope: existing.scope } : {}) };
  });
  const edits: TypedEdit[] = old
    .filter((c) => !next.some((item) => item.id === c.id))
    .map((c) => ({ op: 'remove_condition', condition_id: c.id }));
  for (const condition of next) {
    const existing = old.find((c) => c.id === condition.id);
    if (existing?.operator === 'between') {
      if (JSON.stringify(existing.value) !== JSON.stringify(condition.value))
        edits.push({
          op: 'replace_condition_value',
          condition_id: existing.id,
          value: condition.value,
        });
    } else edits.push({ op: 'upsert_condition', condition });
  }
  const group = next.length ? anyMonths(next.map((c) => c.id)) : null;
  const ids = old.map((c) => c.id);
  const replace = (node: Tree): Tree | null => {
    if (sameIds(node, ids) && (ids.length === 1 ? node.kind === 'predicate' : node.kind === 'any'))
      return group;
    if (node.kind === 'predicate') return node;
    const children = (node.children ?? []).flatMap((child) => {
      const replaced = replace(child);
      return replaced ? [replaced] : [];
    });
    return children.length ? { ...node, children } : null;
  };
  tree = old.length
    ? (replace(tree) ?? { kind: 'all', children: [] })
    : group
      ? append(tree, group)
      : tree;
  edits.push({ op: 'replace_tree', tree_kind: treeKind, tree });
  return edits;
}
