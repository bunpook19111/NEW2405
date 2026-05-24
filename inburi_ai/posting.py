from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from .config import SETTINGS
from .graphics import file_to_base64


def build_make_payload(caption: str, report: dict[str, Any], image_path: Path) -> dict[str, Any]:
    # ใช้ PNG ถ้ามี เพราะ Facebook/LINE ไม่รองรับ SVG
    png_path_str = report.get("image_png_path")
    if png_path_str:
        img_path = Path(png_path_str)
        if img_path.exists():
            return {
                "caption": caption,
                "page_name": SETTINGS.facebook_page_name,
                "risk_level": report.get("risk", {}).get("level"),
                "confidence": report.get("validation", {}).get("confidence"),
                "safe_mode_blocked": report.get("safe_mode_blocked", False),
                "image_filename": img_path.name,
                "image_mime": "image/png",
                "image_base64": file_to_base64(img_path),
                "report": report,
            }
    # Fallback ไปใช้ SVG ถ้าไม่มี PNG (cairosvg ไม่ได้ติดตั้ง)
    return {
        "caption": caption,
        "page_name": SETTINGS.facebook_page_name,
        "risk_level": report.get("risk", {}).get("level"),
        "confidence": report.get("validation", {}).get("confidence"),
        "safe_mode_blocked": report.get("safe_mode_blocked", False),
        "image_filename": image_path.name,
        "image_mime": "image/svg+xml",
        "image_base64": file_to_base64(image_path),
        "report": report,
        "image_warning": "PNG unavailable; SVG sent — Facebook/LINE may not display this correctly",
    }


def post_to_make(payload: dict[str, Any]) -> tuple[bool, str]:
    if not SETTINGS.make_webhook_url:
        return False, "MAKE_WEBHOOK_URL is empty"
    try:
        r = requests.post(SETTINGS.make_webhook_url, json=payload, timeout=SETTINGS.request_timeout_s)
        r.raise_for_status()
        return True, f"posted: HTTP {r.status_code}"
    except Exception as exc:
        return False, f"post failed: {exc}"
