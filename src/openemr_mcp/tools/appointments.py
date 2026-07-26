"""Appointment list tool."""

from openemr_mcp.data_source import get_effective_data_source, get_http_client
from openemr_mcp.schemas import Appointment

MOCK_APPOINTMENTS: list[Appointment] = [
    Appointment(
        appointment_id="a100",
        patient_id="p001",
        start_time="2026-02-25T10:00:00-08:00",
        reason="Annual checkup",
        provider_id="prov006",
        provider_name="Dr. Robert Kim",
    ),
    Appointment(
        appointment_id="a101",
        patient_id="p001",
        start_time="2026-03-10T14:30:00-08:00",
        reason="Follow-up",
        provider_id="prov006",
        provider_name="Dr. Robert Kim",
    ),
    Appointment(
        appointment_id="a200",
        patient_id="p003",
        start_time="2026-02-28T09:15:00-08:00",
        reason="Lab review",
        provider_id="prov005",
        provider_name="Dr. Elena Vasquez",
    ),
    Appointment(
        appointment_id="a300",
        patient_id="p004",
        start_time="2026-03-05T08:30:00-05:00",
        reason="Cardiology consult",
        provider_id="prov002",
        provider_name="Dr. Marcus Johnson",
    ),
    Appointment(
        appointment_id="a301",
        patient_id="p004",
        start_time="2026-04-01T10:00:00-05:00",
        reason="Stress test",
        provider_id="prov002",
        provider_name="Dr. Marcus Johnson",
    ),
    Appointment(
        appointment_id="a400",
        patient_id="p005",
        start_time="2026-03-12T11:00:00-06:00",
        reason="Thyroid follow-up",
        provider_id="prov004",
        provider_name="Dr. James Okafor",
    ),
    Appointment(
        appointment_id="a500",
        patient_id="p006",
        start_time="2026-03-03T09:00:00-08:00",
        reason="INR check",
        provider_id="prov001",
        provider_name="Dr. Sarah Chen",
    ),
    Appointment(
        appointment_id="a501",
        patient_id="p006",
        start_time="2026-03-17T09:00:00-08:00",
        reason="INR check",
        provider_id="prov001",
        provider_name="Dr. Sarah Chen",
    ),
    Appointment(
        appointment_id="a600",
        patient_id="p008",
        start_time="2026-03-07T13:00:00-06:00",
        reason="Diabetes management",
        provider_id="prov004",
        provider_name="Dr. James Okafor",
    ),
    Appointment(
        appointment_id="a700",
        patient_id="p009",
        start_time="2026-03-20T15:00:00-05:00",
        reason="Psychiatry follow-up",
        provider_id="prov007",
        provider_name="Dr. Amelia Torres",
    ),
    Appointment(
        appointment_id="a800",
        patient_id="p012",
        start_time="2026-03-11T08:00:00-07:00",
        reason="A1C lab draw",
        provider_id="prov003",
        provider_name="Dr. Priya Patel",
    ),
    Appointment(
        appointment_id="a900",
        patient_id="p013",
        start_time="2026-03-14T14:00:00-06:00",
        reason="Pain management",
        provider_id="prov011",
        provider_name="Dr. Fatima Hassan",
    ),
    Appointment(
        appointment_id="a1000",
        patient_id="p015",
        start_time="2026-03-06T10:00:00-05:00",
        reason="Well-woman exam",
        provider_id="prov015",
        provider_name="Dr. Mei Li",
    ),
    Appointment(
        appointment_id="a1100",
        patient_id="p016",
        start_time="2026-03-09T11:30:00-05:00",
        reason="Blood pressure check",
        provider_id="prov006",
        provider_name="Dr. Robert Kim",
    ),
    Appointment(
        appointment_id="a1200",
        patient_id="p019",
        start_time="2026-03-18T09:00:00-08:00",
        reason="Rheumatology follow-up",
        provider_id="prov009",
        provider_name="Dr. Linda Park",
    ),
    Appointment(
        appointment_id="a1300",
        patient_id="p022",
        start_time="2026-03-25T10:00:00-05:00",
        reason="Neurology consult",
        provider_id="prov010",
        provider_name="Dr. Carlos Meza",
    ),
    Appointment(
        appointment_id="a1400",
        patient_id="p023",
        start_time="2026-03-15T13:30:00-05:00",
        reason="New patient intake",
        provider_id="prov005",
        provider_name="Dr. Elena Vasquez",
    ),
    Appointment(
        appointment_id="a1500",
        patient_id="p024",
        start_time="2026-03-08T09:45:00-08:00",
        reason="Asthma follow-up",
        provider_id="prov012",
        provider_name="Dr. William Grant",
    ),
]


def run_appointment_list(patient_id: str) -> list[Appointment]:
    pid = (patient_id or "").strip()
    if not pid:
        return []
    ds = get_effective_data_source()
    if ds == "api":
        from openemr_mcp.repositories.fhir_api import get_appointments_api

        return get_appointments_api(pid, get_http_client())
    return [a for a in MOCK_APPOINTMENTS if a.patient_id == pid]
