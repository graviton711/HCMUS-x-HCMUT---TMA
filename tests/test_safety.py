import pytest

from crawler.safety import UnsafeURLError, normalized_origin, validate_public_url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://127.0.0.1/admin",
        "http://10.0.0.5/",
        "http://169.254.169.254/latest/meta-data/",
        "http://localhost/",
        "https://user:pass@example.com/",
    ],
)
def test_blocks_unsafe_seed_urls(url):
    with pytest.raises(UnsafeURLError):
        validate_public_url(url)


def test_public_ip_is_accepted_and_url_fragment_is_removed():
    assert validate_public_url("https://8.8.8.8/docs#section") == "https://8.8.8.8/docs"


def test_cross_origin_links_are_rejected():
    origin = normalized_origin("https://example.com/")
    with pytest.raises(UnsafeURLError, match="Cross-origin"):
        validate_public_url("https://other.example.com/", origin)


def test_url_with_invalid_port_is_rejected():
    with pytest.raises(UnsafeURLError, match="invalid port"):
        normalized_origin("https://example.com:99999/")
