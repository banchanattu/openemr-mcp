"""FastMCP-based Streamable HTTP transport for openemr-mcp."""

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from openemr_mcp.server import _TOOLS, _invoke_tool

_log = logging.getLogger("openemr_mcp")


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


def run_streamable_http(host: str, port: int, path: str) -> None:
    mcp = build_http_server(host=host, port=port, path=path)
    _log.info("starting streamable-http server at http://%s:%s%s", host, port, path)
    mcp.run(transport="streamable-http")
