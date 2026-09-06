import anyio
import httpx

from openemr_mcp.config import settings
from openemr_mcp.http_server import build_streamable_http_app


def _request(method: str, path: str):
    app, _ = build_streamable_http_app("127.0.0.1", 8305, "/mcp")

    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path)

    return anyio.run(_run)


def test_well_known_mcp_card_is_public_even_when_request_auth_required(monkeypatch):
    monkeypatch.setattr(settings, "openemr_auth_mode", "request_token")
    monkeypatch.setattr(settings, "openemr_require_request_auth", True)
    monkeypatch.setattr(settings, "openemr_mcp_public_base_url", "https://mcp.example.com")
    monkeypatch.setattr(settings, "openemr_mcp_authorization_server", "https://auth.example.com/oauth2/default")
    monkeypatch.setattr(settings, "openemr_mcp_enable_sse_card_entry", False)

    response = _request("GET", "/.well-known/mcp.json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "openemr-mcp-server"
    assert payload["version"] == "0.1.0"
    assert payload["remotes"] == [{"type": "streamable-http", "url": "https://mcp.example.com/mcp"}]
    assert payload["authentication"]["required"] is True
    assert payload["authentication"]["authorizationServer"] == "https://auth.example.com/oauth2/default"
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_ai_catalog_is_public_and_points_to_server_card(monkeypatch):
    monkeypatch.setattr(settings, "openemr_auth_mode", "request_token")
    monkeypatch.setattr(settings, "openemr_require_request_auth", True)
    monkeypatch.setattr(settings, "openemr_mcp_public_base_url", "https://mcp.example.com")

    response = _request("GET", "/.well-known/ai-catalog.json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/ai-catalog+json")
    payload = response.json()
    assert payload["spec_version"] == "1.0"
    assert payload["entries"][0]["identifier"] == "urn:air:mcp.example.com:mcp:openemr-mcp-server"
    assert payload["entries"][0]["type"] == "application/mcp-server-card+json"
    assert payload["entries"][0]["media_type"] == "application/mcp-server-card+json"
    assert payload["entries"][0]["url"] == "https://mcp.example.com/.well-known/mcp.json"


def test_mcp_catalog_is_public_and_points_to_server_card(monkeypatch):
    monkeypatch.setattr(settings, "openemr_auth_mode", "auto")
    monkeypatch.setattr(settings, "openemr_require_request_auth", False)
    monkeypatch.setattr(settings, "openemr_mcp_public_base_url", "https://mcp.example.com")

    response = _request("GET", "/.well-known/mcp/catalog.json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert payload["specVersion"] == "draft"
    assert payload["entries"][0]["identifier"] == "urn:air:mcp.example.com:mcp:openemr-mcp-server"
    assert payload["entries"][0]["displayName"] == "OpenEMR Healthcare MCP Server"
    assert payload["entries"][0]["mediaType"] == "application/mcp-server-card+json"
    assert payload["entries"][0]["url"] == "https://mcp.example.com/.well-known/mcp.json"


def test_well_known_card_omits_authentication_when_request_auth_not_required(monkeypatch):
    monkeypatch.setattr(settings, "openemr_auth_mode", "auto")
    monkeypatch.setattr(settings, "openemr_require_request_auth", False)
    monkeypatch.setattr(settings, "openemr_mcp_public_base_url", "https://mcp.example.com")
    monkeypatch.setattr(settings, "openemr_mcp_authorization_server", None)
    monkeypatch.setattr(settings, "openemr_mcp_enable_sse_card_entry", False)

    response = _request("GET", "/.well-known/mcp.json")

    assert response.status_code == 200
    payload = response.json()
    assert "authentication" not in payload


def test_legacy_server_card_redirects(monkeypatch):
    monkeypatch.setattr(settings, "openemr_auth_mode", "auto")
    monkeypatch.setattr(settings, "openemr_require_request_auth", False)

    app, _ = build_streamable_http_app("127.0.0.1", 8305, "/mcp")

    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            follow_redirects=False,
        ) as client:
            return await client.get("/.well-known/mcp/server-card.json")

    response = anyio.run(_run)

    assert response.status_code == 301
    assert response.headers["location"] == "/.well-known/mcp.json"
    assert response.headers["access-control-allow-origin"] == "*"


def test_oauth_protected_resource_matches_configured_public_url(monkeypatch):
    monkeypatch.setattr(settings, "openemr_auth_mode", "request_token")
    monkeypatch.setattr(settings, "openemr_require_request_auth", True)
    monkeypatch.setattr(settings, "openemr_mcp_public_base_url", "https://mcp.example.com")
    monkeypatch.setattr(settings, "openemr_mcp_authorization_server", None)
    monkeypatch.setattr(settings, "openemr_oauth_site", "default")

    response = _request("GET", "/.well-known/oauth-protected-resource")

    assert response.status_code == 200
    payload = response.json()
    assert payload["resource"] == "https://mcp.example.com/mcp"
    assert payload["authorization_servers"] == ["https://mcp.example.com/oauth2/default"]
    assert payload["scopes_supported"] == ["openid", "fhirUser", "patient/*.read"]
    assert payload["bearer_methods_supported"] == ["header"]


def test_well_known_options_returns_cors_headers(monkeypatch):
    monkeypatch.setattr(settings, "openemr_auth_mode", "auto")
    monkeypatch.setattr(settings, "openemr_require_request_auth", False)

    response = _request("OPTIONS", "/.well-known/mcp.json")

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["access-control-allow-methods"] == "GET, OPTIONS"
    assert response.headers["access-control-allow-headers"] == "Content-Type, Authorization"


def test_mcp_catalog_options_returns_cors_headers(monkeypatch):
    monkeypatch.setattr(settings, "openemr_auth_mode", "auto")
    monkeypatch.setattr(settings, "openemr_require_request_auth", False)

    response = _request("OPTIONS", "/.well-known/mcp/catalog.json")

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "*"


def test_mcp_endpoint_auth_boundary_is_unchanged(monkeypatch):
    monkeypatch.setattr(settings, "openemr_auth_mode", "request_token")
    monkeypatch.setattr(settings, "openemr_require_request_auth", True)

    response = _request("POST", "/mcp/")

    assert response.status_code == 401
    assert response.json()["error"] == "Missing bearer token"
