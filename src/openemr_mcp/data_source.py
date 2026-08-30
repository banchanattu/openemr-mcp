"""Simplified data source resolver for the standalone MCP server."""

import logging
import os

from openemr_mcp.repositories._errors import ToolError

logger = logging.getLogger(__name__)

SUPPORTED_DATA_SOURCES = {"mock", "api"}


def get_effective_data_source() -> str:
    """Return the active data source: 'mock' | 'api'."""
    source = os.environ.get("OPENEMR_DATA_SOURCE", "mock").strip().lower()
    if source not in SUPPORTED_DATA_SOURCES:
        raise ToolError(
            f"Unsupported OPENEMR_DATA_SOURCE '{source}'. Supported values are: api, mock."
        )
    return source


def get_http_client():
    """Return an OpenEMR FHIR HTTP client configured from env vars."""
    from openemr_mcp.auth import OAuth2TokenManager
    from openemr_mcp.config import settings
    from openemr_mcp.request_auth import get_request_auth_context

    def _safe_http_error_detail(response) -> str:
        details: list[str] = []
        auth_header = response.headers.get("www-authenticate")
        if auth_header:
            details.append(f" WWW-Authenticate: {auth_header[:200]}")
        body = (response.text or "").strip()
        if body:
            details.append(f" Response body: {body[:200]}")
        return "".join(details)

    def _auth_mode_hint(status_code: int) -> str:
        if status_code != 401:
            return ""
        request_context = get_request_auth_context()
        if request_context and request_context.access_token:
            return " Request bearer token was forwarded to OpenEMR and rejected."
        if settings.openemr_auth_mode == "request_token" or settings.openemr_require_request_auth:
            return " Request bearer token was required but not available to the outbound OpenEMR client."
        return (
            " No inbound bearer token was available, so request-token forwarding was not used."
            " The server fell back to configured OpenEMR OAuth credentials."
            " If this deployment should forward caller tokens, set OPENEMR_AUTH_MODE=request_token"
            " or OPENEMR_REQUIRE_REQUEST_AUTH=true and send Authorization: Bearer on the MCP request."
        )

    class _OpenEMRClient:
        """Minimal FHIR + REST client for OpenEMR, matching the interface used by repositories."""

        def __init__(self):
            self._token_manager = OAuth2TokenManager(settings)

        def _get_headers(self) -> dict:
            token = self._token_manager.get_valid_access_token()
            if settings.openemr_log_outbound_bearer_token:
                logger.warning("#### OPENEMR OUTBOUND BEARER TOKEN START ####")
                logger.warning("%s", token)
                logger.warning("#### OPENEMR OUTBOUND BEARER TOKEN END ####")
            return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        def get_fhir(self, resource_path: str, params: dict | None = None) -> dict:
            """GET /apis/default/fhir/{resource_path}"""
            base = settings.openemr_api_base_url.rstrip("/")
            url = f"{base}/fhir/{resource_path}"
            return self.get_fhir_url(url, params=params)

        def post_fhir(self, resource_path: str, json_body: dict) -> dict:
            """POST /apis/default/fhir/{resource_path}"""
            import httpx

            base = settings.openemr_api_base_url.rstrip("/")
            url = f"{base}/fhir/{resource_path}"
            headers = self._get_headers()
            headers["Content-Type"] = "application/fhir+json"
            try:
                r = httpx.post(url, json=json_body, headers=headers, timeout=15.0)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as exc:
                from openemr_mcp.repositories._errors import ToolError

                hint = _auth_mode_hint(exc.response.status_code)
                detail = _safe_http_error_detail(exc.response)
                raise ToolError(f"FHIR API error: {exc.response.status_code}{hint}{detail}") from exc
            except Exception as exc:
                from openemr_mcp.repositories._errors import ToolError

                raise ToolError(f"FHIR API unreachable: {exc}") from exc

        def get_fhir_url(self, url: str, params: dict | None = None) -> dict:
            """GET an absolute FHIR pagination URL returned by Bundle.link."""
            import httpx

            headers = self._get_headers()
            try:
                r = httpx.get(url, params=params, headers=headers, timeout=15.0)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    return {}
                from openemr_mcp.repositories._errors import ToolError

                hint = _auth_mode_hint(exc.response.status_code)
                detail = _safe_http_error_detail(exc.response)
                raise ToolError(f"FHIR API error: {exc.response.status_code}{hint}{detail}") from exc
            except Exception as exc:
                from openemr_mcp.repositories._errors import ToolError

                raise ToolError(f"FHIR API unreachable: {exc}") from exc

        def get_rest(self, path: str, params: dict | None = None) -> dict:
            """GET /apis/default/api/{path}"""
            import httpx

            base = settings.openemr_api_base_url.rstrip("/")
            resource_path = path.lstrip("/")
            if not resource_path.startswith("api/"):
                resource_path = f"api/{resource_path}"
            url = f"{base}/{resource_path}"
            headers = self._get_headers()
            try:
                r = httpx.get(url, params=params, headers=headers, timeout=15.0)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as exc:
                from openemr_mcp.repositories._errors import ToolError

                hint = _auth_mode_hint(exc.response.status_code)
                detail = _safe_http_error_detail(exc.response)
                raise ToolError(f"REST API error: HTTP {exc.response.status_code}{hint}{detail}") from exc
            except Exception as exc:
                from openemr_mcp.repositories._errors import ToolError

                raise ToolError(f"REST API error: {exc}") from exc

        def post_rest(self, path: str, json_body: dict) -> dict:
            """POST /apis/default/api/{path}"""
            import httpx

            base = settings.openemr_api_base_url.rstrip("/")
            resource_path = path.lstrip("/")
            if not resource_path.startswith("api/"):
                resource_path = f"api/{resource_path}"
            url = f"{base}/{resource_path}"
            headers = self._get_headers()
            headers["Content-Type"] = "application/json"
            try:
                r = httpx.post(url, json=json_body, headers=headers, timeout=15.0)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as exc:
                from openemr_mcp.repositories._errors import ToolError

                hint = _auth_mode_hint(exc.response.status_code)
                detail = _safe_http_error_detail(exc.response)
                raise ToolError(f"REST API error: HTTP {exc.response.status_code}{hint}{detail}") from exc
            except Exception as exc:
                from openemr_mcp.repositories._errors import ToolError

                raise ToolError(f"REST API error: {exc}") from exc

    return _OpenEMRClient()
