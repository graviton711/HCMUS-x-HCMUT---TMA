from domain.common import now, uid
from domain.crawl import (
    CrawlRequest,
    CrawlResult,
    Evidence,
    Fact,
    OfferSnapshot,
    PriceQuote,
    SourceCapability,
    SourceResult,
    Supplier,
    TourSnapshot,
)


def fixture_registry() -> list[SourceCapability]:
    return [
        SourceCapability(
            source_id="demo",
            supplier_id="supplier_demo",
            approved_domains=["tour-demo.invalid"],
            access_status="approved",
            checked_at=now().isoformat(),
            modes=["discover", "compare_urls"],
            searchable_fields=["destinations", "supplier"],
            returned_fields=[
                "destinations",
                "departure_origin",
                "duration_days",
                "hotel_stars_min",
                "shopping_stops",
                "departure_date",
                "return_date",
                "estimated_cost",
            ],
            freshness_seconds={
                "departure_date": 86400,
                "return_date": 86400,
                "price": 86400,
                "availability": 86400,
            },
        )
    ]


def fixture_result(request: CrawlRequest) -> CrawlResult:
    timestamp = now().isoformat()
    evidence, tours, offers, results = [], [], [], []
    configs = {
        "tour-a": ("country:jp", 5, 4, 0, 10000000, 7000000),
        "tour-b": ("country:kr", 5, 3, 2, 9000000, None),
        "tour-c": ("country:jp", 6, 5, 0, 12000000, 9000000),
    }
    requested = (
        [(t.target_id, t.url) for t in request.targets]
        if request.mode == "compare_urls"
        else [(None, f"https://tour-demo.invalid/{slug}") for slug in configs]
    )
    for target_id, url in requested:
        slug = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
        if slug not in configs:
            results.append(
                SourceResult(
                    source_id="demo", target_id=target_id, status="error", reason_code="TOUR_NOT_FOUND"
                )
            )
            continue
        country, days, stars, shopping, adult, child = configs[slug]
        tid, oid = uid("tour"), uid("offer")

        def fact(snapshot_id, field, value, quote=None, url=url):
            eid = uid("ev")
            raw = quote or f"[MÔ PHỎNG] {field}: {value}"
            evidence.append(
                Evidence(
                    id=eid,
                    snapshot_id=snapshot_id,
                    url=url,
                    publisher="supplier_demo",
                    method="synthetic_fixture",
                    locator=f"/{field}",
                    raw_quote=raw,
                    observed_at=timestamp,
                )
            )
            return dict(
                value=value,
                raw_value=raw,
                data_state="present",
                verification="unverified",
                completeness="complete",
                observed_at=timestamp,
                evidence_ids=[eid],
            )

        fields = {
            k: fact(tid, k, v)
            for k, v in {
                "destinations": [country],
                "departure_origin": "city:vn:hcmc",
                "duration_days": days,
                "hotel_stars_min": stars,
                "shopping_stops": shopping,
                "transport": ["flight"],
                "flight_stops": 0,
                "included_services": ["airfare", "visa"],
                "supplier": "supplier_demo",
            }.items()
        }
        tours.append(
            TourSnapshot(
                snapshot_id=tid,
                tour_id=slug,
                supplier_id="supplier_demo",
                canonical_url=url,
                observed_at=timestamp,
                fields=fields,
            )
        )
        prices = []
        for basis, amount in (("per_adult", adult), ("per_child", child)):
            if amount is None:
                continue
            q = PriceQuote(
                quote_id=uid("quote"),
                kind="exact",
                amount=amount,
                currency="VND",
                basis=basis,
                coverage="tour_price",
                age_min=0 if basis == "per_child" else None,
                age_max_exclusive=18 if basis == "per_child" else None,
            )
            prices.append(fact(oid, f"price_quotes/{basis}", q))
        offer_fields = {
            k: fact(oid, k, v)
            for k, v in {
                "departure_date": "2026-11-10",
                "return_date": f"2026-11-{9 + days:02d}",
                "availability": 15,
            }.items()
        }
        offers.append(
            OfferSnapshot(
                snapshot_id=oid,
                offer_id=f"{slug}-nov10",
                tour_snapshot_id=tid,
                fields=offer_fields,
                price_quotes=prices,
                pricing_complete=Fact[bool](
                    **fact(
                        oid,
                        "pricing_complete",
                        True,
                        "[MÔ PHỎNG] Các giá niêm yết không có phụ thu bắt buộc hoặc giảm giá khác, áp dụng mọi cấu hình phòng.",
                    )
                ),
            )
        )
        results.append(
            SourceResult(
                source_id="demo",
                target_id=target_id,
                status="ok",
                tour_snapshot_ids=[tid],
                offer_snapshot_ids=[oid],
            )
        )
    return CrawlResult(
        request_id=request.request_id,
        origin="synthetic",
        source_results=results,
        suppliers=[Supplier(supplier_id="supplier_demo", display_name="Nhà cung cấp mô phỏng")],
        tours=tours,
        offers=offers,
        evidence=evidence,
    )
