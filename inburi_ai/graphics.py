from __future__ import annotations

import base64
import html
from pathlib import Path

from .config import SETTINGS
from .models import ForecastPoint, Observation, RiskResult, ValidationResult
from .utils import fmt_m, fmt_q

COLORS = {
    "green": ("#dcfce7", "#16a34a", "#14532d"),
    "yellow": ("#fef9c3", "#ca8a04", "#713f12"),
    "orange": ("#ffedd5", "#ea580c", "#7c2d12"),
    "red": ("#fee2e2", "#dc2626", "#7f1d1d"),
    "gray": ("#f3f4f6", "#6b7280", "#374151"),
}


def _e(x: object) -> str:
    return html.escape(str(x))


def make_svg(obs: Observation, forecasts: list[ForecastPoint], risk: RiskResult, validation: ValidationResult, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bg, main, text = COLORS.get(risk.color, COLORS["gray"])
    f24 = next((x for x in forecasts if x.horizon_h == 24), None)
    level = obs.level_msl if obs.level_msl is not None else SETTINGS.level_min_msl
    bank = obs.bank_msl
    # ใช้สเกลสัมบูรณ์ 0-bank เพื่อให้แถบน้ำสะท้อนระดับจริง
    # ไม่ใช้ level_min จาก settings เพราะน้ำอาจต่ำกว่าค่านั้นได้
    level_floor = 0.0
    pct = max(0.0, min(1.0, (level - level_floor) / max(bank - level_floor, 0.1)))
    water_y = 505 - int(pct * 315)
    water_h = 505 - water_y
    forecast_line = "ยังคาดการณ์ไม่ได้"
    if f24 and f24.expected_level_msl is not None:
        forecast_line = f"24 ชม. {f24.expected_level_msl:.2f} ม. ({f24.low_msl:.2f}-{f24.high_msl:.2f})"
    caption_level = "น้ำยังมีพื้นที่" if risk.color == "green" else "เริ่มเฝ้าระวัง" if risk.color == "yellow" else "น้ำสูงมาก" if risk.color == "orange" else "ใกล้ตลิ่งมาก!"
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675">
  <defs>
    <linearGradient id="sky" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#e0f2fe"/><stop offset="100%" stop-color="#f8fafc"/></linearGradient>
    <filter id="shadow"><feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="#0f172a" flood-opacity="0.13"/></filter>
  </defs>
  <rect width="1200" height="675" fill="url(#sky)"/>
  <circle cx="1020" cy="105" r="58" fill="#fde68a" opacity="0.9"/>
  <path d="M0 555 C 180 500, 310 600, 500 545 S 850 500, 1200 555 L1200 675 L0 675 Z" fill="#bae6fd"/>
  <rect x="42" y="34" width="1116" height="607" rx="34" fill="white" filter="url(#shadow)" opacity="0.96"/>

  <text x="78" y="88" font-family="Arial, Tahoma, sans-serif" font-size="38" font-weight="800" fill="#0f172a">รอดมั้ย? น้ำเจ้าพระยา อินทร์บุรี</text>
  <text x="82" y="125" font-family="Arial, Tahoma, sans-serif" font-size="21" fill="#475569">ภาพเข้าใจง่ายสำหรับชุมชน · อัปเดต {_e(obs.ts.strftime('%d/%m/%Y %H:%M น.'))}</text>

  <rect x="78" y="152" width="315" height="145" rx="28" fill="#eff6ff"/>
  <text x="105" y="195" font-family="Arial" font-size="22" font-weight="700" fill="#1e3a8a">ระดับน้ำตอนนี้</text>
  <text x="105" y="255" font-family="Arial" font-size="56" font-weight="900" fill="#0f172a">{_e('?' if obs.level_msl is None else f'{obs.level_msl:.2f}')}</text>
  <text x="255" y="255" font-family="Arial" font-size="24" fill="#475569">ม.รทก.</text>

  <rect x="430" y="152" width="315" height="145" rx="28" fill="#f0fdf4"/>
  <text x="457" y="195" font-family="Arial" font-size="22" font-weight="700" fill="#14532d">ท้ายเขื่อนเจ้าพระยา</text>
  <text x="457" y="255" font-family="Arial" font-size="56" font-weight="900" fill="#0f172a">{_e('?' if obs.discharge_cms is None else f'{obs.discharge_cms:.0f}')}</text>
  <text x="610" y="255" font-family="Arial" font-size="24" fill="#475569">ลบ.ม./วิ</text>

  <rect x="782" y="152" width="315" height="145" rx="28" fill="{bg}"/>
  <text x="810" y="195" font-family="Arial" font-size="22" font-weight="700" fill="{text}">สถานะชุมชน</text>
  <text x="810" y="255" font-family="Arial" font-size="40" font-weight="900" fill="{main}">{_e(risk.emoji)} {_e(risk.level)}</text>

  <rect x="92" y="340" width="430" height="205" rx="26" fill="#f8fafc" stroke="#cbd5e1"/>
  <line x1="130" y1="385" x2="485" y2="385" stroke="#ef4444" stroke-width="5" stroke-dasharray="10 8"/>
  <text x="132" y="375" font-family="Arial" font-size="18" fill="#991b1b">ขอบตลิ่ง {bank:.2f} ม.</text>
  <rect x="130" y="{water_y}" width="355" height="{water_h}" fill="#38bdf8" opacity="0.9" rx="4"/>
  <path d="M130 {water_y} C 190 {water_y-16}, 240 {water_y+16}, 305 {water_y} S 420 {water_y-16}, 485 {water_y}" fill="none" stroke="#0284c7" stroke-width="5"/>
  <text x="132" y="575" font-family="Arial" font-size="26" font-weight="800" fill="#0f172a">เหลือจากตลิ่ง: {_e(fmt_m(risk.freeboard_m))}</text>

  <rect x="570" y="335" width="527" height="220" rx="28" fill="#f8fafc" stroke="#e2e8f0"/>
  <text x="602" y="382" font-family="Arial" font-size="27" font-weight="900" fill="#0f172a">น้องเจ้าพระยาบอกว่า...</text>
  <text x="602" y="430" font-family="Arial" font-size="35" font-weight="900" fill="{main}">{_e(caption_level)}</text>
  <text x="602" y="478" font-family="Arial" font-size="25" fill="#334155">คาดการณ์: {_e(forecast_line)}</text>
  <text x="602" y="520" font-family="Arial" font-size="22" fill="#475569">ความเชื่อมั่น {validation.confidence}% · โมเดลคลาดเคลื่อน ±{validation.model_rmse_m:.2f} ม.</text>

  <circle cx="1040" cy="506" r="45" fill="#facc15"/>
  <circle cx="1025" cy="495" r="6" fill="#0f172a"/><circle cx="1055" cy="495" r="6" fill="#0f172a"/>
  <path d="M1022 518 Q1040 535 1058 518" stroke="#0f172a" stroke-width="5" fill="none" stroke-linecap="round"/>
  <path d="M990 548 Q1040 585 1090 548" fill="#38bdf8" opacity="0.55"/>

  <text x="78" y="620" font-family="Arial" font-size="18" fill="#64748b">ระบบช่วยเฝ้าระวัง ไม่ใช่ประกาศราชการ · ถ้าข้อมูลไม่ครบ ระบบจะลดความเชื่อมั่นและไม่โพสต์เตือนเกินจริง</text>
</svg>'''
    out_path.write_text(svg, encoding="utf-8")
    return out_path


def make_png_from_svg(svg_path: Path, png_path: Path | None = None) -> Path | None:
    """Convert SVG to PNG for Facebook/LINE posting when cairosvg is installed.

    Returns None instead of failing the whole warning system if native PNG conversion
    is unavailable in the runtime.
    """
    if png_path is None:
        png_path = svg_path.with_suffix(".png")
    try:
        import cairosvg  # type: ignore
        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), output_width=1200, output_height=675)
        return png_path
    except Exception:
        return None


def file_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")
