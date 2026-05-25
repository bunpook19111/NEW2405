from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .caption import build_caption
from .config import SETTINGS
from .forecast import EmpiricalForecastModel, risk_from_level, validate
from .graphics import make_png_from_svg, make_svg
from .route_analysis import estimate_water_mass_to_inburi, explain_for_villagers, route_summary
from .ai_council import ai_council_summary
from .history import history_summary, latest_valid, load_history_csv
from .models import Observation
from .posting import build_make_payload, post_to_make
from .sources import fetch_live_observation, fetch_route_readings
from .utils import now_local


def _asdict(obj: Any) -> Any:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dataclass_fields__"):
        d = asdict(obj)
        return d
    return obj


def build_report(obs: Observation, model: EmpiricalForecastModel, target_q: float | None, route_readings: list[Any] | None = None) -> tuple[dict[str, Any], str, Path]:
    forecasts = model.forecast(obs.level_msl, obs.discharge_cms, target_q if target_q is not None else obs.discharge_cms)
    f24 = next((x for x in forecasts if x.horizon_h == 24), None)
    validation = validate(obs, model, target_q)
    risk = risk_from_level(obs.level_msl, obs.bank_msl, forecast_high=(f24.high_msl if f24 else None))
    mass = estimate_water_mass_to_inburi(obs)
    public_explain = explain_for_villagers(obs, risk, mass, forecasts)
    caption = build_caption(obs, forecasts, risk, validation) + "\n\n🧭 เส้นทางน้ำ: " + public_explain

    SETTINGS.output_dir.mkdir(parents=True, exist_ok=True)
    image_path = SETTINGS.output_dir / "inburi_friendly_water_watch.svg"
    make_svg(obs, forecasts, risk, validation, image_path)
    png_path = make_png_from_svg(image_path)

    report = {
        "generated_at": now_local().isoformat(),
        "observation": obs.to_dict(),
        "target_q_cms": target_q if target_q is not None else obs.discharge_cms,
        "forecast": [_asdict(x) for x in forecasts],
        "risk": _asdict(risk),
        "validation": _asdict(validation),
        "caption": caption,
        "image_path": str(image_path),
        "image_png_path": str(png_path) if png_path else None,
        "water_mass": mass.to_dict(),
        "route": route_summary(route_readings or []),
        "public_explain": public_explain,
        "model": {
            "name": "empirical-local-rating-lag-v1",
            "rmse_m": model.rmse_m,
            "q_range": model.q_range(),
            "history_rows_used": len(model.history),
        },
    }
    return report, caption, image_path


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    history = load_history_csv(args.history_csv or SETTINGS.history_csv)
    model = EmpiricalForecastModel(history)
    latest = latest_valid(history)

    if args.simulate_level is not None or args.simulate_q is not None:
        obs = Observation(
            ts=now_local(),
            level_msl=args.simulate_level if args.simulate_level is not None else (latest.level_msl if latest else None),
            discharge_cms=args.simulate_q if args.simulate_q is not None else (latest.discharge_cms if latest else None),
            bank_msl=SETTINGS.bank_level_msl,
            source="simulation",
            quality_note="โหมดจำลอง",
        )
    elif args.use_history_latest:
        obs = latest or Observation(now_local(), None, None, SETTINGS.bank_level_msl, "history_empty", "ไม่มีข้อมูลย้อนหลัง")
    else:
        obs = fetch_live_observation(latest)

    route_readings = fetch_route_readings(obs)
    report, caption, image_path = build_report(obs, model, args.target_q, route_readings)
    report["history_summary"] = history_summary(history)
    report["ai_council"] = ai_council_summary(report, enabled=not getattr(args, "no_ai", False))

    # Safe mode: never auto-post high-risk claims with low confidence.
    if SETTINGS.safe_mode and report["validation"]["confidence"] < SETTINGS.post_min_confidence:
        report["safe_mode_blocked"] = True
        report["caption"] = "⚠️ ระบบขอให้ตรวจสอบข้อมูลก่อนโพสต์\n\n" + caption
    else:
        report["safe_mode_blocked"] = False

    report_path = SETTINGS.output_dir / "inburi_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.post:
        payload = build_make_payload(report["caption"], report, image_path)
        if SETTINGS.dry_run:
            report["posted"] = False
            report["post_message"] = "DRY_RUN=true จึงยังไม่ส่ง Make.com"
        elif report["safe_mode_blocked"]:
            report["posted"] = False
            report["post_message"] = "Safe mode blocked auto post"
        else:
            ok, msg = post_to_make(payload)
            report["posted"] = ok
            report["post_message"] = msg
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(report["caption"])
    print(f"\nREPORT={report_path}")
    print(f"IMAGE={image_path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Inburi Chao Phraya AI flood watch")
    parser.add_argument("--post", action="store_true", help="send to Make.com webhook when safe")
    parser.add_argument("--use-history-latest", action="store_true", help="do not fetch live; use latest history row")
    parser.add_argument("--simulate-q", type=float, default=None, help="simulate Chao Phraya dam discharge cms")
    parser.add_argument("--simulate-level", type=float, default=None, help="simulate Inburi level MSL")
    parser.add_argument("--target-q", type=float, default=None, help="scenario: if dam discharge becomes this cms")
    parser.add_argument("--history-csv", type=Path, default=None, help="history CSV path")
    parser.add_argument("--no-ai", action="store_true", help="disable Gemini/Claude/OpenAI council even when keys exist")
    args = parser.parse_args()
    run_once(args)


if __name__ == "__main__":
    main()
