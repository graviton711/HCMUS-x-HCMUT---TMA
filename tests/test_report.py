from crawler.models import CrawlReport, Evidence, ObservedField, TourSample, TourSchemaField


def test_json_report_contains_readable_labels_and_only_report_sections():
    report = CrawlReport(
        source_url="https://example.test/tours",
        status="partial",
        pages_scanned=12,
        requests_made=20,
        supplier={
            "display_name": ObservedField(value="Example Tours", status="found"),
            "license_claims": ObservedField(value="Provider claim"),
        },
        tour_schema=[
            TourSchemaField("tour_code", "string", "found"),
            TourSchemaField("title", "string", "found"),
        ],
        sample_tour=TourSample(
            "https://example.test/tour/one",
            {
                "tour_code": ObservedField(
                    value="123",
                    status="found",
                    evidence=[
                        Evidence(
                            "https://example.test/tour/one",
                            "json_ld",
                            '"identifier":"123"',
                            "json_ld[0]/@graph/1/identifier",
                        )
                    ],
                ),
                "title": ObservedField(value="Tour One", status="found"),
            },
        ),
    )

    data = report.to_dict()

    assert data["supplier"]["display_name"]["label"] == "Tên hiển thị"
    assert data["tour_schema"][0]["name"] == "tour_code"
    assert data["tour_schema"][0]["label"] == "Mã tour"
    assert data["sample_tour"]["fields"]["tour_code"]["label"] == "Mã tour"
    assert data["sample_tour"]["fields"]["tour_code"]["value"] == "123"
    assert data["sample_tour"]["fields"]["tour_code"]["evidence"][0]["json_path"] == (
        "json_ld[0]/@graph/1/identifier"
    )
    assert data["schema_version"] == "1.2"
    assert "pages" not in data
    assert "requests_made" not in data
    assert "license_claims" in data["supplier"]
