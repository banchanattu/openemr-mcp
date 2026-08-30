"""FastMCP-based Streamable HTTP transport for openemr-mcp."""

import json
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
from openemr_mcp.schemas import AppointmentCreateResult, PatientMatch
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
        request_body, replay_receive = await _capture_request_body(receive)
        _log_mcp_http_request(scope, headers, request_body)
        auth_header = headers.get("authorization")
        refresh_token = headers.get(settings.openemr_refresh_token_header)
        token = None
        try:
            token = parse_bearer_token(auth_header)
        except ValueError as exc:
            response = JSONResponse({"error": str(exc)}, status_code=401)
            await response(scope, replay_receive, send)
            return

        if not token and _request_auth_required():
            response = JSONResponse({"error": "Missing bearer token"}, status_code=401)
            await response(scope, replay_receive, send)
            return

        claims = decode_jwt_claims(token) if token else None
        if token and settings.openemr_validate_request_token_locally and claims is None:
            response = JSONResponse({"error": "Bearer token is not a valid JWT"}, status_code=401)
            await response(scope, replay_receive, send)
            return
        if claims is not None and not claims_are_active(claims):
            response = JSONResponse({"error": "Bearer token is expired or not yet active"}, status_code=401)
            await response(scope, replay_receive, send)
            return

        context = RequestAuthContext(access_token=token, refresh_token=refresh_token, claims=claims) if token else None
        context_token = set_request_auth_context(context)
        try:
            await self.app(scope, replay_receive, send)
        finally:
            reset_request_auth_context(context_token)


async def _capture_request_body(receive: Receive) -> tuple[bytes, Receive]:
    messages: list[dict[str, Any]] = []
    body_parts: list[bytes] = []

    while True:
        message = await receive()
        messages.append(message)
        if message["type"] != "http.request":
            break
        body = message.get("body", b"")
        if body:
            body_parts.append(body)
        if not message.get("more_body", False):
            break

    async def _replay_receive() -> dict[str, Any]:
        if messages:
            return messages.pop(0)
        return {"type": "http.request", "body": b"", "more_body": False}

    return b"".join(body_parts), _replay_receive


def _log_mcp_http_request(scope: Scope, headers: Headers, request_body: bytes) -> None:
    method_name = None
    tool_name = None
    if request_body:
        try:
            payload = json.loads(request_body)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            method_name = payload.get("method")
            params = payload.get("params")
            if isinstance(params, dict):
                tool_name = params.get("name")

    _log.info(
        "mcp_http method=%s path=%s has_auth=%s rpc_method=%s tool=%s",
        scope.get("method"),
        scope.get("path"),
        bool(headers.get("authorization")),
        method_name,
        tool_name,
    )


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
    def openemr_patient_search(query: str) -> list[PatientMatch]:
        return _invoke_tool("openemr_patient_search", {"query": query})

    @mcp.tool(
        name="openemr_patient_create",
        description=_tool_description("openemr_patient_create"),
    )
    def openemr_patient_create(
        first_name: str,
        last_name: str,
        date_of_birth: str,
        birth_sex: str,
    ) -> PatientMatch:
        return _invoke_tool(
            "openemr_patient_create",
            {
                "first_name": first_name,
                "last_name": last_name,
                "date_of_birth": date_of_birth,
                "birth_sex": birth_sex,
            },
        )

    @mcp.tool(
        name="openemr_patient_list",
        description=_tool_description("openemr_patient_list"),
    )
    def openemr_patient_list(limit: int = 50) -> list[PatientMatch]:
        return _invoke_tool("openemr_patient_list", {"limit": limit})

    @mcp.tool(
        name="openemr_appointment_list",
        description=_tool_description("openemr_appointment_list"),
    )
    def openemr_appointment_list(patient_id: str) -> Any:
        return _invoke_tool("openemr_appointment_list", {"patient_id": patient_id})

    @mcp.tool(
        name="openemr_appointment_create",
        description=_tool_description("openemr_appointment_create"),
    )
    def openemr_appointment_create(
        patient_id: str,
        title: str,
        comments: str,
        event_date: str,
        start_time: str,
        category_id: str = "5",
        duration: str = "900",
        appointment_status: str = "^",
        facility_id: str = "9",
        billing_location_id: str = "10",
        provider_id: str | None = None,
    ) -> AppointmentCreateResult:
        return _invoke_tool(
            "openemr_appointment_create",
            {
                "patient_id": patient_id,
                "title": title,
                "comments": comments,
                "event_date": event_date,
                "start_time": start_time,
                "category_id": category_id,
                "duration": duration,
                "appointment_status": appointment_status,
                "facility_id": facility_id,
                "billing_location_id": billing_location_id,
                "provider_id": provider_id,
            },
        )

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
