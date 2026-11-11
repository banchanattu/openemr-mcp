"""Lab trends tool: A1c, LDL, eGFR trajectories."""

from datetime import datetime, timedelta, timezone

from openemr_mcp.data_source import get_effective_data_source, get_http_client
from openemr_mcp.schemas import MetricTrajectory, TrajectoryPoint

LAB_METRIC_META: dict = {
    "a1c": {"display_name": "HbA1c", "unit": "%"},
    "ldl": {"display_name": "LDL Cholesterol", "unit": "mg/dL"},
    "egfr": {"display_name": "eGFR", "unit": "mL/min/1.73m²"},
}

LAB_LOINC_CODES: dict = {
    "a1c": ["4548-4", "4549-2", "17856-6"],
    "ldl": ["13457-7", "18262-6", "2089-1"],
    "egfr": ["33914-3", "62238-1"],
}

TP = TrajectoryPoint

_MOCK_LAB_DATA: dict = {
    "p001": [
        TP(metric="a1c", value=6.8, unit="%", effective_at="2024-03-01T00:00:00", source="mock", code="4548-4"),
        TP(metric="a1c", value=7.0, unit="%", effective_at="2024-09-01T00:00:00", source="mock", code="4548-4"),
        TP(metric="a1c", value=7.1, unit="%", effective_at="2025-03-01T00:00:00", source="mock", code="4548-4"),
        TP(metric="a1c", value=7.2, unit="%", effective_at="2025-09-01T00:00:00", source="mock", code="4548-4"),
        TP(metric="ldl", value=145.0, unit="mg/dL", effective_at="2024-03-01T00:00:00", source="mock", code="13457-7"),
        TP(metric="ldl", value=138.0, unit="mg/dL", effective_at="2024-09-01T00:00:00", source="mock", code="13457-7"),
        TP(metric="ldl", value=125.0, unit="mg/dL", effective_at="2025-03-01T00:00:00", source="mock", code="13457-7"),
        TP(metric="ldl", value=118.0, unit="mg/dL", effective_at="2025-09-01T00:00:00", source="mock", code="13457-7"),
        TP(
            metric="egfr",
            value=72.0,
            unit="mL/min/1.73m²",
            effective_at="2024-03-01T00:00:00",
            source="mock",
            code="33914-3",
        ),
        TP(
            metric="egfr",
            value=68.0,
            unit="mL/min/1.73m²",
            effective_at="2024-09-01T00:00:00",
            source="mock",
            code="33914-3",
        ),
        TP(
            metric="egfr",
            value=63.0,
            unit="mL/min/1.73m²",
            effective_at="2025-03-01T00:00:00",
            source="mock",
            code="33914-3",
        ),
        TP(
            metric="egfr",
            value=58.0,
            unit="mL/min/1.73m²",
            effective_at="2025-09-01T00:00:00",
            source="mock",
            code="33914-3",
        ),
    ],
    "p002": [
        TP(metric="a1c", value=8.5, unit="%", effective_at="2024-06-01T00:00:00", source="mock", code="4548-4"),
        TP(metric="a1c", value=9.1, unit="%", effective_at="2024-12-01T00:00:00", source="mock", code="4548-4"),
        TP(metric="a1c", value=9.6, unit="%", effective_at="2025-06-01T00:00:00", source="mock", code="4548-4"),
        TP(metric="ldl", value=160.0, unit="mg/dL", effective_at="2024-06-01T00:00:00", source="mock", code="13457-7"),
        TP(metric="ldl", value=185.0, unit="mg/dL", effective_at="2024-12-01T00:00:00", source="mock", code="13457-7"),
        TP(metric="ldl", value=205.0, unit="mg/dL", effective_at="2025-06-01T00:00:00", source="mock", code="13457-7"),
    ],
    "p008": [
        TP(metric="a1c", value=9.2, unit="%", effective_at="2024-01-15T00:00:00", source="mock", code="4548-4"),
        TP(metric="a1c", value=9.8, unit="%", effective_at="2024-07-15T00:00:00", source="mock", code="4548-4"),
        TP(metric="a1c", value=10.1, unit="%", effective_at="2025-01-15T00:00:00", source="mock", code="4548-4"),
        TP(
            metric="egfr",
            value=55.0,
            unit="mL/min/1.73m²",
            effective_at="2024-01-15T00:00:00",
            source="mock",
            code="33914-3",
        ),
        TP(
            metric="egfr",
            value=50.0,
            unit="mL/min/1.73m²",
            effective_at="2024-07-15T00:00:00",
            source="mock",
            code="33914-3",
        ),
        TP(
            metric="egfr",
            value=44.0,
            unit="mL/min/1.73m²",
            effective_at="2025-01-15T00:00:00",
            source="mock",
            code="33914-3",
        ),
    ],
    "p004": [
        TP(metric="a1c", value=7.6, unit="%", effective_at="2024-07-01T00:00:00", source="mock", code="4548-4"),
        TP(metric="a1c", value=8.0, unit="%", effective_at="2025-01-01T00:00:00", source="mock", code="4548-4"),
        TP(metric="a1c", value=8.2, unit="%", effective_at="2025-07-01T00:00:00", source="mock", code="4548-4"),
        TP(metric="ldl", value=138.0, unit="mg/dL", effective_at="2024-07-01T00:00:00", source="mock", code="13457-7"),
        TP(metric="ldl", value=142.0, unit="mg/dL", effective_at="2025-01-01T00:00:00", source="mock", code="13457-7"),
    ],
    "p005": [
        TP(metric="a1c", value=6.8, unit="%", effective_at="2024-05-01T00:00:00", source="mock", code="4548-4"),
        TP(metric="a1c", value=7.1, unit="%", effective_at="2024-11-01T00:00:00", source="mock", code="4548-4"),
        TP(metric="a1c", value=7.4, unit="%", effective_at="2025-05-01T00:00:00", source="mock", code="4548-4"),
        TP(metric="ldl", value=132.0, unit="mg/dL", effective_at="2024-05-01T00:00:00", source="mock", code="13457-7"),
        TP(metric="ldl", value=128.0, unit="mg/dL", effective_at="2025-05-01T00:00:00", source="mock", code="13457-7"),
    ],
    "p016": [
        TP(metric="ldl", value=148.0, unit="mg/dL", effective_at="2024-04-01T00:00:00", source="mock", code="13457-7"),
        TP(metric="ldl", value=152.0, unit="mg/dL", effective_at="2025-04-01T00:00:00", source="mock", code="13457-7"),
        TP(metric="a1c", value=5.8, unit="%", effective_at="2024-04-01T00:00:00", source="mock", code="4548-4"),
        TP(metric="a1c", value=6.1, unit="%", effective_at="2025-04-01T00:00:00", source="mock", code="4548-4"),
    ],
    "p041": [
        TP(metric="ldl", value=145.0, unit="mg/dL", effective_at="2024-06-01T00:00:00", source="mock", code="13457-7"),
        TP(metric="ldl", value=162.0, unit="mg/dL", effective_at="2024-12-01T00:00:00", source="mock", code="13457-7"),
        TP(metric="ldl", value=168.0, unit="mg/dL", effective_at="2025-06-01T00:00:00", source="mock", code="13457-7"),
        TP(metric="a1c", value=7.4, unit="%", effective_at="2024-06-01T00:00:00", source="mock", code="4548-4"),
        TP(metric="a1c", value=7.6, unit="%", effective_at="2024-12-01T00:00:00", source="mock", code="4548-4"),
        TP(metric="a1c", value=7.8, unit="%", effective_at="2025-06-01T00:00:00", source="mock", code="4548-4"),
    ],
}


def _from_date_str(window_months: int) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_months * 30)
    return cutoff.strftime("%Y-%m-%d")


def _build_trajectory(metric: str, points: list[TrajectoryPoint], window_months: int) -> MetricTrajectory:
    meta = LAB_METRIC_META.get(metric, {"display_name": metric, "unit": ""})
    sorted_pts = sorted(points, key=lambda p: p.effective_at)
    latest = sorted_pts[-1].value if sorted_pts else None
    previous = sorted_pts[0].value if len(sorted_pts) > 1 else None
    delta_abs = round(latest - previous, 4) if latest is not None and previous is not None else None
    delta_pct = round((delta_abs / previous) * 100, 2) if delta_abs is not None and previous and previous != 0 else None
    return MetricTrajectory(
        metric=metric,
        display_name=meta["display_name"],
        unit=meta["unit"],
        window_months=window_months,
        points=sorted_pts,
        latest_value=latest,
        previous_value=previous,
        delta_abs=delta_abs,
        delta_pct=delta_pct,
    )


def run_lab_trends(
    patient_id: str, metrics: list[str] | None = None, window_months: int = 24
) -> list[MetricTrajectory]:
    """Return lab metric trajectories for a patient over the given window."""
    target_metrics = metrics or list(LAB_METRIC_META.keys())
    from_date = _from_date_str(window_months)
    ds = get_effective_data_source()
    raw_points: list[TrajectoryPoint] = []
    if ds == "api":
        from openemr_mcp.repositories.fhir_api import get_observation_trends_api

        codes = []
        for m in target_metrics:
            codes.extend(LAB_LOINC_CODES.get(m, []))
        raw_points = get_observation_trends_api(patient_id, "laboratory", from_date, codes or None, get_http_client())
    else:
        pid = patient_id.lower()
        if not pid.startswith("p"):
            pid = "p" + (pid.lstrip("0") or "0")
        all_mock = _MOCK_LAB_DATA.get(pid, [])
        raw_points = [p for p in all_mock if p.effective_at >= from_date]
    grouped: dict = {m: [] for m in target_metrics}
    for pt in raw_points:
        if pt.metric in grouped:
            grouped[pt.metric].append(pt)
    return [_build_trajectory(metric, pts, window_months) for metric, pts in grouped.items()]
