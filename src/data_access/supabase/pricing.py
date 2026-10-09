"""Explicit catalog price terms, bound to the stored offer rather than inferred."""

from decimal import Decimal

from pydantic import Field, StrictBool, model_validator

from domain.common import Model, instant
from domain.crawl import ExtraCharge, PriceQuote


class CatalogPricing(Model):
    observed_at: str
    quotes: list[PriceQuote] = Field(min_length=1, max_length=3)
    extra_charges: list[ExtraCharge] = Field(max_length=50)
    complete: StrictBool

    @model_validator(mode="before")
    @classmethod
    def no_boolean_amounts(cls, data):
        if isinstance(data, dict):
            for item in [*data.get("quotes", []), *data.get("extra_charges", [])]:
                if isinstance(item, dict) and any(
                    type(item.get(k)) is bool for k in ("amount", "upper_amount")
                ):
                    raise ValueError("Boolean price is invalid")
        return data

    def bound(self, offer, tour):
        observed = offer["observed_at"]
        if instant(self.observed_at) != instant(
            observed.isoformat() if hasattr(observed, "isoformat") else observed
        ):
            raise ValueError("Price metadata observation must match offer")
        prices = offer.get("price_by_age")
        if not isinstance(prices, dict):
            raise ValueError("Price metadata requires stored age prices")
        seen = set()
        for quote in self.quotes:
            label = {"per_adult": "adult", "per_child": "child", "per_infant": "infant"}.get(quote.basis)
            amount = prices.get(label)
            if (
                label is None
                or label in seen
                or type(amount) is bool
                or amount is None
                or Decimal(str(amount)) != Decimal(str(quote.amount))
                or quote.currency != tour.get("currency")
                or quote.kind != tour.get("price_type")
                or quote.coverage == "unspecified"
            ):
                raise ValueError("Price terms contradict stored amount, currency, kind or basis")
            seen.add(label)
        return self
