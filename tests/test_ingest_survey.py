from ingest.survey import _robots_sitemaps


def test_robots_sitemaps_extracts_all_declared():
    text = "\n".join([
        "User-agent: *",
        "Disallow: /admin",
        "Sitemap: https://example.test/sitemap.xml",
        "",
        "Sitemap: https://example.test/du-lich/sitemap_index.xml",
    ])
    assert _robots_sitemaps(text) == [
        "https://example.test/sitemap.xml",
        "https://example.test/du-lich/sitemap_index.xml",
    ]


def test_robots_sitemaps_case_insensitive_and_empty():
    assert _robots_sitemaps("SITEMAP: https://example.test/s.xml") == [
        "https://example.test/s.xml",
    ]
    assert _robots_sitemaps("User-agent: *\nDisallow: /") == []
