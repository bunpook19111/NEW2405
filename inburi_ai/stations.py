from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Any
from datetime import datetime


@dataclass(frozen=True)
class RiverStation:
    code: str
    name_th: str
    province: str
    river_km_to_inburi: float
    bank_msl: Optional[float] = None
    role: str = "midstream"


@dataclass
class StationReading:
    code: str
    name_th: str
    ts: datetime
    level_msl: Optional[float] = None
    discharge_cms: Optional[float] = None
    bank_msl: Optional[float] = None
    trend_3h_m: Optional[float] = None
    trend_6h_m: Optional[float] = None
    source: str = "unknown"
    quality_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ts"] = self.ts.isoformat()
        return d


ROUTE_STATIONS: list[RiverStation] = [
    RiverStation("C.2", "นครสวรรค์", "นครสวรรค์", 155, role="upstream"),
    RiverStation("C.13", "เขื่อนเจ้าพระยา/ชัยนาท", "ชัยนาท", 62, role="dam"),
    RiverStation("SINGBURI", "เมืองสิงห์บุรี", "สิงห์บุรี", 18, role="midstream"),
    RiverStation("INBURI", "อินทร์บุรี", "สิงห์บุรี", 0, bank_msl=13.00, role="target"),
    RiverStation("ANGTHONG", "อ่างทอง", "อ่างทอง", -45, role="downstream"),
]


def station_by_code(code: str) -> RiverStation | None:
    code_u = code.upper()
    return next((s for s in ROUTE_STATIONS if s.code.upper() == code_u), None)
