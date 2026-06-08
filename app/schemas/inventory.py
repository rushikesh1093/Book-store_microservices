"""
schemas/inventory.py — Pydantic schemas for inventory reports.
TODO: Implement once inventory data pipeline is built.
"""
from pydantic import BaseModel
from typing import Optional


class InventoryStatus(BaseModel):
    """Placeholder: stock status for a single book."""
    book_id:    str
    title:      str
    quantity:   int   = 0
    reserved:   int   = 0
    available:  int   = 0
    # TODO: Add reorder_level, warehouse_location


class LowStockAlert(BaseModel):
    """Placeholder: alert for books below reorder level."""
    book_id:       str
    title:         str
    current_stock: int
    reorder_level: int
