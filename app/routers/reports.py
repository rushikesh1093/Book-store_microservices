"""
app/routers/reports.py

Report generation & download.
  POST /reports/generate            Generate a PDF/CSV/Excel report (job-tracked)
  GET  /reports/sales               Sales report data (JSON) or ?format=pdf|csv|xlsx
  GET  /reports/inventory           Inventory report data (JSON) or ?format=...
  GET  /reports/customers           Customers report data (JSON) or ?format=...
  GET  /reports/{id}                Report job status / metadata
  GET  /reports/{id}/download       Download a generated report file

NOTE: the static /sales, /inventory, /customers routes are declared BEFORE the
dynamic /{report_id} route so they are matched first.
"""
import asyncio
import os
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.events import ReportJob
from app.models.schemas import ReportRequest, ReportResponse
from app.services.report_service import ReportService, build_dataset_records

router = APIRouter(prefix="/reports", tags=["reports"])

_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
_VALID_FORMATS = {"pdf", "csv", "xlsx"}


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


async def _report(
    report_type: str,
    fmt: Optional[str],
    start: Optional[date],
    end: Optional[date],
    db: AsyncSession,
):
    """
    Shared handler for the typed report endpoints.

    Without ?format= it returns the dataset as JSON rows. With a valid format it
    generates a downloadable file and returns the job metadata (including the
    download URL).
    """
    if fmt:
        fmt = fmt.lower()
        if fmt not in _VALID_FORMATS:
            raise HTTPException(400, f"Invalid format '{fmt}'. Use pdf, csv or xlsx.")
        try:
            job = await ReportService(db).generate(report_type, fmt, start, end)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        if job.status == "failed":
            raise HTTPException(500, f"Report generation failed: {job.error}")
        return _to_response(job)

    try:
        rows = await asyncio.to_thread(build_dataset_records, report_type, start, end)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"report_type": report_type, "count": len(rows), "rows": rows}


@router.get("/sales")
async def report_sales(
    format: Optional[str] = Query(None, description="pdf | csv | xlsx (omit for JSON)"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await _report("sales", format, start_date, end_date, db)


@router.get("/inventory")
async def report_inventory(
    format: Optional[str] = Query(None, description="pdf | csv | xlsx (omit for JSON)"),
    db: AsyncSession = Depends(get_db),
):
    return await _report("inventory", format, None, None, db)


@router.get("/customers")
async def report_customers(
    format: Optional[str] = Query(None, description="pdf | csv | xlsx (omit for JSON)"),
    db: AsyncSession = Depends(get_db),
):
    return await _report("customers", format, None, None, db)


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
