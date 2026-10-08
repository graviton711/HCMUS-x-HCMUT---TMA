"""Shared, bounded signals for grounding and omission validation."""

import re
import unicodedata

from requirements.normalize import fold

SIGNALS = {
    "tour_type": r"\bghep doan\b",
    "route": r"\bdi doc\s+(?:mien trung|tay nguyen)\b",
    "supplier_reputation": r"\b(?:uy tin|dang tin cay|danh tieng tot)\b",
    "service_quality": r"\b(?:(?:dv|dich vu)\s+(?:rat\s+)?tot|chat luong dich vu tot)\b",
    "price_value": r"\b(?:gia\s+(?:ca\s+)?(?:hop ly|phai chang)|dang tien)\b",
    "nature": r"\bthien nhien\b",
}


def polarity(text, start):
    prefix = fold(text[:start])
    # Restrict negation to the current clause; another preference must not inherit it.
    clause = re.split(r"[,.;\n]|\b(?:va|nhung)\b", prefix)[-1][-65:]
    if re.search(r"\b(?:khong can|khong quan tam|bo qua)\b[^,.;\n]{0,45}$", clause):
        return "irrelevant"
    if re.search(r"\b(?:khong muon|khong thich|tranh|khong)\b[^,.;\n]{0,45}$", clause):
        return "negative"
    return "positive"


def has_positive(field, text):
    return any(polarity(text, start) == "positive" for start in signal_offsets(field, text))


def signal_offsets(field, text):
    return [start for start, _ in signal_spans(field, text)]


def signal_spans(field, text):
    chars, offsets = [], []
    for index, char in enumerate(text):
        normalized = unicodedata.normalize("NFD", char.lower().replace("đ", "d"))
        for letter in normalized:
            if unicodedata.category(letter) != "Mn":
                chars.append(letter)
                offsets.append(index)
    spans = []
    for match in re.finditer(SIGNALS[field], "".join(chars)):
        end = offsets[match.end() - 1] + 1
        while end < len(text) and unicodedata.category(text[end]) == "Mn":
            end += 1
        spans.append((offsets[match.start()], end))
    return spans


def coverage_manifest(text):
    signals = []
    for field in SIGNALS:
        for start, end in signal_spans(field, text):
            quote = text[start:end]
            if text.count(quote) != 1:
                quote = text
            signals.append({"field": field, "quote": quote, "polarity": polarity(text, start)})
    return signals


def quote_candidates(text):
    candidates = {row["quote"] for row in coverage_manifest(text)}
    start = 0
    for match in re.finditer(r"(?<!\d)[.!?](?!\d)|[,;\n]", text):
        for end in (match.start(), match.end()):
            quote = text[start:end].strip()
            if quote and text.count(quote) == 1:
                candidates.add(quote)
        start = match.end()
    final = text[start:].strip()
    if final and text.count(final) == 1:
        candidates.add(final)
    candidates.add(text)
    return sorted(candidates, key=lambda q: (len(q), q))


def qualitative_polarities(field, message, source):
    """Find signals inside the grounded span but inspect preceding original context."""
    return {polarity(message.text, source.start + start) for start in signal_offsets(field, source.quote)}
