"""Grounded non-condition slots for the v2 proposal parser."""

import re
from typing import Literal

from pydantic import Field, model_validator

from domain.common import AppError, Model
from requirements.extraction import InitialExtraction, UpdateExtraction
from requirements.normalize import fold, ground

V2_PROMPT = """
V2 mở rộng schema v1. Ưu tiên đọc các control được hỗ trợ; đừng bỏ slider hoặc tạo unsupported cho chúng.
'ưu tiên tiết kiệm mức 4' phải tạo preference_updates [{dimension:cost,level:4,quote:'ưu tiên tiết kiệm mức 4'}].
cost=tiết kiệm/chi phí, comfort=thoải mái, pace=nhịp đi, culture=văn hóa; level chỉ 0..5 user nêu rõ.
Không tự suy level nếu user chỉ nói 'thích thoải mái'. Không đổi condition budget thành slider.
reference_urls_update/notes_update chỉ khi user yêu cầu rõ ràng; mọi nội dung mới có quote duy nhất từ message.
Ví dụ INITIAL 'Đi Nhật. Ưu tiên tiết kiệm mức 4.':
{"conditions":[{"id":"dest","field":"destinations","operator":"contains","strength":"hard","raw_values":["Nhật"],"quote":"Đi Nhật"}],"hard_tree":null,"preference_tree":null,"party":null,"operations":[],"preference_updates":[{"dimension":"cost","level":4,"quote":"Ưu tiên tiết kiệm mức 4"}],"reference_urls_update":null,"notes_update":null}
Ví dụ UPDATE 'Thời lượng thành 6 ngày và ưu tiên tiết kiệm lên mức 4':
conditions rỗng; operations replace đúng duration ID trong previous; preference_updates chứa cost level4 với quote 'ưu tiên tiết kiệm lên mức 4'.
Các slots cũng được dùng trong lượt UPDATE, dù câu chỉ nói 'chỉ operations/party' ở quy tắc v1.
"""


class RawPreference(Model):
    dimension: Literal["cost", "comfort", "pace", "culture"]
    level: int = Field(ge=0, le=5)
    quote: str = Field(min_length=1, max_length=8000)


class RawURLs(Model):
    urls: list[str] = Field(max_length=5)
    quote: str = Field(min_length=1, max_length=8000)


class RawNotes(Model):
    text: str = Field(max_length=8000)
    quote: str = Field(min_length=1, max_length=8000)


class ExtraSlots(Model):
    preference_updates: list[RawPreference] = Field(default_factory=list, max_length=4)
    reference_urls_update: RawURLs | None = None
    notes_update: RawNotes | None = None

    @model_validator(mode="after")
    def no_duplicate_dimensions(self):
        if len({x.dimension for x in self.preference_updates}) != len(self.preference_updates):
            raise ValueError("Duplicate preference update")
        return self


class InitialExtractionV2(InitialExtraction, ExtraSlots):
    preference_updates: list[RawPreference] = Field(max_length=4)
    reference_urls_update: RawURLs | None
    notes_update: RawNotes | None


class UpdateExtractionV2(UpdateExtraction, ExtraSlots):
    preference_updates: list[RawPreference] = Field(max_length=4)
    reference_urls_update: RawURLs | None
    notes_update: RawNotes | None


class SlotExtractor:
    def __init__(self, nim):
        self.nim = nim
        self.slots = ExtraSlots()
        self.sources = {}

    async def extract(self, message, previous=None, *, feedback=None):
        method = getattr(self.nim, "extract_v2", self.nim.extract)
        extraction, metrics = await method(message, previous, feedback=feedback)
        self.slots = ExtraSlots.model_validate(
            {k: getattr(extraction, k) for k in ExtraSlots.model_fields if hasattr(extraction, k)}
        )
        # Completeness guard for explicit UI control grammar; never infer a condition here.
        dimensions = {
            "tiet kiem": "cost",
            "chi phi": "cost",
            "thoai mai": "comfort",
            "nhip di": "pace",
            "van hoa": "culture",
        }
        supplied = {p.dimension: p.level for p in self.slots.preference_updates}
        text = fold(message.text)
        for clause in re.split(r"[.;\n]", text):
            if re.search(r"\b(khong|giu nguyen|truoc|cu)\b", clause):
                continue
            matches = list(
                re.finditer(
                    r"(tiet kiem|chi phi|thoai mai|nhip di|van hoa)\s*(?:len\s*)?muc\s*([0-5])\b", clause
                )
            )
            if len({m.group(1) for m in matches}) != len(matches):
                continue
            for match in matches:
                dimension, level = dimensions[match.group(1)], int(match.group(2))
                if supplied.get(dimension) != level:
                    error = AppError("LLM_INVALID_OUTPUT", "Thiếu preference slot user nêu tường minh.", 502)
                    error.repair_hint = f"Bắt buộc giữ preference_updates dimension={dimension}, level={level}, quote nguyên văn duy nhất; không tạo unsupported hoặc bỏ slot."
                    raise error
        self.sources = {}
        for pref in self.slots.preference_updates:
            self.sources[f"preference_levels.{pref.dimension}"] = ground(message, pref.quote).model_dump(
                mode="json"
            )
        urls = self.slots.reference_urls_update
        if urls:
            if any(u not in urls.quote for u in urls.urls):
                raise AppError("LLM_INVALID_OUTPUT", "URL phải có trong quote gốc.", 502)
            self.sources["reference_urls"] = ground(message, urls.quote).model_dump(mode="json")
        notes = self.slots.notes_update
        if notes:
            if notes.text and notes.text not in notes.quote:
                raise AppError("LLM_INVALID_OUTPUT", "Notes phải có trong quote gốc.", 502)
            self.sources["notes"] = ground(message, notes.quote).model_dump(mode="json")
        return extraction, metrics
