"""Medication list tool."""

from openemr_mcp.data_source import get_effective_data_source, get_http_client
from openemr_mcp.schemas import Medication, MedicationListResponse

MOCK_MEDICATIONS: dict = {
    "p001": [
        Medication(drug="Lisinopril", dosage="10 mg", status="active"),
        Medication(drug="Metformin", dosage="500 mg", status="active"),
    ],
    "p004": [
        Medication(drug="Atorvastatin", dosage="40 mg", status="active"),
        Medication(drug="Amlodipine", dosage="5 mg", status="active"),
        Medication(drug="Aspirin", dosage="81 mg", status="active"),
    ],
    "p005": [Medication(drug="Levothyroxine", dosage="50 mcg", status="active")],
    "p006": [
        Medication(drug="Warfarin", dosage="5 mg", status="active"),
        Medication(drug="Digoxin", dosage="0.125 mg", status="active"),
        Medication(drug="Furosemide", dosage="40 mg", status="active"),
        Medication(drug="Potassium Chloride", dosage="20 mEq", status="active"),
    ],
    "p008": [
        Medication(drug="Insulin Glargine", dosage="20 units", status="active"),
        Medication(drug="Metoprolol Succinate", dosage="50 mg", status="active"),
        Medication(drug="Lisinopril", dosage="20 mg", status="active"),
        Medication(drug="Atorvastatin", dosage="80 mg", status="active"),
        Medication(drug="Aspirin", dosage="81 mg", status="active"),
    ],
    "p009": [
        Medication(drug="Sertraline", dosage="100 mg", status="active"),
        Medication(drug="Lorazepam", dosage="0.5 mg", status="active"),
    ],
    "p010": [
        Medication(drug="Omeprazole", dosage="20 mg", status="active"),
        Medication(drug="Ibuprofen", dosage="400 mg", status="active"),
    ],
    "p012": [
        Medication(drug="Metformin", dosage="1000 mg", status="active"),
        Medication(drug="Glipizide", dosage="5 mg", status="active"),
        Medication(drug="Lisinopril", dosage="40 mg", status="active"),
    ],
    "p013": [
        Medication(drug="Escitalopram", dosage="10 mg", status="active"),
        Medication(drug="Gabapentin", dosage="300 mg", status="active"),
    ],
    "p016": [
        Medication(drug="Amlodipine", dosage="10 mg", status="active"),
        Medication(drug="Hydrochlorothiazide", dosage="25 mg", status="active"),
        Medication(drug="Losartan", dosage="50 mg", status="active"),
    ],
    "p019": [
        Medication(drug="Prednisone", dosage="10 mg", status="active"),
        Medication(drug="Methotrexate", dosage="15 mg", status="active"),
        Medication(drug="Folic Acid", dosage="1 mg", status="active"),
    ],
    "p022": [
        Medication(drug="Donepezil", dosage="10 mg", status="active"),
        Medication(drug="Memantine", dosage="10 mg", status="active"),
    ],
    "p024": [
        Medication(drug="Albuterol Inhaler", dosage="90 mcg", status="active"),
        Medication(drug="Fluticasone Nasal Spray", dosage="50 mcg", status="active"),
        Medication(drug="Montelukast", dosage="10 mg", status="active"),
    ],
    "p041": [
        Medication(drug="Atorvastatin", dosage="40 mg", status="active"),
        Medication(drug="Metformin", dosage="1000 mg", status="active"),
    ],
}


def _normalize_patient_id(patient_id: str) -> str:
    s = (patient_id or "").strip().lower()
    if not s:
        return ""
    if s.startswith("p"):
        return s
    try:
        return "p" + str(int(s))
    except ValueError:
        return s


def run_medication_list(patient_id: str) -> MedicationListResponse:
    pid_raw = (patient_id or "").strip()
    if not pid_raw:
        return MedicationListResponse(patient_id="", medications=[])
    pid = _normalize_patient_id(pid_raw)
    ds = get_effective_data_source()
    if ds == "api":
        from openemr_mcp.repositories.fhir_api import get_medications_api

        meds = get_medications_api(pid_raw, get_http_client())
        return MedicationListResponse(patient_id=pid, medications=meds)
    meds = MOCK_MEDICATIONS.get(pid, [])
    return MedicationListResponse(patient_id=pid, medications=meds)
