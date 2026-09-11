"""
Neon (PostgreSQL) Warehouse Adapter (Owner: Ankit Shukla)
Responsible for relational clinical schema and metadata warehouse operations.
"""
from Database.Neon.connection import NeonWarehouseManager

__all__ = ["NeonWarehouseManager"]
