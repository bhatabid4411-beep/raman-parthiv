import os
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from fastapi import HTTPException

def find_col(df: pd.DataFrame, candidates, required=True, label=""):
    cols_norm = {c: c.strip() for c in df.columns}
    df.rename(columns=cols_norm, inplace=True)
    lower_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand in df.columns:
            return cand
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    if required:
        raise HTTPException(
            status_code=400,
            detail=f"Could not find '{label}' column. Tried: {candidates}. Found: {list(df.columns)}",
        )
    return None

def base_noext(s):
    s = str(s).strip()
    s = os.path.basename(s)
    return os.path.splitext(s)[0]

def generate_contour(
    merged_csv_path: Path,
    index_csv_path: Path,
    out_joined_csv: Path,
    out_png: Path,
    target_shift: float,
    tolerance: float,
) -> Tuple[float, int]:
    if not merged_csv_path.exists():
        raise HTTPException(status_code=400, detail="Merged spectra file missing.")
    if not index_csv_path.exists():
        raise HTTPException(status_code=400, detail="Index file missing.")

    spec = pd.read_csv(merged_csv_path)
    idx = pd.read_csv(index_csv_path)

    shift_col = find_col(spec, ["Shift","shift","RamanShift","Wavenumber","WaveNumber","Raman_Shift"], True, "Shift")

    # pick closest shift row
    irow = (spec[shift_col] - target_shift).abs().idxmin()
    actual_shift = float(spec.loc[irow, shift_col])

    if abs(actual_shift - target_shift) > tolerance:
        # not fatal; but you can make it fatal if needed
        pass

    vals = spec.loc[irow].drop(labels=[shift_col])
    df_vals = vals.reset_index()
    df_vals.columns = ["SpecCol","Intensity"]
    df_vals["Key"] = df_vals["SpecCol"].apply(base_noext)

    file_col = find_col(idx, ["FileName","filename","File","file","Name","name"], True, "FileName")
    x_col    = find_col(idx, ["X","x","Col","col","Column","column"], True, "X")
    y_col    = find_col(idx, ["Y","y","Row","row","Line","line"], True, "Y")

    idx["Key"] = idx[file_col].apply(base_noext)

    joined = pd.merge(idx, df_vals[["Key","Intensity"]], on="Key", how="inner")
    if joined.empty:
        strict = pd.merge(idx, df_vals, left_on=file_col, right_on="SpecCol", how="inner")
        joined = strict.rename(columns={file_col:"FileName", x_col:"X", y_col:"Y"})
    else:
        joined = joined.rename(columns={file_col:"FileName", x_col:"X", y_col:"Y"})

    if joined.empty:
        raise HTTPException(
            status_code=400,
            detail="No points joined. Check that index.csv filenames match spectra column names.",
        )

    joined[["FileName","X","Y","Intensity"]].to_csv(out_joined_csv, index=False)

    # plot contour
    x = joined["X"].astype(float).to_numpy()
    y = joined["Y"].astype(float).to_numpy()
    z = joined["Intensity"].astype(float).to_numpy()

    triang = mtri.Triangulation(x, y)
    plt.figure()
    cf = plt.tricontourf(triang, z, levels=64)
    plt.tricontour(triang, z, colors="k", linewidths=0.2)
    plt.gca().set_aspect("equal", adjustable="box")
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.title(f"Raman intensity at {actual_shift:.0f} cm$^{{-1}}$")
    cbar = plt.colorbar(cf)
    cbar.set_label("Intensity (a.u.)")
    plt.tight_layout()
    plt.savefig(out_png, dpi=300)
    plt.close()

    return actual_shift, int(len(joined))
