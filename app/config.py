from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_SPECTRA_EXT = {".csv", ".asc"}
ALLOWED_INDEX_EXT = {".csv"}
