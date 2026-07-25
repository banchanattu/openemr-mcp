"""Patient search tool."""

from openemr_mcp.data_source import get_effective_data_source, get_http_client
from openemr_mcp.repositories._errors import ToolError
from openemr_mcp.schemas import PatientMatch

MOCK_PATIENTS: list[PatientMatch] = [
    PatientMatch(patient_id="p001", full_name="John Doe", dob="1985-02-10", sex="Male", city="Anytown"),
    PatientMatch(patient_id="p002", full_name="Jane Smith", dob="1990-07-22", sex="Female", city="Springfield"),
    PatientMatch(patient_id="p003", full_name="Asha Patel", dob="1978-11-03", sex="Female", city="Portland"),
    PatientMatch(patient_id="p004", full_name="Carlos Rivera", dob="1972-04-15", sex="Male", city="Miami"),
    PatientMatch(patient_id="p005", full_name="Maria Garcia", dob="1988-09-30", sex="Female", city="Houston"),
    PatientMatch(patient_id="p006", full_name="David Chen", dob="1965-12-08", sex="Male", city="San Francisco"),
    PatientMatch(patient_id="p007", full_name="Fatima Al-Hassan", dob="1995-01-20", sex="Female", city="Dearborn"),
    PatientMatch(patient_id="p008", full_name="Robert Williams", dob="1950-06-14", sex="Male", city="Chicago"),
    PatientMatch(patient_id="p009", full_name="Priya Sharma", dob="1983-03-25", sex="Female", city="Edison"),
    PatientMatch(patient_id="p010", full_name="James Wilson", dob="1970-11-11", sex="Male", city="Denver"),
    PatientMatch(patient_id="p011", full_name="Yuki Tanaka", dob="1992-07-04", sex="Female", city="Seattle"),
    PatientMatch(patient_id="p012", full_name="Michael Brown", dob="1958-08-19", sex="Male", city="Phoenix"),
    PatientMatch(patient_id="p013", full_name="Linda Martinez", dob="1975-05-02", sex="Female", city="Dallas"),
    PatientMatch(patient_id="p014", full_name="Ahmed Omar", dob="1980-10-28", sex="Male", city="Minneapolis"),
    PatientMatch(patient_id="p015", full_name="Sarah O'Brien", dob="1999-02-14", sex="Female", city="Boston"),
    PatientMatch(patient_id="p016", full_name="Wei Zhang", dob="1968-01-07", sex="Male", city="New York"),
    PatientMatch(patient_id="p017", full_name="Emily Davis", dob="1993-06-18", sex="Female", city="Austin"),
    PatientMatch(patient_id="p018", full_name="Oluwaseun Adeyemi", dob="1987-12-22", sex="Male", city="Atlanta"),
    PatientMatch(patient_id="p019", full_name="Rosa Hernandez", dob="1961-09-05", sex="Female", city="Los Angeles"),
    PatientMatch(patient_id="p020", full_name="Nikolai Petrov", dob="1977-04-30", sex="Male", city="Anchorage"),
    PatientMatch(patient_id="p021", full_name="Grace Kim", dob="2001-08-12", sex="Female", city="Baltimore"),
    PatientMatch(patient_id="p022", full_name="Thomas Anderson", dob="1955-03-17", sex="Male", city="Detroit"),
    PatientMatch(patient_id="p023", full_name="Aisha Mohammed", dob="1990-11-29", sex="Female", city="Columbus"),
    PatientMatch(patient_id="p024", full_name="John Yoohoo", dob="1991-05-16", sex="Male", city="Reno"),
]


def run_patient_search(query: str) -> list[PatientMatch]:
    q = (query or "").strip()
    if not q:
        raise ToolError("No patient found.")
    ds = get_effective_data_source()
    if ds == "db":
        from openemr_mcp.repositories.patient import get_openemr_connection, search_patients

        return search_patients(q, get_openemr_connection)
    if ds == "api":
        from openemr_mcp.repositories.fhir_api import search_patients_api

        return search_patients_api(q, get_http_client())
    q_lower = q.lower()
    return [p for p in MOCK_PATIENTS if q_lower in p.full_name.lower()]


def run_get_patient_by_id(pid: int) -> PatientMatch | None:
    if pid <= 0:
        return None
    ds = get_effective_data_source()
    if ds == "db":
        from openemr_mcp.repositories.patient import get_openemr_connection, get_patient_by_id

        return get_patient_by_id(pid, get_openemr_connection)
    if ds == "api":
        from openemr_mcp.repositories.fhir_api import get_patient_by_pid_api

        return get_patient_by_pid_api(pid, get_http_client())
    pid_str_padded = f"p{pid:03d}"
    pid_str_plain = f"p{pid}"
    for p in MOCK_PATIENTS:
        if p.patient_id in (pid_str_padded, pid_str_plain):
            return p
    return None
