from typing import Literal

from pydantic import Field, model_validator

from domain.common import Identifier, Model

POLICY = "semantic-assessment-v1"


class Citation(Model):
    excerpt_id: Identifier
    quote: str = Field(min_length=1, max_length=1200)


class RawAssessment(Model):
    candidate_id: Identifier
    condition_id: Identifier
    status: Literal["matched", "not_matched", "unknown"]
    citations: list[Citation] = Field(max_length=4)

    @model_validator(mode="after")
    def support(self):
        if self.status != "unknown" and not self.citations:
            raise ValueError("Interpretation requires citations")
        return self


class AssessmentBatch(Model):
    items: list[RawAssessment] = Field(max_length=100)


class Assessment(RawAssessment):
    tour_snapshot_id: Identifier
    evidence_ids: list[Identifier]
    usable_for_ranking: bool
    reason_code: str


class SemanticReport(Model):
    state: Literal["completed", "partial", "skipped"]
    policy_version: str = POLICY
    model: str | None = None
    fingerprint: str
    items: list[Assessment] = Field(default_factory=list, max_length=100)
    requested_pairs: int = 0
    assessed_pairs: int = 0
    limited: bool = False
    reason_code: str | None = None
    repair_used: bool = False
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Diễn giải của model trên nội dung snapshot; không xác minh chất lượng dịch vụ, uy tín hoặc tổng chi phí."
        ]
    )
