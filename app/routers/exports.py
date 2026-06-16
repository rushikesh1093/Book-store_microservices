"""
app/routers/exports.py

Direct, streamed data exports (no job tracking).
  GET /exports/sales.csv
  GET /exports/sales.xlsx
"""
import io
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.services.report_service import _sales_dataframe

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/sales.csv")
async def export_sales_csv(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    df = _sales_dataframe(start_date, end_date)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sales.csv"},
    )


@router.get("/sales.xlsx")
async def export_sales_xlsx(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    df = _sales_dataframe(start_date, end_date)
    buffer = io.BytesIO()
    with pd_excel_writer(buffer) as writer:
        df.to_excel(writer, index=False, sheet_name="Sales")
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": "attachment; filename=sales.xlsx"},
    )


def pd_excel_writer(buffer: io.BytesIO):
    import pandas as pd

    return pd.ExcelWriter(buffer, engine="openpyxl")
