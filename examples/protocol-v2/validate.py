"""Offline consistency checks of draft exchanges, not a v2 server test."""
from __future__ import annotations

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "src"))
from pydantic import TypeAdapter  # noqa: E402
from domain.requirements import Condition, Party, Tree, Value  # noqa: E402
from domain.crawl import PriceQuote  # noqa: E402

checks = []


def check(name, value):
    if not value:
        raise AssertionError(name)
    checks.append(name)


folder = Path(__file__).resolve().parent
samples = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in folder.glob("*.json")}
for name, sample in samples.items():
    check(name + " synthetic", sample["origin"] == "synthetic" and bool(sample["scenario"]))
    for i, e in enumerate(sample["exchanges"]):
        b = e["response"]["body"]
        check(f"{name}:{i} envelope", b["schema_version"] == "2.0-draft" and b["request_id"])
        check(f"{name}:{i} payload", ("data" in b) != ("error" in b))
        if e["method"] in ("POST", "PATCH"):
            check(f"{name}:{i} retry key", bool(e["headers"]["Idempotency-Key"]))


def data(e):
    return e["response"]["body"]["data"]


req1 = data(samples["requirements"]["exchanges"][0])
batch = samples["batch-edit"]["exchanges"]
confirmed = next(data(e) for e in batch if e["path"].endswith("/confirm"))
cancelled = next(data(e) for e in batch if e["path"].endswith("/cancel"))
check("atomic revision increment", confirmed["revision"] == req1["revision"] + 1)
check("cancel preserves latest confirmed snapshot", cancelled["committed_requirement"] == confirmed)
preview = next(data(e) for e in batch if e["path"] == "/v2/proposals/proposal_demo")
diff = {c["id"]: c for c in preview["changes"]}
check("budget before remains committed", diff["change_budget"]["before"] == 35000000)
check("compound parse retains all edits", set(diff) == {"change_budget", "change_duration", "change_cost"})
discarded = next(data(e) for e in batch if e["path"].endswith("/discard-changes"))
check("discard preserves unrelated fields", {c["id"] for c in discarded["changes"]} == {"change_budget", "change_duration"})

for req in (req1, confirmed, preview["preview"], discarded["preview"]):
    ids = {c["id"] for c in req["conditions"]}
    for c in req["conditions"]:
        Condition.model_validate(c)
    Party.model_validate(req["party"])
    for key, strength in (("hard_tree", "hard"), ("preference_tree", "soft")):
        Tree.model_validate(req[key])
        nodes = [req[key]]
        while nodes:
            node = nodes.pop()
            if node["kind"] == "predicate":
                check("tree ref/strength", node["condition_id"] in ids and next(c for c in req["conditions"] if c["id"] == node["condition_id"])["strength"] == strength)
            nodes.extend(node.get("children", []))
    check("shared v1 typed Value/tree/party validation", True)

for c in samples["requirements"]["exchanges"][0]["request"]["input"]["form"]["conditions"]:
    TypeAdapter(Value).validate_python(c["value"])

comparison = data(samples["comparison"]["exchanges"][-1])["result"]
check("comparison full immutable revision", comparison["requirement_snapshot"] == confirmed and comparison["revision"] == confirmed["revision"])
columns = {c["id"]: c for c in comparison["columns"]}
rows = {r["id"]: r for r in comparison["rows"]}
cells = comparison["cells"]
check("complete row/column matrix", {(c["row_id"], c["column_id"]) for c in cells} == {(r, c) for r in rows for c in columns} and len(cells) == len(rows) * len(columns))
evidence = {data(e)["id"]: data(e) for e in samples["evidence"]["exchanges"]}
evaluations = {e["id"]: e for e in comparison["evaluations"]}
for cell in cells:
    check("all cells have freshness", cell["freshness"]["state"] in ("fresh", "stale", "unknown"))
    check("cell evaluation refs", set(cell["evaluation_ids"]) <= set(evaluations))
    col, row = columns[cell["column_id"]], rows[cell["row_id"]]
    for eid in cell["evidence_ids"]:
        check("cell evidence exists", eid in evidence)
        snap = col["offer_snapshot_id"] if row["scope"] == "offer" else col["tour_snapshot_id"]
        check("evidence bound to correct offer/tour", evidence[eid]["snapshot_id"] == snap)
    if cell["value"] is None:
        check("missing cell remains unknown with reason", cell["data_state"] == "missing" and cell["reason_code"] and not cell["evidence_ids"])
for e in evaluations.values():
    check("evaluation condition/evidence refs", e["condition_id"] in {c["id"] for c in confirmed["conditions"]} and set(e["evidence_ids"]) <= set(evidence))
    if e["reason_code"] == "PRICE_INCOMPLETE":
        check("incomplete cost cannot have exact upper bound", e["status"] == "unknown" and e["actual"]["upper"] is None)
for metric in comparison["analysis"]["metrics"]:
    a, b = metric["operands"]
    check("metric units comparable", all(a[k] == b[k] == metric[k] for k in ("currency", "basis", "coverage")))
    check("subtraction exact", metric["result"] == a["value"] - b["value"])
    for op in metric["operands"]:
        check("operand evidence binding", all(evidence[i]["snapshot_id"] == op["snapshot_id"] for i in op["evidence_ids"]))
for col in columns.values():
    for offer in col["offer_options"]:
        for quote in offer["price_quotes"]:
            PriceQuote.model_validate(quote["value"])
    check("selected offer exists", col["selected_offer_snapshot_id"] in {o["snapshot_id"] for o in col["offer_options"]})
for e in evidence.values():
    quote = e["locator"]["text_quote"]
    check("locator exact text grounded", quote["exact"] in e["raw_quote"])
    if quote["prefix"]:
        check("locator prefix precedes exact", e["raw_quote"].index(quote["prefix"]) < e["raw_quote"].index(quote["exact"]))
    check("deep link safe synthetic origin", e["deep_link"]["url"].startswith(e["source_url"] + "#"))

crawl = data(samples["crawler"]["exchanges"][0])
check("crawler correlation", crawl["request_id"] == samples["crawler"]["exchanges"][0]["request"]["request_id"])
check("crawler canonical tour/offer refs", {o["tour_snapshot_id"] for o in crawl["offers"]} <= {t["snapshot_id"] for t in crawl["tours"]})
for offer in crawl["offers"]:
    for quote in offer["price_quotes"]:
        PriceQuote.model_validate(quote["value"])
        check("crawler quote evidence binding", all(evidence[i]["snapshot_id"] == offer["snapshot_id"] for i in quote["evidence_ids"]))
check("crawler receives no raw user provenance", all("sources" not in c for c in samples["crawler"]["exchanges"][0]["request"]["query_spec"]["conditions"]))
events = data(samples["activity"]["exchanges"][1])["items"]
check("activity order/cursor unique", [e["seq"] for e in events] == list(range(1, len(events) + 1)))
check("cancel has no published result", data(samples["activity"]["exchanges"][-1])["result"] is None)
source_exchanges = samples["admin"]["exchanges"]
source = next(data(e) for e in source_exchanges if e["path"].endswith("/approvals"))
check("source approval does not auto activate", source["access_status"] == "approved" and source["state"] == "paused")
source = next(data(e) for e in source_exchanges if e["method"] == "PATCH" and "sources/" in e["path"])
check("source activation requires approved", source["state"] == "active" and source["access_status"] == "approved")
print(json.dumps({"sample_files": len(samples), "checks_passed": len(checks), "scope": "Draft consistency plus reused v1 Value/Condition/Tree/Party/PriceQuote validation; no v2 server, auth or real crawling"}, ensure_ascii=False))
