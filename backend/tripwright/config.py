"""Settings from the environment. Variable names match the Akamai Hack Midwest starter kit.

Like the starter kit, every optional block has a local fallback: with no DATABASE_URL
trips live in a SQLite file, and with no OBJ_* settings evidence is written to disk.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")  # variables already set in the shell win, e.g. DEMO_MODE=true uvicorn ...

DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


# Akamai hosted inference (OpenAI-compatible chat completions).
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://ws.akamai-workshops.com/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CHAT_MODEL = os.getenv("CHAT_MODEL", "hackathon-chat")
# The workshop endpoint allows 60 requests/min per team and 4,096 output tokens.
MODEL_RPM = int(os.getenv("MODEL_RPM", "50"))
MODEL_CONCURRENCY = int(os.getenv("MODEL_CONCURRENCY", "4"))
MODEL_MAX_TOKENS = int(os.getenv("MODEL_MAX_TOKENS", "2000"))

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# Akamai Managed PostgreSQL; empty falls back to SQLite.
DATABASE_URL = os.getenv("DATABASE_URL", "") or f"sqlite:///{DATA_DIR / 'tripwright.db'}"

# Akamai Object Storage (S3-compatible); empty falls back to DATA_DIR/evidence.
OBJ_ENDPOINT = os.getenv("OBJ_ENDPOINT", "")
OBJ_BUCKET = os.getenv("OBJ_BUCKET", "")
OBJ_ACCESS_KEY = os.getenv("OBJ_ACCESS_KEY", "")
OBJ_SECRET_KEY = os.getenv("OBJ_SECRET_KEY", "")

DEMO_MODE = _flag("DEMO_MODE")  # serve recorded tool results, never browse
RECORD_FIXTURES = _flag("RECORD_FIXTURES")  # save live tool results as demo fixtures
BROWSER_WORKERS = int(os.getenv("BROWSER_WORKERS", "4"))  # parallel Chromium sessions
AGENT_TIMEOUT_S = int(os.getenv("AGENT_TIMEOUT_S", "240"))
MAX_RETRIES = 2  # times the orchestrator sends a result back before falling back
