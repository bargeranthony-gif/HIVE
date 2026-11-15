import pytest

from hive.browser import validate_url


def test_validate_http_and_https_urls():
    assert validate_url("https://example.com") == "https://example.com"
    assert validate_url("http://localhost:8000/test") == (
        "http://localhost:8000/test"
    )


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com",
        "javascript:alert(1)",
        "https://",
        "https://user:password@example.com",
    ],
)
def test_reject_unsupported_or_unsafe_urls(url):
    with pytest.raises(ValueError):
        validate_url(url)


def test_validate_url_trims_whitespace():
    assert validate_url("  https://example.com  ") == "https://example.com"
