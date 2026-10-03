"""Raw block extraction: pure functions, full fidelity, no guessing."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser

from bs4 import BeautifulSoup

_LD_JSON_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I
)


def parse_json_ld(html: str) -> list:
    """Every parseable JSON-LD node, in document order."""
    blocks = []
    for match in _LD_JSON_RE.finditer(html):
        try:
            data = json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        blocks.extend(data if isinstance(data, list) else [data])
    return blocks


def js_unescape(text: str) -> str:
    """Single-pass JS string unescape (no chained replaces, no double-decoding)."""
    out: list[str] = []
    i, n = 0, len(text)
    simple = {"\\": "\\", '"': '"', "n": "\n", "t": "\t", "r": "\r",
              "b": "\b", "f": "\f", "/": "/"}
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            nxt = text[i + 1]
            if nxt in simple:
                out.append(simple[nxt])
                i += 2
                continue
            if nxt == "u" and i + 5 < n:
                try:
                    out.append(chr(int(text[i + 2 : i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
        out.append(ch)
        i += 1
    return "".join(out)


def balanced_slice(text: str, start: int) -> str | None:
    """Balanced {...} slice respecting strings/escapes; None when unbalanced."""
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_embedded_object(html: str, key: str):
    """First balanced JSON object after a bare key (handles escaped payloads)."""
    decoded = js_unescape(html)
    idx = decoded.find(f'"{key}"')
    if idx < 0:
        return None
    brace = decoded.find("{", idx)
    if brace < 0:
        return None
    raw = balanced_slice(decoded, brace)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {"_unparsed_chars": len(raw)}


class _TextCollector(HTMLParser):
    """Collects text chunks; ignores CSS visibility like a scraper should."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.chunks.append(text)


def _strip_scripts(html: str) -> str:
    return re.sub(r"<(script|style|noscript)[\s>].*?</\1>", " ", html, flags=re.S | re.I)


def page_prose(html: str) -> str:
    """Readable prose: visible text plus decoded script payloads (generic)."""
    parser = _TextCollector()
    parser.feed(re.sub(r"<[^>]{1,500}>", " ", _strip_scripts(html)))
    visible = "\n".join(parser.chunks)
    decoded = js_unescape(html)
    return visible + "\n\n# Embedded payloads\n\n" + decoded[:120_000]


def walk_departures(node, found: list) -> None:
    """Collect every dict carrying a departureDate, containers preserved."""
    if isinstance(node, dict):
        if isinstance(node.get("departureDate"), str):
            found.append(node)
        for value in node.values():
            walk_departures(value, found)
    elif isinstance(node, list):
        for value in node:
            walk_departures(value, found)


def _num(text: str) -> int | None:
    digits = re.sub(r"\D", "", text or "")
    return int(digits) if digits else None


def iso_to_dmy(iso: object) -> str:
    """2026-10-25T08:00:00 -> 25/10/2026 (empty when unparseable)."""
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(iso or ""))
    if not match:
        return ""
    return f"{match.group(3)}/{match.group(2)}/{match.group(1)}"


def parse_panel_detail(segment: str) -> dict:
    """Labeled fields from one expanded detail panel (generic patterns)."""
    lines = [line.strip() for line in segment.splitlines() if line.strip()]
    detail: dict = {}
    flights = re.findall(r"\b([A-Z]{2}\d{2,4})\b", segment)
    if flights:
        detail["flights"] = sorted(set(flights))
    times = re.findall(r"\b([0-2]\d:[0-5]\d)\b", segment)
    if times:
        detail["flight_times"] = times
    tiers = []
    for index, line in enumerate(lines):
        price_hit = re.search(r"(\d[\d.,]*)\s*(₫|đ(?![\wÀ-ỹà-ỹ]))", line)
        if price_hit:
            amount = _num(price_hit.group(1))
            label = lines[index - 1] if index > 0 else ""
            if label.startswith("(") and index > 1:
                label = f"{lines[index - 2]} {label}"
            tiers.append({"label": label, "price": amount})
    if tiers:
        detail["tiered_prices"] = tiers
    for anchor, field in (("tập trung", "meeting_point"), ("khách sạn", "hotel_address")):
        for index, line in enumerate(lines):
            if anchor in line.casefold():
                detail[field] = " ".join(lines[index + 1 : index + 3])
                break
    return detail


def parse_snapshots(snapshots: list) -> dict:
    """Detail per snapshot attributed to the clicked row (no date guessing)."""
    panels: dict = {}
    for clicked_date, html in snapshots:
        if not clicked_date:
            continue
        text = page_text_only(html)
        start = text.find("Thông tin tour:")
        if start < 0:
            continue
        end = text.find("Những thông tin cần lưu ý", start)
        segment = text[start:end] if end > start else text[start : start + 4000]
        detail = parse_panel_detail(segment)
        if detail:
            panels[clicked_date] = detail
    return panels


def parse_fallback(text: str, dmy: str, code: str) -> dict:
    """Last-resort panel for one date from joined rendered text.

    Used only when per-snapshot parsing missed a clicked row. Segments from
    the row's list occurrence to the next date; noisier than snapshots.
    """
    positions = [m.start() for m in re.finditer(re.escape(dmy), text)]
    start = None
    for pos in positions:
        if code and code[:12] in text[pos : pos + 3000]:
            start = pos
            break
    if start is None and positions:
        start = positions[0]
    if start is None:
        return {}
    following = [m.start() for m in re.finditer(r"\d{2}/\d{2}/20\d{2}", text[start + 10 :])]
    end = start + 10 + following[0] if following else start + 4000
    return parse_panel_detail(text[start:end])


def page_text_only(html: str) -> str:
    """All text incl. CSS-hidden nodes (parser ignores visibility)."""
    parser = _TextCollector()
    parser.feed(_strip_scripts(html))
    return re.sub(r"[ \t]+", " ", "\n".join(parser.chunks))


def parse_sections(html: str, anchors: dict, heading_keywords: dict | None = None) -> dict:
    """Section text by element id, falling back to heading-keyword scan.

    Fallback (generic): headings whose text contains any keyword mapped to the
    section name; collects following siblings until the next heading.
    heading_keywords maps section name -> keywords; profiles declare them.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: dict = {}
    keywords = heading_keywords or {}
    for name, ids in anchors.items():
        text = ""
        for anchor in ids:
            node = soup.find(id=anchor)
            if node is not None:
                text = node.get_text("\n", strip=True)
                break
        if not text:
            wants = [key.casefold() for key in keywords.get(name, [])]
            for heading in soup.find_all(["h2", "h3"]):
                title = heading.get_text(" ", strip=True)
                if wants and any(key in title.casefold() for key in wants):
                    parts = [title]
                    for sibling in heading.find_next_siblings():
                        if sibling.name in {"h1", "h2", "h3"}:
                            break
                        chunk = sibling.get_text("\n", strip=True)
                        if chunk:
                            parts.append(chunk)
                    text = "\n".join(parts)
                    break
        out[name] = text
    return out


def parse_itinerary_days(html: str) -> list:
    """Day-by-day blocks: native <details> first, heading siblings as fallback."""
    soup = BeautifulSoup(html, "html.parser")
    days = []
    for day in soup.find_all(["h3"]):
        title = day.get_text(" ", strip=True)
        if not re.match(r"Ngày\s+\d+", title, re.I):
            continue
        details_tag = day.find_parent("details")
        if details_tag is not None:
            parts = []
            for child in details_tag.children:
                if getattr(child, "name", None) == "summary":
                    continue
                text = child.get_text("\n", strip=True) if hasattr(child, "get_text") else str(child).strip()
                if text:
                    parts.append(text)
            detail = "\n".join(parts)
        else:
            parts = []
            for sibling in day.find_next_siblings():
                if sibling.name in {"h1", "h2", "h3"}:
                    break
                text = sibling.get_text("\n", strip=True)
                if text:
                    parts.append(text)
            detail = "\n".join(parts)
        days.append({"day": title[:120], "detail": detail[:2000]})
    return days
