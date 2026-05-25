from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Optional

from .config import SETTINGS

TZ = ZoneInfo(SETTINGS.timezone)


def now_local() -> datetime:
    return datetime.now(TZ)


def parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if not s or s.lower() in {"nan", "none", "null"} or s in {"-", "—"}:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def parse_datetime_th(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None

    # แปลงปี พ.ศ. → ค.ศ. ก่อน parse (เช่น 25/05/2568 → 25/05/2025)
    # พ.ศ. มักมากกว่า ค.ศ. 543 ปี และจะมีค่าตั้งแต่ 2500 ขึ้นไปในข้อมูลปัจจุบัน
    def _convert_be_year(date_str: str) -> str:
        def _replace_year(m: re.Match) -> str:
            y = int(m.group(0))
            return str(y - 543) if y >= 2500 else m.group(0)
        return re.sub(r"\d{4}", _replace_year, date_str)

    s_ce = _convert_be_year(s)

    formats = [
        "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
        "%Y.%m.%d %H:%M", "%Y.%m.%d",
        "%d/%m/%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s_ce, fmt)
            return dt.replace(tzinfo=TZ)
        except ValueError:
            pass
    return None


def fmt_m(x: Optional[float]) -> str:
    return "ไม่พบข้อมูล" if x is None else f"{x:.2f} ม."


def fmt_q(x: Optional[float]) -> str:
    return "ไม่พบข้อมูล" if x is None else f"{x:,.0f} ลบ.ม./วิ"
