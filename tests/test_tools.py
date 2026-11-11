"""Smoke tests — verify all 20 MCP tools return expected types in mock mode."""

import pytest

from openemr_mcp.repositories._errors import ToolError
from openemr_mcp.schemas import (
    AppointmentCreateResult,
    DrugInteractionResponse,
    DrugSafetyFlag,
    DrugSafetyFlagListResponse,
    FDAAdverseEventSummary,
    FDADrugLabelResult,
    HealthTrajectoryResponse,
    MedicationListResponse,
    PatientMatch,
    ProviderSearchResponse,
    SymptomLookupResponse,
    VisitPrepResponse,
)

# ---------------------------------------------------------------------------
# Patient
# ---------------------------------------------------------------------------


def test_patient_search_returns_matches():
    from openemr_mcp.tools.patient import run_patient_search

    results = run_patient_search("John")
    assert isinstance(results, list)
    assert len(results) >= 1
    assert results[0].patient_id.startswith("p")


def test_patient_search_no_results():
    from openemr_mcp.tools.patient import run_patient_search

    results = run_patient_search("zzznomatchxxx")
    assert isinstance(results, list)
    assert len(results) == 0


def test_patient_search_empty_query_rejected():
    from openemr_mcp.tools.patient import run_patient_search

    with pytest.raises(ToolError, match="query is required for patient search"):
        run_patient_search("")


def test_patient_list_default_limit():
    from openemr_mcp.tools.patient import run_patient_list

    results = run_patient_list()
    assert isinstance(results, list)
    assert len(results) == 24


def test_patient_list_custom_limit():
    from openemr_mcp.tools.patient import run_patient_list

    results = run_patient_list(limit=5)
    assert isinstance(results, list)
    assert len(results) == 5
    assert results[0].patient_id == "p001"


def test_patient_list_rejects_invalid_limit():
    from openemr_mcp.tools.patient import run_patient_list

    with pytest.raises(ToolError, match="limit must be greater than 0"):
        run_patient_list(limit=0)


def test_patient_search_rejects_unsupported_data_source(monkeypatch):
    from openemr_mcp.tools.patient import run_patient_search

    monkeypatch.setenv("OPENEMR_DATA_SOURCE", "db")

    with pytest.raises(ToolError, match="Unsupported OPENEMR_DATA_SOURCE 'db'"):
        run_patient_search("John")


def test_patient_create_mock_patient():
    from openemr_mcp.tools.patient import run_create_patient, run_patient_search

    created = run_create_patient("Taylor", "Example", "1994-01-15", "Female")
    assert isinstance(created, PatientMatch)
    assert created.patient_id.startswith("p")
    assert created.full_name == "Taylor Example"
    assert created.dob == "1994-01-15"
    assert created.sex == "Female"

    matches = run_patient_search("Taylor Example")
    assert any(match.patient_id == created.patient_id for match in matches)


def test_patient_create_rejects_invalid_birth_sex():
    from openemr_mcp.tools.patient import run_create_patient

    with pytest.raises(ToolError, match="birth_sex must be one of"):
        run_create_patient("Chris", "Example", "1994-01-15", "Invalid")


def test_create_patient_api_uses_official_name_payload():
    from openemr_mcp.repositories.fhir_api import create_patient_api
    from openemr_mcp.schemas import PatientCreate

    captured: dict = {}

    class FakeHttpClient:
        def post_fhir(self, resource_path: str, json_body: dict) -> dict:
            captured["resource_path"] = resource_path
            captured["json_body"] = json_body
            return {
                "uuid": "123",
            }

    patient = create_patient_api(
        PatientCreate(
            first_name="Jane",
            last_name="Example",
            date_of_birth="1990-07-22",
            birth_sex="Female",
        ),
        FakeHttpClient(),
    )

    assert captured["resource_path"] == "Patient"
    assert captured["json_body"]["name"][0]["use"] == "official"
    assert captured["json_body"]["name"][0]["given"] == ["Jane"]
    assert captured["json_body"]["name"][0]["family"] == "Example"
    assert captured["json_body"]["active"] is True
    assert captured["json_body"]["birthDate"] == "1990-07-22"
    assert captured["json_body"]["gender"] == "female"
    assert "extension" not in captured["json_body"]
    assert patient.patient_id == "p123"
    assert patient.full_name == "Jane Example"


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------


def test_appointment_list_known_patient():
    from openemr_mcp.schemas import Appointment
    from openemr_mcp.tools.appointments import run_appointment_list

    results = run_appointment_list("p001")
    assert isinstance(results, list)
    if results:
        assert isinstance(results[0], Appointment)


def test_appointment_list_unknown_patient():
    from openemr_mcp.tools.appointments import run_appointment_list

    results = run_appointment_list("p999")
    assert isinstance(results, list)
    assert len(results) == 0


def test_appointment_create_mock_patient():
    from openemr_mcp.tools.appointments import run_appointment_list, run_create_appointment

    created = run_create_appointment(
        patient_id="p001",
        category_id="5",
        title="Office Visit",
        duration="900",
        comments="Test",
        appointment_status="-",
        event_date="2026-08-01",
        start_time="09:00",
        facility_id="9",
        billing_location_id="10",
        provider_id="prov1",
    )

    assert isinstance(created, AppointmentCreateResult)
    assert created.appointment_id is not None
    assert created.patient_id == "p001"
    assert created.status == "created"
    assert created.start_time == "2026-08-01T09:00"
    assert created.reason == "Office Visit"
    assert created.provider_id == "prov1"

    results = run_appointment_list("p001")
    assert any(item.appointment_id == created.appointment_id for item in results)


def test_appointment_create_mock_defaults_to_pending_status():
    from openemr_mcp.tools.appointments import run_create_appointment

    created = run_create_appointment(
        patient_id="p001",
        title="Office Visit",
        comments="Brief note",
        event_date="2026-08-01",
        start_time="09:00",
    )

    assert isinstance(created, AppointmentCreateResult)
    assert created.status == "created"


def test_appointment_create_rejects_invalid_event_date():
    from openemr_mcp.tools.appointments import run_create_appointment

    with pytest.raises(ToolError, match="event_date must be in YYYY-MM-DD format"):
        run_create_appointment(
            patient_id="p001",
            category_id="5",
            title="Office Visit",
            duration="900",
            comments="Test",
            appointment_status="-",
            event_date="08/01/2026",
            start_time="09:00",
            facility_id="9",
            billing_location_id="10",
        )


def test_appointment_create_rejects_missing_title():
    from openemr_mcp.tools.appointments import run_create_appointment

    with pytest.raises(ToolError, match="title is required"):
        run_create_appointment(
            patient_id="p001",
            category_id="5",
            title="",
            duration="900",
            comments="Test",
            appointment_status="-",
            event_date="2026-08-01",
            start_time="09:00",
            facility_id="9",
            billing_location_id="10",
        )


def test_create_appointment_api_uses_rest_payload():
    from openemr_mcp.repositories.fhir_api import create_appointment_api
    from openemr_mcp.schemas import AppointmentCreate

    captured: dict = {}

    class FakeHttpClient:
        def post_rest(self, path: str, json_body: dict) -> dict:
            captured["path"] = path
            captured["json_body"] = json_body
            return {
                "status": "created",
                "data": {
                    "pc_eid": "55",
                    "pc_eventDate": "2026-08-01",
                    "pc_startTime": "09:00",
                    "pc_title": "Office Visit",
                    "pc_aid": "1",
                },
            }

    result = create_appointment_api(
        AppointmentCreate(
            patient_id="p001",
            category_id="5",
            title="Office Visit",
            duration="900",
            comments="Test",
            appointment_status="-",
            event_date="2026-08-01",
            start_time="09:00",
            facility_id="9",
            billing_location_id="10",
            provider_id="prov1",
        ),
        FakeHttpClient(),
    )

    assert captured["path"] == "patient/1/appointment"
    assert captured["json_body"] == {
        "pc_catid": "5",
        "pc_title": "Office Visit",
        "pc_duration": "900",
        "pc_hometext": "Test",
        "pc_apptstatus": "-",
        "pc_eventDate": "2026-08-01",
        "pc_startTime": "09:00",
        "pc_facility": "9",
        "pc_billing_location": "10",
        "pc_aid": "1",
    }
    assert result.appointment_id == "a55"
    assert result.patient_id == "p001"
    assert result.status == "created"
    assert result.start_time == "2026-08-01T09:00"
    assert result.reason == "Office Visit"
    assert result.provider_id == "prov1"


def test_get_appointments_api_uses_patient_appointment_route_for_uuid():
    from openemr_mcp.repositories.fhir_api import get_appointments_api

    captured: dict = {}

    class FakeHttpClient:
        def get_rest(self, path: str, params: dict | None = None) -> dict:
            captured["path"] = path
            captured["params"] = params
            return {
                "data": [
                    {
                        "pc_eid": "55",
                        "pc_pid": "a25943d6-4711-419d-8f8b-42a9f8cc3069",
                        "pc_eventDate": "2026-08-04",
                        "pc_startTime": "13:00",
                        "pc_title": "Knee Pain",
                        "pc_aid": "1",
                    }
                ]
            }

    results = get_appointments_api("pa25943d6-4711-419d-8f8b-42a9f8cc3069", FakeHttpClient())

    assert captured["path"] == "patient/a25943d6-4711-419d-8f8b-42a9f8cc3069/appointment"
    assert captured["params"] is None
    assert len(results) == 1
    assert results[0].appointment_id == "a55"
    assert results[0].patient_id == "pa25943d6-4711-419d-8f8b-42a9f8cc3069"
    assert results[0].start_time == "2026-08-04T13:00"
    assert results[0].reason == "Knee Pain"
    assert results[0].provider_id == "prov1"


# ---------------------------------------------------------------------------
# Medications
# ---------------------------------------------------------------------------


def test_medication_list_known_patient():
    from openemr_mcp.tools.medications import run_medication_list

    result = run_medication_list("p001")
    assert isinstance(result, MedicationListResponse)
    assert len(result.medications) >= 1
    assert result.medications[0].drug


def test_medication_list_unknown_patient():
    from openemr_mcp.tools.medications import run_medication_list

    result = run_medication_list("p999")
    assert isinstance(result, MedicationListResponse)
    assert result.medications == []


# ---------------------------------------------------------------------------
# Drug Interactions
# ---------------------------------------------------------------------------


def test_drug_interaction_check_known_pair():
    from openemr_mcp.tools.drug_interactions import run_drug_interaction_check

    result = run_drug_interaction_check(["warfarin", "aspirin"])
    assert isinstance(result, DrugInteractionResponse)
    assert len(result.interactions) >= 1


def test_drug_interaction_check_no_interaction():
    from openemr_mcp.tools.drug_interactions import run_drug_interaction_check

    result = run_drug_interaction_check(["vitamin_c"])
    assert isinstance(result, DrugInteractionResponse)
    assert result.has_critical is False


def test_drug_interaction_check_empty():
    from openemr_mcp.tools.drug_interactions import run_drug_interaction_check

    result = run_drug_interaction_check([])
    assert isinstance(result, DrugInteractionResponse)
    assert result.interactions == []


def test_drug_interaction_openfda(monkeypatch):
    """OpenFDA provider returns interactions using FAERS co-reporting."""
    import types

    from openemr_mcp.tools import drug_interactions

    monkeypatch.setattr(drug_interactions.settings, "drug_interaction_source", "openfda")

    sample = {
        "results": [
            {"term": "Hemorrhage", "count": 120},
            {"term": "Headache", "count": 10},
        ]
    }

    def fake_get(url, params=None, timeout=None):
        resp = types.SimpleNamespace()
        resp.status_code = 200
        resp.json = lambda: sample

        def raise_for_status(): ...

        resp.raise_for_status = raise_for_status
        return resp

    monkeypatch.setattr(drug_interactions.httpx, "get", fake_get)

    result = drug_interactions.run_drug_interaction_check(["warfarin", "aspirin"])
    assert result.has_critical is True
    assert result.interactions
    assert result.interactions[0].severity in ("HIGH", "MODERATE")


def test_drug_interaction_openfda_strict_no_fallback(monkeypatch):
    """OpenFDA failure raises ToolError without fallback to mock."""
    import pytest

    from openemr_mcp.repositories._errors import ToolError
    from openemr_mcp.tools import drug_interactions

    monkeypatch.setattr(drug_interactions.settings, "drug_interaction_source", "openfda")

    def fake_get_failure(url, params=None, timeout=None):
        raise Exception("API unavailable")

    monkeypatch.setattr(drug_interactions.httpx, "get", fake_get_failure)

    with pytest.raises(ToolError) as exc_info:
        drug_interactions.run_drug_interaction_check(["warfarin", "aspirin"])

    error_msg = str(exc_info.value).lower()
    assert "openfda" in error_msg
    assert "no fallback data used" in error_msg


def test_drug_interaction_rxnorm_strict_no_fallback(monkeypatch):
    """RxNorm failure raises ToolError without fallback to mock."""
    import pytest

    from openemr_mcp.repositories._errors import ToolError
    from openemr_mcp.tools import drug_interactions

    monkeypatch.setattr(drug_interactions.settings, "drug_interaction_source", "rxnorm")

    def fake_get_failure(url, params=None, timeout=None):
        raise Exception("404 Not Found")

    monkeypatch.setattr(drug_interactions.httpx, "get", fake_get_failure)

    with pytest.raises(ToolError) as exc_info:
        drug_interactions.run_drug_interaction_check(["warfarin", "aspirin"])

    error_msg = str(exc_info.value).lower()
    assert "rxnorm" in error_msg
    assert "no fallback data used" in error_msg


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


def test_provider_search_by_specialty():
    from openemr_mcp.tools.providers import run_provider_search

    result = run_provider_search(specialty="Cardiology")
    assert isinstance(result, ProviderSearchResponse)
    assert len(result.providers) >= 1
    assert result.specialty_queried == "Cardiology"


def test_provider_search_no_filters():
    from openemr_mcp.tools.providers import run_provider_search

    result = run_provider_search()
    assert isinstance(result, ProviderSearchResponse)
    assert len(result.providers) >= 5


# ---------------------------------------------------------------------------
# FDA
# ---------------------------------------------------------------------------


def test_fda_adverse_events_known_drug():
    from openemr_mcp.tools.fda import run_fda_adverse_events

    result = run_fda_adverse_events("metformin")
    assert isinstance(result, FDAAdverseEventSummary)
    assert result.drug_name
    assert result.total_reports >= 0


def test_fda_drug_label_known_drug():
    from openemr_mcp.tools.fda import run_fda_drug_label

    result = run_fda_drug_label("metformin")
    assert isinstance(result, FDADrugLabelResult)
    assert result.drug_name


# ---------------------------------------------------------------------------
# Symptoms
# ---------------------------------------------------------------------------


def test_symptom_lookup_chest_pain():
    from openemr_mcp.tools.symptoms import run_symptom_lookup

    result = run_symptom_lookup(["chest pain", "shortness of breath"])
    assert isinstance(result, SymptomLookupResponse)
    assert len(result.possible_conditions) >= 1
    assert result.urgency_level in ("URGENT", "SEE_DOCTOR", "MONITOR")
    assert result.disclaimer


def test_symptom_lookup_no_match():
    from openemr_mcp.tools.symptoms import run_symptom_lookup

    result = run_symptom_lookup(["blurry_nonexistent_symptom_xyz"])
    assert isinstance(result, SymptomLookupResponse)
    assert result.urgency_level == "MONITOR"


# ---------------------------------------------------------------------------
# Drug Safety Flags (CRUD)
# ---------------------------------------------------------------------------


def test_drug_safety_flag_crud(tmp_path, monkeypatch):
    """Create → list → update → delete a drug safety flag."""
    import openemr_mcp.repositories.drug_safety as ds_repo

    # Redirect the SQLite DB to a temp directory
    test_db = tmp_path / "flags.db"
    ds_repo.close_db()
    monkeypatch.setattr(ds_repo, "_DB_PATH", test_db)
    monkeypatch.setattr(ds_repo, "_conn", None)

    from openemr_mcp.tools.drug_safety import (
        run_create_drug_safety_flag,
        run_delete_drug_safety_flag,
        run_get_drug_safety_flags,
        run_update_drug_safety_flag,
    )

    # Create
    flag = run_create_drug_safety_flag(
        patient_id="p001",
        drug_name="warfarin",
        description="Bleeding risk noted",
        severity="HIGH",
    )
    assert isinstance(flag, DrugSafetyFlag)
    assert flag.drug_name == "warfarin"
    flag_id = flag.id

    # List
    listing = run_get_drug_safety_flags("p001")
    assert isinstance(listing, DrugSafetyFlagListResponse)
    assert any(f.id == flag_id for f in listing.flags)

    # Update
    updated = run_update_drug_safety_flag(flag_id, severity="MODERATE")
    assert updated is not None
    assert updated.severity == "MODERATE"

    # Delete
    deleted = run_delete_drug_safety_flag(flag_id)
    assert deleted is True

    # List again — should be empty
    listing2 = run_get_drug_safety_flags("p001")
    assert not any(f.id == flag_id for f in listing2.flags)


# ---------------------------------------------------------------------------
# Lab Trends
# ---------------------------------------------------------------------------


def test_lab_trends_all_metrics():
    from openemr_mcp.tools.lab_trends import run_lab_trends

    result = run_lab_trends("p001")
    assert isinstance(result, list)
    assert len(result) >= 1
    assert result[0].points


def test_lab_trends_single_metric():
    from openemr_mcp.tools.lab_trends import run_lab_trends

    result = run_lab_trends("p001", metrics=["a1c"])
    assert isinstance(result, list)
    names = [t.metric for t in result]
    assert "a1c" in names


# ---------------------------------------------------------------------------
# Vital Trends
# ---------------------------------------------------------------------------


def test_vital_trends_all_metrics():
    from openemr_mcp.tools.vital_trends import run_vital_trends

    result = run_vital_trends("p001")
    assert isinstance(result, list)
    assert len(result) >= 1


def test_vital_trends_weight_only():
    from openemr_mcp.tools.vital_trends import run_vital_trends

    result = run_vital_trends("p001", metrics=["weight"])
    assert isinstance(result, list)
    assert all(t.metric == "weight" for t in result)


# ---------------------------------------------------------------------------
# Questionnaire Trends
# ---------------------------------------------------------------------------


def test_questionnaire_trends_phq9():
    from openemr_mcp.tools.questionnaire import run_questionnaire_trends

    result = run_questionnaire_trends("p001")
    assert isinstance(result, list)
    if result:
        assert result[0].metric in ("PHQ-9", "phq9")


# ---------------------------------------------------------------------------
# Health Trajectory
# ---------------------------------------------------------------------------


def test_health_trajectory():
    from openemr_mcp.tools.trajectory import run_health_trajectory

    result = run_health_trajectory("p001")
    assert isinstance(result, HealthTrajectoryResponse)
    assert result.patient_id == "p001"
    assert isinstance(result.trajectories, list)
    assert isinstance(result.alerts, list)


# ---------------------------------------------------------------------------
# Visit Prep
# ---------------------------------------------------------------------------


def test_visit_prep_returns_brief():
    from openemr_mcp.tools.visit_prep import run_visit_prep

    result = run_visit_prep("p001")
    assert isinstance(result, VisitPrepResponse)
    assert result.metadata.patient_id == "p001"
    brief = result.brief
    assert brief.top_risks is not None
    assert brief.medication_safety is not None
    assert brief.care_gaps is not None
    assert brief.agenda is not None


def test_visit_prep_unknown_patient():
    from openemr_mcp.tools.visit_prep import run_visit_prep

    result = run_visit_prep("p999")
    assert isinstance(result, VisitPrepResponse)
    # Should return abstentions for missing data, not crash
    assert result.metadata.patient_id == "p999"


# ---------------------------------------------------------------------------
# Auth interface regression guard
# ---------------------------------------------------------------------------


def test_oauth2_token_manager_exposes_get_valid_access_token():
    """Regression: data_source._get_headers calls get_valid_access_token, not get_token.
    If the method is renamed again this test will catch the mismatch before it ships."""
    from openemr_mcp.auth import OAuth2TokenManager

    assert callable(getattr(OAuth2TokenManager, "get_valid_access_token", None)), (
        "OAuth2TokenManager must expose get_valid_access_token — data_source._get_headers depends on it"
    )
    assert not hasattr(OAuth2TokenManager, "get_token"), (
        "OAuth2TokenManager must not expose 'get_token' — use get_valid_access_token"
    )


def test_get_http_client_method_name_contract():
    """Verify _OpenEMRClient._get_headers calls get_valid_access_token.
    Inspects source to catch future renames without needing a live OpenEMR."""
    import inspect

    from openemr_mcp import data_source

    src = inspect.getsource(data_source)
    assert "get_valid_access_token" in src, "data_source must call get_valid_access_token, not get_token"
    assert "get_token()" not in src, "data_source must not call the non-existent get_token() method"


# ---------------------------------------------------------------------------
# No-fabrication guards for live external sources
# ---------------------------------------------------------------------------


def test_rxnorm_source_does_not_fallback_to_mock(monkeypatch):
    from openemr_mcp.tools import drug_interactions

    monkeypatch.setattr(drug_interactions.settings, "drug_interaction_source", "rxnorm")
    monkeypatch.setattr(drug_interactions, "_run_rxnorm_check", lambda meds: None)
    with pytest.raises(ToolError, match="no fallback data used"):
        drug_interactions.run_drug_interaction_check(["warfarin", "aspirin"])


def test_infermedica_source_does_not_fallback_to_mock(monkeypatch):
    from openemr_mcp.tools import symptoms

    monkeypatch.setattr(symptoms.settings, "symptom_source", "infermedica")
    monkeypatch.setattr(symptoms, "_run_infermedica_check", lambda symptoms_list: None)
    with pytest.raises(ToolError, match="no fallback data used"):
        symptoms.run_symptom_lookup(["chest pain"])


def test_openfda_live_failure_does_not_fallback_to_mock(monkeypatch):
    from openemr_mcp.services import openfda_client

    monkeypatch.setattr(openfda_client.settings, "openfda_source", "live")

    def _raise_connect_error(*args, **kwargs):
        raise openfda_client.httpx.ConnectError("network unavailable")

    monkeypatch.setattr(openfda_client.httpx, "get", _raise_connect_error)
    with pytest.raises(ToolError, match="no fallback data used"):
        openfda_client.get_adverse_events("metformin")
