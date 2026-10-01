import hashlib
import re
from decimal import Decimal

from domain.common import AppError
from domain.requirements import (
    Budget,
    Clarification,
    Condition,
    DateValue,
    Message,
    Party,
    Readiness,
    Requirement,
    SetValue,
    Tree,
    UnresolvedValue,
)
from requirements.extraction import Extraction
from requirements.normalize import ground, money, normalize, normalize_party


def conjunction(conditions: list[Condition], soft: bool) -> Tree:
    return Tree(kind="all", children=[Tree(kind="predicate", condition_id=c.id)
                                     for c in conditions if (c.strength == "soft") == soft])


def prune(tree: Tree, removed: set[str]) -> Tree | None:
    if tree.kind == "predicate":
        return None if tree.condition_id in removed else tree
    children = [n for c in tree.children if (n := prune(c, removed)) is not None]
    if not children:
        return None
    return Tree(kind=tree.kind, children=children)


def required_ids(tree: Tree) -> set[str]:
    if tree.kind == "predicate":
        return {tree.condition_id}
    parts = [required_ids(c) for c in tree.children]
    if not parts:
        return set()
    return set.union(*parts) if tree.kind == "all" else set.intersection(*parts)


def contradictions(r: Requirement) -> list[str]:
    bounds = {}
    for c in r.conditions:
        if c.id not in required_ids(r.hard_tree) or isinstance(c.value, (UnresolvedValue, SetValue)):
            continue
        v = c.value
        scope = (c.field, v.currency, v.basis, v.coverage) if isinstance(v, Budget) else (c.field,)
        lower, upper, lower_closed, upper_closed = bounds.get(scope, (None, None, True, True))
        n = v.value if isinstance(v, DateValue) else Decimal(v.amount)
        hi = getattr(v, "upper", None)
        if hi is not None and not isinstance(v, DateValue):
            hi = Decimal(hi)
        if c.operator in {"eq", "gte", "gt", "between"}:
            closed = c.operator != "gt"
            if lower is None or n > lower:
                lower, lower_closed = n, closed
            elif n == lower:
                lower_closed &= closed
        if c.operator in {"eq", "lte", "lt", "between"}:
            hi = hi if c.operator == "between" else n
            closed = c.operator != "lt"
            if upper is None or hi < upper:
                upper, upper_closed = hi, closed
            elif hi == upper:
                upper_closed &= closed
        bounds[scope] = lower, upper, lower_closed, upper_closed
    conflicts = [str(k[0]) for k, (lo, hi, lc, hc) in bounds.items()
                 if lo is not None and hi is not None and (lo > hi or (lo == hi and not (lc and hc)))]
    dep = bounds.get(("departure_date",), (None, None, True, True))
    ret = bounds.get(("return_date",), (None, None, True, True))
    if dep[0] is not None and ret[1] is not None and (dep[0] > ret[1] or (dep[0] == ret[1] and not ret[3])):
        conflicts.append("departure_date/return_date")
    return conflicts


def finalize(r: Requirement) -> Requirement:
    questions = []

    def ask(path, reason, question, options=None, blocking=True):
        digest = hashlib.sha256(f"{r.id}:{r.revision}:{path}:{reason}".encode()).hexdigest()[:20]
        questions.append(Clarification(id=f"q_{digest}", field_path=path, reason_code=reason,
                                       question=question, options=options or [], blocking=blocking))

    unsupported = False
    for c in r.conditions:
        hard = c.strength != "soft"
        if isinstance(c.value, UnresolvedValue):
            unsupported |= c.field == "unsupported" and hard
            if c.value.reason == "DATE_NEEDS_CLARIFICATION" and re.search(r"(?<!\d)\d{1,2}/\d{1,2}(?![\d/])", c.value.raw):
                ask(f"conditions.{c.id}.value", "DATE_YEAR_REQUIRED", "Ngày bạn nói thuộc năm nào?", blocking=hard)
            else:
                ask(f"conditions.{c.id}.value", c.value.reason,
                    f"Bạn làm rõ điều kiện: {c.value.raw}", blocking=hard)
        elif isinstance(c.value, Budget):
            if not c.value.currency:
                ask(f"conditions.{c.id}.value.currency", "CURRENCY_REQUIRED", "Ngân sách dùng tiền tệ nào?", ["VND", "USD"], hard)
            if not c.value.basis:
                ask(f"conditions.{c.id}.value.basis", "BUDGET_BASIS_REQUIRED", "Ngân sách tính cho ai?",
                    ["group_total", "per_adult", "per_person"], hard)
    for path in contradictions(r):
        ask("conditions", "CONTRADICTORY_CONDITIONS", f"Các giới hạn {path} đang mâu thuẫn; bạn muốn giữ giới hạn nào?")
    positive_scope = any(c.field in {"destinations", "supplier"} and isinstance(c.value, SetValue)
                         and c.operator not in {"excludes", "not_in"} for c in r.conditions)
    if r.mode == "discover" and not positive_scope:
        ask("conditions", "SEARCH_SCOPE_REQUIRED", "Bạn muốn tìm tour đến đâu hoặc của nhà cung cấp nào?")
    # Party details block cost calculation only; static acquisition can continue.
    group_budgets = [c for c in r.conditions if isinstance(c.value, Budget) and c.value.basis in {"group_total", "per_person"}]
    if group_budgets:
        blocking = any(c.strength != "soft" for c in group_budgets)
        if r.party.adults is None:
            ask("party.adults", "PARTY_REQUIRED", "Nhóm có bao nhiêu người lớn?", blocking=blocking)
        for child in r.party.children:
            if child.age is None:
                ask(f"party.children.{child.id}.age", "CHILD_AGE_REQUIRED", "Bé bao nhiêu tuổi?", blocking=blocking)
    blockers = [q.reason_code for q in questions if q.blocking]
    data = r.model_dump()
    data["clarifications"] = questions
    data["readiness"] = Readiness(
        status="unsupported" if unsupported else "needs_clarification" if questions else "ready",
        can_collect_data=r.mode == "compare_urls" or positive_scope,
        can_evaluate_hard_constraints=not blockers,
        reasons=list(dict.fromkeys(blockers)),
    )
    return Requirement.model_validate(data)


def from_extraction(*, extraction: Extraction, message: Message, requirement_id: str, mode: str,
                    timezone: str, targets: list, previous: Requirement | None = None) -> Requirement:
    if previous is None:
        if extraction.operations:
            raise AppError("LLM_INVALID_OUTPUT", "Initial extraction không được sửa revision cũ.", 502)
        conditions = [normalize(c, message, timezone) for c in extraction.conditions]
        hard_tree = extraction.hard_tree or conjunction(conditions, False)
        soft_tree = extraction.preference_tree or conjunction(conditions, True)
        party = normalize_party(extraction.party, Party(), message)
        messages, revision = [message], 1
    else:
        if extraction.conditions or extraction.hard_tree or extraction.preference_tree:
            raise AppError("LLM_INVALID_OUTPUT", "Update phải dùng operations; không ghi đè toàn bộ state.", 502)
        conditions = list(previous.conditions)
        hard_tree, soft_tree = previous.hard_tree, previous.preference_tree
        changed = set()
        for op in extraction.operations:
            ref = ground(message, op.quote)
            if op.target_id in changed:
                raise AppError("LLM_INVALID_OUTPUT", "Một lượt sửa trùng target.", 502)
            if op.target_id:
                changed.add(op.target_id)
            old = next((c for c in conditions if c.id == op.target_id), None)
            if op.op != "add" and old is None:
                raise AppError("LLM_INVALID_OUTPUT", "Target sửa không tồn tại.", 502)
            if op.op == "increment_budget":
                budgets = [c for c in previous.conditions if isinstance(c.value, Budget)]
                if len(budgets) != 1 or not isinstance(old.value, Budget) or not old.value.currency or not old.value.basis:
                    raise AppError("LLM_INVALID_OUTPUT", "Không xác định duy nhất ngân sách cần tăng.", 502)
                if op.delta_raw not in op.quote:
                    raise AppError("LLM_INVALID_OUTPUT", "Delta thiếu quote.", 502)
                delta = money(op.delta_raw)
                values = old.value.model_dump()
                for key in ("amount", "upper"):
                    if values[key] is not None:
                        amount = Decimal(values[key]) + delta
                        values[key] = int(amount) if old.value.currency == "VND" else format(amount, "f")
                replacement = Condition.model_validate({**old.model_dump(), "value": Budget(**values), "sources": [*old.sources, ref]})
            elif op.op in {"add", "replace"}:
                replacement = normalize(op.condition, message, timezone)
                if op.op == "replace":
                    replacement = replacement.model_copy(update={"id": old.id})
                elif any(c.id == replacement.id for c in conditions):
                    raise AppError("LLM_INVALID_OUTPUT", "ID điều kiện mới bị trùng.", 502)
            else:
                replacement = None
            if old:
                conditions = [c for c in conditions if c.id != old.id]
                if replacement is None or replacement.strength != old.strength:
                    hard_tree = prune(hard_tree, {old.id}) or Tree(kind="all")
                    soft_tree = prune(soft_tree, {old.id}) or Tree(kind="all")
            if replacement:
                conditions.append(replacement)
                if old is None or replacement.strength != old.strength:
                    leaf = Tree(kind="predicate", condition_id=replacement.id)
                    if replacement.strength == "soft":
                        soft_tree = Tree(kind="all", children=[soft_tree, leaf])
                    else:
                        hard_tree = Tree(kind="all", children=[hard_tree, leaf])
        party = normalize_party(extraction.party, previous.party, message)
        messages, revision = [*previous.messages, message], previous.revision + 1
    return finalize(Requirement(id=requirement_id, revision=revision, mode=mode, timezone=timezone,
                                targets=targets, messages=messages, party=party, conditions=conditions,
                                hard_tree=hard_tree, preference_tree=soft_tree))
