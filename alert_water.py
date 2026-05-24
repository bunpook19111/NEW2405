from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from inburi_ai.app import run_once
from inburi_ai.config import SETTINGS
from inburi_ai.utils import now_local


def _load_last_alert(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _cooldown_active(last: dict | None, reasons: list[str]) -> bool:
    if not last or not last.get("urgent"):
        return False
    try:
        last_ts = datetime.fromisoformat(last.get("sent_at") or last.get("checked_at"))
    except Exception:
        return False
    last_reasons = set(last.get("reasons") or [])
    # New/different danger reason is allowed through even during cooldown.
    if set(reasons) - last_reasons:
        return False
    return now_local() - last_ts < timedelta(minutes=SETTINGS.alert_cooldown_minutes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inburi urgent water alert checker")
    parser.add_argument("--simulate-q", type=float, default=None)
    parser.add_argument("--simulate-level", type=float, default=None)
    parser.add_argument("--use-history-latest", action="store_true")
    parser.add_argument("--history-csv", type=Path, default=None)
    parser.add_argument("--post", action="store_true")
    parser.add_argument("--target-q", type=float, default=None)
    parser.add_argument("--no-ai", action="store_true")
    args = parser.parse_args()

    report = run_once(args)
    risk = report.get("risk", {})
    obs = report.get("observation", {})
    q = obs.get("discharge_cms")
    freeboard = risk.get("freeboard_m")
    urgent = False
    reasons: list[str] = []
    if freeboard is not None and freeboard <= 0.80:
        urgent = True
        reasons.append(f"น้ำเหลือห่างตลิ่ง {freeboard:.2f} ม.")
    if freeboard is not None and freeboard <= 0:
        urgent = True
        reasons.append("น้ำแตะ/ล้นตลิ่ง")
    if q is not None and q >= 1500:
        urgent = True
        reasons.append(f"เขื่อนเจ้าพระยาระบาย {q:.0f} ลบ.ม./วิ")

    out = SETTINGS.output_dir / "inburi_alert.json"
    out.parent.mkdir(exist_ok=True)
    last = _load_last_alert(out)
    cooldown = urgent and _cooldown_active(last, reasons)

    # บันทึก sent_at ทุกครั้งที่ urgent และไม่ใช่ cooldown
    # (ไม่ขึ้นกับ DRY_RUN เพื่อให้ cooldown ทำงานถูกต้องแม้ในโหมด dry)
    now_ts = now_local()
    alert = {
        "checked_at": now_ts.isoformat(),
        "sent_at": None if cooldown or not urgent else now_ts.isoformat(),
        "urgent": urgent,
        "cooldown_active": cooldown,
        "cooldown_minutes": SETTINGS.alert_cooldown_minutes,
        "reasons": reasons,
        "caption": report.get("caption", ""),
        "dry_run": SETTINGS.dry_run,
    }
    out.write_text(json.dumps(alert, ensure_ascii=False, indent=2), encoding="utf-8")

    if urgent and cooldown:
        print("⏳ ALERT COOLDOWN")
        print("; ".join(reasons))
    elif urgent:
        print("🚨 ALERT")
        print("; ".join(reasons))
    else:
        print("✅ NORMAL")
        print("ยังไม่เข้าเงื่อนไขเตือนด่วน")


if __name__ == "__main__":
    main()
