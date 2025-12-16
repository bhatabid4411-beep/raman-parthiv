from pydantic import BaseModel, Field

class MergeResponse(BaseModel):
    jobId: str
    mergedFilename: str
    totalFiles: int
    usedFiles: int

class ContourRequest(BaseModel):
    jobId: str
    target_shift: float = Field(..., description="Raman shift in cm^-1")
    tolerance: float = Field(0.5, description="Allowed mismatch in cm^-1")

class ContourResponse(BaseModel):
    jobId: str
    actual_shift: float
    joinedCsv: str
    contourPng: str
