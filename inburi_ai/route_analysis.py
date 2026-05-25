from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import timedelta
from typing import Any, Optional

from .config import SETTINGS
from .models import Observation, ForecastPoint, RiskResult, ValidationResult
from .stations import ROUTE_STATIONS, StationReading
from .utils import now_local


@dataclass
class WaterMassEstimate:
    source_station: str
    distance_km: float
    speed_kmh_low: float
    speed_kmh_high: float
    eta_low_h: float
    eta_high_h: float
    eta_window_text: str
    volume_label: str
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _q_to_speed_range(q: Optional[float], dq: Optional[float] = None) -> tuple[float, float, str]:
    # Empirical Chao Phraya reach estimate for public warning, not hydraulic modeling.
    if q is None:
        return 2.5, 5.5, "ยังไม่ทราบมวลน้ำแน่ชัด"
    accel = abs(dq or 0) >= 300
    if q >= 2600:
        return (7.0, 13.0, "มวลน้ำมากมาก") if accel else (6.0, 11.0, "มวลน้ำมากมาก")
    if q >= 2200:
        return (6.0, 11.0, "มวลน้ำมาก") if accel else (5.0, 9.5, "มวลน้ำมาก")
    if q >= 1800:
        return (4.5, 8.5, "มวลน้ำค่อนข้างมาก")
    if q >= 1400:
        return (3.5, 7.0, "มวลน้ำปานกลาง")
    if q >= 900:
        return (2.5, 5.5, "มวลน้ำน้อยถึงปานกลาง")
    return 1.8, 4.0, "มวลน้ำน้อย"


def estimate_water_mass_to_inburi(obs: Observation, previous_q: Optional[float] = None) -> WaterMassEstimate:
    q = obs.discharge_cms
    dq = None if q is None or previous_q is None else q - previous_q
    low_speed, high_speed, label = _q_to_speed_range(q, dq)
    distance = 62.0  # Chao Phraya Dam C.13 to Inburi approx river reach
    eta_low = distance / max(high_speed, 0.1)
    eta_high = distance / max(low_speed, 0.1)
    start = now_local()
    a = start + timedelta(hours=eta_low)
    b = start + timedelta(hours=eta_high)
    eta_text = f"ประมาณ {eta_low:.0f}-{eta_high:.0f} ชม. หรือช่วง {a.strftime('%d/%m %H:%M')}–{b.strftime('%d/%m %H:%M')}"
    if dq is None:
        reason = "ใช้ปริมาณระบายล่าสุดและระยะทางชัยนาท→อินทร์บุรีเป็นฐาน เพราะยังไม่มีค่าเปลี่ยนแปลงรอบก่อน"
    else:
        direction = "เพิ่มขึ้น" if dq > 0 else "ลดลง" if dq < 0 else "ทรงตัว"
        reason = f"เทียบปริมาณระบายกับรอบก่อน: {direction} {abs(dq):.0f} ลบ.ม./วิ จึงปรับช่วงความเร็วของมวลน้ำ"
    return WaterMassEstimate("C.13", distance, low_speed, high_speed, round(eta_low,1), round(eta_high,1), eta_text, label, reason)


def route_summary(readings: list[StationReading]) -> dict[str, Any]:
    by_code = {r.code.upper(): r for r in readings}
    rows=[]
    for s in ROUTE_STATIONS:
        r=by_code.get(s.code.upper())
        rows.append({
            "code": s.code,
            "name_th": s.name_th,
            "province": s.province,
            "km_to_inburi": s.river_km_to_inburi,
            "role": s.role,
            "level_msl": None if r is None else r.level_msl,
            "discharge_cms": None if r is None else r.discharge_cms,
            "trend_3h_m": None if r is None else r.trend_3h_m,
            "source": None if r is None else r.source,
        })
    return {"route_name":"แม่น้ำเจ้าพระยา → อินทร์บุรี", "stations": rows}


def explain_for_villagers(obs: Observation, risk: RiskResult, mass: WaterMassEstimate, forecast: list[ForecastPoint]) -> str:
    f12 = next((f for f in forecast if f.horizon_h == 12), None)
    f24 = next((f for f in forecast if f.horizon_h == 24), None)
    parts=[
        f"ตอนนี้ระดับน้ำอินทร์บุรีอยู่ที่ {obs.level_msl:.2f} ม.รทก." if obs.level_msl is not None else "ยังอ่านระดับน้ำอินทร์บุรีสดไม่ได้",
        f"เหลือห่างตลิ่ง {risk.freeboard_m:.2f} ม." if risk.freeboard_m is not None else "ยังคำนวณระยะห่างตลิ่งไม่ได้",
        f"มวลน้ำจากชัยนาทอยู่ในระดับ: {mass.volume_label}",
        f"คาดว่าการเปลี่ยนแปลงจากเขื่อนจะมาถึงอินทร์บุรี {mass.eta_window_text}",
    ]
    if f12 and f12.expected_change_m is not None:
        parts.append(f"อีก 12 ชม. น้ำมีแนวโน้มเปลี่ยน {f12.expected_change_m:+.2f} ม.")
    if f24 and f24.high_msl is not None:
        parts.append(f"กรอบสูงสุด 24 ชม. ที่ควรเฝ้าระวัง: {f24.high_msl:.2f} ม.รทก.")
    return " | ".join(parts)
