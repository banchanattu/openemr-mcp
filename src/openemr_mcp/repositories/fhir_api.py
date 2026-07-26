"""
FHIR R4 API repositories: patient, medication, appointment, provider, trajectory.
Maps FHIR Bundle responses to domain models.
"""

import re
from typing import Any

from openemr_mcp.repositories._errors import ToolError
from openemr_mcp.schemas import Appointment, Medication, PatientCreate, PatientMatch, Provider, TrajectoryPoint

FHIR_PATIENT_PAGE_SIZE = "200"
FHIR_PATIENT_MAX_PAGES = 25


def _patient_id_from_fhir_id(resource_id: str) -> str:
    if not resource_id:
        return ""
    s = str(resource_id).strip()
    if s.startswith("p"):
        return s
    try:
        return "p" + str(int(s))
    except (ValueError, TypeError):
        return "p" + s


def _full_name_from_fhir_name(name_list: Any) -> str | None:
    if not name_list or not isinstance(name_list, list):
        return None
    parts = []
    for n in name_list:
        if not isinstance(n, dict):
            continue
        given = n.get("given")
        if isinstance(given, list) and given:
            parts.extend(given)
        elif isinstance(given, str):
            parts.append(given)
        family = n.get("family")
        if family:
            parts.append(family)
    return " ".join(parts).strip() or None


def _bundle_entries(bundle: Any) -> list[dict[str, Any]]:
    entries = bundle.get("entry") if isinstance(bundle, dict) else None
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _next_link(bundle: Any) -> str | None:
    links = bundle.get("link") if isinstance(bundle, dict) else None
    if not isinstance(links, list):
        return None
    for link in links:
        if not isinstance(link, dict):
            continue
        if link.get("relation") != "next":
            continue
        url = link.get("url")
        if isinstance(url, str) and url.strip():
            return url.strip()
    return None


def _search_patient_bundles(params: dict[str, str] | None, http_client: Any) -> list[dict[str, Any]]:
    bundle = http_client.get_fhir("Patient", params=params)
    entries = _bundle_entries(bundle)
    next_url = _next_link(bundle)
    pages_fetched = 1
    while next_url and pages_fetched < FHIR_PATIENT_MAX_PAGES:
        bundle = http_client.get_fhir_url(next_url)
        entries.extend(_bundle_entries(bundle))
        next_url = _next_link(bundle)
        pages_fetched += 1
    return entries


def search_patients_api(query: str, http_client: Any) -> list[PatientMatch]:
    q = (query or "").strip()
    parts = q.split()
    try:
        if not q:
            entries = _search_patient_bundles({"_count": FHIR_PATIENT_PAGE_SIZE}, http_client)
        elif len(parts) == 1:
            entries = _search_patient_bundles({"name": q, "_count": FHIR_PATIENT_PAGE_SIZE}, http_client)
        else:
            given = parts[0]
            family = parts[-1]
            entries = _search_patient_bundles({"given": given, "family": family, "_count": FHIR_PATIENT_PAGE_SIZE}, http_client)
            if not entries:
                entries = _search_patient_bundles({"name": family, "_count": FHIR_PATIENT_PAGE_SIZE}, http_client)
    except ToolError:
        raise
    if not entries:
        return []
    out = []
    for entry in entries:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not resource or not isinstance(resource, dict):
            continue
        if resource.get("resourceType") != "Patient":
            continue
        pid = _patient_id_from_fhir_id(resource.get("id"))
        if not pid:
            continue
        full_name = _full_name_from_fhir_name(resource.get("name")) or "Unknown"
        dob = resource.get("birthDate")
        if dob is not None:
            dob = str(dob).strip() or None
        sex = resource.get("gender")
        if sex is not None:
            sex = str(sex).strip() or None
        city = None
        addr = resource.get("address")
        if isinstance(addr, list) and len(addr) > 0 and isinstance(addr[0], dict):
            city = addr[0].get("city")
            if city is not None:
                city = str(city).strip() or None
        out.append(PatientMatch(patient_id=pid, full_name=full_name, dob=dob, sex=sex, city=city))
    return out


def get_patient_by_pid_api(pid: int, http_client: Any) -> PatientMatch | None:
    try:
        resource = http_client.get_fhir(f"Patient/{pid}")
    except ToolError:
        raise
    if not isinstance(resource, dict) or resource.get("resourceType") != "Patient":
        return None
    fhir_id = resource.get("id")
    if not fhir_id:
        return None
    patient_id = _patient_id_from_fhir_id(fhir_id)
    full_name = _full_name_from_fhir_name(resource.get("name")) or "Unknown"
    dob = resource.get("birthDate")
    if dob is not None:
        dob = str(dob).strip() or None
    sex = resource.get("gender")
    if sex is not None:
        sex = str(sex).strip() or None
    city = None
    addr = resource.get("address")
    if isinstance(addr, list) and len(addr) > 0 and isinstance(addr[0], dict):
        city = addr[0].get("city")
        if city is not None:
            city = str(city).strip() or None
    return PatientMatch(patient_id=patient_id, full_name=full_name, dob=dob, sex=sex, city=city)


def create_patient_api(payload: PatientCreate, http_client: Any) -> PatientMatch:
    resource = {
        "resourceType": "Patient",
        "active": True,
        "name": [
            {
                "use": "official",
                "given": [payload.first_name],
                "family": payload.last_name,
            }
        ],
        "birthDate": payload.date_of_birth,
        "gender": payload.birth_sex.lower(),
    }
    created = http_client.post_fhir("Patient", resource)
    if not isinstance(created, dict):
        raise ToolError("FHIR API returned an invalid Patient create response.")
    created_id = created.get("id") or created.get("uuid")
    patient_id = _patient_id_from_fhir_id(created_id)
    if not patient_id:
        raise ToolError("FHIR API create response missing patient id.")
    full_name = _full_name_from_fhir_name(created.get("name")) or f"{payload.first_name} {payload.last_name}"
    city = None
    addr = created.get("address")
    if isinstance(addr, list) and addr and isinstance(addr[0], dict):
        city = addr[0].get("city")
        if city is not None:
            city = str(city).strip() or None
    return PatientMatch(
        patient_id=patient_id,
        full_name=full_name,
        dob=str(created.get("birthDate") or payload.date_of_birth),
        sex=str(created.get("gender") or payload.birth_sex).strip().title(),
        city=city,
    )


def _fhir_patient_ref(patient_id_str: str) -> str | None:
    s = (patient_id_str or "").strip().lower()
    if not s:
        return None
    raw = s[1:] if s.startswith("p") else s
    if not raw:
        return None
    try:
        return f"Patient/{int(raw)}"
    except (ValueError, TypeError):
        pass
    return f"Patient/{raw}"


def _dosage_from_fhir(dosage_instruction: Any) -> str | None:
    if not dosage_instruction or not isinstance(dosage_instruction, list):
        return None
    first = dosage_instruction[0]
    if not isinstance(first, dict):
        return None
    dr_list = first.get("doseAndRate")
    if not isinstance(dr_list, list) or not dr_list:
        return None
    dr = dr_list[0]
    if not isinstance(dr, dict):
        return None
    dq = dr.get("doseQuantity")
    if not isinstance(dq, dict):
        return None
    value = dq.get("value")
    unit = dq.get("unit")
    parts = []
    if value is not None:
        parts.append(str(value))
    if unit:
        parts.append(str(unit).strip())
    return " ".join(parts).strip() or None


def get_medications_api(patient_id_str: str, http_client: Any) -> list[Medication]:
    patient_ref = _fhir_patient_ref(patient_id_str)
    if patient_ref is None:
        return []
    try:
        bundle = http_client.get_fhir("MedicationRequest", params={"patient": patient_ref})
    except ToolError:
        raise
    entries = bundle.get("entry") if isinstance(bundle, dict) else None
    if not entries or not isinstance(entries, list):
        return []
    out = []
    for entry in entries:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not resource or not isinstance(resource, dict):
            continue
        if resource.get("resourceType") != "MedicationRequest":
            continue
        mcc = resource.get("medicationCodeableConcept")
        drug = "Unknown"
        if isinstance(mcc, dict):
            text = mcc.get("text")
            if text:
                drug = str(text).strip() or "Unknown"
            else:
                coding = mcc.get("coding")
                if isinstance(coding, list) and coding and isinstance(coding[0], dict):
                    display = coding[0].get("display") or coding[0].get("code")
                    if display:
                        drug = str(display).strip() or "Unknown"
        dosage = _dosage_from_fhir(resource.get("dosageInstruction"))
        status = resource.get("status")
        if status is not None:
            status = str(status).strip().lower()
        if status not in ("active", "inactive", "completed"):
            status = "active"
        out.append(Medication(drug=drug, dosage=dosage, status=status))
    return out


def get_appointments_api(patient_id_str: str, http_client: Any) -> list[Appointment]:
    s = (patient_id_str or "").strip().lower()
    if not s:
        return []
    raw = s[1:] if s.startswith("p") else s
    if not raw:
        return []
    try:
        pid_int = int(raw)
        try:
            data = http_client.get_rest(f"appointment/{pid_int}")
        except ToolError:
            raise
        items: Any = data
        if isinstance(data, dict):
            items = data.get("data") or data.get("appointments") or []
        if not isinstance(items, list):
            return []
        out = []
        for item in items:
            if not isinstance(item, dict):
                continue
            appt_id = item.get("pc_eid") or item.get("id")
            appt_pid = item.get("pc_pid") or item.get("patient_id") or pid_int
            date_str = str(item.get("pc_eventDate") or item.get("date") or "").strip()
            time_str = str(item.get("pc_startTime") or item.get("start_time") or "").strip()
            if date_str and len(date_str) >= 10:
                start_time = f"{date_str[:10]}T{time_str or '00:00:00'}"
            else:
                start_time = ""
            reason = str(item.get("pc_title") or item.get("reason") or "").strip() or None
            provider_aid = item.get("pc_aid") or item.get("provider_id")
            provider_id = "prov" + str(provider_aid) if provider_aid else None
            pf = str(item.get("provider_fname") or "").strip()
            pl = str(item.get("provider_lname") or "").strip()
            name_parts = [n for n in [pf, pl] if n]
            provider_name = "Dr. " + " ".join(name_parts) if name_parts else None
            out.append(
                Appointment(
                    appointment_id="a" + str(appt_id) if appt_id else "",
                    patient_id="p" + str(appt_pid),
                    start_time=start_time,
                    reason=reason,
                    provider_id=provider_id,
                    provider_name=provider_name,
                )
            )
        return out
    except (ValueError, TypeError):
        pass
    # UUID path
    patient_ref = f"Patient/{raw}"
    try:
        bundle = http_client.get_fhir("Appointment", params={"patient": patient_ref})
    except ToolError:
        raise
    entries = bundle.get("entry") if isinstance(bundle, dict) else None
    if not entries or not isinstance(entries, list):
        return []
    out = []
    for entry in entries:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not resource or not isinstance(resource, dict):
            continue
        if resource.get("resourceType") != "Appointment":
            continue
        appt_id = str(resource.get("id") or "").strip()
        start = str(resource.get("start") or "").strip()
        start_time = start[:19] if len(start) >= 19 else start
        reason_list = resource.get("reasonCode") or resource.get("serviceType") or []
        reason = None
        if isinstance(reason_list, list) and reason_list:
            first = reason_list[0]
            if isinstance(first, dict):
                cc = first.get("coding") or []
                if cc and isinstance(cc, list):
                    reason = str(cc[0].get("display") or "").strip() or None
                reason = reason or str(first.get("text") or "").strip() or None
        description = str(resource.get("description") or "").strip()
        reason = reason or description or None
        provider_id = None
        provider_name = None
        for participant in resource.get("participant") or []:
            actor = participant.get("actor") if isinstance(participant, dict) else None
            if not isinstance(actor, dict):
                continue
            ref = str(actor.get("reference") or "")
            display = str(actor.get("display") or "").strip()
            if "Practitioner" in ref:
                pid_ref = ref.split("/")[-1] if "/" in ref else ref
                provider_id = "prov" + pid_ref
                provider_name = ("Dr. " + display) if display and not display.startswith("Dr.") else display or None
                break
        out.append(
            Appointment(
                appointment_id="a" + appt_id if appt_id else "",
                patient_id="p" + raw,
                start_time=start_time,
                reason=reason,
                provider_id=provider_id,
                provider_name=provider_name,
            )
        )
    return out


def search_providers_api(specialty: str | None, location: str | None, http_client: Any) -> list[Provider]:
    params: dict = {}
    if specialty and specialty.strip():
        params["specialty"] = specialty.strip()
    try:
        bundle = http_client.get_fhir("Practitioner", params=params or None)
    except ToolError:
        raise
    entries = bundle.get("entry") if isinstance(bundle, dict) else None
    if not entries or not isinstance(entries, list):
        return []
    spec_lower = specialty.strip().lower() if specialty and specialty.strip() else None
    loc_lower = location.strip().lower() if location and location.strip() else None
    out = []
    for entry in entries:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not resource or not isinstance(resource, dict):
            continue
        if resource.get("resourceType") != "Practitioner":
            continue
        resource_id = str(resource.get("id") or "").strip()
        if not resource_id:
            continue
        provider_id = "prov" + resource_id
        full_name = _full_name_from_fhir_name(resource.get("name")) or "Unknown"
        if full_name != "Unknown" and not full_name.startswith("Dr."):
            full_name = "Dr. " + full_name
        spec_val = "General"
        qualifications = resource.get("qualification")
        if isinstance(qualifications, list):
            for q in qualifications:
                if not isinstance(q, dict):
                    continue
                code = q.get("code")
                if isinstance(code, dict):
                    coding = code.get("coding")
                    if isinstance(coding, list) and coding:
                        display = coding[0].get("display") or coding[0].get("code") or ""
                        if display:
                            spec_val = str(display).strip()
                            break
                    text = code.get("text")
                    if text:
                        spec_val = str(text).strip()
                        break
        loc_val = ""
        for ext in resource.get("extension") or []:
            if not isinstance(ext, dict):
                continue
            url = ext.get("url") or ""
            if "facility" in url.lower() or "location" in url.lower():
                loc_val = str(ext.get("valueString") or "").strip()
                break
        if not loc_val:
            addr = resource.get("address")
            if isinstance(addr, list) and addr and isinstance(addr[0], dict):
                loc_val = str(addr[0].get("city") or "").strip()
        if spec_lower and spec_lower not in spec_val.lower():
            continue
        if loc_lower and loc_lower not in loc_val.lower():
            continue
        out.append(
            Provider(
                provider_id=provider_id,
                full_name=full_name,
                specialty=spec_val,
                location=loc_val,
                accepting_new_patients=True,
            )
        )
    return out


# ---------------------------------------------------------------------------
# LOINC / observation maps
# ---------------------------------------------------------------------------
_LOINC_METRIC_MAP: dict = {
    "4548-4": ("a1c", "%"),
    "4549-2": ("a1c", "%"),
    "17856-6": ("a1c", "%"),
    "13457-7": ("ldl", "mg/dL"),
    "18262-6": ("ldl", "mg/dL"),
    "2089-1": ("ldl", "mg/dL"),
    "33914-3": ("egfr", "mL/min/1.73m²"),
    "62238-1": ("egfr", "mL/min/1.73m²"),
    "29463-7": ("weight", "kg"),
    "8480-6": ("bp_systolic", "mmHg"),
    "8462-4": ("bp_diastolic", "mmHg"),
    "85354-9": ("bp_panel", ""),
}
_LOCAL_CODE_ALIASES: dict = {
    "HBA1C": ("a1c", "%"),
    "A1C": ("a1c", "%"),
    "LDL": ("ldl", "mg/dL"),
    "LDL-C": ("ldl", "mg/dL"),
    "EGFR": ("egfr", "mL/min/1.73m²"),
    "GFR": ("egfr", "mL/min/1.73m²"),
    "WEIGHT": ("weight", "kg"),
    "WT": ("weight", "kg"),
    "SYSTOLIC": ("bp_systolic", "mmHg"),
    "DIASTOLIC": ("bp_diastolic", "mmHg"),
}


def _resolve_metric_from_coding(coding_list: Any) -> tuple | None:
    if not isinstance(coding_list, list):
        return None
    for coding in coding_list:
        if not isinstance(coding, dict):
            continue
        code = str(coding.get("code") or "").strip()
        if code in _LOINC_METRIC_MAP:
            return _LOINC_METRIC_MAP[code]
        code_upper = code.upper()
        if code_upper in _LOCAL_CODE_ALIASES:
            return _LOCAL_CODE_ALIASES[code_upper]
    return None


def _extract_observation_value(resource: dict) -> tuple | None:
    vq = resource.get("valueQuantity")
    if isinstance(vq, dict):
        val = vq.get("value")
        unit = str(vq.get("unit") or vq.get("code") or "").strip()
        if val is not None:
            try:
                return (float(val), unit)
            except (ValueError, TypeError):
                pass
    vs = resource.get("valueString")
    if vs:
        m = re.match(r"([\d.]+)", str(vs).strip())
        if m:
            try:
                return (float(m.group(1)), "")
            except ValueError:
                pass
    return None


def _effective_datetime(resource: dict) -> str:
    edt = resource.get("effectiveDateTime")
    if edt:
        return str(edt).strip()
    ep = resource.get("effectivePeriod")
    if isinstance(ep, dict) and ep.get("start"):
        return str(ep["start"]).strip()
    issued = resource.get("issued")
    if issued:
        return str(issued).strip()
    return ""


def _parse_bp_panel(resource: dict, effective: str) -> list[TrajectoryPoint]:
    points: list[TrajectoryPoint] = []
    for comp in resource.get("component") or []:
        if not isinstance(comp, dict):
            continue
        cc = comp.get("code") or {}
        coding = cc.get("coding") if isinstance(cc, dict) else None
        resolved = _resolve_metric_from_coding(coding)
        if resolved is None:
            continue
        metric, default_unit = resolved
        if metric not in ("bp_systolic", "bp_diastolic"):
            continue
        vq = comp.get("valueQuantity")
        if isinstance(vq, dict) and vq.get("value") is not None:
            try:
                val = float(vq["value"])
                unit = str(vq.get("unit") or default_unit).strip()
                points.append(
                    TrajectoryPoint(
                        metric=metric,
                        value=val,
                        unit=unit or default_unit,
                        effective_at=effective,
                        source="fhir_observation",
                        code="85354-9",
                    )
                )
            except (ValueError, TypeError):
                pass
    return points


def get_observation_trends_api(
    patient_id_str: str, category: str, from_date: str, code_filters: list[str] | None, http_client: Any
) -> list[TrajectoryPoint]:
    patient_ref = _fhir_patient_ref(patient_id_str)
    if patient_ref is None:
        return []
    params: dict = {
        "patient": patient_ref,
        "category": category,
        "date": f"ge{from_date}",
        "_sort": "date",
        "_count": "200",
    }
    if code_filters:
        params["code"] = ",".join(code_filters)
    try:
        bundle = http_client.get_fhir("Observation", params=params)
    except ToolError:
        raise
    entries = bundle.get("entry") if isinstance(bundle, dict) else None
    if not entries or not isinstance(entries, list):
        return []
    points: list[TrajectoryPoint] = []
    for entry in entries:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(resource, dict):
            continue
        if resource.get("resourceType") != "Observation":
            continue
        if resource.get("status") in ("cancelled", "entered-in-error"):
            continue
        cc = resource.get("code") or {}
        coding = cc.get("coding") if isinstance(cc, dict) else None
        resolved = _resolve_metric_from_coding(coding)
        if resolved is None:
            continue
        metric, default_unit = resolved
        effective = _effective_datetime(resource)
        if not effective:
            continue
        if metric == "bp_panel":
            points.extend(_parse_bp_panel(resource, effective))
            continue
        val_unit = _extract_observation_value(resource)
        if val_unit is None:
            continue
        value, unit = val_unit
        loinc_code = None
        if isinstance(coding, list):
            for c in coding:
                if isinstance(c, dict) and c.get("code"):
                    loinc_code = str(c["code"]).strip()
                    break
        points.append(
            TrajectoryPoint(
                metric=metric,
                value=value,
                unit=unit or default_unit,
                effective_at=effective,
                source="fhir_observation",
                code=loinc_code,
            )
        )
    return points


def get_questionnaire_trends_api(
    patient_id_str: str, from_date: str, questionnaire_name_filters: list[str] | None, http_client: Any
) -> list[TrajectoryPoint]:
    patient_ref = _fhir_patient_ref(patient_id_str)
    if patient_ref is None:
        return []
    params: dict = {"patient": patient_ref, "authored": f"ge{from_date}", "_sort": "authored", "_count": "100"}
    try:
        bundle = http_client.get_fhir("QuestionnaireResponse", params=params)
    except ToolError:
        raise
    entries = bundle.get("entry") if isinstance(bundle, dict) else None
    if not entries or not isinstance(entries, list):
        return []
    name_filters_lower = [f.lower() for f in (questionnaire_name_filters or ["phq"])]
    points: list[TrajectoryPoint] = []
    for entry in entries:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(resource, dict):
            continue
        if resource.get("resourceType") != "QuestionnaireResponse":
            continue
        if resource.get("status") in ("stopped", "entered-in-error"):
            continue
        q_ref = str(resource.get("questionnaire") or "").lower()
        q_title = str(resource.get("title") or "").lower()
        if not any(f in q_ref or f in q_title for f in name_filters_lower):
            continue
        authored = str(resource.get("authored") or "").strip()
        if not authored:
            continue
        score = _extract_questionnaire_total_score(resource)
        if score is None:
            continue
        points.append(
            TrajectoryPoint(metric="phq9", value=score, unit="score", effective_at=authored, source="fhir_observation")
        )
    return points


def _extract_questionnaire_total_score(resource: dict) -> float | None:
    items = resource.get("item") or []
    total_score = None
    running_sum = 0.0
    item_count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        link_id = str(item.get("linkId") or "").lower()
        answers = item.get("answer") or []
        if "total" in link_id or "score" in link_id:
            for ans in answers:
                if not isinstance(ans, dict):
                    continue
                val = ans.get("valueInteger") or ans.get("valueDecimal")
                if val is not None:
                    try:
                        total_score = float(val)
                    except (ValueError, TypeError):
                        pass
        for ans in answers:
            if not isinstance(ans, dict):
                continue
            val = ans.get("valueInteger") or ans.get("valueDecimal")
            if val is not None:
                try:
                    running_sum += float(val)
                    item_count += 1
                except (ValueError, TypeError):
                    pass
    if total_score is not None:
        return total_score
    if item_count > 0:
        return running_sum
    return None
