"""Vital trends tool: weight, BP systolic/diastolic trajectories."""

from datetime import datetime, timedelta, timezone

from openemr_mcp.data_source import get_effective_data_source, get_http_client
from openemr_mcp.schemas import MetricTrajectory, TrajectoryPoint

VITAL_METRIC_META: dict = {
    "weight": {"display_name": "Weight", "unit": "kg"},
    "bp_systolic": {"display_name": "Systolic BP", "unit": "mmHg"},
    "bp_diastolic": {"display_name": "Diastolic BP", "unit": "mmHg"},
}

VITAL_LOINC_CODES: dict = {
    "weight": ["29463-7"],
    "bp_systolic": ["8480-6", "85354-9"],
    "bp_diastolic": ["8462-4", "85354-9"],
}

TP = TrajectoryPoint

_MOCK_VITAL_DATA: dict = {
    "p001": [
        TP(metric="weight", value=82.0, unit="kg", effective_at="2024-03-01T00:00:00", source="mock"),
        TP(metric="weight", value=83.5, unit="kg", effective_at="2024-09-01T00:00:00", source="mock"),
        TP(metric="weight", value=85.0, unit="kg", effective_at="2025-03-01T00:00:00", source="mock"),
        TP(metric="weight", value=87.2, unit="kg", effective_at="2025-09-01T00:00:00", source="mock"),
        TP(metric="bp_systolic", value=128.0, unit="mmHg", effective_at="2024-03-01T00:00:00", source="mock"),
        TP(metric="bp_systolic", value=132.0, unit="mmHg", effective_at="2024-09-01T00:00:00", source="mock"),
        TP(metric="bp_systolic", value=138.0, unit="mmHg", effective_at="2025-03-01T00:00:00", source="mock"),
        TP(metric="bp_systolic", value=142.0, unit="mmHg", effective_at="2025-09-01T00:00:00", source="mock"),
        TP(metric="bp_diastolic", value=78.0, unit="mmHg", effective_at="2024-03-01T00:00:00", source="mock"),
        TP(metric="bp_diastolic", value=80.0, unit="mmHg", effective_at="2024-09-01T00:00:00", source="mock"),
        TP(metric="bp_diastolic", value=84.0, unit="mmHg", effective_at="2025-03-01T00:00:00", source="mock"),
        TP(metric="bp_diastolic", value=88.0, unit="mmHg", effective_at="2025-09-01T00:00:00", source="mock"),
    ],
    "p002": [
        TP(metric="weight", value=95.0, unit="kg", effective_at="2024-06-01T00:00:00", source="mock"),
        TP(metric="weight", value=97.5, unit="kg", effective_at="2024-12-01T00:00:00", source="mock"),
        TP(metric="weight", value=101.0, unit="kg", effective_at="2025-06-01T00:00:00", source="mock"),
        TP(metric="bp_systolic", value=145.0, unit="mmHg", effective_at="2024-06-01T00:00:00", source="mock"),
        TP(metric="bp_systolic", value=152.0, unit="mmHg", effective_at="2024-12-01T00:00:00", source="mock"),
        TP(metric="bp_systolic", value=162.0, unit="mmHg", effective_at="2025-06-01T00:00:00", source="mock"),
        TP(metric="bp_diastolic", value=88.0, unit="mmHg", effective_at="2024-06-01T00:00:00", source="mock"),
        TP(metric="bp_diastolic", value=92.0, unit="mmHg", effective_at="2024-12-01T00:00:00", source="mock"),
        TP(metric="bp_diastolic", value=98.0, unit="mmHg", effective_at="2025-06-01T00:00:00", source="mock"),
    ],
    "p008": [
        TP(metric="weight", value=105.0, unit="kg", effective_at="2024-01-15T00:00:00", source="mock"),
        TP(metric="weight", value=107.0, unit="kg", effective_at="2024-07-15T00:00:00", source="mock"),
        TP(metric="weight", value=110.5, unit="kg", effective_at="2025-01-15T00:00:00", source="mock"),
        TP(metric="bp_systolic", value=158.0, unit="mmHg", effective_at="2024-01-15T00:00:00", source="mock"),
        TP(metric="bp_systolic", value=163.0, unit="mmHg", effective_at="2024-07-15T00:00:00", source="mock"),
        TP(metric="bp_systolic", value=168.0, unit="mmHg", effective_at="2025-01-15T00:00:00", source="mock"),
        TP(metric="bp_diastolic", value=95.0, unit="mmHg", effective_at="2024-01-15T00:00:00", source="mock"),
        TP(metric="bp_diastolic", value=98.0, unit="mmHg", effective_at="2024-07-15T00:00:00", source="mock"),
        TP(metric="bp_diastolic", value=102.0, unit="mmHg", effective_at="2025-01-15T00:00:00", source="mock"),
    ],
    "p004": [
        TP(metric="bp_systolic", value=146.0, unit="mmHg", effective_at="2024-07-01T00:00:00", source="mock"),
        TP(metric="bp_systolic", value=150.0, unit="mmHg", effective_at="2025-01-01T00:00:00", source="mock"),
        TP(metric="bp_systolic", value=148.0, unit="mmHg", effective_at="2025-07-01T00:00:00", source="mock"),
        TP(metric="bp_diastolic", value=90.0, unit="mmHg", effective_at="2024-07-01T00:00:00", source="mock"),
        TP(metric="bp_diastolic", value=94.0, unit="mmHg", effective_at="2025-01-01T00:00:00", source="mock"),
        TP(metric="bp_diastolic", value=92.0, unit="mmHg", effective_at="2025-07-01T00:00:00", source="mock"),
    ],
    "p016": [
        TP(metric="bp_systolic", value=152.0, unit="mmHg", effective_at="2024-04-01T00:00:00", source="mock"),
        TP(metric="bp_systolic", value=156.0, unit="mmHg", effective_at="2024-10-01T00:00:00", source="mock"),
        TP(metric="bp_systolic", value=158.0, unit="mmHg", effective_at="2025-04-01T00:00:00", source="mock"),
        TP(metric="bp_diastolic", value=92.0, unit="mmHg", effective_at="2024-04-01T00:00:00", source="mock"),
        TP(metric="bp_diastolic", value=94.0, unit="mmHg", effective_at="2024-10-01T00:00:00", source="mock"),
        TP(metric="bp_diastolic", value=96.0, unit="mmHg", effective_at="2025-04-01T00:00:00", source="mock"),
    ],
}


def _from_date_str(window_months: int) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_months * 30)
    return cutoff.strftime("%Y-%m-%d")


def _build_trajectory(metric: str, points: list[TrajectoryPoint], window_months: int) -> MetricTrajectory:
    meta = VITAL_METRIC_META.get(metric, {"display_name": metric, "unit": ""})
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


def run_vital_trends(
    patient_id: str, metrics: list[str] | None = None, window_months: int = 24
) -> list[MetricTrajectory]:
    """Return vital metric trajectories for a patient over the given window."""
    target_metrics = metrics or list(VITAL_METRIC_META.keys())
    from_date = _from_date_str(window_months)
    ds = get_effective_data_source()
    raw_points: list[TrajectoryPoint] = []
    if ds == "api":
        from openemr_mcp.repositories.fhir_api import get_observation_trends_api

        codes: list[str] = []
        for m in target_metrics:
            codes.extend(VITAL_LOINC_CODES.get(m, []))
        codes = list(dict.fromkeys(codes))
        raw_points = get_observation_trends_api(patient_id, "vital-signs", from_date, codes or None, get_http_client())
    else:
        pid = patient_id.lower()
        if not pid.startswith("p"):
            pid = "p" + (pid.lstrip("0") or "0")
        all_mock = _MOCK_VITAL_DATA.get(pid, [])
        raw_points = [p for p in all_mock if p.effective_at >= from_date]
    grouped: dict = {m: [] for m in target_metrics}
    for pt in raw_points:
        if pt.metric in grouped:
            grouped[pt.metric].append(pt)
    return [_build_trajectory(metric, pts, window_months) for metric, pts in grouped.items()]
