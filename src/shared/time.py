"""One clock for the whole product: Vietnam local time.

Every observed/provenance timestamp the system writes uses Asia/Ho_Chi_Minh
(+07:00), ISO-8601 with offset, so logs, CSVs, detail JSONs and database rows
read the same wall-clock time the tour operators publish in.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def now_vn_iso() -> str:
    """Current Vietnam time, e.g. 2026-10-07T19:30:00+07:00."""
    return datetime.now(VN_TZ).isoformat(timespec="seconds")
