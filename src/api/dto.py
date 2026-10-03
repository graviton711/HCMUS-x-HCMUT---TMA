from typing import Literal

from pydantic import Field, JsonValue, model_validator

from domain.common import Identifier, Model
from domain.requirements import Party, Target, Tree, Value


class FormCondition(Model):
    id: Identifier
    field: str
    operator: str
    value: Value
    strength: Literal["hard", "soft", "unresolved"] = "hard"


class Form(Model):
    conditions: list[FormCondition] = Field(default_factory=list, max_length=50)
    party: Party = Field(default_factory=Party)
    hard_tree: Tree | None = None
    preference_tree: Tree | None = None


class CreateRequirement(Model):
    mode: Literal["discover", "compare_urls"]
    text: str | None = Field(default=None, min_length=1, max_length=8000)
    form: Form | None = None
    urls: list[str] = Field(default_factory=list, max_length=5)
    timezone: str = "Asia/Ho_Chi_Minh"

    @model_validator(mode="after")
    def inputs(self):
        if self.text is not None and self.form is not None:
            raise ValueError("Choose text or form")
        if self.mode == "discover" and (self.urls or (not self.text and self.form is None)):
            raise ValueError("Discover needs text/form and no URL targets")
        if self.mode == "compare_urls" and not 2 <= len(self.urls) <= 5:
            raise ValueError("Compare needs 2..5 URLs")
        if len(set(self.urls)) != len(self.urls):
            raise ValueError("Duplicate URLs")
        for url in self.urls:
            Target(target_id="check", url=url)
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown timezone") from exc
        return self


class Edit(Model):
    op: Literal["add", "replace", "remove", "reorder"]
    target: str = Field(min_length=1, max_length=200)
    value: JsonValue = None


class Answer(Model):
    clarification_id: Identifier
    value: JsonValue


class PatchRequirement(Model):
    expected_revision: int = Field(ge=1)
    text: str | None = Field(default=None, min_length=1, max_length=8000)
    edits: list[Edit] | None = Field(default=None, min_length=1, max_length=30)
    answers: list[Answer] | None = Field(default=None, min_length=1, max_length=30)

    @model_validator(mode="after")
    def one_input(self):
        if sum(x is not None for x in (self.text, self.edits, self.answers)) != 1:
            raise ValueError("Choose exactly one of text/edits/answers")
        return self


class OfferSelection(Model):
    target_id: Identifier
    offer_snapshot_id: Identifier


class CreateComparison(Model):
    requirement_id: Identifier
    revision: int = Field(ge=1)
    offer_selections: list[OfferSelection] = Field(default_factory=list, max_length=5)
    reuse_comparison_id: Identifier | None = None

    @model_validator(mode="after")
    def selections(self):
        if self.offer_selections and not self.reuse_comparison_id:
            raise ValueError("Select offers from a previous comparison")
        return self
