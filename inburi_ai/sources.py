from __future__ import annotations

import json
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .config import SETTINGS
from .models import Observation
from .stations import ROUTE_STATIONS, StationReading
from .utils import now_local, parse_float


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": SETTINGS.user_agent})
    return s


def _get_text_with_retry(url: str, attempts: int = 3) -> str:
    last_exc: Exception | None = None
    for i in range(max(1, attempts)):
        try:
            r = _session().get(url, timeout=SETTINGS.request_timeout_s, verify=SETTINGS.verify_tls)
            r.raise_for_status()
            return r.text
        except Exception as exc:  # network/public-site robustness
            last_exc = exc
            if i < attempts - 1:
                time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"fetch failed after {attempts} attempts: {last_exc}")


def _extract_near_label(text: str, labels: list[str], min_val: float = 4, max_val: float = 16) -> tuple[float | None, str]:
    lowered = text.lower()
    for label in labels:
        idx = lowered.find(label.lower())
        if idx >= 0:
            chunk = text[max(0, idx - 160): idx + 700]
            numbers = [parse_float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", chunk)]
            candidates = [x for x in numbers if x is not None and min_val <= x <= max_val]
            if candidates:
                return candidates[0], f"พบใกล้คำว่า {label}"
    return None, "ไม่พบตัวเลขใกล้ชื่อสถานี"


def fetch_inburi_level_thaiwater() -> Observation:
    """Best-effort fetch from Singburi Thaiwater public page.

    If the page layout changes, returns level=None instead of guessing.
    """
    url = "https://singburi.thaiwater.net/wl"
    try:
        html = _get_text_with_retry(url)
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ", strip=True)
        level, note = _extract_near_label(text, ["อินทร์บุรี", "inburi"])
        if level is not None:
            return Observation(now_local(), level, None, SETTINGS.bank_level_msl, url)
        return Observation(now_local(), None, None, SETTINGS.bank_level_msl, url, note)
    except Exception as exc:
        return Observation(now_local(), None, None, SETTINGS.bank_level_msl, url, f"อ่าน Thaiwater ไม่สำเร็จ: {exc}")


def fetch_c13_discharge_hii() -> Optional[float]:
    """Best-effort C.13 downstream discharge from HII chart JS data.

    ค่าปริมาณระบายที่สมเหตุสมผลสำหรับเขื่อนเจ้าพระยาอยู่ที่ 50-5000 ลบ.ม./วิ
    ค่าต่ำกว่า 50 หรือสูงกว่า 5000 ถือว่าผิดปกติ
    """
    _Q_MIN = 50.0
    _Q_MAX = 5000.0
    url = "https://tiwrm.hii.or.th/DATA/REPORT/php/chart/chaopraya/small/chaopraya.php"
    try:
        text = _get_text_with_retry(url)
        match = re.search(r"var\s+json_data\s*=\s*(\[.*?\]);", text, re.S)
        if match:
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                data = []
            # data อาจเป็น list ของ dict หรือโครงสร้างอื่น ต้องตรวจก่อน
            for item in (data if isinstance(data, list) else []):
                if not isinstance(item, dict):
                    continue
                # ลองดึงจาก key nested ต่างๆ ที่ HII ใช้
                for section_key in ("itc_water", "water", "data"):
                    section = item.get(section_key)
                    if not isinstance(section, dict):
                        continue
                    for station_key in ("C13", "c13", "C.13"):
                        station = section.get(station_key)
                        if not isinstance(station, dict):
                            continue
                        for val_key in ("q", "discharge", "value", "storage", "outflow"):
                            val = parse_float(station.get(val_key))
                            if val is not None and _Q_MIN <= val <= _Q_MAX:
                                return val
        # Fallback: หาตัวเลขใกล้ "C13" แต่ต้องอยู่ในช่วงสมเหตุสมผล
        idx = text.find("C13")
        if idx >= 0:
            chunk = text[idx: idx + 500]
            nums = [parse_float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", chunk)]
            candidates = [x for x in nums if x is not None and _Q_MIN <= x <= _Q_MAX]
            if candidates:
                return candidates[0]
    except Exception:
        return None
    return None


def fetch_route_readings(best_obs: Observation | None = None) -> list[StationReading]:
    """Fetch route-station readings on a best-effort basis.

    Public data sites sometimes change HTML/JS shape, so this function is intentionally
    conservative: it fills stations only when values can be parsed with reasonable confidence.
    The report will expose missing stations as null instead of inventing numbers.
    """
    readings: list[StationReading] = []
    now = now_local()
    # Known target and dam values from the primary observation/fetchers.
    if best_obs is not None:
        readings.append(StationReading(
            code="INBURI", name_th="อินทร์บุรี", ts=now,
            level_msl=best_obs.level_msl, discharge_cms=best_obs.discharge_cms,
            bank_msl=best_obs.bank_msl, source=best_obs.source, quality_note=best_obs.quality_note,
        ))
    q_c13 = best_obs.discharge_cms if best_obs else None
    if q_c13 is None:
        q_c13 = fetch_c13_discharge_hii()
    readings.append(StationReading(
        code="C.13", name_th="เขื่อนเจ้าพระยา/ชัยนาท", ts=now,
        discharge_cms=q_c13, source="HII/RID best-effort", quality_note="ปริมาณระบายท้ายเขื่อนเจ้าพระยา",
    ))
    # Try Singburi page for nearby midstream station labels.
    try:
        text = BeautifulSoup(_get_text_with_retry("https://singburi.thaiwater.net/wl"), "lxml").get_text(" ", strip=True)
        for code, labels in {
            "SINGBURI": ["เมืองสิงห์บุรี", "สิงห์บุรี"],
            "INBURI": ["อินทร์บุรี"],
        }.items():
            if any(r.code.upper() == code for r in readings) and code == "INBURI":
                continue
            level, note = _extract_near_label(text, labels)
            st = next((x for x in ROUTE_STATIONS if x.code == code), None)
            if st:
                readings.append(StationReading(code=code, name_th=st.name_th, ts=now, level_msl=level, bank_msl=st.bank_msl, source="Thaiwater Singburi", quality_note=note))
    except Exception:
        pass
    # placeholders for route completeness; nulls make pending stations visible in JSON/UI.
    have = {r.code.upper() for r in readings}
    for st in ROUTE_STATIONS:
        if st.code.upper() not in have:
            readings.append(StationReading(code=st.code, name_th=st.name_th, ts=now, bank_msl=st.bank_msl, source="pending_fetcher", quality_note="ยังไม่มี fetcher ที่ parse ได้มั่นใจ"))
    return readings


def fetch_live_observation(history_latest: Observation | None = None) -> Observation:
    live_level = fetch_inburi_level_thaiwater()
    q = fetch_c13_discharge_hii()
    if live_level.level_msl is None and history_latest is not None:
        level = history_latest.level_msl
        note = "ใช้ข้อมูลย้อนหลังล่าสุดแทน เพราะอ่านระดับน้ำสดไม่ได้; " + live_level.quality_note
        source = f"history_fallback + {live_level.source}"
    else:
        level = live_level.level_msl
        note = live_level.quality_note
        source = live_level.source
    if q is None and history_latest is not None:
        q = history_latest.discharge_cms
        note = (note + "; " if note else "") + "ใช้ค่าเขื่อนย้อนหลังล่าสุดแทน เพราะอ่าน C.13 สดไม่ได้"
    return Observation(now_local(), level, q, SETTINGS.bank_level_msl, source, note)
