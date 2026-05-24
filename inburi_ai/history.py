from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from .config import SETTINGS
from .models import Observation
from .utils import parse_datetime_th, parse_float


def load_history_csv(path: Path | str = SETTINGS.history_csv) -> list[Observation]:
    path = Path(path)
    if not path.exists():
        return []
    rows: list[Observation] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ts = parse_datetime_th(r.get("วันที่เวลา") or r.get("วันที่") or r.get("datetime") or r.get("time"))
            level = parse_float(r.get("ระดับน้ำ (ม.รทก.)") or r.get("ระดับน้ำ") or r.get("level_msl"))
            q = parse_float(r.get("ปริมาณน้ำปล่อยเขื่อนเจ้าพระยา (ลบ.ม./วินาที)") or r.get("ปริมาณน้ำปล่อยเขื่อนเจ้าพระยา") or r.get("discharge_cms"))
            bank = parse_float(r.get("ระดับตลิ่ง (ม.รทก.)") or r.get("bank_msl")) or SETTINGS.bank_level_msl
            if ts is None or level is None:
                continue
            rows.append(Observation(ts=ts, level_msl=level, discharge_cms=q, bank_msl=bank, source=str(path)))
    return clean_history(rows)


def clean_history(rows: Iterable[Observation]) -> list[Observation]:
    clean: list[Observation] = []
    seen: set[tuple[str, float | None, float | None]] = set()
    for r in rows:
        if r.level_msl is not None and not (0 <= r.level_msl <= 25):
            continue
        if r.discharge_cms is not None and not (0 <= r.discharge_cms <= 6000):
            continue
        key = (r.ts.isoformat(), r.level_msl, r.discharge_cms)
        if key in seen:
            continue
        seen.add(key)
        clean.append(r)
    clean.sort(key=lambda x: x.ts)
    return clean


def latest_valid(history: list[Observation]) -> Observation | None:
    for row in reversed(history):
        if row.level_msl is not None:
            return row
    return None


def history_summary(history: list[Observation]) -> dict:
    qs = [x.discharge_cms for x in history if x.discharge_cms is not None]
    levels = [x.level_msl for x in history if x.level_msl is not None]
    return {
        "rows": len(history),
        "q_min": min(qs) if qs else None,
        "q_max": max(qs) if qs else None,
        "level_min": min(levels) if levels else None,
        "level_max": max(levels) if levels else None,
        "start": history[0].ts.isoformat() if history else None,
        "end": history[-1].ts.isoformat() if history else None,
    }
