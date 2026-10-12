"""Evidence gate: junk filtering plus verbatim validation. Fail loud, never invent."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date

OK, BLOCKED, FETCH_FAIL, PARSE_FAIL = "ok", "blocked", "fetch_fail", "parse_fail"

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)


def visible_len(value: object) -> int:
    """Visible-text characters of a value (HTML tags don't count)."""
    if not isinstance(value, str):
        return 0
    return len(re.sub(r"\s+", " ", re.sub(r"<[^>]{1,500}>", " ", value)).strip())


def is_junk_field(key: str, value: object, presentation: set, keep: re.Pattern,
                  min_visible: int = 40) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        if not value.strip():
            return True
        if UUID_RE.match(value.strip()):
            return True
        if key.casefold() in presentation:
            return True
        if visible_len(value) >= min_visible:
            return False
        return not keep.search(key)
    if isinstance(value, bool):
        return not keep.search(key)
    if isinstance(value, (int, float)):
        return not keep.search(key)
    return isinstance(value, (dict, list)) and not value


def compile_keep(patterns: list) -> re.Pattern:
    """Keep-patterns always case-insensitive (keys are camelCase)."""
    return re.compile("|".join(patterns or [r"(?!)"]), re.I)


def filter_dep(dep: dict, presentation: set, keep: re.Pattern, min_visible: int = 40) -> dict:
    return {k: v for k, v in dep.items() if not is_junk_field(k, v, presentation, keep, min_visible)}


def fallback_fields(record: dict) -> list[str]:
    """Record fields that fell back to empty (no usable value extracted).

    A rising fallback share per field across runs is the cheapest layout-drift
    signal: the site changed faster than any re-survey schedule.
    """
    return sorted(key for key, value in record.items()
                  if value in (None, "", [], {}))


def summarize_details(details: list[dict], fill_fields: Sequence[str]) -> dict:
    """Run stats from detail JSONs: tour count, mean price, fill rates."""
    prices: list[float] = []
    fills: dict[str, int] = {}
    fallback_total = 0
    for detail in details:
        record = detail.get("record") if isinstance(detail, dict) else None
        if not isinstance(record, dict):
            continue
        price = record.get("price")
        if isinstance(price, bool):
            pass
        elif isinstance(price, (int, float)) and price > 0:
            prices.append(float(price))
        for field in fill_fields:
            value = record.get(field)
            fills[field] = fills.get(field, 0) + (0 if value in (None, "", [], {}) else 1)
        fallback_total += len(fallback_fields(record))
    tours = len(details)
    return {
        "tours": tours,
        "price_mean": (sum(prices) / len(prices)) if prices else None,
        "fill": {f: (fills.get(f, 0) / tours if tours else 0.0) for f in fill_fields},
        "fallback_total": fallback_total,
    }


def compare_quality(current: dict, previous: dict, cfg: dict) -> list[str]:
    """Warn-only drift signals of the current run against the previous good one."""
    warnings: list[str] = []
    min_ratio = float(cfg.get("min_tours_ratio", 0.8))
    max_shift = float(cfg.get("max_price_shift", 0.3))
    min_fill = float(cfg.get("min_fill_rate", 0.85))
    prev_tours = int(previous.get("tours", 0) or 0)
    cur_tours = int(current.get("tours", 0) or 0)
    if prev_tours > 0 and cur_tours / prev_tours < min_ratio:
        warnings.append(f"tours {cur_tours} below {min_ratio:.2f} of previous {prev_tours}")
    prev_mean = previous.get("price_mean")
    cur_mean = current.get("price_mean")
    if prev_mean and cur_mean and prev_mean > 0:
        shift = abs(cur_mean - prev_mean) / prev_mean
        if shift > max_shift:
            warnings.append(f"mean price shifted {shift:.2f} "
                            f"({prev_mean:.0f} -> {cur_mean:.0f})")
    for field, rate in (current.get("fill") or {}).items():
        if rate < min_fill:
            warnings.append(f"fill {field} {rate:.2f} below {min_fill:.2f}")
    return warnings


def dedupe_departures(departures: list) -> tuple[list, dict]:
    """Hoist values identical across all departures to tour level."""
    if not departures:
        return departures, {}
    shared: dict = {}
    for key in set(departures[0].keys()):
        values = [dep.get(key) for dep in departures]
        if all(v == values[0] and v not in (None, "") for v in values):
            shared[key] = values[0]
    if not shared:
        return departures, {}
    return [{k: v for k, v in dep.items() if k not in shared} for dep in departures], shared


def extract_notes(payloads: list, pattern: str, min_visible: int = 40) -> dict:
    """Notes subtrees keyed by semantic key pattern (generic, never URLs)."""
    note_pat = re.compile(pattern, re.I) if pattern else None
    notes: dict = {}

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if (
                    isinstance(key, str)
                    and note_pat is not None
                    and note_pat.search(key)
                    and visible_len(value) >= min_visible
                    and key not in notes
                ):
                    notes[key] = value
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for payload in payloads:
        walk(payload)
    return notes


def normalize(text: str) -> str:
    return re.sub(r"\W+", " ", text.casefold()).strip()


def _leaves(value: object) -> list[str]:
    """Scalar leaves of a record value for verbatim checking."""
    if value is None:
        return []
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [re.sub(r"\D", "", str(value))]
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_leaves(item))
        return out
    if isinstance(value, dict):
        out = []
        for item in value.values():
            out.extend(_leaves(item))
        return out
    return []


def verify_record(record: dict, raw: dict, html: str) -> tuple[str, list[str]]:
    """Verbatim evidence check for one static DSL record.

    Evidence is always checked against RAW pre-clean values, never against
    cleaned output: a normalized enum (`mixed`) or a reformatted structure
    can never appear verbatim, so checking cleaned values would fail honest
    records. A field with an empty raw but a non-empty value was synthesized
    without a source and counts as missing. Structural keys such as the
    source url are never checked. No fuzzy matching.
    """
    context_norm = normalize(html)
    context_digits = re.sub(r"\D", "", html)
    missing: list[str] = []
    checked = 0
    for key, value in record.items():
        if key == "url":
            continue
        raw_leaves = [leaf for leaf in _leaves(raw.get(key)) if normalize(leaf)]
        if not raw_leaves:
            if _leaves(value):
                missing.append(key)
            continue
        checked += len(raw_leaves)
        ok = True
        for leaf in raw_leaves:
            if leaf.isdigit():
                if leaf not in context_digits:
                    ok = False
                    break
            elif normalize(leaf) not in context_norm:
                ok = False
                break
        if not ok:
            missing.append(key)
    if checked == 0:
        return "unverified", missing
    if not missing:
        return "verified", missing
    return "partial", missing


_REQUIRED_RECORD_FIELDS = {
    "tour_name", "departure_city", "destinations", "duration_days", "price",
    "currency", "itinerary", "inclusions", "exclusions",
}
_STRING_RECORD_FIELDS = {
    "tour_name", "departure_city", "currency", "price_type", "departure_pattern",
    "itinerary", "inclusions", "exclusions", "cancellation_policy", "surcharges",
    "child_policy", "route_text",
}
_PLACE_TYPES = {
    "place", "country", "city", "administrativearea", "state", "province",
    "island", "touristattraction", "touristdestination", "geographicregion",
}


def _empty(value: object) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _shape_problem(field: str, value: object) -> str:
    """Canonical type/format validation, without coercing bad extraction."""
    if field in _STRING_RECORD_FIELDS:
        if not isinstance(value, str):
            return "expected_string"
        if field == "currency" and value and not re.fullmatch(r"[A-Z]{3}", value):
            return "expected_iso_4217_code"
        if field == "price_type" and value and value not in {"fixed", "from", "contact"}:
            return "invalid_price_type"
        return ""
    if field in {"duration_days", "duration_nights", "price", "single_supplement"}:
        if isinstance(value, bool) or not isinstance(value, int):
            return "expected_integer"
        if value < 0 or (field in {"duration_days", "price"} and value == 0):
            return "out_of_range"
        return ""
    if field in {"destinations", "route"}:
        if not isinstance(value, list):
            return "expected_list_of_strings"
        if any(not isinstance(item, str) or not item.strip() for item in value):
            return "expected_nonempty_string_items"
        if field == "destinations" and not value:
            return "empty_destinations"
        return ""
    if field == "transport":
        accepted = {"", "flight", "bus", "train", "cruise", "mixed"}
        return "invalid_transport" if not isinstance(value, str) or value not in accepted else ""
    if field == "accommodation":
        accepted = {"", "homestay", "2_star", "3_star", "4_star", "5_star", "mixed"}
        return "invalid_accommodation" if not isinstance(value, str) or value not in accepted else ""
    if field == "offers":
        if not isinstance(value, list):
            return "expected_list_of_offers"
        for offer in value:
            if not isinstance(offer, dict):
                return "expected_offer_object"
            departure_date = offer.get("departure_date")
            if not isinstance(departure_date, str) or not re.fullmatch(
                    r"\d{4}-\d{2}-\d{2}", departure_date):
                return "invalid_offer_departure_date"
            try:
                date.fromisoformat(departure_date)
            except ValueError:
                return "invalid_offer_departure_date"
            price = offer.get("price")
            if isinstance(price, bool) or not isinstance(price, int) or price < 0:
                return "invalid_offer_price"
            availability = offer.get("availability", "unknown")
            if not isinstance(availability, str) or availability not in {"available", "sold_out", "unknown"}:
                return "invalid_offer_availability"
        return ""
    return ""


def _structured_place_names(nodes: object) -> set[str]:
    names: set[str] = set()

    def visit(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if not isinstance(node, dict):
            return
        raw_types = node.get("@type", [])
        types = raw_types if isinstance(raw_types, list) else [raw_types]
        if any(str(item).rsplit("/", 1)[-1].casefold() in _PLACE_TYPES for item in types):
            name = node.get("name")
            if isinstance(name, str) and name.strip():
                names.add(normalize(name))
        for value in node.values():
            visit(value)

    visit(nodes)
    return names


def _source_problem(field: str, value: object, source_raw: object) -> str:
    """Check that normalization is grounded in the field's own raw value."""
    raw_values = _leaves(source_raw)
    raw_text = " ".join(raw_values).casefold()
    source = normalize(raw_text)
    if field in {"price", "duration_days", "duration_nights", "single_supplement"}:
        number_tokens = re.findall(
            r"(?<!\d)\d{1,3}(?:[.,\s]\d{3})+(?!\d)|(?<!\d)\d+(?!\d)", raw_text)
        source_numbers = {int(re.sub(r"\D", "", token)) for token in number_tokens}
        if (not isinstance(value, int) or isinstance(value, bool) or
                value not in source_numbers):
            return "numeric_value_not_grounded_in_field_source"
    elif field == "route":
        stops = value if isinstance(value, list) else []
        cursor = 0
        for stop in stops:
            normalized = normalize(stop) if isinstance(stop, str) else ""
            position = source.find(normalized, cursor) if normalized else -1
            if position < 0:
                return "route_stop_not_grounded_or_order_changed"
            cursor = position + len(normalized)
    elif field == "currency":
        aliases = {
            "VND": ("vnd", "vnđ", "dong", "đ"),
            "USD": ("usd", "us dollar", "$"),
            "EUR": ("eur", "euro", "€"),
            "CNY": ("cny", "rmb", "yuan", "¥"),
        }
        choices = aliases.get(str(value), (str(value).casefold(),))
        normalized_choices = [normalize(item) for item in choices]
        literal_choices = [item.casefold() for item in choices if not normalize(item)]
        if (not any(item and item in source for item in normalized_choices) and
                not any(item in raw_text for item in literal_choices)):
            return "currency_not_grounded_in_field_source"
    elif field == "transport":
        mode_terms = {
            "flight": ("may bay", "flight", "airline"),
            "bus": ("xe", "bus", "coach", "car"),
            "train": ("tau hoa", "tau lua", "train"),
            "cruise": ("du thuyen", "cruise", "tau bien"),
        }
        padded_source = f" {source} "
        found = [mode for mode, terms in mode_terms.items()
                 if any((f" {normalize(term)} " in padded_source
                         if " " not in normalize(term) else normalize(term) in source)
                        for term in terms)]
        if value == "mixed" and len(found) < 2:
            return "mixed_transport_not_supported_by_multiple_modes"
        if value in mode_terms and value not in found:
            return "transport_not_grounded_in_field_source"
    elif field == "accommodation":
        stars = set(re.findall(r"\b([2-5])\s*(?:sao|star|\*)", raw_text))
        has_homestay = "homestay" in source
        if value == "homestay" and not has_homestay:
            return "accommodation_not_grounded_in_field_source"
        if value == "mixed" and len(stars) + int(has_homestay) < 2:
            return "mixed_accommodation_not_supported_by_multiple_types"
        if isinstance(value, str) and value.endswith("_star"):
            expected = value[0]
            if expected not in stars:
                return "accommodation_not_grounded_in_field_source"
    elif field == "price_type":
        from_markers = ("gia tu", "starting at", "from")
        contact_markers = ("lien he", "contact", "call for")
        if value == "from" and not any(marker in source for marker in from_markers):
            return "price_type_not_grounded_in_field_source"
        if value == "contact" and not any(marker in source for marker in contact_markers):
            return "price_type_not_grounded_in_field_source"
        if value == "fixed":
            explicit = any(marker in source for marker in ("gia co dinh", "fixed price", "gia tron goi"))
            ambiguous = any(marker in source for marker in from_markers + contact_markers)
            has_price = bool(re.search(r"\d", " ".join(raw_values)))
            if not explicit and (ambiguous or not has_price):
                return "fixed_price_not_grounded_in_field_source"
    elif field in _STRING_RECORD_FIELDS and field != "price_type":
        normalized = normalize(value) if isinstance(value, str) else ""
        if normalized and normalized not in source:
            return "cleaned_value_not_grounded_in_field_source"
    return ""


def _taxonomy_place_names(html: str, profile: dict) -> set[str]:
    validation = profile.get("destination_validation") or {}
    selector = validation.get("selector", "") if isinstance(validation, dict) else ""
    rule = (profile.get("fields") or {}).get("destinations") or {}
    selector = selector or rule.get("taxonomy_selector", "")
    if not selector:
        return set()
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        values = [node.get_text(" ", strip=True) for node in soup.select(str(selector))]
    except Exception:
        return set()
    return {normalize(value) for value in values if normalize(value)}


_COMPOSITE_PLACE_RE = re.compile(r"\s+[–—-]\s+")


def verify_record_fields(record: dict, raw: dict, html: str, profile: dict,
                         extraction_states: dict | None = None,
                         structured_data: object = None
                         ) -> tuple[str, list[str], dict[str, dict[str, object]]]:
    """Verify each canonical field against its declared coordinate and contract.

    This intentionally does not accept a value because the same string happens
    to occur somewhere else on the page. `raw` must be the exact pre-clean value
    from the profile rule; `extraction_states` identifies locator/clean failures.
    """
    rules_value = profile.get("fields")
    rules: dict = rules_value if isinstance(rules_value, dict) else {}
    states: dict = extraction_states if isinstance(extraction_states, dict) else {}
    fields = set(rules) | set(record) | _REQUIRED_RECORD_FIELDS
    fields.discard("url")
    fields.discard("json_ld")
    checks: dict[str, dict[str, object]] = {}
    missing: list[str] = []
    structured_places = _structured_place_names(structured_data)
    structured_places |= _structured_place_names(raw)
    taxonomy_places = _taxonomy_place_names(html, profile)
    place_names = structured_places | taxonomy_places

    for field in sorted(fields):
        rule_value = rules.get(field)
        rule: dict = rule_value if isinstance(rule_value, dict) else {}
        value = record.get(field, "")
        source_raw = raw.get(field, "") if isinstance(raw, dict) else ""
        state = str(states.get(field, ""))
        source: dict[str, object] = {"kind": rule.get("source", "unknown")}
        for coordinate in ("selector", "path", "entity", "label", "start_label", "taxonomy_selector"):
            if rule.get(coordinate):
                source[coordinate] = rule[coordinate]

        status = "verified"
        reason = "source_value_and_shape_verified"
        details: dict[str, object] = {}
        if field not in rules:
            status, reason = "failed", "required_field_has_no_profile_rule"
        elif rule.get("status") == "not_observed" or state == "declared_not_observed":
            status, reason = "not_observed", "profile_declares_source_absence"
        elif state in {"selector_missing", "extraction_error", "clean_error", "api_fetch_failed",
                       "api_fetch_unavailable"}:
            status, reason = "failed", state
        elif state == "clean_empty":
            status, reason = "failed", "clean_removed_or_failed_to_produce_value"
        elif state == "source_empty" or _empty(value):
            status, reason = "unverified", "source_coordinate_empty_without_not_observed_declaration"
        elif not _empty(source_raw) and not state:
            # Backward-compatible detail JSON has raw values but no diagnostics.
            status, reason = "unverified", "extractor_diagnostics_missing"
        elif _empty(source_raw):
            status, reason = "failed", "value_has_no_raw_source_value"
        else:
            shape = _shape_problem(field, value)
            if shape:
                status, reason = "failed", shape
            elif field == "destinations":
                names = [normalize(item) for item in value]
                details = {
                    "confirmed_structured_data": [item for item, normalized in zip(value, names, strict=True)
                                                   if normalized in structured_places],
                    "confirmed_taxonomy": [item for item, normalized in zip(value, names, strict=True)
                                            if normalized in taxonomy_places],
                }
                unsupported = [item for item, normalized in zip(value, names, strict=True)
                               if normalized not in place_names]
                details["unconfirmed"] = unsupported
                if unsupported:
                    composite = next((item for item in unsupported
                                      if len(_COMPOSITE_PLACE_RE.split(item.strip())) > 1), None)
                    if composite:
                        parts = [normalize(part) for part in _COMPOSITE_PLACE_RE.split(composite.strip())]
                        if all(part in place_names for part in parts):
                            status, reason = "failed", "composite_destination_split_is_source_confirmed"
                        else:
                            status, reason = "unverified", "composite_destination_not_confirmed_as_atomic_place"
                    else:
                        status, reason = "unverified", "destination_not_confirmed_by_source_taxonomy_or_structured_data"
            else:
                source_problem = _source_problem(field, value, source_raw)
                if source_problem:
                    status, reason = "failed", source_problem

        checks[field] = {"status": status, "reason": reason, "source": source}
        if details:
            checks[field]["details"] = details
        if status in {"failed", "unverified"} or (status == "not_observed" and field in _REQUIRED_RECORD_FIELDS):
            missing.append(field)

    checked = [item for item in checks.values() if item["status"] != "not_observed"]
    if checked and all(item["status"] == "verified" for item in checked) and not missing:
        verdict = "verified"
    elif any(item["status"] == "verified" for item in checked):
        verdict = "partial"
    else:
        verdict = "unverified"
    return verdict, sorted(set(missing)), checks


OFFER_KEY_MAP = {
    "departureDate": "departure_date",
    "salePrice": "price",
    "tourCode": "tour_code",
    "meetingPlace": "pickup_point",
    "hotelName": "hotel_location",
}

OFFER_SORT_KEYS = ("departure_date", "price")


def normalize_offer(dep: dict) -> dict:
    """Map browser camelCase to the contract snake_case; unknown keys pass through."""
    if not isinstance(dep, dict):
        return dep
    out: dict = {}
    for key, value in dep.items():
        out[OFFER_KEY_MAP.get(key, key)] = value
    return out


def sort_offers(offers: list) -> list:
    """Deterministic Runner ordering so profiles never sort in `clean` (no lambda)."""
    if not isinstance(offers, list):
        return offers
    try:
        return sorted(offers, key=lambda d: (
            str(d.get("departure_date", "")) if isinstance(d, dict) else "",
            d.get("price", 0) if isinstance(d, dict) and isinstance(d.get("price"), (int, float)) else 0,
        ))
    except TypeError:
        return offers


def departure_evidence(dep: dict, context: str) -> str:
    """Spot-check one departure: key decision values verbatim in context.

    Returns verified (all present), partial (some present), or unverified.
    Generic: checks whatever decision fields the entry carries, no fixed schema.
    """
    context_norm = normalize(context)
    checks = []
    for name in ("tour_code", "tourCode", "price", "salePrice",
                 "departure_date", "departureDate", "pickup_point", "meetingPlace"):
        value = dep.get(name)
        if value is None or value == "":
            continue
        checks.append(normalize(str(value)) in context_norm)
    if not checks:
        return "unverified"
    if all(checks):
        return "verified"
    return "partial" if any(checks) else "unverified"
