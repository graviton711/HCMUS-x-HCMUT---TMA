from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator

from domain.common import Identifier, Model, instant

Level = Annotated[int, Field(ge=1, le=5)]
Kind = Literal["preferences", "template", "saved_tour"]


class Levels(Model):
    cost: Level = 3
    comfort: Level = 3
    pace: Level = 3
    culture: Level = 3


class TravelPreferences(Model):
    hotel_stars: Annotated[int | None, Field(ge=1, le=5)] = None
    duration_days: Annotated[int | None, Field(ge=1, le=90)] = None
    shopping: Literal["any", "few"] = "any"
    prefer_lower_listed_price: bool = False
    levels: Levels = Field(default_factory=Levels)


class TemplateValues(Model):
    departure_origin: Identifier | None = None
    destinations: list[Identifier] = Field(default_factory=list, max_length=10)
    adults: Annotated[int | None, Field(ge=1, le=100)] = None
    child_count: int = Field(default=0, ge=0, le=20)
    preferences: TravelPreferences = Field(default_factory=TravelPreferences)


class TravelTemplate(Model):
    name: str = Field(min_length=1, max_length=80)
    values: TemplateValues


class SavedTour(Model):
    title: str = Field(min_length=1, max_length=500)
    supplier: str | None = Field(default=None, max_length=200)
    url: str = Field(max_length=2048)
    comparison_id: Identifier
    column_id: Identifier
    offer_snapshot_id: Identifier | None = None
    departure_date: str | None = Field(default=None, max_length=100)
    price_label: str | None = Field(default=None, max_length=250)
    evaluated_at: str
    saved_at: str
    status_at_save: Literal["recommended", "needs_verification", "reference"]
    note: str = Field(default="", max_length=1000)
    collection: str = Field(default="", max_length=80)

    @model_validator(mode="after")
    def safe_snapshot(self):
        parts = urlsplit(self.url)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            raise ValueError("Invalid source URL")
        instant(self.evaluated_at)
        instant(self.saved_at)
        return self


PAYLOADS = {"preferences": TravelPreferences, "template": TravelTemplate, "saved_tour": SavedTour}


class Versioned(Model):
    expected_version: int = Field(ge=0)


class PreferencesWrite(Versioned):
    preferences: TravelPreferences


class TemplateWrite(Versioned):
    item_id: Identifier
    template: TravelTemplate


class SaveTour(Versioned):
    comparison_id: Identifier
    column_id: Identifier


class EditTour(Versioned):
    note: str = Field(max_length=1000)
    collection: str = Field(max_length=80)


class DeleteItem(Versioned):
    kind: Kind
    item_id: Identifier
