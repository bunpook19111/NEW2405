from datetime import timedelta
from pathlib import Path

from inburi_ai.caption import build_caption
from inburi_ai.forecast import EmpiricalForecastModel, risk_from_level, validate
from inburi_ai.graphics import make_svg
from inburi_ai.history import load_history_csv
from inburi_ai.models import Observation
from inburi_ai.sources import _extract_near_label
from inburi_ai.utils import now_local
import alert_water


def _sample():
    rows = load_history_csv(Path("data/inburi_history.csv"))
    model = EmpiricalForecastModel(rows)
    obs = Observation(now_local(), 12.50, 1500, 13.00, "test")
    forecasts = model.forecast(obs.level_msl, obs.discharge_cms, obs.discharge_cms)
    risk = risk_from_level(obs.level_msl, obs.bank_msl, forecasts[-1].high_msl)
    validation = validate(obs, model)
    return obs, forecasts, risk, validation


def test_caption_keeps_section_blank_lines_and_hashtags():
    obs, forecasts, risk, validation = _sample()
    text = build_caption(obs, forecasts, risk, validation)
    assert "\n\n🔮" in text
    assert "#อินทร์บุรี" in text


def test_graphics_level_normalization_not_almost_full_at_12_5(tmp_path):
    obs, forecasts, risk, validation = _sample()
    svg_path = make_svg(obs, forecasts, risk, validation, tmp_path / "x.svg")
    svg = svg_path.read_text(encoding="utf-8")
    assert "ขอบตลิ่ง 13.00" in svg

    # ระดับ 12.5 ม. บนสเกล 0-13 ม. = ~96% → water_y ควรสูง (เข้าใกล้ตลิ่ง)
    # water_y = 505 - int(pct * 315)  โดย pct = 12.5/13 ≈ 0.9615
    # → water_y ≈ 505 - 302 = 203  ยอมรับช่วง ±5 px เผื่อ rounding
    import re
    water_y_matches = re.findall(r'<rect[^>]*\by="(\d+)"[^>]*fill="#38bdf8"', svg)
    assert water_y_matches, "ไม่พบ rect แถบน้ำในไฟล์ SVG"
    water_y = int(water_y_matches[0])
    # ค่าที่คาดหวัง: 203 ± 5
    assert 198 <= water_y <= 208, (
        f"water_y={water_y} ไม่อยู่ในช่วงที่คาดหวัง (198-208) "
        f"สำหรับระดับน้ำ 12.5 ม. บนสเกล 0-13 ม."
    )


def test_source_extract_fallback_parse_failure_is_none():
    level, note = _extract_near_label("สถานี อินทร์บุรี ไม่มีตัวเลข", ["อินทร์บุรี"])
    assert level is None
    assert note


def test_alert_cooldown_same_reason_active():
    last = {"urgent": True, "sent_at": (now_local() - timedelta(minutes=10)).isoformat(), "reasons": ["x"]}
    assert alert_water._cooldown_active(last, ["x"])
    assert not alert_water._cooldown_active(last, ["x", "y"])
