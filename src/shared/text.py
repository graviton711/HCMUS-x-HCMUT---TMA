"""Shared Vietnamese text folding for accent/case-insensitive matching."""

from __future__ import annotations

import re
import unicodedata


def fold_vi(value: str) -> str:
    """Fold Vietnamese text to plain lowercase ASCII alphanumerics.

    Used for matching place labels and catalog text without guessing
    geographic aliases: đ→d, casefold, strip diacritics, drop everything
    except a-z0-9.
    """
    decomposed = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    plain = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]", "", plain)
