"""Parameterized acquisition priority. Raw SQL matches never establish eligibility."""

from domain.requirements import DateValue
from requirements.catalog import CATALOG, expand_entities


def folded_sql(column):
    accented = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
    plain = "a" * 17 + "e" * 11 + "i" * 5 + "o" * 17 + "u" * 11 + "y" * 5 + "d"
    return f"translate(lower(COALESCE({column},'')), '{accented}', '{plain}')"


def acquisition_priority(requirement, conditions, *, analysis=False, targets=()):
    params = {}
    scores = []
    for i, c in enumerate(conditions if not analysis else []):
        if c.field not in {"destinations", "departure_origin"} or c.operator in {"excludes", "not_in"}:
            continue
        ids = set(getattr(c.value, "items", [])) | {
            m.entity_id for m in getattr(c.value, "members", []) if m.entity_id
        }
        aliases = [name for name, eid in CATALOG["place"].items() if ids & expand_entities({eid}, "place")]
        if not aliases:
            continue
        key = f"geo_{i}"
        params[key] = aliases
        if c.field == "departure_origin":
            matched = f"trim({folded_sql('tours.departure_city')}) = ANY(CAST(:{key} AS text[]))"
        else:
            matched = (
                "EXISTS (SELECT 1 FROM jsonb_array_elements_text(CASE WHEN jsonb_typeof(tours.destinations)='array' "
                "THEN tours.destinations ELSE '[]'::jsonb END) AS places(place) "
                f"CROSS JOIN LATERAL regexp_split_to_table({folded_sql('place')}, '\\s+[–—-]\\s+') AS pieces(piece) "
                f"WHERE trim(piece) = ANY(CAST(:{key} AS text[])))"
            )
        scores.append(f"CASE WHEN {matched} THEN 1 ELSE 0 END")
    for i, target in enumerate(targets):
        from urllib.parse import urlsplit, urlunsplit

        url = urlsplit(target.url)
        key = f"target_{i}"
        params[key] = urlunsplit((url.scheme, url.netloc, url.path or "/", "", ""))
        scores.append(
            f"CASE WHEN regexp_replace(COALESCE(NULLIF(tours.canonical_url,''),tours.url), '[?#].*$', '') = :{key} THEN 100 ELSE 0 END"
        )
    by_id = {c.id: c for c in conditions}

    def condition_sql(c):
        value = c.value
        resolved = getattr(value, "resolved_date", None)
        if resolved:
            value = DateValue(value=resolved)
        index = len(params)
        if c.field == "departure_date" and isinstance(value, DateValue):
            lo, hi = f"date_{index}", f"date_end_{index}"
            params[lo] = value.value
            field = "offers.departure_date"
            if c.operator == "between":
                params[hi] = value.upper
                return f"{field} BETWEEN CAST(:{lo} AS date) AND CAST(:{hi} AS date)"
            op = {"eq": "=", "lt": "<", "lte": "<=", "gt": ">", "gte": ">="}.get(c.operator)
            return f"{field} {op} CAST(:{lo} AS date)" if op else "TRUE"
        if (
            c.field == "estimated_cost"
            and getattr(value, "measure", None) == "listed"
            and value.basis == "per_adult"
        ):
            lo, hi, currency = f"price_{index}", f"price_end_{index}", f"currency_{index}"
            params[lo], params[currency] = value.amount, value.currency
            field = "(CASE WHEN jsonb_typeof(offers.price_by_age->'adult')='number' THEN (offers.price_by_age->>'adult')::numeric END)"
            prefix = f"tours.currency=:{currency} AND tours.price_type IN ('from','exact') AND {field}>0 AND "
            if c.operator == "between":
                params[hi] = value.upper
                return prefix + f"{field} BETWEEN CAST(:{lo} AS numeric) AND CAST(:{hi} AS numeric)"
            op = {"lt": "<", "lte": "<=", "gt": ">", "gte": ">="}.get(c.operator)
            return prefix + f"{field} {op} CAST(:{lo} AS numeric)" if op else "TRUE"
        return "TRUE"

    def tree_sql(tree):
        if tree.kind == "predicate":
            condition = by_id.get(tree.condition_id)
            return "(" + condition_sql(condition) + ")" if condition else "TRUE"
        children = [tree_sql(child) for child in tree.children]
        return "(" + (" AND " if tree.kind == "all" else " OR ").join(children) + ")" if children else "TRUE"

    offer_predicate = tree_sql(requirement.hard_tree) if not analysis else "TRUE"
    geo = " + ".join(scores) or "0"
    priority = f"({geo}) * 2 + CASE WHEN EXISTS (SELECT 1 FROM public.offers WHERE offers.tour_id=tours.id AND {offer_predicate}) THEN 1 ELSE 0 END"
    return priority if not analysis else "0", offer_predicate, params
