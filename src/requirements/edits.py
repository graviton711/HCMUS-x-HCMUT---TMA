from domain.common import AppError, uid
from domain.requirements import Budget, Condition, Party, Requirement, SourceReference, Target, Tree
from requirements.service import conjunction, finalize, prune


def form_requirement(form, *, requirement_id, mode, timezone, targets):
    conditions = []
    for c in form.conditions:
        source = SourceReference(kind="form", field_path=f"conditions.{c.id}", submitted_value=c.model_dump(mode="json"))
        sources = [source]
        raw = c.model_dump()
        if isinstance(c.value, Budget):
            raw["value"]["coverage_origin"] = "explicit" if "coverage" in c.value.model_fields_set else "system_default"
        if isinstance(c.value, Budget) and raw["value"]["coverage_origin"] == "system_default":
            sources.append(SourceReference(kind="system_default", field_path="value.coverage",
                                            submitted_value="tour_price", rule="budget_tour_price_v1"))
        conditions.append(Condition(**raw, sources=sources))
    party = Party.model_validate({**form.party.model_dump(), "sources": [SourceReference(
        kind="form", field_path="party", submitted_value=form.party.model_dump(exclude={"sources"}))]})
    return finalize(Requirement(id=requirement_id, revision=1, mode=mode, timezone=timezone, targets=targets,
        party=party, conditions=conditions, hard_tree=form.hard_tree or conjunction(conditions, False),
        preference_tree=form.preference_tree or conjunction(conditions, True)))


def apply_edits(previous: Requirement, edits: list) -> Requirement:
    data = previous.model_dump()
    data["revision"] += 1
    data["clarifications"] = []
    conditions = {c.id: c.model_dump() for c in previous.conditions}
    hard, soft = previous.hard_tree, previous.preference_tree
    for edit in edits:
        op, path, value = edit.op, edit.target.split("."), edit.value
        source = SourceReference(kind="form", field_path=edit.target, submitted_value=value).model_dump()
        if path[0] == "conditions":
            if op == "add" and len(path) == 1 and isinstance(value, dict):
                raw = {**value, "sources": [source]}
                if isinstance(raw.get("value"), dict) and raw["value"].get("kind") == "budget":
                    raw["value"]["coverage_origin"] = "explicit" if "coverage" in raw["value"] else "system_default"
                    raw["value"] = Budget.model_validate(raw["value"]).model_dump()
                    if raw["value"]["coverage_origin"] == "system_default":
                        raw["sources"].append(SourceReference(kind="system_default", field_path="value.coverage",
                            rule="budget_tour_price_v1", submitted_value="tour_price").model_dump())
                condition = Condition.model_validate(raw)
                if condition.id in conditions:
                    raise AppError("INVALID_EDIT", "Condition ID đã tồn tại.")
                conditions[condition.id] = condition.model_dump()
                leaf = Tree(kind="predicate", condition_id=condition.id)
                if condition.strength == "soft":
                    soft = Tree(kind="all", children=[soft, leaf])
                else:
                    hard = Tree(kind="all", children=[hard, leaf])
                continue
            if len(path) < 2 or path[1] not in conditions:
                raise AppError("INVALID_EDIT", "Không tìm thấy condition cần sửa.")
            cid = path[1]
            old_strength = conditions[cid]["strength"]
            if op == "remove" and len(path) == 2:
                del conditions[cid]
                hard, soft = prune(hard, {cid}) or Tree(kind="all"), prune(soft, {cid}) or Tree(kind="all")
                continue
            if op != "replace":
                raise AppError("INVALID_EDIT", "Condition chỉ nhận add/remove/replace hợp lệ.")
            if len(path) == 3 and path[2] in {"value", "strength", "operator"}:
                if path[2] == "value" and isinstance(value, dict) and value.get("kind") == "budget":
                    value = {**value, "coverage_origin": "explicit" if "coverage" in value else "system_default"}
                    if value["coverage_origin"] == "system_default":
                        conditions[cid]["sources"].append(SourceReference(kind="system_default", field_path="value.coverage",
                            rule="budget_tour_price_v1", submitted_value="tour_price").model_dump())
                conditions[cid][path[2]] = value
            elif len(path) == 4 and path[2] == "value" and path[3] in {"amount", "upper", "currency", "basis", "coverage", "items", "value"}:
                conditions[cid]["value"][path[3]] = value
                if path[3] == "coverage":
                    conditions[cid]["value"]["coverage_origin"] = "explicit"
            else:
                raise AppError("INVALID_EDIT", "Đường dẫn sửa không được hỗ trợ.")
            conditions[cid]["sources"].append(source)
            updated = Condition.model_validate(conditions[cid])
            if updated.strength != old_strength:
                hard, soft = prune(hard, {cid}) or Tree(kind="all"), prune(soft, {cid}) or Tree(kind="all")
                leaf = Tree(kind="predicate", condition_id=cid)
                if updated.strength == "soft":
                    soft = Tree(kind="all", children=[soft, leaf])
                else:
                    hard = Tree(kind="all", children=[hard, leaf])
        elif path[0] == "party" and op == "replace":
            if len(path) == 2 and path[1] in {"adults", "children", "rooming"}:
                data["party"][path[1]] = value
            elif len(path) == 4 and path[1] == "children" and path[3] == "age":
                child = next((c for c in data["party"]["children"] if c["id"] == path[2]), None)
                if child is None:
                    raise AppError("INVALID_EDIT", "Không tìm thấy trẻ trong nhóm.")
                child["age"] = value
            else:
                raise AppError("INVALID_EDIT", "Đường dẫn nhóm khách không hợp lệ.")
            data["party"]["sources"].append(source)
        elif path[0] == "targets" and previous.mode == "compare_urls":
            if op == "add" and len(path) == 1 and isinstance(value, dict) and set(value) <= {"url", "position"}:
                target = Target(target_id=uid("target"), url=value.get("url"))
                position = value.get("position", len(data["targets"]))
                if type(position) is not int or not 0 <= position <= len(data["targets"]):
                    raise AppError("INVALID_EDIT", "Vị trí target không hợp lệ.")
                data["targets"].insert(position, target.model_dump())
            elif op == "remove" and len(path) == 2 and any(t["target_id"] == path[1] for t in data["targets"]):
                data["targets"] = [t for t in data["targets"] if t["target_id"] != path[1]]
            elif op == "reorder" and len(path) == 1 and isinstance(value, list):
                by_id = {t["target_id"]: t for t in data["targets"]}
                if len(value) != len(by_id) or set(value) != set(by_id):
                    raise AppError("INVALID_EDIT", "Reorder phải chứa đủ target IDs, không trùng.")
                data["targets"] = [by_id[x] for x in value]
            else:
                raise AppError("INVALID_EDIT", "Thao tác target không hợp lệ.")
        else:
            raise AppError("INVALID_EDIT", "Field không được sửa qua endpoint này.")
    data.update(conditions=list(conditions.values()), hard_tree=hard, preference_tree=soft)
    return finalize(Requirement.model_validate(data))


def answer_edits(previous: Requirement, answers):
    from api.dto import Edit
    edits = []
    seen = set()
    for answer in answers:
        question = next((q for q in previous.clarifications if q.id == answer.clarification_id), None)
        if question is None or question.id in seen:
            raise AppError("STALE_CLARIFICATION", "Câu hỏi không thuộc revision hiện tại hoặc bị trùng.", 409)
        seen.add(question.id)
        if question.field_path == "conditions":
            raise AppError("INVALID_ANSWER", "Sửa conditions trực tiếp để giải quyết phạm vi/mâu thuẫn.")
        value = answer.value
        if question.reason_code == "DATE_YEAR_REQUIRED":
            import re
            from datetime import date
            from domain.requirements import DateValue
            if type(value) is not int or not 1900 <= value <= 2100:
                raise AppError("INVALID_ANSWER", "Năm phải là số nguyên trong 1900–2100.")
            condition = next(c for c in previous.conditions if c.id == question.field_path.split(".")[1])
            match = re.search(r"(\d{1,2})/(\d{1,2})", condition.value.raw)
            try:
                value = DateValue(value=date(value, int(match.group(2)), int(match.group(1))).isoformat()).model_dump()
            except ValueError as exc:
                raise AppError("INVALID_ANSWER", "Ngày không tồn tại trong năm này.") from exc
        edits.append(Edit(op="replace", target=question.field_path, value=value))
    return edits
