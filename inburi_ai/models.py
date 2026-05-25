from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Optional


@dataclass
class Observation:
    ts: datetime
    level_msl: Optional[float]
    discharge_cms: Optional[float]
    bank_msl: float
    source: str = "unknown"
    quality_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ts"] = self.ts.isoformat()
        return d


@dataclass
class ForecastPoint:
    horizon_h: int
    expected_level_msl: Optional[float]
    low_msl: Optional[float]
    high_msl: Optional[float]
    expected_change_m: Optional[float]
    eta_label: str


@dataclass
class RiskResult:
    level: str
    emoji: str
    color: str
    freeboard_m: Optional[float]
    score: int
    advice: str
    public_words: str


@dataclass
class ValidationResult:
    confidence: int
    issues: list[str]
    q_range: tuple[Optional[float], Optional[float]]
    model_rmse_m: float
    can_auto_post: bool


@dataclass
class ScenarioResult:
    target_q_cms: Optional[float]
    q_change_cms: Optional[float]
    forecast: list[ForecastPoint]
    risk: RiskResult
    validation: ValidationResult
