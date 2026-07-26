"""
OpenEMR MCP Server — Model Context Protocol server for OpenEMR.

Registers 19 tools: patient search/list/create, appointments, medications, drug interactions,
provider search, FDA adverse events, FDA drug labels, symptom lookup, drug safety
flag CRUD, lab trends, vital trends, questionnaire trends, health trajectory,
and visit prep.

Run via:
    openemr-mcp                                             # stdio transport (default)
    OPENEMR_DATA_SOURCE=mock openemr-mcp
    openemr-mcp --transport streamable-http --port 8305     # network server
"""

import argparse
import asyncio
import json
import logging
import os
import time
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from openemr_mcp import config as _config  # Load .env defaults before parsing transport options.

_ = _config
_log = logging.getLogger("openemr_mcp")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

server = Server("openemr-mcp")


# ---------------------------------------------------------------------------
# Tool schemas (JSON Schema for each tool's inputSchema)
# ---------------------------------------------------------------------------

_TOOLS = [
    types.Tool(
        name="openemr_patient_search",
        description="Search OpenEMR patients by name or partial name. Requires a non-empty query. Do not use this tool to list all patients.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Patient name or partial name to search for"},
            },
            "required": ["query"],
        },
    ),
    types.Tool(
        name="openemr_patient_create",
        description="Create a new OpenEMR patient using the required demographic fields.",
        inputSchema={
            "type": "object",
            "properties": {
                "first_name": {"type": "string", "description": "Patient first name"},
                "last_name": {"type": "string", "description": "Patient last name"},
                "date_of_birth": {"type": "string", "description": "Birth date in YYYY-MM-DD format"},
                "birth_sex": {
                    "type": "string",
                    "description": "Birth sex",
                    "enum": ["Male", "Female", "Other", "Unknown"],
                },
            },
            "required": ["first_name", "last_name", "date_of_birth", "birth_sex"],
        },
    ),
    types.Tool(
        name="openemr_patient_list",
        description="List patients. Use this tool when the user asks for all patients or a general patient list.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of patients to return (default 50)",
                    "default": 50,
                },
            },
        },
    ),
    types.Tool(
        name="openemr_appointment_list",
        description="List upcoming appointments for a patient.",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "OpenEMR patient ID (e.g., 'p001')"},
            },
            "required": ["patient_id"],
        },
    ),
    types.Tool(
        name="openemr_medication_list",
        description="Return the current medication list for a patient.",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "OpenEMR patient ID (e.g., 'p001')"},
            },
            "required": ["patient_id"],
        },
    ),
    types.Tool(
        name="openemr_drug_interaction_check",
        description="Check a list of medications for known drug-drug interactions. Returns severity-classified interactions.",
        inputSchema={
            "type": "object",
            "properties": {
                "medications": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of drug names to check for interactions",
                },
            },
            "required": ["medications"],
        },
    ),
    types.Tool(
        name="openemr_provider_search",
        description="Search for healthcare providers by specialty and/or location.",
        inputSchema={
            "type": "object",
            "properties": {
                "specialty": {"type": "string", "description": "Medical specialty (e.g., 'Cardiology')"},
                "location": {"type": "string", "description": "City or facility name"},
            },
        },
    ),
    types.Tool(
        name="openemr_fda_adverse_events",
        description="Query FDA FAERS database for adverse event reports on a drug.",
        inputSchema={
            "type": "object",
            "properties": {
                "drug_name": {"type": "string", "description": "Generic or brand name of the drug"},
                "limit": {
                    "type": "integer",
                    "description": "Max number of top reactions to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["drug_name"],
        },
    ),
    types.Tool(
        name="openemr_fda_drug_label",
        description="Retrieve official FDA drug label including boxed warnings, contraindications, and indications.",
        inputSchema={
            "type": "object",
            "properties": {
                "drug_name": {"type": "string", "description": "Generic or brand name of the drug"},
            },
            "required": ["drug_name"],
        },
    ),
    types.Tool(
        name="openemr_symptom_lookup",
        description="Look up possible conditions for a list of symptoms. Returns ranked conditions with urgency level and medical disclaimer.",
        inputSchema={
            "type": "object",
            "properties": {
                "symptoms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of symptom descriptions (e.g., ['chest pain', 'shortness of breath'])",
                },
            },
            "required": ["symptoms"],
        },
    ),
    types.Tool(
        name="openemr_drug_safety_flag_create",
        description="Create a drug safety flag for a patient (adverse event, recall, warning, contraindication, or custom note).",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "OpenEMR patient ID"},
                "drug_name": {"type": "string", "description": "Name of the drug being flagged"},
                "description": {"type": "string", "description": "Clinical description of the safety concern"},
                "flag_type": {
                    "type": "string",
                    "enum": ["adverse_event", "recall", "warning", "contraindication", "custom"],
                    "default": "adverse_event",
                },
                "severity": {"type": "string", "enum": ["HIGH", "MODERATE", "LOW"], "default": "MODERATE"},
                "source": {
                    "type": "string",
                    "enum": ["FDA_FAERS", "FDA_LABEL", "FDA_RECALL", "CLINICIAN", "AGENT"],
                    "default": "AGENT",
                },
            },
            "required": ["patient_id", "drug_name", "description"],
        },
    ),
    types.Tool(
        name="openemr_drug_safety_flag_list",
        description="List all drug safety flags for a patient, optionally filtered by status.",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "OpenEMR patient ID"},
                "status_filter": {
                    "type": "string",
                    "enum": ["active", "resolved", "under_review"],
                    "description": "Filter by flag status (optional)",
                },
            },
            "required": ["patient_id"],
        },
    ),
    types.Tool(
        name="openemr_drug_safety_flag_update",
        description="Update a drug safety flag's severity, description, or status.",
        inputSchema={
            "type": "object",
            "properties": {
                "flag_id": {"type": "string", "description": "UUID of the flag to update"},
                "severity": {"type": "string", "enum": ["HIGH", "MODERATE", "LOW"]},
                "description": {"type": "string"},
                "status": {"type": "string", "enum": ["active", "resolved", "under_review"]},
            },
            "required": ["flag_id"],
        },
    ),
    types.Tool(
        name="openemr_drug_safety_flag_delete",
        description="Delete a drug safety flag by ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "flag_id": {"type": "string", "description": "UUID of the flag to delete"},
            },
            "required": ["flag_id"],
        },
    ),
    types.Tool(
        name="openemr_lab_trends",
        description="Return longitudinal lab trajectories for a patient (A1c, LDL, eGFR).",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "OpenEMR patient ID"},
                "metrics": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["a1c", "ldl", "egfr"]},
                    "description": "Metrics to return (default: all)",
                },
                "window_months": {
                    "type": "integer",
                    "description": "Lookback window in months (default 24)",
                    "default": 24,
                },
            },
            "required": ["patient_id"],
        },
    ),
    types.Tool(
        name="openemr_vital_trends",
        description="Return longitudinal vital sign trajectories for a patient (weight, BP systolic/diastolic).",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "OpenEMR patient ID"},
                "metrics": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["weight", "bp_systolic", "bp_diastolic"]},
                    "description": "Metrics to return (default: all)",
                },
                "window_months": {
                    "type": "integer",
                    "description": "Lookback window in months (default 24)",
                    "default": 24,
                },
            },
            "required": ["patient_id"],
        },
    ),
    types.Tool(
        name="openemr_questionnaire_trends",
        description="Return longitudinal questionnaire score trajectories for a patient (PHQ-9 depression screening).",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "OpenEMR patient ID"},
                "instrument": {
                    "type": "string",
                    "description": "Questionnaire name (default 'PHQ-9')",
                    "default": "PHQ-9",
                },
                "window_months": {
                    "type": "integer",
                    "description": "Lookback window in months (default 24)",
                    "default": 24,
                },
            },
            "required": ["patient_id"],
        },
    ),
    types.Tool(
        name="openemr_health_trajectory",
        description="Aggregate all metric trajectories (labs, vitals, questionnaires) and compute clinical drift alerts for a patient.",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "OpenEMR patient ID"},
                "window_months": {
                    "type": "integer",
                    "description": "Lookback window in months (default 24)",
                    "default": 24,
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Subset of metrics to include (default: all)",
                },
            },
            "required": ["patient_id"],
        },
    ),
    types.Tool(
        name="openemr_visit_prep",
        description="Generate a pre-visit clinical brief for a patient: top risks, medication safety, care gaps, and suggested agenda. Evidence-linked, no hallucination.",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "OpenEMR patient ID"},
                "window_months": {
                    "type": "integer",
                    "description": "Clinical data lookback window in months (default 24)",
                    "default": 24,
                },
            },
            "required": ["patient_id"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return _TOOLS


def _json(obj: Any) -> str:
    if hasattr(obj, "model_dump"):
        return obj.model_dump_json(indent=2)
    return json.dumps(obj, indent=2, default=str)


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        result = _invoke_tool(name, arguments)
        return [types.TextContent(type="text", text=_json(result))]
    except Exception as exc:
        error_payload = {"error": str(exc), "tool": name}
        return [types.TextContent(type="text", text=json.dumps(error_payload))]


def _invoke_tool(name: str, args: dict) -> Any:
    t0 = time.perf_counter()
    try:
        result = _dispatch(name, args)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        _log.info("tool=%s status=ok latency_ms=%.1f", name, elapsed_ms)
        return result
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        _log.error("tool=%s status=error latency_ms=%.1f error=%s", name, elapsed_ms, exc, exc_info=True)
        raise


def _dispatch(name: str, args: dict) -> Any:
    if name == "openemr_patient_search":
        from openemr_mcp.tools.patient import run_patient_search

        return run_patient_search(args["query"])

    if name == "openemr_patient_create":
        from openemr_mcp.tools.patient import run_create_patient

        return run_create_patient(
            first_name=args["first_name"],
            last_name=args["last_name"],
            date_of_birth=args["date_of_birth"],
            birth_sex=args["birth_sex"],
        )

    if name == "openemr_patient_list":
        from openemr_mcp.tools.patient import run_patient_list

        return run_patient_list(limit=args.get("limit", 50))

    if name == "openemr_appointment_list":
        from openemr_mcp.tools.appointments import run_appointment_list

        return run_appointment_list(args["patient_id"])

    if name == "openemr_medication_list":
        from openemr_mcp.tools.medications import run_medication_list

        return run_medication_list(args["patient_id"])

    if name == "openemr_drug_interaction_check":
        from openemr_mcp.tools.drug_interactions import run_drug_interaction_check

        return run_drug_interaction_check(args["medications"])

    if name == "openemr_provider_search":
        from openemr_mcp.tools.providers import run_provider_search

        return run_provider_search(
            specialty=args.get("specialty"),
            location=args.get("location"),
        )

    if name == "openemr_fda_adverse_events":
        from openemr_mcp.tools.fda import run_fda_adverse_events

        return run_fda_adverse_events(args["drug_name"], limit=args.get("limit", 5))

    if name == "openemr_fda_drug_label":
        from openemr_mcp.tools.fda import run_fda_drug_label

        return run_fda_drug_label(args["drug_name"])

    if name == "openemr_symptom_lookup":
        from openemr_mcp.tools.symptoms import run_symptom_lookup

        return run_symptom_lookup(args["symptoms"])

    if name == "openemr_drug_safety_flag_create":
        from openemr_mcp.tools.drug_safety import run_create_drug_safety_flag

        return run_create_drug_safety_flag(
            patient_id=args["patient_id"],
            drug_name=args["drug_name"],
            description=args["description"],
            flag_type=args.get("flag_type", "adverse_event"),
            severity=args.get("severity", "MODERATE"),
            source=args.get("source", "AGENT"),
        )

    if name == "openemr_drug_safety_flag_list":
        from openemr_mcp.tools.drug_safety import run_get_drug_safety_flags

        return run_get_drug_safety_flags(
            patient_id=args["patient_id"],
            status_filter=args.get("status_filter"),
        )

    if name == "openemr_drug_safety_flag_update":
        from openemr_mcp.tools.drug_safety import run_update_drug_safety_flag

        result = run_update_drug_safety_flag(
            flag_id=args["flag_id"],
            severity=args.get("severity"),
            description=args.get("description"),
            status=args.get("status"),
        )
        return result or {"error": "flag not found"}

    if name == "openemr_drug_safety_flag_delete":
        from openemr_mcp.tools.drug_safety import run_delete_drug_safety_flag

        deleted = run_delete_drug_safety_flag(args["flag_id"])
        return {"deleted": deleted, "flag_id": args["flag_id"]}

    if name == "openemr_lab_trends":
        from openemr_mcp.tools.lab_trends import run_lab_trends

        return run_lab_trends(
            patient_id=args["patient_id"],
            metrics=args.get("metrics"),
            window_months=args.get("window_months", 24),
        )

    if name == "openemr_vital_trends":
        from openemr_mcp.tools.vital_trends import run_vital_trends

        return run_vital_trends(
            patient_id=args["patient_id"],
            metrics=args.get("metrics"),
            window_months=args.get("window_months", 24),
        )

    if name == "openemr_questionnaire_trends":
        from openemr_mcp.tools.questionnaire import run_questionnaire_trends

        return run_questionnaire_trends(
            patient_id=args["patient_id"],
            instrument=args.get("instrument", "PHQ-9"),
            window_months=args.get("window_months", 24),
        )

    if name == "openemr_health_trajectory":
        from openemr_mcp.tools.trajectory import run_health_trajectory

        return run_health_trajectory(
            patient_id=args["patient_id"],
            window_months=args.get("window_months", 24),
            metrics=args.get("metrics"),
        )

    if name == "openemr_visit_prep":
        from openemr_mcp.tools.visit_prep import run_visit_prep

        return run_visit_prep(
            patient_id=args["patient_id"],
            window_months=args.get("window_months", 24),
        )

    raise ValueError(f"Unknown tool: {name!r}")


async def _main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the OpenEMR MCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "http"],
        default=os.getenv("OPENEMR_MCP_TRANSPORT", "stdio"),
        help="Transport to expose. Use streamable-http to run a network server.",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("OPENEMR_MCP_HOST", "127.0.0.1"),
        help="Bind host for streamable-http transport.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("OPENEMR_MCP_PORT", "8305")),
        help="Bind port for streamable-http transport.",
    )
    parser.add_argument(
        "--path",
        default=os.getenv("OPENEMR_MCP_PATH", "/mcp"),
        help="HTTP mount path for streamable-http transport.",
    )
    return parser.parse_args(argv)


def _normalize_transport(transport: str) -> str:
    if transport == "http":
        return "streamable-http"
    return transport


def _normalize_path(path: str) -> str:
    cleaned = path.strip() or "/mcp"
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    return cleaned


def run(argv: list[str] | None = None):
    """Entry point: openemr-mcp"""
    args = _parse_args(argv)
    transport = _normalize_transport(args.transport)
    if transport == "stdio":
        asyncio.run(_main())
        return

    from openemr_mcp.http_server import run_streamable_http

    run_streamable_http(
        host=args.host,
        port=args.port,
        path=_normalize_path(args.path),
    )


if __name__ == "__main__":
    run()
