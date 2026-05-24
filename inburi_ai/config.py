from __future__ import annotations

import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "รอดมั้ย AI น้ำอินทร์บุรี"
    timezone: str = os.getenv("TZ", "Asia/Bangkok")
    bank_level_msl: float = float(os.getenv("INBURI_BANK_LEVEL_MSL", "13.00"))
    history_csv: Path = Path(os.getenv("HISTORY_CSV", "data/inburi_history.csv"))
    output_dir: Path = Path(os.getenv("OUTPUT_DIR", "outputs"))
    make_webhook_url: str = os.getenv("MAKE_WEBHOOK_URL", "").strip()
    facebook_page_name: str = os.getenv("FACEBOOK_PAGE_NAME", "รอดมั้ย")
    safe_mode: bool = _bool("SAFE_MODE", True)
    dry_run: bool = _bool("DRY_RUN", True)
    post_min_confidence: int = int(os.getenv("POST_MIN_CONFIDENCE", "60"))
    request_timeout_s: int = int(os.getenv("REQUEST_TIMEOUT_S", "20"))
    verify_tls: bool = _bool("VERIFY_TLS", True)
    user_agent: str = os.getenv("USER_AGENT", "inburi-flood-watch-ai/1.0")
    ai_council_enabled: bool = _bool("AI_COUNCIL_ENABLED", False)
    alert_cooldown_minutes: int = int(os.getenv("ALERT_COOLDOWN_MINUTES", "120"))
    level_min_msl: float = float(os.getenv("INBURI_LEVEL_MIN_MSL", "8.0"))


SETTINGS = Settings()
