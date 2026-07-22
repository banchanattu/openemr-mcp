import base64
import json
import time
import types

import anyio
import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from openemr_mcp.auth import OAuth2TokenManager, OpenEMROAuthError
from openemr_mcp.config import settings
from openemr_mcp.http_server import RequestAuthMiddleware
from openemr_mcp.repositories._errors import ToolError
from openemr_mcp.request_auth import (
    RequestAuthContext,
    get_request_auth_context,
    reset_request_auth_context,
    set_request_auth_context,
)


def _jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.signature"


@pytest.fixture
def auth_settings(monkeypatch):
    monkeypatch.setattr(settings, "openemr_auth_mode", "auto")
    monkeypatch.setattr(settings, "openemr_require_request_auth", False)
    monkeypatch.setattr(settings, "openemr_refresh_token_header", "X-Refresh-Token")
    monkeypatch.setattr(settings, "openemr_enable_request_token_refresh", False)
    monkeypatch.setattr(settings, "openemr_validate_request_token_locally", False)


def _build_test_app():
    async def endpoint(request):
        context = get_request_auth_context()
        return JSONResponse(
            {
                "authenticated": bool(context and context.access_token),
                "user_id": context.user_id if context else None,
            }
        )

    app = Starlette(routes=[Route("/mcp", endpoint, methods=["POST"])])
    app.add_middleware(RequestAuthMiddleware)
    return app


def _request(app, headers=None):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/mcp", json={}, headers=headers)

    return anyio.run(_run)


def test_http_middleware_rejects_missing_bearer_when_required(auth_settings, monkeypatch):
    monkeypatch.setattr(settings, "openemr_auth_mode", "request_token")
    monkeypatch.setattr(settings, "openemr_require_request_auth", True)
    app = _build_test_app()

    response = _request(app)

    assert response.status_code == 401
    assert response.json()["error"] == "Missing bearer token"


def test_http_middleware_accepts_bearer_when_required(auth_settings, monkeypatch):
    monkeypatch.setattr(settings, "openemr_auth_mode", "request_token")
    monkeypatch.setattr(settings, "openemr_require_request_auth", True)
    app = _build_test_app()

    response = _request(app, headers={"Authorization": "Bearer trusted-token"})

    assert response.status_code == 200
    assert response.json()["authenticated"] is True


def test_http_middleware_rejects_non_bearer_authorization(auth_settings, monkeypatch):
    monkeypatch.setattr(settings, "openemr_require_request_auth", True)
    app = _build_test_app()

    response = _request(app, headers={"Authorization": "Basic abc"})

    assert response.status_code == 401
    assert "Bearer token" in response.json()["error"]


def test_http_middleware_decodes_local_jwt_claims(auth_settings, monkeypatch):
    monkeypatch.setattr(settings, "openemr_require_request_auth", True)
    monkeypatch.setattr(settings, "openemr_validate_request_token_locally", True)
    app = _build_test_app()
    token = _jwt({"sub": "user-123", "preferred_username": "alice"})

    response = _request(app, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["user_id"] == "alice"


def test_http_middleware_rejects_expired_local_jwt(auth_settings, monkeypatch):
    monkeypatch.setattr(settings, "openemr_require_request_auth", True)
    monkeypatch.setattr(settings, "openemr_validate_request_token_locally", True)
    app = _build_test_app()
    token = _jwt({"sub": "user-123", "exp": time.time() - 60})

    response = _request(app, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert "expired" in response.json()["error"]


def test_request_token_is_forwarded_to_openemr_headers(auth_settings):
    context_token = set_request_auth_context(RequestAuthContext(access_token="trusted-openemr-token"))
    try:
        headers = __import__("openemr_mcp.data_source", fromlist=["get_http_client"]).get_http_client()._get_headers()
    finally:
        reset_request_auth_context(context_token)

    assert headers["Authorization"] == "Bearer trusted-openemr-token"
    assert headers["Accept"] == "application/json"


def test_request_token_mode_fails_closed_without_context(auth_settings, monkeypatch):
    monkeypatch.setattr(settings, "openemr_auth_mode", "request_token")
    monkeypatch.setattr(settings, "openemr_require_request_auth", True)

    with pytest.raises(OpenEMROAuthError, match="Request access token required"):
        OAuth2TokenManager(settings).get_valid_access_token()


def test_fhir_401_reports_fallback_oauth_when_request_token_missing(auth_settings, monkeypatch):
    from openemr_mcp.data_source import get_http_client

    monkeypatch.setattr(settings, "openemr_auth_mode", "auto")
    monkeypatch.setattr(settings, "openemr_require_request_auth", False)

    def fake_get_valid_access_token(self, force_refresh=False):
        return "server-owned-token"

    def fake_http_get(url, params=None, headers=None, timeout=None):
        request = httpx.Request("GET", url, params=params, headers=headers)
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError("401", request=request, response=response)

    monkeypatch.setattr(OAuth2TokenManager, "get_valid_access_token", fake_get_valid_access_token)
    monkeypatch.setattr(httpx, "get", fake_http_get)

    with pytest.raises(ToolError, match="No inbound bearer token was available"):
        get_http_client().get_fhir("Practitioner")


def test_fhir_401_reports_forwarded_request_token(auth_settings, monkeypatch):
    from openemr_mcp.data_source import get_http_client

    monkeypatch.setattr(settings, "openemr_auth_mode", "auto")
    monkeypatch.setattr(settings, "openemr_require_request_auth", False)

    captured = types.SimpleNamespace(headers=None)

    def fake_http_get(url, params=None, headers=None, timeout=None):
        captured.headers = headers
        request = httpx.Request("GET", url, params=params, headers=headers)
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError("401", request=request, response=response)

    monkeypatch.setattr(httpx, "get", fake_http_get)

    context_token = set_request_auth_context(RequestAuthContext(access_token="trusted-openemr-token"))
    try:
        with pytest.raises(ToolError, match="Request bearer token was forwarded to OpenEMR and rejected"):
            get_http_client().get_fhir("Practitioner")
    finally:
        reset_request_auth_context(context_token)

    assert captured.headers["Authorization"] == "Bearer trusted-openemr-token"
