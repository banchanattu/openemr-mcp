"""Questionnaire trends tool: PHQ-9 score trajectories."""

from datetime import datetime, timedelta, timezone

from openemr_mcp.data_source import get_effective_data_source, get_http_client
from openemr_mcp.schemas import MetricTrajectory, TrajectoryPoint

QUESTIONNAIRE_METRIC_META: dict = {
    "phq9": {"display_name": "PHQ-9 Depression Score", "unit": "score"},
}

TP = TrajectoryPoint

_MOCK_QUESTIONNAIRE_DATA: dict = {
    "p001": [
        TP(metric="phq9", value=4.0, unit="score", effective_at="2024-03-01T00:00:00", source="mock"),
        TP(metric="phq9", value=5.0, unit="score", effective_at="2024-09-01T00:00:00", source="mock"),
        TP(metric="phq9", value=6.0, unit="score", effective_at="2025-03-01T00:00:00", source="mock"),
        TP(metric="phq9", value=7.0, unit="score", effective_at="2025-09-01T00:00:00", source="mock"),
    ],
    "p002": [
        TP(metric="phq9", value=8.0, unit="score", effective_at="2024-06-01T00:00:00", source="mock"),
        TP(metric="phq9", value=11.0, unit="score", effective_at="2024-12-01T00:00:00", source="mock"),
        TP(metric="phq9", value=14.0, unit="score", effective_at="2025-06-01T00:00:00", source="mock"),
    ],
    "p009": [
        TP(metric="phq9", value=12.0, unit="score", effective_at="2024-04-01T00:00:00", source="mock"),
        TP(metric="phq9", value=15.0, unit="score", effective_at="2024-10-01T00:00:00", source="mock"),
        TP(metric="phq9", value=20.0, unit="score", effective_at="2025-04-01T00:00:00", source="mock"),
    ],
}


def _from_date_str(window_months: int) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_months * 30)
    return cutoff.strftime("%Y-%m-%d")


def _build_trajectory(metric: str, points: list[TrajectoryPoint], window_months: int) -> MetricTrajectory:
    meta = QUESTIONNAIRE_METRIC_META.get(metric, {"display_name": metric, "unit": "score"})
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


def run_questionnaire_trends(
    patient_id: str, instrument: str | None = "PHQ-9", window_months: int = 24
) -> list[MetricTrajectory]:
    """Return questionnaire score trajectories for a patient."""
    from_date = _from_date_str(window_months)
    ds = get_effective_data_source()
    raw_points: list[TrajectoryPoint] = []
    name_filters = [instrument] if instrument else ["PHQ-9"]
    if ds == "api":
        from openemr_mcp.repositories.fhir_api import get_questionnaire_trends_api

        raw_points = get_questionnaire_trends_api(patient_id, from_date, name_filters, get_http_client())
    else:
        pid = patient_id.lower()
        if not pid.startswith("p"):
            pid = "p" + (pid.lstrip("0") or "0")
        all_mock = _MOCK_QUESTIONNAIRE_DATA.get(pid, [])
        raw_points = [p for p in all_mock if p.effective_at >= from_date]
    grouped: dict = {"phq9": []}
    for pt in raw_points:
        if pt.metric == "phq9":
            grouped["phq9"].append(pt)
    return [_build_trajectory("phq9", grouped["phq9"], window_months)]
