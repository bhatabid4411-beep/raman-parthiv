import shutil
import uuid
from pathlib import Path
from .config import OUTPUT_DIR

def new_job_id() -> str:
    return uuid.uuid4().hex

def job_dir(job_id: str) -> Path:
    p = OUTPUT_DIR / job_id
    p.mkdir(parents=True, exist_ok=True)
    return p

def ensure_job(job_id: str) -> Path:
    p = OUTPUT_DIR / job_id
    if not p.exists():
        raise FileNotFoundError(f"Job not found: {job_id}")
    return p

def clear_all_jobs() -> int:
    """
    Deletes all job folders under OUTPUT_DIR.
    Returns count of deleted job folders.
    """
    if not OUTPUT_DIR.exists():
        return 0

    deleted = 0
    for item in OUTPUT_DIR.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
            deleted += 1
        else:
            # if any stray files exist
            try:
                item.unlink()
            except Exception:
                pass
    return deleted
