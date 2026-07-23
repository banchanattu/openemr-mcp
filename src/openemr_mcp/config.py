"""Configuration for openemr-mcp. All settings via environment variables."""

import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict

# Load local env defaults from cwd.
# Precedence: process env > cwd .env.local > cwd .env
for _env_name in (".env", ".env.local"):
    _env_path = Path.cwd() / _env_name
    _cwd_env = dotenv_values(_env_path) if _env_path.exists() else {}
    for _key, _value in _cwd_env.items():
        if _value is not None and _key not in os.environ:
            os.environ[_key] = _value


class Settings(BaseModel):
    env: str = os.getenv("ENV", "dev")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # OpenEMR data source: mock (default) | db (MySQL) | api (FHIR R4)
    openemr_data_source: str = os.getenv("OPENEMR_DATA_SOURCE", "mock")

    # MySQL connection (used when OPENEMR_DATA_SOURCE=db)
    openemr_db_host: str = os.getenv("OPENEMR_DB_HOST", "localhost")
    openemr_db_port: int = int(os.getenv("OPENEMR_DB_PORT", "3306"))
    openemr_db_user: str = os.getenv("OPENEMR_DB_USER", "openemr")
    openemr_db_password: str = os.getenv("OPENEMR_DB_PASSWORD", "")
    openemr_db_name: str = os.getenv("OPENEMR_DB_NAME", "openemr")

    # FHIR R4 API (used when OPENEMR_DATA_SOURCE=api)
    openemr_api_base_url: str | None = os.getenv("OPENEMR_API_BASE_URL")
    openemr_auth_mode: str = os.getenv("OPENEMR_AUTH_MODE", "auto")
    openemr_require_request_auth: bool = os.getenv("OPENEMR_REQUIRE_REQUEST_AUTH", "false").lower() == "true"
    openemr_refresh_token_header: str = os.getenv("OPENEMR_REFRESH_TOKEN_HEADER", "X-Refresh-Token")
    openemr_enable_request_token_refresh: bool = (
        os.getenv("OPENEMR_ENABLE_REQUEST_TOKEN_REFRESH", "false").lower() == "true"
    )
    openemr_validate_request_token_locally: bool = (
        os.getenv("OPENEMR_VALIDATE_REQUEST_TOKEN_LOCALLY", "true").lower() == "true"
    )
    openemr_log_outbound_bearer_token: bool = (
        os.getenv("OPENEMR_LOG_OUTBOUND_BEARER_TOKEN", "false").lower() == "true"
    )
    openemr_oauth_site: str = os.getenv("OPENEMR_OAUTH_SITE", "default")
    openemr_oauth_client_id: str | None = os.getenv("OPENEMR_OAUTH_CLIENT_ID")
    openemr_oauth_client_secret: str | None = os.getenv("OPENEMR_OAUTH_CLIENT_SECRET")
    openemr_oauth_username: str | None = os.getenv("OPENEMR_OAUTH_USERNAME")
    openemr_oauth_password: str | None = os.getenv("OPENEMR_OAUTH_PASSWORD")
    openemr_api_verify_ssl: bool = os.getenv("OPENEMR_API_VERIFY_SSL", "true").lower() == "true"
    openemr_enable_client_via_sql: bool = os.getenv("OPENEMR_ENABLE_CLIENT_VIA_SQL", "false").lower() == "true"
    openemr_docker_service: str | None = os.getenv("OPENEMR_DOCKER_SERVICE")
    openemr_docker_cwd: str | None = os.getenv("OPENEMR_DOCKER_CWD")

    # Drug interaction source: mock (default) | openfda (OpenFDA FAERS — free, no key) | rxnorm (deprecated/unavailable)
    drug_interaction_source: str = os.getenv("DRUG_INTERACTION_SOURCE", "mock")

    # Symptom lookup source: mock (default) | infermedica (free tier 100/day)
    symptom_source: str = os.getenv("SYMPTOM_SOURCE", "mock")
    infermedica_app_id: str | None = os.getenv("INFERMEDICA_APP_ID")
    infermedica_app_key: str | None = os.getenv("INFERMEDICA_APP_KEY")

    # FDA drug safety: mock (default) | live (free, no key required)
    openfda_source: str = os.getenv("OPENFDA_SOURCE", "mock")
    openfda_api_key: str | None = os.getenv("OPENFDA_API_KEY")

    model_config = ConfigDict(extra="ignore")


settings = Settings()
