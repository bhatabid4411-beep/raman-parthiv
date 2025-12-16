from pathlib import Path
from typing import List
import zipfile
import io


from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse, StreamingResponse

from .schemas import MergeResponse, ContourRequest, ContourResponse
from .storage import new_job_id, job_dir, ensure_job, clear_all_jobs
from .services.merge_service import merge_spectra_paths
from .services.contour_service import generate_contour

app = FastAPI(title="Raman CSV Backend")

MERGED_NAME = "merged_raman_map.csv"

@app.get("/")
def health():
    return {"status": "ok"}



@app.post("/jobs/merge-spectra", response_model=MergeResponse)
async def merge_spectra(zip_file: UploadFile = File(...)):
    # ✅ delete previous outputs
    clear_all_jobs()

    # validate zip
    if not zip_file.filename or not zip_file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Please upload a .zip file.")

    job_id = new_job_id()
    jdir = job_dir(job_id)

    zip_path = jdir / "upload.zip"
    zip_bytes = await zip_file.read()
    if not zip_bytes:
        raise HTTPException(status_code=400, detail="Zip file is empty.")
    zip_path.write_bytes(zip_bytes)

    extract_dir = jdir / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)

    # extract safely (prevent zip slip)
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            for member in z.infolist():
                member_path = (extract_dir / member.filename).resolve()
                if extract_dir not in member_path.parents and member_path != extract_dir:
                    raise HTTPException(status_code=400, detail="Unsafe zip contents (path traversal).")
            z.extractall(extract_dir)
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid zip file.")

    # collect spectra files recursively
    spectra_paths = []
    for ext in (".csv", ".asc"):
        spectra_paths.extend(extract_dir.rglob(f"*{ext}"))

    out_path = jdir / MERGED_NAME
    total, used = merge_spectra_paths(spectra_paths, out_path)

    return MergeResponse(
        jobId=job_id,
        mergedFilename=MERGED_NAME,
        totalFiles=total,
        usedFiles=used,
    )

@app.post("/jobs/contour")
async def contour(
    jobId: str = Form(...),
    target_shift: float = Form(...),
    tolerance: float = Form(0.5),
    index_file: UploadFile = File(...),
):
    jdir = ensure_job(jobId)

    merged_csv = jdir / MERGED_NAME
    if not merged_csv.exists():
        raise HTTPException(status_code=400, detail="Run /jobs/merge-spectra first for this jobId.")

    index_path = jdir / "index.csv"
    raw = await index_file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="index.csv is empty.")
    index_path.write_bytes(raw)

    shift_int = int(target_shift)
    out_joined = jdir / f"intensity_{shift_int}_joined.csv"
    out_png = jdir / f"contour_{shift_int}.png"

    actual_shift, points = generate_contour(
        merged_csv_path=merged_csv,
        index_csv_path=index_path,
        out_joined_csv=out_joined,
        out_png=out_png,
        target_shift=target_shift,
        tolerance=tolerance,
    )

    # ✅ build zip in memory
    zip_buf = io.BytesIO()
    zip_name = f"contour_{shift_int}_outputs.zip"

    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(out_png, arcname=out_png.name)
        z.write(out_joined, arcname=out_joined.name)

        # optional: include a small info txt
        info = f"jobId={jobId}\nrequested_shift={target_shift}\nactual_shift={actual_shift}\npoints={points}\n"
        z.writestr("info.txt", info)

    zip_buf.seek(0)

    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
    )

@app.get("/jobs/{job_id}/file/{filename}")
def get_job_file(job_id: str, filename: str):
    jdir = ensure_job(job_id)
    path = (jdir / filename).resolve()

    # prevent path traversal
    if jdir not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")

    # correct media types
    if filename.lower().endswith(".png"):
        return FileResponse(path, media_type="image/png", filename=filename)
    if filename.lower().endswith(".csv"):
        return FileResponse(path, media_type="text/csv", filename=filename)

    return FileResponse(path, filename=filename)
