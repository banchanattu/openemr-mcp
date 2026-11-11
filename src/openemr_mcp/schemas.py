"""All Pydantic schemas for openemr-mcp tools."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------


class PatientMatch(BaseModel):
    patient_id: str
    full_name: str
    dob: str | None = None
    sex: str | None = None
    city: str | None = None


class PatientCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: str = Field(..., min_length=10, max_length=10)
    birth_sex: str = Field(..., min_length=1, max_length=20)


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------


class Appointment(BaseModel):
    appointment_id: str
    patient_id: str
    start_time: str
    reason: str | None = None
    provider_id: str | None = None
    provider_name: str | None = None


class AppointmentCreate(BaseModel):
    patient_id: str = Field(..., min_length=1, max_length=100)
    category_id: str = Field(default="5", min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    duration: str = Field(default="900", min_length=1, max_length=100)
    comments: str = Field(..., min_length=1, max_length=1000)
    appointment_status: str = Field(default="^", min_length=1, max_length=50)
    event_date: str = Field(..., min_length=10, max_length=10)
    start_time: str = Field(..., min_length=5, max_length=8)
    facility_id: str = Field(default="9", min_length=1, max_length=100)
    billing_location_id: str = Field(default="10", min_length=1, max_length=100)
    provider_id: str | None = Field(default=None, min_length=1, max_length=100)


class AppointmentCreateResult(BaseModel):
    appointment_id: str | None = None
    patient_id: str
    status: str
    start_time: str | None = None
    reason: str | None = None
    provider_id: str | None = None
    message: str | None = None
    raw_data: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Medications & Drug Interactions
# ---------------------------------------------------------------------------


class Medication(BaseModel):
    drug: str
    dosage: str | None = None
    status: str  # "active" | "inactive"


class MedicationListResponse(BaseModel):
    patient_id: str
    medications: list[Medication]


class DrugInteraction(BaseModel):
    drug_a: str
    drug_b: str
    severity: Literal["HIGH", "MODERATE", "LOW"]
    description: str


class DrugInteractionResponse(BaseModel):
    medications_checked: list[str]
    interactions: list[DrugInteraction]
    has_critical: bool


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


class Provider(BaseModel):
    provider_id: str
    full_name: str
    specialty: str
    location: str
    accepting_new_patients: bool


class ProviderSearchResponse(BaseModel):
    providers: list[Provider]
    specialty_queried: str = ""
    location_queried: str = ""


# ---------------------------------------------------------------------------
# Symptoms
# ---------------------------------------------------------------------------


class PossibleCondition(BaseModel):
    name: str
    likelihood: Literal["HIGH", "MODERATE", "LOW"]
    urgency: Literal["URGENT", "SEE_DOCTOR", "MONITOR"]


class SymptomLookupResponse(BaseModel):
    symptoms_checked: list[str]
    possible_conditions: list[PossibleCondition]
    urgency_level: Literal["URGENT", "SEE_DOCTOR", "MONITOR"]
    disclaimer: str


# ---------------------------------------------------------------------------
# Drug Safety Flags
# ---------------------------------------------------------------------------


class DrugSafetyFlag(BaseModel):
    id: str
    patient_id: str
    drug_name: str
    flag_type: Literal["adverse_event", "recall", "warning", "contraindication", "custom"]
    severity: Literal["HIGH", "MODERATE", "LOW"]
    source: Literal["FDA_FAERS", "FDA_LABEL", "FDA_RECALL", "CLINICIAN", "AGENT"]
    description: str
    status: Literal["active", "resolved", "under_review"] = "active"
    created_at: str
    updated_at: str
    created_by: str = "agent"


class DrugSafetyFlagCreate(BaseModel):
    patient_id: str = Field(..., min_length=1, max_length=50)
    drug_name: str = Field(..., min_length=1, max_length=200)
    flag_type: Literal["adverse_event", "recall", "warning", "contraindication", "custom"] = "adverse_event"
    severity: Literal["HIGH", "MODERATE", "LOW"] = "MODERATE"
    source: Literal["FDA_FAERS", "FDA_LABEL", "FDA_RECALL", "CLINICIAN", "AGENT"] = "AGENT"
    description: str = Field(..., min_length=1, max_length=1000)
    created_by: str = "agent"


class DrugSafetyFlagUpdate(BaseModel):
    severity: Literal["HIGH", "MODERATE", "LOW"] | None = None
    description: str | None = None
    status: Literal["active", "resolved", "under_review"] | None = None


class DrugSafetyFlagListResponse(BaseModel):
    patient_id: str
    flags: list[DrugSafetyFlag]
    active_count: int
    high_severity_count: int


# ---------------------------------------------------------------------------
# FDA Drug Safety
# ---------------------------------------------------------------------------


class FDAAdverseEvent(BaseModel):
    reaction: str
    outcome: str | None = None
    serious: bool = False
    report_count: int = 1


class FDAAdverseEventSummary(BaseModel):
    drug_name: str
    total_reports: int
    serious_reports: int
    top_reactions: list[FDAAdverseEvent]
    data_source: str = "FDA FAERS (OpenFDA)"
    disclaimer: str = (
        "This data is from FDA's Adverse Event Reporting System (FAERS). "
        "Reports are voluntary and may not reflect actual incidence rates. "
        "For clinical decisions, consult a licensed pharmacist or physician."
    )


class FDADrugLabelResult(BaseModel):
    drug_name: str
    brand_names: list[str] = []
    generic_name: str | None = None
    boxed_warning: str | None = None
    warnings: str | None = None
    contraindications: str | None = None
    indications_and_usage: str | None = None
    manufacturer: str | None = None
    data_source: str = "FDA Drug Label (OpenFDA)"
    has_boxed_warning: bool = False


# ---------------------------------------------------------------------------
# Trajectory / Health Trends
# ---------------------------------------------------------------------------


class TrajectoryPoint(BaseModel):
    metric: str
    value: float
    unit: str
    effective_at: str
    source: Literal[
        "fhir_observation",
        "form_vitals",
        "procedure_result",
        "questionnaire_response",
        "mock",
    ]
    code: str | None = None


class MetricTrajectory(BaseModel):
    metric: str
    display_name: str
    unit: str
    window_months: int
    points: list[TrajectoryPoint]
    latest_value: float | None = None
    previous_value: float | None = None
    delta_abs: float | None = None
    delta_pct: float | None = None


class DriftAlert(BaseModel):
    metric: str
    severity: Literal["info", "moderate", "high"]
    title: str
    rationale: str
    evidence_points: list[TrajectoryPoint] = Field(default_factory=list)


class HealthTrajectoryResponse(BaseModel):
    patient_id: str
    generated_at: str
    window_months: int
    trajectories: list[MetricTrajectory]
    alerts: list[DriftAlert]
    data_gaps: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Visit Prep
# ---------------------------------------------------------------------------


class EvidenceItem(BaseModel):
    evidence_id: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    summary: str = Field(default="")


class EvidenceStore(BaseModel):
    items: list[EvidenceItem] = Field(default_factory=list)


class Claim(BaseModel):
    text: str = Field(..., min_length=1)
    evidence_ids: list[str] = Field(..., min_length=1)

    @field_validator("evidence_ids")
    @classmethod
    def evidence_ids_non_empty_elements(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("evidence_ids must be non-empty")
        for eid in v:
            if not (eid and eid.strip()):
                raise ValueError("evidence_ids must not contain empty strings")
        return v


class Abstention(BaseModel):
    reason_code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    missing_evidence_keys: list[str] = Field(...)


class VisitPrepSection(BaseModel):
    claims: list[Claim] = Field(default_factory=list)
    abstentions: list[Abstention] = Field(default_factory=list)


class VisitPrepBrief(BaseModel):
    top_risks: VisitPrepSection
    changes_since_last_visit: VisitPrepSection
    medication_safety: VisitPrepSection
    care_gaps: VisitPrepSection
    agenda: VisitPrepSection
    abstentions: VisitPrepSection


class VisitPrepMetadata(BaseModel):
    patient_id: str = Field(..., min_length=1)
    window_months: int = Field(..., ge=1, le=36)
    generated_at: str = Field(..., min_length=1)


class VisitPrepResponse(BaseModel):
    brief: VisitPrepBrief
    metadata: VisitPrepMetadata
    evidence_store: EvidenceStore = Field(default_factory=EvidenceStore)
