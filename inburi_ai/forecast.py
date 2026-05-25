from __future__ import annotations

import math
import statistics
from typing import Optional

from .config import SETTINGS
from .models import ForecastPoint, Observation, RiskResult, ValidationResult


class EmpiricalForecastModel:
    """Empirical model: C.13 discharge -> Inburi level + lag.

    This model is deliberately conservative. It never claims certainty.
    It uses historical observations as a first local rating curve and adds uncertainty bands.
    """

    def __init__(self, history: list[Observation]):
        self.history = [h for h in history if h.level_msl is not None and h.discharge_cms is not None]
        self.q_values = [float(h.discharge_cms) for h in self.history if h.discharge_cms is not None]
        self.level_values = [float(h.level_msl) for h in self.history if h.level_msl is not None]
        self.rmse_m = self._cross_validated_rmse()

    def ready(self) -> bool:
        return len(self.history) >= 20

    def q_range(self) -> tuple[Optional[float], Optional[float]]:
        if not self.q_values:
            return None, None
        return min(self.q_values), max(self.q_values)

    def _nearest_prediction(self, q: Optional[float], exclude_index: Optional[int] = None) -> Optional[float]:
        if q is None or not self.history:
            return None
        candidates = [(i, h) for i, h in enumerate(self.history) if i != exclude_index and h.discharge_cms is not None and h.level_msl is not None]
        if not candidates:
            return None
        nearest = sorted(candidates, key=lambda item: abs((item[1].discharge_cms or 0) - q))[:16]
        weights: list[float] = []
        vals: list[float] = []
        for _, h in nearest:
            distance = abs((h.discharge_cms or 0) - q)
            # Keep a floor so repeated equal discharge does not dominate too much.
            weight = 1.0 / max(25.0, distance)
            weights.append(weight)
            vals.append((h.level_msl or 0.0) * weight)
        if not weights:
            return None
        return sum(vals) / sum(weights)

    def _cross_validated_rmse(self) -> float:
        if len(self.history) < 12:
            return 0.45
        errors: list[float] = []
        for i, h in enumerate(self.history):
            pred = self._nearest_prediction(h.discharge_cms, exclude_index=i)
            if pred is not None and h.level_msl is not None:
                errors.append(h.level_msl - pred)
        if len(errors) < 8:
            return 0.40
        rmse = math.sqrt(sum(e * e for e in errors) / len(errors))
        return round(max(0.12, min(0.90, rmse)), 2)

    def steady_level_for_q(self, q: Optional[float]) -> Optional[float]:
        return self._nearest_prediction(q)

    def lag_hours_for_q(self, q: Optional[float], q_change: Optional[float] = None) -> tuple[int, int, str]:
        """Estimate lag range. More water usually travels faster; sudden changes arrive sooner."""
        if q is None:
            return 12, 30, "ยังไม่ทราบความเร็ว"
        sudden = abs(q_change or 0) >= 300
        if q >= 2200:
            return (3, 9, "เร็วมาก") if sudden else (4, 12, "เร็วมาก")
        if q >= 1900:
            return (5, 12, "เร็ว") if sudden else (6, 16, "เร็ว")
        if q >= 1500:
            return (8, 18, "ปานกลาง-เร็ว") if sudden else (10, 24, "ปานกลาง")
        if q >= 1000:
            return (11, 24, "ปานกลาง") if sudden else (14, 30, "ปานกลาง-ช้า")
        return (20, 42, "ช้า")

    def forecast(self, current_level: Optional[float], current_q: Optional[float], target_q: Optional[float]) -> list[ForecastPoint]:
        horizons = [3, 6, 12, 24, 48]
        if current_level is None:
            return [ForecastPoint(h, None, None, None, None, "ไม่มีระดับน้ำล่าสุด") for h in horizons]
        target_q = target_q if target_q is not None else current_q
        steady = self.steady_level_for_q(target_q)
        if steady is None:
            return [ForecastPoint(h, None, None, None, None, "ไม่มีข้อมูลเขื่อนเพียงพอ") for h in horizons]
        q_change = None if current_q is None or target_q is None else target_q - current_q
        lag_min, lag_max, speed = self.lag_hours_for_q(target_q, q_change)
        points: list[ForecastPoint] = []
        for h in horizons:
            if h <= lag_min:
                factor = 0.18 * h / max(lag_min, 1)
            elif h >= lag_max:
                factor = min(1.0, 0.72 + 0.28 * (h - lag_max) / max(lag_max, 1))
            else:
                factor = 0.18 + 0.54 * (h - lag_min) / max(lag_max - lag_min, 1)
            expected = current_level + (steady - current_level) * factor
            band = self.rmse_m * (1.05 if h <= 6 else 1.25 if h <= 12 else 1.55 if h <= 24 else 1.85)
            points.append(ForecastPoint(
                horizon_h=h,
                expected_level_msl=round(expected, 2),
                low_msl=round(expected - band, 2),
                high_msl=round(expected + band, 2),
                expected_change_m=round(expected - current_level, 2),
                eta_label=f"คาดว่ามวลน้ำตอบสนอง{speed} ราว {lag_min}-{lag_max} ชม."
            ))
        return points


def risk_from_level(level: Optional[float], bank: float = SETTINGS.bank_level_msl, forecast_high: Optional[float] = None) -> RiskResult:
    if level is None:
        return RiskResult("ข้อมูลไม่พอ", "⚪", "gray", None, 0, "ยังไม่ควรประกาศตัวเลขเตือนภัย เพราะข้อมูลไม่ครบ", "รอข้อมูล")
    effective = max(level, forecast_high if forecast_high is not None else level)
    freeboard_now = round(bank - level, 2)
    freeboard_effective = bank - effective
    if freeboard_effective <= 0:
        return RiskResult("วิกฤต/แตะตลิ่ง", "🔴", "red", freeboard_now, 100, "บ้านริมน้ำและพื้นที่นอกคันกั้นน้ำควรยกของขึ้นสูงและติดตามประกาศท้องถิ่นทันที", "น้ำใกล้หรือเกินตลิ่ง")
    if freeboard_effective <= 0.30:
        return RiskResult("วิกฤตใกล้ล้น", "🔴", "red", freeboard_now, 92, "เหลือระยะจากตลิ่งน้อยมาก ควรเตรียมพร้อมอพยพจุดเสี่ยง", "เหลือขอบตลิ่งน้อยมาก")
    if freeboard_effective <= 0.80:
        return RiskResult("เสี่ยงสูง", "🟠", "orange", freeboard_now, 78, "เฝ้าระวังทุก 1-3 ชั่วโมง โดยเฉพาะบ้านริมน้ำและพื้นที่ต่ำ", "น้ำสูง ต้องเฝ้าระวังใกล้ชิด")
    if freeboard_effective <= 1.50:
        return RiskResult("เฝ้าระวัง", "🟡", "yellow", freeboard_now, 55, "ติดตามสถานการณ์ต่อเนื่อง และเตรียมยกของหากอยู่ริมน้ำ", "เริ่มเฝ้าระวัง")
    return RiskResult("ปกติ", "🟢", "green", freeboard_now, 25, "ยังมีระยะจากตลิ่ง แต่ควรดูแนวโน้มเขื่อนและฝนเหนือ", "ยังมีพื้นที่ปลอดภัย")


def validate(obs: Observation, model: EmpiricalForecastModel, target_q: Optional[float] = None) -> ValidationResult:
    confidence = 92
    issues: list[str] = []
    if obs.level_msl is None:
        confidence -= 40
        issues.append("ไม่พบระดับน้ำอินทร์บุรีล่าสุด")
    elif not (4 <= obs.level_msl <= 16):
        confidence -= 40
        issues.append("ระดับน้ำอยู่นอกช่วงที่ระบบคาดว่าเป็นไปได้")
    if obs.discharge_cms is None:
        confidence -= 30
        issues.append("ไม่พบปริมาณระบายท้ายเขื่อนเจ้าพระยา")
    elif not (0 <= obs.discharge_cms <= 6000):
        confidence -= 35
        issues.append("ค่าระบายเขื่อนอยู่นอกช่วงที่ควรเป็น")
    qmin, qmax = model.q_range()
    check_q = target_q if target_q is not None else obs.discharge_cms
    if check_q is not None and qmin is not None and qmax is not None:
        if check_q < qmin - 100 or check_q > qmax + 100:
            confidence -= 15
            issues.append(f"ค่าเขื่อน {check_q:.0f} อยู่นอกช่วงข้อมูลย้อนหลังที่มี ({qmin:.0f}-{qmax:.0f})")
    if not model.ready():
        confidence -= 18
        issues.append("ข้อมูลย้อนหลังยังน้อย ควรใช้เป็นโมเดลเบื้องต้น")
    if model.rmse_m > 0.45:
        confidence -= 10
        issues.append(f"ค่าคลาดเคลื่อนโมเดลยังสูง ±{model.rmse_m:.2f} ม.")
    confidence = max(5, min(95, confidence))
    return ValidationResult(confidence, issues, (qmin, qmax), model.rmse_m, confidence >= SETTINGS.post_min_confidence)
