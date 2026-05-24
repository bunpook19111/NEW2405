from __future__ import annotations

from .models import ForecastPoint, Observation, RiskResult, ValidationResult
from .utils import fmt_m, fmt_q


def build_caption(obs: Observation, forecasts: list[ForecastPoint], risk: RiskResult, validation: ValidationResult) -> str:
    f6 = next((x for x in forecasts if x.horizon_h == 6), None)
    f12 = next((x for x in forecasts if x.horizon_h == 12), None)
    f24 = next((x for x in forecasts if x.horizon_h == 24), None)
    lines = [
        f"{risk.emoji} รอดมั้ย? รายงานน้ำเจ้าพระยา อ.อินทร์บุรี",
        f"อัปเดต {obs.ts.strftime('%d/%m/%Y %H:%M น.')}",
        "",
        f"🌊 ระดับน้ำตอนนี้: {fmt_m(obs.level_msl)}รทก.",
        f"📏 เหลือจากตลิ่ง: {fmt_m(risk.freeboard_m)}" if risk.freeboard_m is not None else "📏 ระยะตลิ่ง: ยังประเมินไม่ได้",
        f"💧 ท้ายเขื่อนเจ้าพระยา: {fmt_q(obs.discharge_cms)}",
    ]
    if f24 and f24.expected_level_msl is not None:
        lines.extend([
            "",
            "🔮 แนวโน้มจากข้อมูลย้อนหลัง",
            f"อีก 6 ชม.: {f6.expected_level_msl:.2f} ม. ({f6.expected_change_m:+.2f} ม.)" if f6 else "",
            f"อีก 12 ชม.: {f12.expected_level_msl:.2f} ม. ({f12.expected_change_m:+.2f} ม.)" if f12 else "",
            f"อีก 24 ชม.: {f24.expected_level_msl:.2f} ม. ช่วงเป็นไปได้ {f24.low_msl:.2f}-{f24.high_msl:.2f} ม.",
            f"⏳ {f24.eta_label}",
        ])
    lines.extend([
        "",
        f"🚦 สถานะ: {risk.level} — {risk.public_words}",
        f"✅ ความเชื่อมั่นข้อมูล: {validation.confidence}%",
        f"คำแนะนำ: {risk.advice}",
    ])
    if validation.issues:
        lines.append("")
        lines.append("⚠️ หมายเหตุระบบตรวจข้อมูล:")
        lines.extend([f"• {issue}" for issue in validation.issues[:3]])
    lines.extend([
        "",
        "หมายเหตุ: เป็นระบบช่วยเฝ้าระวังชุมชน ไม่ใช่ประกาศทางราชการ",
        "#รอดมั้ย #อินทร์บุรี #เจ้าพระยา #เฝ้าระวังน้ำ"
    ])
    return "\n".join(lines)
