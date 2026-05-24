from __future__ import annotations

import os
from typing import Any

import requests

from .config import SETTINGS


def build_ai_prompt(report: dict[str, Any]) -> str:
    slim = {
        "observation": report.get("observation"),
        "risk": report.get("risk"),
        "forecast": report.get("forecast"),
        "water_mass": report.get("water_mass"),
        "route": report.get("route"),
        "validation": report.get("validation"),
    }
    return (
        "คุณคือผู้ช่วยวิเคราะห์น้ำเจ้าพระยาเพื่อชาวบ้านอินทร์บุรี "
        "ให้สรุปสั้น ชัด ไม่ตื่นตระหนก ระบุความไม่แน่นอน ห้ามฟันธงเกินข้อมูลจริง "
        "และให้คำแนะนำที่ชาวบ้านทำตามได้ทันที\n"
        f"ข้อมูลรายงาน JSON:\n{slim}"
    )


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> str:
    r = requests.post(url, headers=headers, json=payload, timeout=SETTINGS.request_timeout_s)
    r.raise_for_status()
    data = r.json()
    # Try common response shapes.
    if isinstance(data, dict):
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        if "content" in data and isinstance(data["content"], list):
            return "\n".join(x.get("text", "") for x in data["content"] if isinstance(x, dict)).strip()
        if "candidates" in data:
            parts = data["candidates"][0].get("content", {}).get("parts", [])
            return "\n".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    return str(data)[:1200]


def _call_openai(prompt: str) -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("missing OPENAI_API_KEY")
    return _post_json(
        "https://api.openai.com/v1/chat/completions",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        {"model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"), "messages": [{"role": "user", "content": prompt}], "temperature": 0.2},
    )


def _call_claude(prompt: str) -> str:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("missing ANTHROPIC_API_KEY")
    return _post_json(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
        {"model": os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"), "max_tokens": 700, "messages": [{"role": "user", "content": prompt}]},
    )


def _call_gemini(prompt: str) -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("missing GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    return _post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
        {"Content-Type": "application/json"},
        {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2, "maxOutputTokens": 700}},
    )


def _fallback(report: dict[str, Any], available: dict[str, bool], note: str = "") -> dict[str, Any]:
    risk = report.get("risk", {})
    mass = report.get("water_mass", {})
    return {
        "mode": "deterministic_fallback",
        "available_models": available,
        "consensus": f"ระดับเตือน {risk.get('emoji','')} {risk.get('level','ไม่ทราบ')} — {mass.get('volume_label','ยังไม่ทราบมวลน้ำ')} — {mass.get('eta_window_text','ยังไม่ทราบเวลาถึง')}",
        "note": note or "ใช้ fallback เพื่อไม่ให้ระบบหยุดเมื่อ AI ภายนอกไม่พร้อม",
    }


def ai_council_summary(report: dict[str, Any], enabled: bool = True) -> dict[str, Any]:
    available = {
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "claude": bool(os.getenv("ANTHROPIC_API_KEY")),
        "openai": bool(os.getenv("OPENAI_API_KEY")),
    }
    if not enabled or not SETTINGS.ai_council_enabled or not any(available.values()):
        return _fallback(report, available, "AI Council ปิดอยู่หรือยังไม่ได้ตั้ง API keys")

    prompt = build_ai_prompt(report)
    responses: dict[str, str] = {}
    errors: dict[str, str] = {}
    for name, fn in (("gemini", _call_gemini), ("claude", _call_claude), ("openai", _call_openai)):
        if not available[name]:
            continue
        try:
            responses[name] = fn(prompt)[:1600]
        except Exception as exc:
            errors[name] = str(exc)[:300]

    if not responses:
        return _fallback(report, available, f"AI call ล้มเหลวทั้งหมด: {errors}")
    consensus = "\n\n".join(f"[{k}] {v}" for k, v in responses.items())
    return {"mode": "multi_ai_live", "available_models": available, "responses": responses, "errors": errors, "consensus": consensus[:2800]}
