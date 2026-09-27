from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin

from .models import Evidence, ObservedField

_MAX_LINKS = 2_000
_MAX_SCRIPTS = 120
_MAX_JSON_LD = 50
TOUR_SCHEMA_TYPES = {
    "tour_code": "string",
    "title": "string",
    "description": "string",
    "route": "string",
    "duration": "string",
    "departure_city": "string",
    "departure_dates": "list[date]",
    "transport": "string",
    "itinerary_by_day": "list[string]",
    "price_options": "list[Offer|AggregateOffer]",
    "included": "string",
    "excluded": "string",
    "policies": "string",
}
_PROPERTY_FIELDS = {
    "duration": "duration",
    "thời lượng": "duration",
    "transport": "transport",
    "phương tiện": "transport",
    "departure city": "departure_city",
    "điểm khởi hành": "departure_city",
    "khởi hành": "departure_city",
}


@dataclass(slots=True)
class Link:
    url: str
    text: str = ""


@dataclass(slots=True)
class JsonObservation:
    value: object
    raw_value: object
    path: str
    priority: int


@dataclass(slots=True)
class PageContent:
    url: str
    title: str = ""
    text: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    links: list[Link] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    inline_scripts: list[str] = field(default_factory=list)
    json_ld: list[object] = field(default_factory=list)


class _HTMLCollector(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.parts: list[str] = []
        self.metadata: dict[str, str] = {}
        self.links: list[Link] = []
        self.scripts: list[str] = []
        self.inline_scripts: list[str] = []
        self.jsonld: list[str] = []
        self._title_depth = 0
        self._script_type = ""
        self._script_src = ""
        self._script_chunks: list[str] = []
        self._inside_script = False
        self._skip_depth = 0
        self._anchor_depth = 0
        self._anchor_href = ""
        self._anchor_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "meta":
            name = (
                (values.get("name") or values.get("property") or values.get("itemprop") or "")
                .strip()
                .lower()
            )
            content = values.get("content", "").strip()
            if name and content:
                self.metadata.setdefault(name, content)
        elif tag == "link" and "canonical" in values.get("rel", "").lower():
            if values.get("href"):
                self.metadata.setdefault("canonical", urljoin(self.base_url, values["href"]))
        elif tag == "a" and values.get("href"):
            self._anchor_depth += 1
            if self._anchor_depth == 1:
                self._anchor_href = urljoin(self.base_url, values["href"])
                self._anchor_text = []
        elif tag == "title":
            self._title_depth += 1
        elif tag == "script":
            self._inside_script = True
            self._script_src = urljoin(self.base_url, values["src"]) if values.get("src") else ""
            self._script_type = values.get("type", "").lower()
            self._script_chunks = []
        elif tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
        elif tag == "a" and self._anchor_depth:
            self._anchor_depth -= 1
            if self._anchor_depth == 0 and self._anchor_href:
                label = _clean(" ".join(self._anchor_text))
                if len(self.links) < _MAX_LINKS:
                    self.links.append(Link(self._anchor_href, label[:180]))
                self._anchor_href = ""
                self._anchor_text = []
        elif tag == "script":
            source = _clean("".join(self._script_chunks))
            if self._script_src:
                if len(self.scripts) < _MAX_SCRIPTS:
                    self.scripts.append(self._script_src)
            elif source and "ld+json" in self._script_type:
                if len(self.jsonld) < _MAX_JSON_LD:
                    self.jsonld.append(source)
            elif source:
                self.inline_scripts.append(source[:100_000])
            self._script_type = ""
            self._script_src = ""
            self._inside_script = False
            self._script_chunks = []
            if self._skip_depth:
                self._skip_depth -= 1
        elif tag in {"style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._title_depth:
            self.metadata["_title"] = (self.metadata.get("_title", "") + " " + data).strip()
        if self._anchor_depth:
            self._anchor_text.append(data)
        if self._inside_script:
            self._script_chunks.append(data)
            return
        if not self._skip_depth:
            cleaned = _clean(data)
            if cleaned:
                self.parts.append(cleaned)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_html(url: str, body: bytes, content_type: str = "") -> PageContent:
    charset_match = re.search(r"charset=([^;\s]+)", content_type, re.I)
    charset = charset_match.group(1).strip("\"'") if charset_match else "utf-8"
    try:
        html = body.decode(charset, errors="replace")
    except LookupError:
        html = body.decode("utf-8", errors="replace")
    collector = _HTMLCollector(url)
    collector.feed(html)
    collector.close()
    data: list[object] = []
    for raw in collector.jsonld:
        try:
            data.append(json.loads(raw))
        except (json.JSONDecodeError, RecursionError, TypeError):
            continue
    metadata = dict(collector.metadata)
    title = metadata.pop("_title", "")
    return PageContent(
        url=url,
        title=_clean(title),
        text=_clean(" ".join(collector.parts))[:1_000_000],
        metadata=metadata,
        links=collector.links,
        scripts=collector.scripts,
        inline_scripts=collector.inline_scripts,
        json_ld=data,
    )


def _json_path(path: str, part: str | int) -> str:
    return f"{path}/{str(part).replace('~', '~0').replace('/', '~1')}"


def _walk_json(value: object, path: str):
    """Iteratively yield JSON nodes with paths, avoiding recursion on untrusted input."""
    pending = [(value, path)]
    while pending:
        current, current_path = pending.pop()
        yield current, current_path
        if isinstance(current, dict):
            pending.extend(
                (_value, _json_path(current_path, key))
                for key, _value in reversed(list(current.items()))
            )
        elif isinstance(current, list):
            pending.extend(
                (_value, _json_path(current_path, index))
                for index, _value in reversed(list(enumerate(current)))
            )


def _schema_types(node: dict[str, object]) -> set[str]:
    raw = node.get("@type", [])
    values = raw if isinstance(raw, list) else [raw]
    return {str(value).rsplit("/", 1)[-1].casefold() for value in values if value}


def _address_string(value: object) -> str:
    if isinstance(value, str):
        return _clean(value)
    if not isinstance(value, dict):
        return ""
    parts: list[str] = []
    for key in (
        "streetAddress",
        "addressLocality",
        "addressRegion",
        "postalCode",
        "addressCountry",
    ):
        item = value.get(key)
        if isinstance(item, dict):
            item = item.get("name") or item.get("@id")
        if isinstance(item, list):
            item = ", ".join(str(entry) for entry in item if isinstance(entry, str))
        if isinstance(item, str) and item.strip():
            parts.append(_clean(item))
    return ", ".join(dict.fromkeys(parts))


def organization_observations(
    documents: list[object],
) -> dict[str, list[JsonObservation]]:
    """Return supplier facts only from explicit Organization/ContactPoint JSON-LD nodes."""
    fields = {
        "display_name": [],
        "legal_name": [],
        "description": [],
        "email": [],
        "phone": [],
        "address": [],
        "license_claims": [],
    }

    def add(field_name: str, raw: object, path: str, priority: int) -> None:
        if field_name == "address":
            value = _address_string(raw)
        elif field_name == "license_claims" and isinstance(raw, dict):
            value = raw
        else:
            value = _scalar(raw)
        if value is not None and value != "":
            fields[field_name].append(JsonObservation(value, raw, path, priority))

    def add_property(
        field_name: str, raw: object, path: str, priority: int
    ) -> None:
        values = raw if isinstance(raw, list) else [raw]
        for index, value in enumerate(values):
            value_path = _json_path(path, index) if isinstance(raw, list) else path
            add(field_name, value, value_path, priority)

    for index, document in enumerate(documents):
        for node, path in _walk_json(document, f"json_ld[{index}]"):
            if not isinstance(node, dict):
                continue
            kinds = _schema_types(node)
            if not {"organization", "localbusiness", "travelagency"} & kinds:
                continue
            priority = 4 if {"localbusiness", "travelagency"} & kinds else 3
            for field_name, key in (
                ("display_name", "name"),
                ("legal_name", "legalName"),
                ("description", "description"),
                ("email", "email"),
                ("phone", "telephone"),
                ("address", "address"),
                ("license_claims", "hasCredential"),
            ):
                if key in node:
                    add_property(field_name, node[key], _json_path(path, key), priority)

            raw_contact_points = node.get("contactPoint", [])
            contact_points = (
                list(enumerate(raw_contact_points))
                if isinstance(raw_contact_points, list)
                else [(None, raw_contact_points)]
            )
            for point_index, point in contact_points:
                if not isinstance(point, dict):
                    continue
                point_path = _json_path(path, "contactPoint")
                if point_index is not None:
                    point_path = _json_path(point_path, point_index)
                for field_name, key in (("email", "email"), ("phone", "telephone")):
                    if key in point:
                        add_property(
                            field_name, point[key], _json_path(point_path, key), priority
                        )
    return fields


def _scalar(value: object) -> str | int | float | None:
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return _clean(value) if isinstance(value, str) else value
    return None


def _scalar_at(node: dict[str, object], key: str, path: str):
    value = _scalar(node.get(key))
    return (value, _json_path(path, key)) if value is not None else None


def _tour_product_nodes(page: PageContent) -> list[tuple[dict[str, object], str]]:
    nodes = [
        (node, path)
        for index, document in enumerate(page.json_ld)
        for node, path in _walk_json(document, f"json_ld[{index}]")
        if isinstance(node, dict)
    ]
    main_entity_ids: set[str] = set()
    for node, _ in nodes:
        if "webpage" not in _schema_types(node):
            continue
        entity = node.get("mainEntity")
        entities = entity if isinstance(entity, list) else [entity]
        main_entity_ids.update(
            item["@id"]
            for item in entities
            if isinstance(item, dict) and isinstance(item.get("@id"), str)
        )

    products = []
    for node, path in nodes:
        kinds = _schema_types(node)
        additional_type = node.get("additionalType", "")
        if isinstance(additional_type, list):
            additional_type = " ".join(str(item) for item in additional_type)
        is_tour = bool({"product", "touristtrip"} & kinds) or "touristtrip" in str(
            additional_type
        ).casefold()
        if is_tour and isinstance(node.get("name"), str):
            products.append((node, path))

    if not products:
        return []
    referenced = [
        candidate
        for candidate in products
        if isinstance(candidate[0].get("@id"), str)
        and candidate[0]["@id"] in main_entity_ids
    ]
    if len(referenced) == 1:
        return referenced

    target = page.metadata.get("canonical", page.url)
    target_path = urljoin(page.url, target).split("#", 1)[0].rstrip("/")
    matching = []
    for candidate in products:
        for key in ("url", "@id"):
            value = candidate[0].get(key)
            if isinstance(value, str) and value.split("#", 1)[0].rstrip("/") == target_path:
                matching.append(candidate)
                break
    if len(matching) == 1:
        return matching
    return products if len(products) == 1 else []


def _offer_records(value: object, path: str):
    pending = [(value, path)]
    while pending:
        current, current_path = pending.pop()
        if isinstance(current, list):
            pending.extend(
                (item, _json_path(current_path, index))
                for index, item in reversed(list(enumerate(current)))
            )
            continue
        if not isinstance(current, dict):
            continue
        kinds = _schema_types(current)
        if "aggregateoffer" in kinds:
            nested = current.get("offers")
            if nested:
                pending.append((nested, _json_path(current_path, "offers")))
            else:
                yield current, current_path
        elif "offer" in kinds or _scalar(current.get("price")) is not None:
            yield current, current_path


def _json_field(value: object, page: PageContent, path: str) -> ObservedField:
    snippet = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return ObservedField(
        value=value,
        status="found",
        evidence=[Evidence(page.url, "json_ld", snippet[:360], path)],
    )


def extract_tour_fields(page: PageContent) -> dict[str, ObservedField]:
    """Extract only explicit tour facts represented by structured JSON-LD."""
    fields: dict[str, ObservedField] = {}
    products = _tour_product_nodes(page)
    if len(products) != 1:
        return fields
    product, product_path = products[0]

    for field_name, key in (
        ("title", "name"),
        ("description", "description"),
        ("tour_code", "identifier"),
    ):
        item = _scalar_at(product, key, product_path)
        if item:
            value, path = item
            fields[field_name] = _json_field(value, page, path)

    properties = product.get("additionalProperty", [])
    if not isinstance(properties, list):
        properties = [properties]
    property_values: dict[str, list[tuple[object, str]]] = {}
    for index, item in enumerate(properties):
        if not isinstance(item, dict):
            continue
        raw_name = item.get("name")
        if not isinstance(raw_name, str):
            continue
        normalized_name = unicodedata.normalize("NFKC", raw_name).strip().casefold()
        field_name = _PROPERTY_FIELDS.get(normalized_name)
        if not field_name:
            continue
        property_path = _json_path(_json_path(product_path, "additionalProperty"), index)
        value = _scalar_at(item, "value", property_path)
        if value:
            property_values.setdefault(field_name, []).append(value)
    for field_name, values in property_values.items():
        distinct = {value for value, _ in values}
        if len(distinct) == 1:
            value, path = values[0]
            fields[field_name] = _json_field(value, page, path)

    offers_path = _json_path(product_path, "offers")
    offers = list(_offer_records(product.get("offers"), offers_path))
    if offers:
        values: list[dict[str, object]] = []
        evidence: list[Evidence] = []
        for offer, offer_path in offers:
            option: dict[str, object] = {}
            for source_key, output_key in (
                ("name", "name"),
                ("sku", "sku"),
                ("price", "price"),
                ("lowPrice", "low_price"),
                ("highPrice", "high_price"),
                ("offerCount", "offer_count"),
                ("priceCurrency", "price_currency"),
                ("availability", "availability"),
                ("validFrom", "valid_from"),
                ("validThrough", "valid_through"),
                ("url", "url"),
            ):
                item = _scalar_at(offer, source_key, offer_path)
                if item:
                    option[output_key] = item[0]
            if option:
                values.append(option)
                evidence.append(
                    Evidence(
                        page.url,
                        "json_ld",
                        json.dumps(option, ensure_ascii=False, separators=(",", ":"))[:360],
                        offer_path,
                    )
                )
        if values:
            fields["price_options"] = ObservedField(
                value=values, status="found", evidence=evidence
            )
    return fields


def contact_values(page: PageContent) -> tuple[list[str], list[str]]:
    email_values = set()
    for link in page.links:
        if link.url.lower().startswith("mailto:"):
            address = unquote(link.url[7:].split("?", 1)[0]).strip()
            if address:
                email_values.add(address)
    phone_values = set()
    for link in page.links:
        if link.url.lower().startswith("tel:"):
            phone = unquote(link.url[4:].split("?", 1)[0]).strip()
            if phone:
                phone_values.add(phone)
    return sorted(email_values), sorted(phone_values)
