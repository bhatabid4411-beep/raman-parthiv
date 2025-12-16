# app/services/merge_service.py
import os
from pathlib import Path
from typing import List, Tuple

import pandas as pd
from fastapi import HTTPException

from ..config import ALLOWED_SPECTRA_EXT


def _safe_stem(filename: str) -> str:
    base = os.path.basename(filename)
    return os.path.splitext(base)[0]


def merge_spectra_paths(paths: List[Path], out_path: Path) -> Tuple[int, int]:
    """
    Merge spectra from local file paths (csv/asc).
    Returns (total_files, used_files).
    """
    if not paths:
        raise HTTPException(status_code=400, detail="No spectra files found to merge.")

    merged = None
    used = 0
    total = 0

    for p in sorted(paths, key=lambda x: x.name.lower()):
        if not p.exists() or not p.is_file():
            continue

        ext = p.suffix.lower()
        if ext not in ALLOWED_SPECTRA_EXT:
            continue

        total += 1

        try:
            # sep=None auto-detect delimiter, comment lines start with '#'
            df = pd.read_csv(p, sep=None, engine="python", header=None, comment="#")
        except Exception:
            continue

        if df.shape[1] < 2:
            continue

        df = df.iloc[:, :2].copy()
        df.columns = ["Shift", _safe_stem(p.name)]
        df["Shift"] = pd.to_numeric(df["Shift"], errors="coerce")
        df = df.dropna(subset=["Shift"])

        if merged is None:
            merged = df
        else:
            merged = pd.merge(merged, df, on="Shift", how="outer")

        used += 1

    if merged is None or used == 0:
        raise HTTPException(status_code=400, detail="No valid spectra files found to merge.")

    merged = merged.sort_values("Shift")
    merged.to_csv(out_path, index=False)
    return total, used
