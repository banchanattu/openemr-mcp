from openemr_mcp.config import normalize_api_base_url


def test_normalize_api_base_url_adds_http_for_host_style_values():
    assert normalize_api_base_url("localhost:8300/apis/default") == "http://localhost:8300/apis/default"


def test_normalize_api_base_url_preserves_explicit_scheme():
    assert normalize_api_base_url("https://openemr.example.com/apis/default") == (
        "https://openemr.example.com/apis/default"
    )


def test_normalize_api_base_url_handles_missing_value():
    assert normalize_api_base_url(None) is None
