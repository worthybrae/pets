"""Database helper — thin wrapper around Supabase client for common operations."""

import logging
import os
from typing import Any

from supabase import create_client, Client

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_supabase() -> Client:
    """Get Supabase client instance (singleton)."""
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SECRET_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SECRET_KEY must be set in environment."
            )
        _client = create_client(url, key)
    return _client


async def insert_row(table: str, data: dict[str, Any]) -> dict[str, Any]:
    """Insert a row into a table. Returns the inserted row."""
    client = get_supabase()
    response = client.table(table).insert(data).execute()
    if response.data:
        return response.data[0]
    return {}


async def query_rows(
    table: str, filters: dict[str, Any], limit: int = 100, order_by: str | None = None, descending: bool = True
) -> list[dict[str, Any]]:
    """Query rows from a table with optional filters and ordering."""
    client = get_supabase()
    query = client.table(table).select("*")
    for key, value in filters.items():
        query = query.eq(key, value)
    if order_by:
        query = query.order(order_by, desc=descending)
    query = query.limit(limit)
    response = query.execute()
    return response.data or []


async def upsert_row(table: str, data: dict[str, Any], on_conflict: str = "id") -> dict[str, Any]:
    """Upsert a row (insert or update on conflict). Returns the upserted row."""
    client = get_supabase()
    response = client.table(table).upsert(data, on_conflict=on_conflict).execute()
    if response.data:
        return response.data[0]
    return {}


async def rpc(function_name: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Call a Postgres RPC function."""
    client = get_supabase()
    response = client.rpc(function_name, params).execute()
    return response.data or []
