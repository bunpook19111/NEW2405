from pathlib import Path

from inburi_ai.forecast import EmpiricalForecastModel, risk_from_level
from inburi_ai.history import load_history_csv


def test_history_loads():
    rows = load_history_csv(Path("data/inburi_history.csv"))
    assert len(rows) >= 20
    assert any(r.discharge_cms is not None for r in rows)


def test_model_forecasts_without_crash():
    rows = load_history_csv(Path("data/inburi_history.csv"))
    model = EmpiricalForecastModel(rows)
    points = model.forecast(current_level=12.80, current_q=2200, target_q=2200)
    assert len(points) == 5
    assert points[-1].expected_level_msl is not None


def test_risk_red_near_bank():
    risk = risk_from_level(12.95, 13.00, forecast_high=13.05)
    assert risk.color == "red"
