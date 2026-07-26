"""Visit prep tool: assemble brief from collectors + rules; verifier enforces evidence_ids."""

import logging
from datetime import datetime, timezone

from openemr_mcp.schemas import (
    Abstention,
    EvidenceStore,
    VisitPrepMetadata,
    VisitPrepResponse,
)
from openemr_mcp.services.visit_prep_assembler import assemble_and_verify
from openemr_mcp.services.visit_prep_collectors_clinical import collect_clinical_evidence
from openemr_mcp.services.visit_prep_collectors_context import collect_context_evidence

logger = logging.getLogger(__name__)


def _build_clinical_payload(patient_id: str, window_months: int) -> dict:
    from openemr_mcp.tools.lab_trends import run_lab_trends
    from openemr_mcp.tools.medications import run_medication_list
    from openemr_mcp.tools.vital_trends import run_vital_trends

    try:
        lab_trajectories = run_lab_trends(patient_id, window_months=window_months)
    except Exception as exc:
        logger.warning("visit_prep: lab_trends failed for %s: %s", patient_id, exc, exc_info=True)
        lab_trajectories = []
    labs = []
    for traj in lab_trajectories:
        for pt in traj.points:
            labs.append({"code": pt.metric, "value": pt.value, "unit": traj.unit, "observed_at": pt.effective_at})

    try:
        vital_trajectories = run_vital_trends(patient_id, window_months=window_months)
    except Exception as exc:
        logger.warning("visit_prep: vital_trends failed for %s: %s", patient_id, exc, exc_info=True)
        vital_trajectories = []
    vitals: list = []
    bp_by_ts: dict = {}
    for traj in vital_trajectories:
        for pt in traj.points:
            if pt.metric == "bp_systolic":
                bp_by_ts.setdefault(pt.effective_at, {})["systolic"] = pt.value
            elif pt.metric == "bp_diastolic":
                bp_by_ts.setdefault(pt.effective_at, {})["diastolic"] = pt.value
            elif pt.metric == "weight":
                vitals.append({"type": "weight", "value": pt.value, "unit": traj.unit, "observed_at": pt.effective_at})
    for ts, bp in bp_by_ts.items():
        if "systolic" in bp and "diastolic" in bp:
            vitals.append(
                {
                    "type": "bp",
                    "value_systolic": bp["systolic"],
                    "value_diastolic": bp["diastolic"],
                    "unit": "mmHg",
                    "observed_at": ts,
                }
            )

    try:
        med_response = run_medication_list(patient_id)
        meds_raw = med_response.medications
    except Exception as exc:
        logger.warning("visit_prep: medication_list failed for %s: %s", patient_id, exc, exc_info=True)
        meds_raw = []
    medications = [
        {"drug": m.drug, "dose": (m.dosage or ""), "route": "", "status": (m.status or ""), "effective_date": ""}
        for m in meds_raw
    ]

    return {"medications": medications, "labs": labs, "vitals": vitals}


def _build_context_payload(patient_id: str) -> dict:
    from openemr_mcp.tools.appointments import run_appointment_list
    from openemr_mcp.tools.patient import run_get_patient_by_id

    appointments: list = []
    demographics = None
    care_team: list = []

    try:
        apts = run_appointment_list(patient_id)
        appointments = [
            {
                "appointment_id": a.appointment_id,
                "start_time": a.start_time or "",
                "status": "scheduled",
                "reason": a.reason or "",
            }
            for a in apts
        ]
    except Exception as exc:
        logger.warning("visit_prep: appointments failed for %s: %s", patient_id, exc, exc_info=True)
        appointments = []
    try:
        pid_int = int((patient_id or "").lstrip("pP").lstrip("0") or "0")
        patient = run_get_patient_by_id(pid_int)
        if patient:
            demographics = {"dob": patient.dob, "sex": patient.sex, "city": patient.city, "name": patient.full_name}
    except Exception as exc:
        logger.warning("visit_prep: demographics failed for %s: %s", patient_id, exc, exc_info=True)
        demographics = None

    return {"appointments": appointments, "demographics": demographics, "care_team": care_team}


def _get_evidence_store(clinical_payload: dict, context_payload: dict) -> EvidenceStore:
    clinical = collect_clinical_evidence(clinical_payload)
    context = collect_context_evidence(context_payload)
    combined = list(clinical.items) + list(context.items)
    combined.sort(key=lambda x: x.evidence_id)
    combined.sort(key=lambda x: x.evidence_id.split("::")[4] if "::" in x.evidence_id else "", reverse=True)
    return EvidenceStore(items=combined)


def _domain_abstentions(clinical_payload: dict, context_payload: dict) -> list[Abstention]:
    empty: list[Abstention] = []
    checks = [
        (clinical_payload.get("medications"), "medications"),
        (clinical_payload.get("labs"), "labs"),
        (clinical_payload.get("vitals"), "vitals"),
        (context_payload.get("appointments"), "appointments"),
        (context_payload.get("care_team"), "care_team"),
    ]
    for value, domain in checks:
        if not value:
            empty.append(
                Abstention(
                    reason_code="missing_data",
                    message=f"{domain} data unavailable for this patient.",
                    missing_evidence_keys=[domain],
                )
            )
    if not context_payload.get("demographics"):
        empty.append(
            Abstention(
                reason_code="missing_data",
                message="demographics data unavailable for this patient.",
                missing_evidence_keys=["demographics"],
            )
        )
    return empty


def run_visit_prep(
    patient_id: str,
    window_months: int = 24,
    evidence_store_override: EvidenceStore | None = None,
) -> VisitPrepResponse:
    """Assemble VisitPrepBrief from collectors + rules."""
    patient_id = (patient_id or "").strip() or "unknown"

    if evidence_store_override is not None:
        store = evidence_store_override
        extra_abstentions: list[Abstention] = []
    else:
        clinical_payload = _build_clinical_payload(patient_id, window_months)
        context_payload = _build_context_payload(patient_id)
        store = _get_evidence_store(clinical_payload, context_payload)
        extra_abstentions = _domain_abstentions(clinical_payload, context_payload)

    brief, evidence_store, _verified = assemble_and_verify(store)

    if extra_abstentions:
        brief.abstentions.abstentions.extend(extra_abstentions)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    metadata = VisitPrepMetadata(patient_id=patient_id, window_months=window_months, generated_at=generated_at)
    return VisitPrepResponse(brief=brief, metadata=metadata, evidence_store=evidence_store)
