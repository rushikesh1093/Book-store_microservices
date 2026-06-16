"""
app/routers/reports.py

Report generation & download.
  POST /reports/generate
  GET  /reports/{id}/download
  GET  /reports/{id}          (status / metadata)
"""
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.events import ReportJob
from app.models.schemas import ReportRequest, ReportResponse
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])

_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _to_response(job: ReportJob) -> ReportResponse:
    return ReportResponse(
        id=job.id,
        report_type=job.report_type,
        file_format=job.file_format,
        status=job.status,
        file_name=job.file_name,
        download_url=f"/reports/{job.id}/download" if job.status == "ready" else None,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error=job.error,
    )


@router.post("/generate", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def generate_report(req: ReportRequest, db: AsyncSession = Depends(get_db)):
    try:
        job = await ReportService(db).generate(
            report_type=req.report_type,
            file_format=req.file_format,
            start=req.start_date,
            end=req.end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if job.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {job.error}",
        )
    return _to_response(job)


@router.get("/{report_id}", response_model=ReportResponse)
async def report_status(report_id: str, db: AsyncSession = Depends(get_db)):
    job = await ReportService(db).get(report_id)
    if not job:
        raise HTTPException(status_code=404, detail="Report not found")
    return _to_response(job)


@router.get("/{report_id}/download")
async def download_report(report_id: str, db: AsyncSession = Depends(get_db)):
    job = await ReportService(db).get(report_id)
    if not job:
        raise HTTPException(status_code=404, detail="Report not found")
    if job.status != "ready" or not job.file_path:
        raise HTTPException(status_code=409, detail=f"Report is '{job.status}', not ready")
    if not os.path.exists(job.file_path):
        raise HTTPException(status_code=410, detail="Report file no longer exists")

    return FileResponse(
        path=job.file_path,
        filename=job.file_name,
        media_type=_MEDIA_TYPES.get(job.file_format, "application/octet-stream"),
    )
