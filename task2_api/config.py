import os
from datetime import date
from pathlib import Path

TODAY = date(2026, 12, 1)

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parent
DEFAULT_CSV = ROOT / "clean_items.csv"
DEFAULT_SQLITE = PACKAGE_DIR / "items.sqlite"


def database_url() -> str:
    configured = os.environ.get("DATABASE_URL")
    if configured:
        return configured
    return f"sqlite:///{DEFAULT_SQLITE.as_posix()}"


def api_key() -> str | None:
    return os.environ.get("API_KEY")
