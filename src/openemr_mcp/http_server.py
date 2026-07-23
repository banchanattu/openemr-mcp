"""FastMCP-based Streamable HTTP transport for openemr-mcp."""

import logging
from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from openemr_mcp.config import settings
from openemr_mcp.request_auth import (
    RequestAuthContext,
    claims_are_active,
    decode_jwt_claims,
    parse_bearer_token,
    reset_request_auth_context,
    set_request_auth_context,
)
from openemr_mcp.server import _TOOLS, _invoke_tool

_log = logging.getLogger("openemr_mcp")


class RequestAuthMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        auth_header = headers.get("authorization")
        refresh_token = headers.get(settings.openemr_refresh_token_header)
        token = None
        try:
            token = parse_bearer_token(auth_header)
        except ValueError as exc:
            response = JSONResponse({"error": str(exc)}, status_code=401)
            await response(scope, receive, send)
            return

        if not token and _request_auth_required():
            response = JSONResponse({"error": "Missing bearer token"}, status_code=401)
            await response(scope, receive, send)
            return

        claims = decode_jwt_claims(token) if token else None
        if token and settings.openemr_validate_request_token_locally and claims is None:
            response = JSONResponse({"error": "Bearer token is not a valid JWT"}, status_code=401)
            await response(scope, receive, send)
            return
        if claims is not None and not claims_are_active(claims):
            response = JSONResponse({"error": "Bearer token is expired or not yet active"}, status_code=401)
            await response(scope, receive, send)
            return

        context = RequestAuthContext(access_token=token, refresh_token=refresh_token, claims=claims) if token else None
        context_token = set_request_auth_context(context)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_request_auth_context(context_token)


def _request_auth_required() -> bool:
    return settings.openemr_auth_mode == "request_token" or settings.openemr_require_request_auth


def _tool_description(name: str) -> str:
    for tool in _TOOLS:
        if tool.name == name:
            return tool.description
    raise KeyError(f"Unknown tool description for {name!r}")


def build_http_server(host: str, port: int, path: str) -> FastMCP:
    mcp = FastMCP(
        "openemr-mcp",
        instructions="OpenEMR MCP server exposing patient, medication, FDA, and clinical trajectory tools.",
        stateless_http=True,
        json_response=True,
    )
    mcp.settings.host = host
    mcp.settings.port = port
    mcp.settings.streamable_http_path = path

    @mcp.tool(
        name="openemr_patient_search",
        description=_tool_description("openemr_patient_search"),
    )
    def openemr_patient_search(query: str) -> Any:
        return _invoke_tool("openemr_patient_search", {"query": query})

    @mcp.tool(
        name="openemr_appointment_list",
        description=_tool_description("openemr_appointment_list"),
    )
    def openemr_appointment_list(patient_id: str) -> Any:
        return _invoke_tool("openemr_appointment_list", {"patient_id": patient_id})

    @mcp.tool(
        name="openemr_medication_list",
        description=_tool_description("openemr_medication_list"),
    )
    def openemr_medication_list(patient_id: str) -> Any:
        return _invoke_tool("openemr_medication_list", {"patient_id": patient_id})

    @mcp.tool(
        name="openemr_drug_interaction_check",
        description=_tool_description("openemr_drug_interaction_check"),
    )
    def openemr_drug_interaction_check(medications: list[str]) -> Any:
        return _invoke_tool("openemr_drug_interaction_check", {"medications": medications})

    @mcp.tool(
        name="openemr_provider_search",
        description=_tool_description("openemr_provider_search"),
    )
    def openemr_provider_search(
        specialty: str | None = None,
        location: str | None = None,
    ) -> Any:
        return _invoke_tool(
            "openemr_provider_search",
            {"specialty": specialty, "location": location},
        )

    @mcp.tool(
        name="openemr_fda_adverse_events",
        description=_tool_description("openemr_fda_adverse_events"),
    )
    def openemr_fda_adverse_events(drug_name: str, limit: int = 5) -> Any:
        return _invoke_tool(
            "openemr_fda_adverse_events",
            {"drug_name": drug_name, "limit": limit},
        )

    @mcp.tool(
        name="openemr_fda_drug_label",
        description=_tool_description("openemr_fda_drug_label"),
    )
    def openemr_fda_drug_label(drug_name: str) -> Any:
        return _invoke_tool("openemr_fda_drug_label", {"drug_name": drug_name})

    @mcp.tool(
        name="openemr_symptom_lookup",
        description=_tool_description("openemr_symptom_lookup"),
    )
    def openemr_symptom_lookup(symptoms: list[str]) -> Any:
        return _invoke_tool("openemr_symptom_lookup", {"symptoms": symptoms})

    @mcp.tool(
        name="openemr_drug_safety_flag_create",
        description=_tool_description("openemr_drug_safety_flag_create"),
    )
    def openemr_drug_safety_flag_create(
        patient_id: str,
        drug_name: str,
        description: str,
        flag_type: str = "adverse_event",
        severity: str = "MODERATE",
        source: str = "AGENT",
    ) -> Any:
        return _invoke_tool(
            "openemr_drug_safety_flag_create",
            {
                "patient_id": patient_id,
                "drug_name": drug_name,
                "description": description,
                "flag_type": flag_type,
                "severity": severity,
                "source": source,
            },
        )

    @mcp.tool(
        name="openemr_drug_safety_flag_list",
        description=_tool_description("openemr_drug_safety_flag_list"),
    )
    def openemr_drug_safety_flag_list(
        patient_id: str,
        status_filter: str | None = None,
    ) -> Any:
        return _invoke_tool(
            "openemr_drug_safety_flag_list",
            {"patient_id": patient_id, "status_filter": status_filter},
        )

    @mcp.tool(
        name="openemr_drug_safety_flag_update",
        description=_tool_description("openemr_drug_safety_flag_update"),
    )
    def openemr_drug_safety_flag_update(
        flag_id: str,
        severity: str | None = None,
        description: str | None = None,
        status: str | None = None,
    ) -> Any:
        return _invoke_tool(
            "openemr_drug_safety_flag_update",
            {
                "flag_id": flag_id,
                "severity": severity,
                "description": description,
                "status": status,
            },
        )

    @mcp.tool(
        name="openemr_drug_safety_flag_delete",
        description=_tool_description("openemr_drug_safety_flag_delete"),
    )
    def openemr_drug_safety_flag_delete(flag_id: str) -> Any:
        return _invoke_tool("openemr_drug_safety_flag_delete", {"flag_id": flag_id})

    @mcp.tool(
        name="openemr_lab_trends",
        description=_tool_description("openemr_lab_trends"),
    )
    def openemr_lab_trends(
        patient_id: str,
        metrics: list[str] | None = None,
        window_months: int = 24,
    ) -> Any:
        return _invoke_tool(
            "openemr_lab_trends",
            {
                "patient_id": patient_id,
                "metrics": metrics,
                "window_months": window_months,
            },
        )

    @mcp.tool(
        name="openemr_vital_trends",
        description=_tool_description("openemr_vital_trends"),
    )
    def openemr_vital_trends(
        patient_id: str,
        metrics: list[str] | None = None,
        window_months: int = 24,
    ) -> Any:
        return _invoke_tool(
            "openemr_vital_trends",
            {
                "patient_id": patient_id,
                "metrics": metrics,
                "window_months": window_months,
            },
        )

    @mcp.tool(
        name="openemr_questionnaire_trends",
        description=_tool_description("openemr_questionnaire_trends"),
    )
    def openemr_questionnaire_trends(
        patient_id: str,
        instrument: str = "PHQ-9",
        window_months: int = 24,
    ) -> Any:
        return _invoke_tool(
            "openemr_questionnaire_trends",
            {
                "patient_id": patient_id,
                "instrument": instrument,
                "window_months": window_months,
            },
        )

    @mcp.tool(
        name="openemr_health_trajectory",
        description=_tool_description("openemr_health_trajectory"),
    )
    def openemr_health_trajectory(
        patient_id: str,
        window_months: int = 24,
        metrics: list[str] | None = None,
    ) -> Any:
        return _invoke_tool(
            "openemr_health_trajectory",
            {
                "patient_id": patient_id,
                "window_months": window_months,
                "metrics": metrics,
            },
        )

    @mcp.tool(
        name="openemr_visit_prep",
        description=_tool_description("openemr_visit_prep"),
    )
    def openemr_visit_prep(patient_id: str, window_months: int = 24) -> Any:
        return _invoke_tool(
            "openemr_visit_prep",
            {"patient_id": patient_id, "window_months": window_months},
        )

    return mcp


def build_streamable_http_app(host: str, port: int, path: str):
    mcp = build_http_server(host=host, port=port, path=path)
    app = mcp.streamable_http_app()
    app.add_middleware(RequestAuthMiddleware)
    return app, mcp


def run_streamable_http(host: str, port: int, path: str) -> None:
    app, mcp = build_streamable_http_app(host=host, port=port, path=path)
    _log.info("starting streamable-http server at http://%s:%s%s", host, port, path)
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=mcp.settings.log_level.lower(),
    )
