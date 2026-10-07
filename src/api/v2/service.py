import hashlib
import json
from datetime import timedelta

from sqlalchemy import func, insert, select, update

from api.dto import Form
from api.store import dump, jobs, resources
from api.v2 import state
from api.v2.models import (
    Change,
    ComparisonV2,
    CreateProposal,
    Interpretation,
    Preferences,
    Proposal,
    RequirementV2,
    canonical_urls,
)
from data_access.v2 import GatewayV2, registry_from_records
from decision.v2 import build_comparison
from domain.common import AppError, now, uid
from domain.requirements import Condition, Message, Readiness, RequirementState, SourceReference, Target, Tree
from requirements.edits import form_requirement
from requirements.nim import parse_validated
from requirements.service import finalize, prune
from requirements.v2 import SlotExtractor


def mode_for(kind, urls):
    return "compare_urls" if kind == "urls" else "hybrid" if urls else "discover"


def membership_tree(base, wanted, field, soft):
    tree = prune(getattr(base, field), {c.id for c in base.conditions} - wanted) or Tree(kind="all")
    base_ids = {c.id for c in base.conditions if (c.strength == "soft") == soft}
    extra = [Tree(kind="predicate", condition_id=cid) for cid in sorted(wanted - base_ids)]
    return Tree(kind="all", children=[tree, *extra]) if extra else tree


def canonical_tree(tree):
    if tree.kind == "predicate":
        return ("predicate", tree.condition_id)
    children = []
    for child in tree.children:
        value = canonical_tree(child)
        if value[0] == tree.kind:
            children.extend(value[1])
        else:
            children.append(value)
    if len(children) == 1:
        return children[0]
    return tree.kind, tuple(sorted(children, key=str))


def changes_between(base, preview, origin):
    changes = []
    old, new = {c.id: c for c in base.conditions}, {c.id: c for c in preview.conditions}
    for cid in sorted(old.keys() | new.keys()):
        before, after = old.get(cid), new.get(cid)
        if (before.model_dump(exclude={"sources"}) if before else None) == (
            after.model_dump(exclude={"sources"}) if after else None
        ):
            continue
        changes.append(
            (
                f"conditions.{cid}",
                before.model_dump(mode="json") if before else None,
                after.model_dump(mode="json") if after else None,
                cid,
            )
        )
    for field in ("party", "reference_urls", "notes"):
        before, after = base.model_dump(mode="json")[field], preview.model_dump(mode="json")[field]
        if field == "party":
            before.pop("sources", None)
            after.pop("sources", None)
        if before != after:
            changes.append((field, before, after, None))
    before_levels, after_levels = (
        base.model_dump(mode="json")["preference_levels"],
        preview.model_dump(mode="json")["preference_levels"],
    )
    for dimension in ("cost", "comfort", "pace", "culture"):
        before = before_levels.get(dimension) if before_levels else None
        after = after_levels.get(dimension) if after_levels else None
        if before != after:
            changes.append((f"preference_levels.{dimension}", before, after, None))
    # Tree changes are retained explicitly. Discard validates the entire resulting AST.
    for field in ("hard_tree", "preference_tree"):
        before, after = getattr(base, field).model_dump(), getattr(preview, field).model_dump()
        if before != after:
            changes.append((field, before, after, None))
    return [
        Change(
            id="change_" + hashlib.sha256(path.encode()).hexdigest()[:24],
            path=path,
            before=before,
            after=after,
            condition_id=cid,
            origin=origin,
            reason="Thay đổi từ bản đã xác nhận; cần review trước khi áp dụng.",
        )
        for path, before, after, cid in changes
    ]


def make_proposal(base, preview, settings, existing=None, origin="user_edit", requested_action=None):
    preview = preview.model_copy(update={"revision": base.revision + 1})
    preview = finalize(RequirementV2.model_validate(preview.model_dump()))
    return Proposal(
        id=existing.id if existing else uid("proposal"),
        version=existing.version + 1 if existing else 1,
        requirement_id=base.id,
        base_revision=base.revision,
        status="needs_clarification" if preview.clarifications else "pending",
        expires_at=existing.expires_at
        if existing
        else (now() + timedelta(minutes=settings.proposal_ttl_minutes)).isoformat(),
        preview=preview,
        changes=changes_between(base, preview, origin),
        clarifications=[q.model_dump() for q in preview.clarifications],
        requested_action=requested_action
        if requested_action is not None
        else (existing.requested_action if existing else None),
    )


def typed_edits(previous, edits):
    data = previous.model_dump(mode="json")
    data["revision"] = max(1, previous.revision)
    by_id = {c.id: c.model_dump(mode="json") for c in previous.conditions}
    hard, soft = previous.hard_tree, previous.preference_tree
    explicit_trees = {}
    for edit in edits:
        if edit.op in {"upsert_condition", "replace_condition_value", "remove_condition"}:
            cid = edit.condition.id if edit.condition else edit.condition_id
            old = by_id.get(cid)
            if edit.op != "upsert_condition" and old is None:
                raise AppError("INVALID_EDIT", "Không tìm thấy condition.")
            if edit.op == "remove_condition":
                del by_id[cid]
                hard, soft = prune(hard, {cid}) or Tree(kind="all"), prune(soft, {cid}) or Tree(kind="all")
                continue
            raw = (
                edit.condition.model_dump(mode="json")
                if edit.condition
                else {**old, "value": edit.value.model_dump(mode="json")}
            )
            raw["sources"] = [
                *(old.get("sources", []) if old else []),
                SourceReference(
                    kind="form",
                    field_path=f"conditions.{cid}",
                    submitted_value={k: v for k, v in raw.items() if k != "sources"},
                ).model_dump(),
            ]
            new = Condition.model_validate(raw)
            if old is None or old["strength"] != new.strength:
                hard, soft = prune(hard, {cid}) or Tree(kind="all"), prune(soft, {cid}) or Tree(kind="all")
                leaf = Tree(kind="predicate", condition_id=cid)
                if new.strength == "soft":
                    soft = Tree(kind="all", children=[soft, leaf])
                else:
                    hard = Tree(kind="all", children=[hard, leaf])
            by_id[cid] = new.model_dump(mode="json")
        elif edit.op == "replace_party":
            data["party"] = edit.party.model_dump(mode="json")
            data["party"]["sources"] = [
                SourceReference(
                    kind="form",
                    field_path="party",
                    submitted_value=edit.party.model_dump(exclude={"sources"}),
                ).model_dump()
            ]
        elif edit.op == "set_preference_level":
            levels = data["preference_levels"] or Preferences().model_dump()
            levels[edit.dimension] = {"level": edit.level, "origin": "user"}
            data["preference_levels"] = levels
        elif edit.op == "replace_reference_urls":
            urls = canonical_urls(edit.reference_urls)
            old_targets = {t.url: t for t in previous.targets}
            data["reference_urls"] = urls
            data["targets"] = [
                old_targets.get(url, Target(target_id=uid("target"), url=url)).model_dump() for url in urls
            ]
            data["mode"] = mode_for(data["input_kind"], urls)
            if not urls and data["input_kind"] == "urls":
                raise AppError("INVALID_EDIT", "URL-only cần ít nhất một URL.")
        elif edit.op == "set_notes":
            data["notes"] = edit.notes
        elif edit.op == "replace_tree":
            explicit_trees[edit.tree_kind] = edit.tree.model_dump()
    data.update(
        conditions=list(by_id.values()), hard_tree=hard.model_dump(), preference_tree=soft.model_dump()
    )
    data.update(explicit_trees)
    return finalize(RequirementV2.model_validate(data))


class Service:
    def __init__(self, store, nim, gateway):
        self.store, self.nim, self.gateway = store, nim, gateway

    def create_requirement(self, c, owner, body):
        rid, urls = uid("req"), canonical_urls(body.reference_urls)
        targets = [Target(target_id=uid("target"), url=u) for u in urls]
        common = dict(
            id=rid,
            input_kind=body.input.kind,
            mode=mode_for(body.input.kind, urls),
            timezone=body.timezone,
            targets=targets,
            reference_urls=urls,
        )
        if body.input.kind == "structured":
            form = body.input.form
            core = form_requirement(
                Form.model_validate(form.model_dump(exclude={"preference_levels", "notes"})),
                requirement_id=rid,
                mode=common["mode"],
                timezone=body.timezone,
                targets=targets,
                requirement_model=RequirementState,
            )
            r = RequirementV2.model_validate(
                {
                    **core.model_dump(),
                    **common,
                    "schema_version": "2.0-draft",
                    "readiness": core.readiness.model_dump(),
                    "preference_levels": form.preference_levels.model_dump(),
                    "notes": form.notes,
                    "provenance": {"source": "user_confirmed_form"},
                }
            )
            self.store.add_resource(c, owner, rid, "requirement_v2", r.model_dump(mode="json"))
            self.store.add_revision(c, owner, r, 0)
            return 201, r.model_dump(mode="json")
        r = RequirementV2(**common, revision=0, readiness=Readiness(can_collect_data=bool(urls)).model_dump())
        self.store.add_resource(c, owner, rid, "requirement_v2", r.model_dump(mode="json"), status="draft")
        preview = r.model_copy(update={"revision": 1})
        p = make_proposal(r, preview, self.store.settings)
        if body.input.kind == "text":
            p = self.queue_parse(c, owner, r, p, body.input.text)
            state.save_proposal(c, owner, p)
            return 202, {
                "requirement_id": rid,
                "revision": 0,
                "proposal_id": p.id,
                "job_id": p.parse_job_id,
                "status": "queued",
            }
        state.save_proposal(c, owner, p)
        return 201, {"requirement_id": rid, "revision": 0, "proposal_id": p.id, "status": "pending"}

    def queue_parse(self, c, owner, base, p, text):
        message = Message(id=uid("msg"), text=text, received_at=now().isoformat())
        jid = self.store.add_job(
            c,
            owner,
            base.id,
            "v2_parse",
            {
                "proposal_id": p.id,
                "proposal_version": p.version,
                "expected_revision": base.revision,
                "message": message.model_dump(),
                "previous": p.preview.model_dump(mode="json")
                if p.preview.conditions or p.preview.messages
                else None,
                "template": p.preview.model_dump(mode="json"),
            },
        )
        return p.model_copy(update={"parse_job_id": jid})

    def propose(self, c, owner, rid, body, requested_action=None):
        base = state.revision(self.store, c, owner, rid)
        if base.revision != body.expected_revision:
            raise AppError("REVISION_CONFLICT", "Yêu cầu đã thay đổi.", 409)
        existing = None
        if body.proposal_id:
            existing = state.proposal(c, owner, body.proposal_id)
            if existing.requirement_id != rid:
                raise AppError("NOT_FOUND", "Proposal không thuộc yêu cầu.", 404)
            state.guard_proposal(
                self.store,
                c,
                owner,
                existing,
                body.expected_revision,
                body.expected_proposal_version,
                allow_parse=True,
            )
        else:
            pending = (
                c.execute(
                    select(state.proposals.c.id).where(
                        state.proposals.c.owner == owner,
                        state.proposals.c.requirement_id == rid,
                        state.proposals.c.status.in_(["pending", "needs_clarification"]),
                    )
                )
                .scalars()
                .all()
            )
            for pid in pending:
                old = state.proposal(c, owner, pid)
                if old.status != "expired":
                    raise AppError("PROPOSAL_CONFLICT", "Đã có proposal; gửi ID/version để tiếp tục.", 409)
        current = existing.preview if existing else base.model_copy(update={"revision": base.revision + 1})
        preview = typed_edits(current, body.input.edits) if body.input.kind == "structured" else current
        p = make_proposal(base, preview, self.store.settings, existing, requested_action=requested_action)
        if body.input.kind == "message":
            p = self.queue_parse(c, owner, base, p, body.input.text)
        state.save_proposal(c, owner, p, expected=existing.version if existing else None)
        if p.parse_job_id:
            return 202, {
                "proposal_id": p.id,
                "proposal_version": p.version,
                "job_id": p.parse_job_id,
                "status": "queued",
            }
        return 200, p.model_dump(mode="json")

    def confirm(self, c, owner, pid, body):
        p = state.proposal(c, owner, pid)
        state.guard_proposal(self.store, c, owner, p, body.expected_revision, body.expected_proposal_version)
        if p.preview.clarifications and any(q.blocking for q in p.preview.clarifications):
            raise AppError("REQUIREMENT_NOT_READY", "Cần làm rõ điều kiện trước khi xác nhận.", 409)
        r = finalize(RequirementV2.model_validate(p.preview.model_dump()))
        self.store.add_revision(c, owner, r, p.base_revision)
        state.save_proposal(
            c,
            owner,
            p.model_copy(update={"status": "confirmed", "version": p.version + 1}),
            expected=p.version,
        )
        return 200, r.model_dump(mode="json")

    def cancel(self, c, owner, pid, body):
        p = state.proposal(c, owner, pid)
        state.guard_proposal(
            self.store, c, owner, p, p.base_revision, body.expected_proposal_version, allow_parse=True
        )
        if p.parse_job_id:
            self.store.cancel(c, owner, p.parse_job_id)
        state.save_proposal(
            c,
            owner,
            p.model_copy(update={"status": "cancelled", "version": p.version + 1}),
            expected=p.version,
        )
        return 200, {
            "proposal_id": pid,
            "status": "cancelled",
            "committed_requirement": state.revision(self.store, c, owner, p.requirement_id).model_dump(
                mode="json"
            ),
        }

    def discard(self, c, owner, pid, body):
        p = state.proposal(c, owner, pid)
        base = state.guard_proposal(
            self.store, c, owner, p, body.expected_revision, body.expected_proposal_version, allow_parse=True
        )
        change_map = {x.id: x for x in p.changes}
        if len(set(body.change_ids)) != len(body.change_ids) or set(body.change_ids) - change_map.keys():
            raise AppError("INVALID_EDIT", "Change IDs không hợp lệ.")
        data = p.preview.model_dump(mode="json")
        conditions = {x.id: x.model_dump(mode="json") for x in p.preview.conditions}
        for cid in body.change_ids:
            change = change_map[cid]
            if change.condition_id:
                if change.before is None:
                    conditions.pop(change.condition_id, None)
                else:
                    conditions[change.condition_id] = change.before
            else:
                if change.path.startswith("preference_levels."):
                    levels = data["preference_levels"] or Preferences().model_dump()
                    levels[change.path.split(".")[1]] = change.before or {
                        "level": 3,
                        "origin": "system_default",
                    }
                    data["preference_levels"] = levels
                else:
                    data[change.path] = change.before
        data["conditions"] = list(conditions.values())
        data["targets"] = [
            Target(
                target_id=next((t.target_id for t in base.targets if t.url == u), uid("target")), url=u
            ).model_dump()
            for u in data["reference_urls"]
        ]
        data["mode"] = mode_for(data["input_kind"], data["reference_urls"])
        # Restore base AST when condition membership changes; preserve base OR grouping.
        for field, is_soft in (("hard_tree", False), ("preference_tree", True)):
            wanted = {x["id"] for x in conditions.values() if (x["strength"] == "soft") == is_soft}
            original = {x.id for x in p.preview.conditions if (x.strength == "soft") == is_soft}
            if wanted == original:
                continue
            tree_change = next((ch for ch in p.changes if ch.path == field), None)
            derived = membership_tree(base, original, field, is_soft)
            explicitly_changed = canonical_tree(getattr(p.preview, field)) != canonical_tree(derived)
            if explicitly_changed and tree_change and tree_change.id not in body.change_ids:
                raise AppError(
                    "DISCARD_DEPENDENCY",
                    "Thay đổi cây liên quan cần được bỏ cùng condition để giữ nghĩa AND/OR.",
                    409,
                    details={"related_change_ids": [tree_change.id]},
                )
            data[field] = membership_tree(base, wanted, field, is_soft).model_dump()
        updated = make_proposal(base, RequirementV2.model_validate(data), self.store.settings, p)
        state.save_proposal(c, owner, updated, expected=p.version)
        return 200, updated.model_dump(mode="json")

    async def parse_job(self, row, worker_id, payload):
        template = RequirementV2.model_validate(payload["template"])
        previous = RequirementV2.model_validate(payload["previous"]) if payload["previous"] else None
        extractor = SlotExtractor(self.nim)
        parsed, metrics = await parse_validated(
            extractor,
            Message.model_validate(payload["message"]),
            previous,
            requirement_id=template.id,
            mode=template.mode,
            timezone=template.timezone,
            targets=template.targets,
            requirement_model=RequirementState,
        )
        preview = RequirementV2.model_validate(
            {
                **template.model_dump(),
                **parsed.model_dump(
                    include={"conditions", "party", "hard_tree", "preference_tree", "messages"}
                ),
            }
        )
        from api.v2.models import TypedEdit

        slot_edits = [
            TypedEdit(op="set_preference_level", dimension=p.dimension, level=p.level)
            for p in extractor.slots.preference_updates
        ]
        if extractor.slots.reference_urls_update:
            slot_edits.append(
                TypedEdit(
                    op="replace_reference_urls", reference_urls=extractor.slots.reference_urls_update.urls
                )
            )
        if extractor.slots.notes_update:
            slot_edits.append(TypedEdit(op="set_notes", notes=extractor.slots.notes_update.text))
        if slot_edits:
            preview = typed_edits(preview, slot_edits)
            preview = preview.model_copy(update={"provenance": {**preview.provenance, **extractor.sources}})
        with self.store.transaction() as c:
            if not state.running(c, row, worker_id):
                return
            p = state.proposal(c, row["owner"], payload["proposal_id"])
            base = state.guard_proposal(
                self.store,
                c,
                row["owner"],
                p,
                payload["expected_revision"],
                payload["proposal_version"],
                allow_parse=True,
            )
            updated = make_proposal(base, preview, self.store.settings, p, "chat_inference")
            state.save_proposal(c, row["owner"], updated, expected=p.version)
            state.emit(c, row["id"], "interpretation", "completed", "Đề xuất đã chuẩn hóa; chờ xác nhận.")
            state.finish(c, row, worker_id, metrics=metrics)

    def current(self, owner, rid):
        with self.store.engine.connect() as c:
            r = state.revision(self.store, c, owner, rid)
            pids = (
                c.execute(
                    select(state.proposals.c.id).where(
                        state.proposals.c.owner == owner,
                        state.proposals.c.requirement_id == rid,
                        state.proposals.c.status.in_(["pending", "needs_clarification"]),
                    )
                )
                .scalars()
                .all()
            )
            active = [state.proposal(c, owner, pid) for pid in pids]
            active = [p for p in active if p.status != "expired" and p.base_revision == r.revision]
            latest_job = c.execute(
                select(jobs.c.id)
                .where(jobs.c.owner == owner, jobs.c.resource_id == rid)
                .order_by(jobs.c.created_at.desc(), jobs.c.id.desc())
                .limit(1)
            ).scalar()
            latest_comparison = c.execute(
                select(resources.c.id)
                .where(
                    resources.c.owner == owner,
                    resources.c.kind == "comparison_v2",
                    resources.c.revision == r.revision,
                    func.coalesce(
                        func.json_extract(resources.c.payload, "$.requirement_id"),
                        func.json_extract(resources.c.payload, "$.result.requirement_id"),
                    )
                    == rid,
                )
                .order_by(resources.c.created_at.desc(), resources.c.id.desc())
                .limit(1)
            ).scalar()
            comparison_job = (
                c.execute(
                    select(jobs.c.id)
                    .where(
                        jobs.c.owner == owner,
                        jobs.c.resource_id == latest_comparison,
                        jobs.c.kind == "v2_comparison",
                    )
                    .order_by(jobs.c.created_at.desc(), jobs.c.id.desc())
                    .limit(1)
                ).scalar()
                if latest_comparison
                else None
            )
        return {
            **r.model_dump(mode="json"),
            "active_proposal": {"id": active[-1].id, "version": active[-1].version} if active else None,
            "latest_job_id": latest_job,
            "latest_comparison_id": latest_comparison,
            "latest_comparison_job_id": comparison_job,
        }

    def registry(self, connection=None):
        if connection is not None:
            records = [
                json.loads(p) for p in connection.execute(select(state.source_registry.c.payload)).scalars()
            ]
            return registry_from_records(records)
        with self.store.engine.connect() as c:
            records = [json.loads(p) for p in c.execute(select(state.source_registry.c.payload)).scalars()]
        return registry_from_records(records)

    def stage(self, row, worker_id, stage, status, summary, **kwargs):
        with self.store.transaction() as c:
            if not state.running(c, row, worker_id):
                raise AppError("JOB_CANCELLED", "Job đã kết thúc.", 409)
            c.execute(update(jobs).where(jobs.c.id == row["id"]).values(phase=stage))
            state.emit(c, row["id"], stage, status, summary, **kwargs)

    def create_comparison(self, c, owner, body):
        r = state.revision(self.store, c, owner, body.requirement_id)
        if r.revision != body.revision:
            raise AppError("REVISION_CONFLICT", "Chỉ tìm theo revision hiện tại đã xác nhận.", 409)
        if not r.readiness.can_collect_data:
            raise AppError("REQUIREMENT_NOT_READY", "Cần làm rõ phạm vi tìm kiếm.", 409)
        pending = (
            c.execute(
                select(state.proposals.c.id).where(
                    state.proposals.c.owner == owner,
                    state.proposals.c.requirement_id == r.id,
                    state.proposals.c.status.in_(["pending", "needs_clarification"]),
                )
            )
            .scalars()
            .all()
        )
        if any(state.proposal(c, owner, pid).status != "expired" for pid in pending):
            raise AppError("PROPOSAL_NOT_CONFIRMED", "Xác nhận hoặc hủy proposal trước khi tìm.", 409)
        payload = body.model_dump(mode="json")
        if body.previous_comparison_id:
            prior = self.store.resource(owner, body.previous_comparison_id, c, "comparison_v2")
            old = json.loads(prior["payload"])
            if prior["status"] not in {"succeeded", "partial"} or old["result"]["requirement_id"] != r.id:
                raise AppError(
                    "OFFER_SELECTION_INVALID", "Comparison trước chưa hoàn tất hoặc thuộc yêu cầu khác.", 409
                )
            if body.round_intent != "initial" and old["result"]["revision"] != r.revision:
                raise AppError("REVISION_CONFLICT", "Nhóm tiếp theo/đổi offer cần cùng revision.", 409)
            if body.round_intent == "next_group":
                payload["excluded_tour_ids"] = sorted(
                    set(
                        payload["excluded_tour_ids"]
                        + old["result"]["recommendations"]["excluded_tour_ids"]
                        + old["result"]["recommendations"]["candidate_ids"]
                    )
                )
            if body.offer_selections:
                columns = {col["tour_id"]: col for col in old["result"]["columns"] if col["tour_id"]}
                for selection in body.offer_selections:
                    if selection.tour_id not in columns or selection.offer_snapshot_id not in {
                        o["snapshot_id"] for o in columns[selection.tour_id]["offer_options"]
                    }:
                        raise AppError("OFFER_SELECTION_INVALID", "Offer không thuộc comparison đã xem.", 409)
        cid = uid("comparison")
        self.store.add_resource(c, owner, cid, "comparison_v2", payload, revision=r.revision)
        jid = self.store.add_job(c, owner, cid, "v2_comparison", payload)
        return 202, {
            "comparison_id": cid,
            "job_id": jid,
            "requirement_id": r.id,
            "revision": r.revision,
            "status": "queued",
        }

    async def comparison_job(self, row, worker_id, payload):
        with self.store.engine.connect() as c:
            r = state.revision(self.store, c, row["owner"], payload["requirement_id"], payload["revision"])
        registry = self.registry()
        self.stage(
            row, worker_id, "reference_collection", "started", "Thu thập nguồn theo yêu cầu đã xác nhận."
        )
        if payload["round_intent"] == "offer_change":
            from domain.crawl import CrawlResult

            old = json.loads(
                self.store.resource(row["owner"], payload["previous_comparison_id"], kind="comparison_v2")[
                    "payload"
                ]
            )
            crawl = CrawlResult.model_validate(old["crawl"])
            approved = {s.source_id for s in registry if s.access_status == "approved"}
            if any(s.source_id not in approved for s in crawl.source_results if s.tour_snapshot_ids):
                raise AppError("SOURCE_BLOCKED", "Nguồn không còn được duyệt để dùng lại snapshot.", 409)
        else:
            crawl = await GatewayV2(self.gateway, registry).collect(r, row["deadline_at"])
        failures = [s for s in crawl.source_results if s.status in {"error", "timeout"}]
        self.stage(
            row,
            worker_id,
            "reference_collection",
            "partial" if failures else "completed",
            "Đã nhận kết quả acquisition.",
            counts={"tours": len(crawl.tours), "offers": len(crawl.offers), "errors": len(failures)},
        )
        if failures and not crawl.tours:
            raise AppError(
                "SOURCES_UNAVAILABLE",
                "Không có snapshot dùng được từ các nguồn được gọi.",
                502,
                retryable=True,
            )
        self.stage(
            row,
            worker_id,
            "normalization",
            "completed",
            "CrawlResult đã qua schema và source/evidence binding.",
        )
        result = ComparisonV2.model_validate(
            build_comparison(
                row["resource_id"],
                r,
                crawl,
                registry,
                now().isoformat(),
                exclusions=payload["excluded_tour_ids"],
                selections=payload["offer_selections"],
                candidate_limit=payload["candidate_limit"],
                progress=lambda stage, status, summary, **kwargs: self.stage(
                    row, worker_id, stage, status, summary, **kwargs
                ),
            )
        )
        with self.store.transaction() as c:
            if not state.running(c, row, worker_id):
                return
            # Pause/block is checked again at publication, after the upstream await.
            active = {s.source_id for s in self.registry(c) if s.access_status == "approved"}
            if any(s.source_id not in active for s in crawl.source_results if s.tour_snapshot_ids):
                raise AppError("SOURCE_BLOCKED", "Nguồn bị chặn trong lúc xử lý.", 409)
            state.persist_snapshots(c, row["owner"], row["resource_id"], crawl)
            status = "partial" if failures else "succeeded"
            c.execute(
                update(resources)
                .where(resources.c.id == row["resource_id"])
                .values(
                    status=status,
                    payload=dump(
                        {"result": result.model_dump(mode="json"), "crawl": crawl.model_dump(mode="json")}
                    ),
                )
            )
            state.finish(c, row, worker_id, status)

    def conversation(self, c, owner, rid, body):
        r = state.revision(self.store, c, owner, rid)
        context = body.context
        if context.requirement_revision != r.revision:
            raise AppError("REVISION_CONFLICT", "Chat context đang dùng yêu cầu cũ.", 409)
        if context.proposal_id:
            p = state.proposal(c, owner, context.proposal_id)
            if p.requirement_id != rid:
                raise AppError("NOT_FOUND", "Proposal không thuộc yêu cầu.", 404)
            state.guard_proposal(
                self.store, c, owner, p, r.revision, context.proposal_version, allow_parse=True
            )
        if context.comparison_id:
            old = self.store.resource(owner, context.comparison_id, c, "comparison_v2")
            result = json.loads(old["payload"]).get("result")
            if not result or result["requirement_id"] != rid or result["revision"] != context.result_revision:
                raise AppError("REVISION_CONFLICT", "Comparison context không đúng snapshot.", 409)
            evidence = {eid for cell in result["cells"] for eid in cell["evidence_ids"]}
            offer_ids = {col["offer_snapshot_id"] for col in result["columns"] if col["offer_snapshot_id"]}
            if set(context.evidence_ids) - evidence or set(context.offer_snapshot_ids) - offer_ids:
                raise AppError("INVALID_INPUT", "Chat context có refs ngoài comparison.")
        elif context.offer_snapshot_ids or context.evidence_ids:
            raise AppError("INVALID_INPUT", "Refs cần comparison context.")
        old = c.execute(
            select(state.messages.c.payload).where(
                state.messages.c.requirement_id == rid,
                state.messages.c.client_message_id == body.client_message_id,
            )
        ).scalar()
        fingerprint = hashlib.sha256(dump(body.model_dump()).encode()).hexdigest()
        if old:
            saved = json.loads(old)
            if saved["fingerprint"] != fingerprint:
                raise AppError("IDEMPOTENCY_CONFLICT", "client_message_id đã dùng với nội dung khác.", 409)
            return 202, saved["accepted"]
        accepted = {"message_id": uid("msg"), "status": "queued"}
        jid = self.store.add_job(
            c,
            owner,
            rid,
            "v2_message",
            {"body": body.model_dump(mode="json"), "message_id": accepted["message_id"]},
        )
        accepted["job_id"] = jid
        c.execute(
            insert(state.messages).values(
                requirement_id=rid,
                client_message_id=body.client_message_id,
                owner=owner,
                created_at=now().isoformat(),
                payload=dump({"fingerprint": fingerprint, "accepted": accepted, "result": None}),
            )
        )
        return 202, accepted

    async def message_job(self, row, worker_id, payload):
        body = payload["body"]
        context = body["context"]
        result = None
        if context["comparison_id"]:
            result = json.loads(
                self.store.resource(row["owner"], context["comparison_id"], kind="comparison_v2")["payload"]
            )["result"]
        bounded_context = {
            "has_proposal": bool(context["proposal_id"]),
            "requirement_revision": context["requirement_revision"],
            "metrics": result["analysis"]["metrics"] if result else [],
            "evaluations": result["evaluations"] if result else [],
        }
        intent = Interpretation.model_validate(
            await self.nim.interpret(
                Message(id=payload["message_id"], text=body["text"], received_at=row["created_at"]),
                bounded_context,
            )
        )
        with self.store.transaction() as c:
            if not state.running(c, row, worker_id):
                return
            current = state.revision(self.store, c, row["owner"], row["resource_id"])
            if current.revision != context["requirement_revision"]:
                raise AppError("REVISION_CONFLICT", "Yêu cầu thay đổi trong lúc xử lý chat.", 409)
            response = {
                "message_id": payload["message_id"],
                "intent": intent.intent,
                "requested_action": intent.requested_action,
                "proposal_id": None,
                "answer": None,
            }
            if intent.intent == "edit":
                proposal_body = CreateProposal(
                    expected_revision=current.revision,
                    proposal_id=context["proposal_id"],
                    expected_proposal_version=context["proposal_version"],
                    input={"kind": "message", "text": body["text"]},
                )
                _, proposed = self.propose(
                    c, row["owner"], current.id, proposal_body, intent.requested_action
                )
                response.update(proposed)
            elif intent.intent in {"search", "next_group"}:
                response["requested_action"] = intent.intent
            elif intent.intent == "answer" and result:
                metric_map = {m["id"]: m for m in result["analysis"]["metrics"]}
                eval_map = {e["id"]: e for e in result["evaluations"]}
                if set(intent.metric_ids) - metric_map.keys() or set(intent.evaluation_ids) - eval_map.keys():
                    raise AppError("LLM_INVALID_OUTPUT", "Câu trả lời chọn refs không thuộc comparison.", 502)
                response["answer"] = {
                    "comparison_id": result["id"],
                    "revision": result["revision"],
                    "metrics": [metric_map[i] for i in intent.metric_ids],
                    "evaluations": [eval_map[i] for i in intent.evaluation_ids],
                    "text": "Các dữ kiện dưới đây thuộc bảng đang xem; mục chưa rõ cần kiểm tra nguồn.",
                }
            else:
                response.update(
                    intent="clarify",
                    answer={"text": "Bạn làm rõ điều kiện cần sửa hoặc chọn bảng để hỏi dữ liệu nhé."},
                )
            saved = c.execute(
                select(state.messages.c.payload).where(
                    state.messages.c.requirement_id == current.id,
                    state.messages.c.client_message_id == body["client_message_id"],
                )
            ).scalar()
            data = json.loads(saved)
            data["result"] = response
            c.execute(
                update(state.messages)
                .where(
                    state.messages.c.requirement_id == current.id,
                    state.messages.c.client_message_id == body["client_message_id"],
                )
                .values(payload=dump(data))
            )
            state.emit(
                c, row["id"], "interpretation", "completed", "Đã xác định ý định; chưa tự commit hoặc tìm."
            )
            state.finish(c, row, worker_id)

    async def run_job(self, row, worker_id, payload):
        self.stage(
            row,
            worker_id,
            {
                "v2_comparison": "orchestration",
                "v2_source_check": "source_check",
                "v2_source_refresh": "source_refresh",
            }.get(row["kind"], "interpretation"),
            "started",
            "Bắt đầu xử lý.",
        )
        handler = {
            "v2_parse": self.parse_job,
            "v2_comparison": self.comparison_job,
            "v2_message": self.message_job,
            "v2_source_check": self.admin.check_job,
            "v2_source_refresh": self.admin.refresh_job,
        }[row["kind"]]
        await handler(row, worker_id, payload)
