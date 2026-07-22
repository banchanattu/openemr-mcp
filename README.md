# openemr-mcp

[![PyPI](https://img.shields.io/pypi/v/openemr-mcp)](https://pypi.org/project/openemr-mcp/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Model Context Protocol (MCP) server for OpenEMR** — connect any MCP-compatible AI assistant (Claude Desktop, Cursor, VS Code Copilot) directly to your OpenEMR instance.

## Features

17 MCP tools covering:

| Category | Tools |
|---|---|
| Patients | `openemr_patient_search` |
| Appointments | `openemr_appointment_list` |
| Medications | `openemr_medication_list`, `openemr_drug_interaction_check` |
| Providers | `openemr_provider_search` |
| FDA Safety | `openemr_fda_adverse_events`, `openemr_fda_drug_label` |
| Symptom Lookup | `openemr_symptom_lookup` |
| Drug Safety Flags | `openemr_drug_safety_flag_create/list/update/delete` |
| Clinical Trends | `openemr_lab_trends`, `openemr_vital_trends`, `openemr_questionnaire_trends` |
| Health Trajectory | `openemr_health_trajectory` |
| Visit Prep | `openemr_visit_prep` |

All tools work in **mock mode** out of the box — no OpenEMR installation required for evaluation.

## Quick Start

### Install

```bash
pip install openemr-mcp
# or with uv:
uv add openemr-mcp
```

### Run (stdio transport)

```bash
# Mock mode — no OpenEMR needed
OPENEMR_DATA_SOURCE=mock openemr-mcp

# Against a live OpenEMR FHIR API
OPENEMR_DATA_SOURCE=api \
  OPENEMR_API_BASE_URL=https://your-openemr/apis/default \
  OPENEMR_OAUTH_SITE=default \
  OPENEMR_OAUTH_CLIENT_ID=... \
  OPENEMR_OAUTH_CLIENT_SECRET=... \
  OPENEMR_OAUTH_USERNAME=admin \
  OPENEMR_OAUTH_PASSWORD=... \
  openemr-mcp
```

### Run As A Network Server

The package can also run as a standalone MCP server over Streamable HTTP.

```bash
# Default endpoint: http://127.0.0.1:8305/mcp
OPENEMR_DATA_SOURCE=mock \
  openemr-mcp --transport streamable-http --host 127.0.0.1 --port 8305
```

Equivalent environment-variable based startup:

```bash
OPENEMR_MCP_TRANSPORT=streamable-http
OPENEMR_MCP_HOST=127.0.0.1
OPENEMR_MCP_PORT=8305
OPENEMR_MCP_PATH=/mcp
OPENEMR_DATA_SOURCE=mock
openemr-mcp
```

Clients should connect to `http://127.0.0.1:8305/mcp`.

Quick smoke test from another terminal:

```bash
uv run python examples/smoke_test_http.py --url http://127.0.0.1:8305/mcp
```

## Local vs Docker Config

This repo uses different env files for local and Docker startup:

| Startup path | Env file | OpenEMR host to use |
|---|---|---|
| `./startlocal.sh` or direct `openemr-mcp` from repo root | `.env.local` or `.env` | `http://localhost:8300/apis/default` |
| `./startdocker.sh` | `.env.docker` or `.env` | `http://host.docker.internal:8300/apis/default` |

Why the host changes:

- A local process can reach your OpenEMR instance at `localhost`.
- A Docker container cannot use its own `localhost` to reach your host machine, so it must use `host.docker.internal`.

This repository now includes a sample `.env.docker` configured for a host OpenEMR instance on port `8300`:

```env
OPENEMR_DATA_SOURCE=api
OPENEMR_API_BASE_URL=http://host.docker.internal:8300/apis/default
OPENEMR_API_VERIFY_SSL=false
```

If your OpenEMR requires OAuth credentials, either:

- set them in `.env.docker`, or
- export them in your shell before running `./startdocker.sh`

To switch back to mock mode:

```env
OPENEMR_DATA_SOURCE=mock
```

For Docker, you can put that in `.env.docker`. For local runs, put it in `.env.local`.

### Common Modes

Local process against your OpenEMR instance:

```env
# .env.local
OPENEMR_DATA_SOURCE=api
OPENEMR_API_BASE_URL=http://localhost:8300/apis/default
OPENEMR_API_VERIFY_SSL=false
```

Docker container against your OpenEMR instance:

```env
# .env.docker
OPENEMR_DATA_SOURCE=api
OPENEMR_API_BASE_URL=http://host.docker.internal:8300/apis/default
OPENEMR_API_VERIFY_SSL=false
```

Mock mode for either startup path:

```env
OPENEMR_DATA_SOURCE=mock
```

## Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "openemr": {
      "command": "uvx",
      "args": ["openemr-mcp"],
      "env": {
        "OPENEMR_DATA_SOURCE": "api",
        "OPENEMR_API_BASE_URL": "https://your-openemr.example.com/apis/default",
        "OPENEMR_OAUTH_SITE": "default",
        "OPENEMR_OAUTH_CLIENT_ID": "your_client_id",
        "OPENEMR_OAUTH_CLIENT_SECRET": "your_client_secret",
        "OPENEMR_OAUTH_USERNAME": "admin",
        "OPENEMR_OAUTH_PASSWORD": "your_password"
      }
    }
  }
}
```

For mock mode (demo / evaluation):

```json
{
  "mcpServers": {
    "openemr": {
      "command": "uvx",
      "args": ["openemr-mcp"],
      "env": {
        "OPENEMR_DATA_SOURCE": "mock"
      }
    }
  }
}
```

## Data Sources

### Patient / Clinical Data (`OPENEMR_DATA_SOURCE`)

| Value | Description |
|---|---|
| `mock` (default) | Built-in curated demo data — 24 patients, no network required |
| `db` | Direct MySQL connection to OpenEMR database |
| `api` | OpenEMR FHIR R4 REST API (recommended for production) |

### Drug Interactions (`DRUG_INTERACTION_SOURCE`)

| Value | Description |
|---|---|
| `mock` (default) | 10 built-in drug pairs — always works, no network |
| `openfda` | OpenFDA FAERS co-reporting heuristic — free, no API key required. Severity based on co-report volume (HIGH ≥ 50, MODERATE ≥ 5). Note: Co-reporting indicates correlation, not definitive causation. |
| `rxnorm` | ⚠️ **DEPRECATED/UNAVAILABLE** — RxNorm interaction API endpoints retired (returns 404) |

### Symptom Checker (`SYMPTOM_SOURCE`)

| Value | Description |
|---|---|
| `mock` (default) | Curated local dataset — 10 clinical groups |
| `infermedica` | Infermedica Symptom Checker API ([register here](https://developer.infermedica.com/)) — free tier 100 calls/day |

### FDA Data (`OPENFDA_SOURCE`)

| Value | Description |
|---|---|
| `mock` (default) | Built-in mock data for 6 common drugs |
| `live` | Live OpenFDA API — free, optional key for higher rate limits |

## Environment Variables

See [.env.example](.env.example) for the full list with comments.

Key variables:

```bash
# Data source
OPENEMR_DATA_SOURCE=mock        # mock | db | api

# MCP transport
OPENEMR_MCP_TRANSPORT=stdio     # stdio | streamable-http
OPENEMR_MCP_HOST=127.0.0.1
OPENEMR_MCP_PORT=8305
OPENEMR_MCP_PATH=/mcp

# MySQL (when OPENEMR_DATA_SOURCE=db)
OPENEMR_DB_HOST=localhost
OPENEMR_DB_PORT=3306
OPENEMR_DB_USER=openemr
OPENEMR_DB_PASSWORD=openemr
OPENEMR_DB_NAME=openemr

# FHIR API (when OPENEMR_DATA_SOURCE=api)
OPENEMR_API_BASE_URL=https://your-openemr/apis/default
OPENEMR_OAUTH_SITE=default
OPENEMR_OAUTH_CLIENT_ID=...
OPENEMR_OAUTH_CLIENT_SECRET=...
OPENEMR_OAUTH_USERNAME=admin
OPENEMR_OAUTH_PASSWORD=...

# Optional external APIs
DRUG_INTERACTION_SOURCE=mock    # mock | openfda | rxnorm (deprecated)
SYMPTOM_SOURCE=mock             # mock | infermedica
INFERMEDICA_APP_ID=
INFERMEDICA_APP_KEY=
OPENFDA_SOURCE=mock             # mock | live
OPENFDA_API_KEY=
```

## Tool Reference

### `openemr_patient_search`
Search patients by name. Returns patient ID, DOB, sex, city.

```json
{ "query": "Jane" }
```

### `openemr_appointment_list`
List upcoming appointments for a patient.

```json
{ "patient_id": "p001" }
```

### `openemr_medication_list`
Return the current medication list for a patient.

```json
{ "patient_id": "p001" }
```

### `openemr_drug_interaction_check`
Check a list of medications for known drug-drug interactions.

```json
{ "medications": ["warfarin", "aspirin", "metformin"] }
```

### `openemr_provider_search`
Search healthcare providers by specialty and/or location.

```json
{ "specialty": "Cardiology", "location": "Boston" }
```

### `openemr_fda_adverse_events`
Query FDA FAERS database for adverse event reports on a drug.

```json
{ "drug_name": "metformin", "limit": 5 }
```

### `openemr_fda_drug_label`
Retrieve official FDA drug label including boxed warnings and contraindications.

```json
{ "drug_name": "warfarin" }
```

### `openemr_symptom_lookup`
Look up possible conditions for a list of symptoms.

```json
{ "symptoms": ["chest pain", "shortness of breath"] }
```

### `openemr_drug_safety_flag_create`
Create a drug safety flag for a patient.

```json
{
  "patient_id": "p001",
  "drug_name": "warfarin",
  "description": "Patient reported unusual bruising",
  "flag_type": "adverse_event",
  "severity": "HIGH"
}
```

### `openemr_drug_safety_flag_list`
List all drug safety flags for a patient.

```json
{ "patient_id": "p001", "status_filter": "active" }
```

### `openemr_drug_safety_flag_update`
Update a drug safety flag's severity, description, or status.

```json
{ "flag_id": "uuid-...", "severity": "MODERATE", "status": "resolved" }
```

### `openemr_drug_safety_flag_delete`
Delete a drug safety flag by ID.

```json
{ "flag_id": "uuid-..." }
```

### `openemr_lab_trends`
Return longitudinal lab trajectories (A1c, LDL, eGFR).

```json
{ "patient_id": "p001", "metrics": ["a1c", "ldl"], "window_months": 24 }
```

### `openemr_vital_trends`
Return longitudinal vital sign trajectories (weight, BP).

```json
{ "patient_id": "p001", "metrics": ["weight", "bp_systolic", "bp_diastolic"] }
```

### `openemr_questionnaire_trends`
Return longitudinal questionnaire score trajectories (PHQ-9).

```json
{ "patient_id": "p001", "instrument": "PHQ-9", "window_months": 24 }
```

### `openemr_health_trajectory`
Aggregate all metric trajectories and compute clinical drift alerts.

```json
{ "patient_id": "p001", "window_months": 24 }
```

### `openemr_visit_prep`
Generate a pre-visit clinical brief: top risks, medication safety, care gaps, and suggested agenda.

```json
{ "patient_id": "p001", "window_months": 24 }
```

## Development

```bash
# Clone and install in editable mode
git clone https://github.com/shruti-jn/openemr-mcp
cd openemr-mcp
pip install -e ".[dev]"

# Run tests (mock mode, no external dependencies)
pytest

# Start server locally
OPENEMR_DATA_SOURCE=mock openemr-mcp
```

## Architecture

```
src/openemr_mcp/
├── server.py              # MCP server — registers all 17 tools
├── config.py              # Pydantic-settings configuration
├── schemas.py             # All Pydantic response schemas
├── auth.py                # OpenEMR OAuth2 token manager
├── data_source.py         # Data source resolver
├── tools/                 # 13 tool modules (17 MCP tools)
├── repositories/          # Data access (MySQL, FHIR R4, SQLite)
└── services/              # Business logic (OpenFDA, trajectory alerts, visit prep)
```

Drug safety flags are persisted in a local SQLite database at `~/.openemr_mcp/drug_safety_flags.db`.

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Pull requests welcome. Please open an issue first for major changes.

This project is part of the [AgentForge](https://github.com/shruti-jn/agentforge-openemr) OpenEMR AI toolkit.
