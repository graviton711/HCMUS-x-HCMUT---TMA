"""Golden eval for the extract prompt. REAL NIM calls, skipped without a key.

New cases go here, never into the prompt. Run locally with .env present:
    uv run pytest tests/test_extract_eval.py -q
"""

import os

import pytest

from backend.input.nim import NimClient
from backend.input.pipeline import build_requirement
from backend.settings import Settings

REF_DATE = "2026-10-09"


def _real_key() -> str:
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    try:
        with open(env_path, encoding="utf-8") as handle:
            for line in handle:
                if line.strip().startswith("NVIDIA_NIM_API="):
                    return line.strip().split("=", 1)[1].strip().strip("'\"")
    except OSError:
        pass
    return ""


needs_key = pytest.mark.skipif(not _real_key(), reason="needs NVIDIA_NIM_API in .env")


@pytest.fixture
def live_nim():
    settings = Settings.load()
    return NimClient(_real_key(), settings.nvidia_nim_model,
                     settings.nim_timeout_seconds, prompt=settings.tuning.extract)


def _req(text, live_nim, settings, form=None):
    return build_requirement(text, form, nim=live_nim, cfg=settings.tuning.input,
                             known_places=[], ref_date=REF_DATE)


@needs_key
def test_eval_or_split(live_nim, settings):
    req = _req("Tour Đà Nẵng hoặc Tây Nguyên 4 ngày", live_nim, settings)
    dests = [c for c in req.conditions if c.field == "destination"]
    assert len(dests) == 1 and dests[0].operator == "any"
    assert set(dests[0].value) == {"Đà Nẵng", "Tây Nguyên"}


@needs_key
def test_eval_tet_lunar_resolve(live_nim, settings):
    req = _req("Đi từ 27/12 âm đến mùng 4 Tết", live_nim, settings)
    dates = {c.field: c.value for c in req.conditions}
    assert dates.get("date_from") == "2027-02-03"
    assert dates.get("date_to") == "2027-02-09"


@needs_key
def test_eval_transport_enum(live_nim, settings):
    req = _req("Tour Đà Lạt đi xe ô tô", live_nim, settings)
    transports = [c.value for c in req.conditions if c.field == "transport"]
    assert transports and transports[0] in ("flight", "bus", "train", "cruise", "mixed")


@needs_key
def test_eval_soft_preferences(live_nim, settings):
    req = _req("Tour Phú Quốc, thích biển đẹp, dịch vụ tốt", live_nim, settings)
    assert len(req.soft()) >= 2


@needs_key
def test_eval_budget_trap_no_number(live_nim, settings):
    req = _req("Tour Đà Lạt giá hợp lý", live_nim, settings)
    assert "budget_max" not in {c.field for c in req.conditions}


@needs_key
def test_eval_budget_grounded_number(live_nim, settings):
    req = _req("Tour Đà Lạt tối đa 8 triệu", live_nim, settings)
    assert [c.value for c in req.conditions if c.field == "budget_max"] == [8000000]


@needs_key
def test_eval_departure_city(live_nim, settings):
    req = _req("Tour Hạ Long đi từ Hà Nội", live_nim, settings)
    cities = [c.value for c in req.conditions if c.field == "departure_city"]
    assert cities and "Hà Nội" in cities[0]


@needs_key
def test_eval_undiacritized(live_nim, settings):
    from backend.input.pipeline import _strip_vi

    req = _req("Tour Da Lat 3 ngay", live_nim, settings)
    dests = [c.value for c in req.conditions if c.field == "destination"]
    assert dests
    first = dests[0][0] if isinstance(dests[0], list) else dests[0]
    assert _strip_vi(first) == "da lat"
