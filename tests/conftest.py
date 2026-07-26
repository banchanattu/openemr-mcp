"""Pytest configuration — force mock mode for all tests."""

import pytest


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Ensure all tests run in mock mode with no external API calls."""
    monkeypatch.setenv("OPENEMR_DATA_SOURCE", "mock")
    monkeypatch.setenv("DRUG_INTERACTION_SOURCE", "mock")
    monkeypatch.setenv("SYMPTOM_SOURCE", "mock")
    monkeypatch.setenv("OPENFDA_SOURCE", "mock")


@pytest.fixture(autouse=True)
def cleanup_drug_safety_db():
    """Close the cached SQLite connection after each test to avoid resource leaks."""
    yield
    import openemr_mcp.repositories.drug_safety as ds_repo

    ds_repo.close_db()
