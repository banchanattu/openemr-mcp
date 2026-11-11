"""ARD discovery helpers for openemr-mcp."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from openemr_mcp.config import settings

SERVER_CARD_SCHEMA_URL = "https://static.modelcontextprotocol.io/schemas/2025-10-17/server.schema.json"
AI_CATALOG_CONTENT_TYPE = "application/ai-catalog+json"
MCP_SERVER_CARD_CONTENT_TYPE = "application/mcp-server-card+json"
WELL_KNOWN_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Cache-Control": "public, max-age=3600",
    "X-Content-Type-Options": "nosniff",
}


def request_auth_is_required() -> bool:
    return settings.openemr_auth_mode == "request_token" or settings.openemr_require_request_auth


def parse_auth_scopes() -> list[str]:
    return [scope.strip() for scope in settings.openemr_mcp_auth_scopes.split(",") if scope.strip()]


def build_public_base_url(request: Request) -> str:
    configured = settings.openemr_mcp_public_base_url
    if configured:
        return configured.rstrip("/")

    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_host:
        scheme = forwarded_proto or request.url.scheme
        return f"{scheme}://{forwarded_host}".rstrip("/")

    return str(request.base_url).rstrip("/")


def join_public_url(base_url: str, path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{base_url.rstrip('/')}{normalized_path}"


def normalize_external_url(url: str) -> str:
    parts = urlsplit(url)
    normalized_path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme, parts.netloc, normalized_path, parts.query, parts.fragment))


def build_authorization_server(request: Request, base_url: str) -> str | None:
    if settings.openemr_mcp_authorization_server:
        return normalize_external_url(settings.openemr_mcp_authorization_server)

    if not request_auth_is_required():
        return None

    site = (settings.openemr_oauth_site or "default").strip("/") or "default"
    return f"{base_url}/oauth2/{site}"


def build_authentication_metadata(request: Request, base_url: str) -> dict[str, Any] | None:
    if not request_auth_is_required():
        return None

    authorization_server = build_authorization_server(request, base_url)
    authentication: dict[str, Any] = {
        "required": True,
        "type": "oauth2",
        "scopes": parse_auth_scopes(),
    }
    if authorization_server:
        authentication["authorizationServer"] = authorization_server
    return authentication


def build_mcp_server_card(request: Request, mcp_path: str, version: str) -> dict[str, Any]:
    base_url = build_public_base_url(request)
    remotes = [
        {
            "type": "streamable-http",
            "url": join_public_url(base_url, mcp_path),
        }
    ]
    if settings.openemr_mcp_enable_sse_card_entry:
        remotes.append(
            {
                "type": "sse",
                "url": join_public_url(base_url, f"{mcp_path.rstrip('/')}/sse"),
            }
        )

    card: dict[str, Any] = {
        "$schema": SERVER_CARD_SCHEMA_URL,
        "name": settings.openemr_mcp_server_name,
        "title": settings.openemr_mcp_server_title,
        "version": version,
        "description": settings.openemr_mcp_server_description,
        "vendor": {
            "name": settings.openemr_mcp_vendor_name,
            "url": settings.openemr_mcp_vendor_url or base_url,
        },
        "remotes": remotes,
        "capabilities": {
            "tools": {"listChanged": True},
            "resources": {"subscribe": False, "listChanged": True},
            "prompts": {"listChanged": False},
        },
    }
    if settings.openemr_mcp_server_icon_url:
        card["icon"] = settings.openemr_mcp_server_icon_url

    authentication = build_authentication_metadata(request, base_url)
    if authentication is not None:
        card["authentication"] = authentication

    return card


def build_server_card_url(request: Request) -> str:
    return join_public_url(build_public_base_url(request), "/.well-known/mcp.json")


def build_catalog_identifier(request: Request) -> str:
    publisher = urlsplit(build_public_base_url(request)).netloc.lower() or "localhost"
    server_name = settings.openemr_mcp_server_name.strip().replace("/", "-") or "openemr-mcp-server"
    return f"urn:air:{publisher}:mcp:{server_name}"


def build_ai_catalog(request: Request) -> dict[str, Any]:
    entry = {
        "identifier": build_catalog_identifier(request),
        "display_name": settings.openemr_mcp_server_title,
        "type": MCP_SERVER_CARD_CONTENT_TYPE,
        "media_type": MCP_SERVER_CARD_CONTENT_TYPE,
        "url": build_server_card_url(request),
        "description": settings.openemr_mcp_server_description,
    }
    return {
        "spec_version": "1.0",
        "entries": [entry],
    }


def build_mcp_catalog(request: Request) -> dict[str, Any]:
    entry = {
        "identifier": build_catalog_identifier(request),
        "displayName": settings.openemr_mcp_server_title,
        "type": MCP_SERVER_CARD_CONTENT_TYPE,
        "mediaType": MCP_SERVER_CARD_CONTENT_TYPE,
        "url": build_server_card_url(request),
        "description": settings.openemr_mcp_server_description,
    }
    return {
        "specVersion": "draft",
        "entries": [entry],
    }


def build_oauth_protected_resource(request: Request, mcp_path: str) -> dict[str, Any]:
    base_url = build_public_base_url(request)
    authorization_server = build_authorization_server(request, base_url)
    authorization_servers = [authorization_server] if authorization_server else []
    scopes = parse_auth_scopes() if request_auth_is_required() else []
    return {
        "resource": join_public_url(base_url, mcp_path),
        "authorization_servers": authorization_servers,
        "scopes_supported": scopes,
        "bearer_methods_supported": ["header"],
    }


def well_known_json_response(payload: dict[str, Any], media_type: str = "application/json") -> JSONResponse:
    return JSONResponse(payload, headers=WELL_KNOWN_HEADERS, media_type=media_type)


def well_known_options_response() -> Response:
    return Response(status_code=204, headers=WELL_KNOWN_HEADERS)
