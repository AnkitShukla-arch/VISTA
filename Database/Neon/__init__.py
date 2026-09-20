"""
Neon (PostgreSQL) Warehouse Adapter
Responsible for relational clinical schema and metadata warehouse operations.
"""
from Database.Neon.connection import NeonWarehouseManager

__all__ = ["NeonWarehouseManager"]
