"""Keep local data paths independent of the terminal's current directory."""

from pathlib import Path

PYTHON_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PYTHON_ROOT.parent
CACHE_PATH = PYTHON_ROOT / ".cache" / "records.sqlite3"
LOG_PATH = PYTHON_ROOT / ".cache" / "logs" / "search.jsonl"
MODEL_CACHE = REPO_ROOT / "models" / "huggingface"
LIBRARY_ROOT = PYTHON_ROOT / "library"
