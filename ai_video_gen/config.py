import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Google Cloud / Vertex AI ---
PROJECT_ID: str = os.getenv("PROJECT_ID", "")
LOCATION: str = os.getenv("LOCATION", "us-central1")
GCS_BUCKET: str = os.getenv("GCS_BUCKET", "").strip()

# --- Veo model ---
VEO_MODEL: str = "veo-3.1-generate-001"

# --- File paths ---
PROMPTS_FILE = Path("input/prompts.json")
OUTPUT_DIR = Path("output")
STYLE_PACKS_FILE = Path("style_packs.json")

# --- Polling ---
POLL_INTERVAL_SECONDS: int = 15

# --- Logo overlay defaults ---
DEFAULT_LOGO_PATH = Path("input/images/logo.png")
DEFAULT_LOGO_POSITION: str = "bottom-right"
DEFAULT_LOGO_SCALE: float = 0.08
DEFAULT_LOGO_OPACITY: float = 0.85
DEFAULT_LOGO_MARGIN: int = 30
