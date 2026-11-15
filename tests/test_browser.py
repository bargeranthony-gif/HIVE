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



def test_browser_python_prefers_legacy_environment(monkeypatch, tmp_path):
    import hive.browser as browser

    monkeypatch.delenv("HIVE_BROWSER_PYTHON", raising=False)
    monkeypatch.setattr(browser, "PROJECT_ROOT", tmp_path)

    interpreter = tmp_path / ".venv-browser-legacy" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.touch()

    assert browser.browser_python() == interpreter.absolute()


def test_browser_python_honors_configured_interpreter(
    monkeypatch, tmp_path
):
    import hive.browser as browser

    target = tmp_path / "python-target"
    target.touch()

    configured = tmp_path / "python-link"
    configured.symlink_to(target)

    monkeypatch.setenv("HIVE_BROWSER_PYTHON", str(configured))

    assert browser.browser_python() == configured.absolute()
