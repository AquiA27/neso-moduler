"""Intent tabanlı veri sorgulama çözümleyicisi."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from databases import Database

from app.config import schema_registry_loader as registry
from .query_builder import build_select_clause, build_order_clause, build_limit_clause
from .exceptions import UnknownIntentError, InvalidFilterError


@dataclass
class DataQueryRequest:
    intent: str
    entities: Dict[str, Any]
    filters: Optional[Dict[str, Any]] = None
    limit: Optional[int] = None
    fields: Optional[List[str]] = None


@dataclass
class DataQueryResult:
    rows: List[Dict[str, Any]]
    metadata: Dict[str, Any]


async def resolve_data_query(db: Database, request: DataQueryRequest) -> DataQueryResult:
    """Intent ve entity bilgilerinden SQL sorgusu oluşturup çalıştırır."""
    select_clause, resolved_fields = build_select_clause(request.intent, request.fields)
    where_clause, params = build_where_clause(request.intent, request.filters or {}, request.entities)
    order_clause = build_order_clause(request.intent, None)
    limit_clause = build_limit_clause(request.intent, request.limit)

    query = f"{select_clause}{where_clause}{order_clause}{limit_clause}"
    rows_raw = await db.fetch_all(query, params)
    rows = [dict(row) for row in rows_raw]

    return DataQueryResult(
        rows=rows,
        metadata={
            "intent": request.intent,
            "fields": resolved_fields or None,
            "filters": request.filters or {},
            "rows_returned": len(rows),
        },
    )


def build_where_clause(intent: str, filters: Dict[str, Any], entities: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    params: Dict[str, Any] = {}
    condition_parts: List[str] = []

    # Sube filtresi zorunlu (varsa)
    sube_id = entities.get("sube_id") or filters.get("sube_id")
    if sube_id is not None:
        condition_parts.append("sube_id = :sube_id")
        params["sube_id"] = sube_id

    if not filters:
        if condition_parts:
            return " WHERE " + " AND ".join(condition_parts), params
        return "", params

    for idx, (key, value) in enumerate(filters.items(), start=1):
        if key == "sube_id":
            # zaten eklendi
            continue
        # Tüm domain'lerde alias taraması (ileride intent->domain map optimize edilebilir)
        try:
            domain, field_meta = registry.resolve_alias(key)
        except registry.FieldNotFoundError as exc:  # type: ignore[attr-defined]
            raise InvalidFilterError(str(exc)) from exc

        operator = "="
        if isinstance(value, dict):
            operator = value.get("op", "=")
            param_value = value.get("value")
        else:
            param_value = value

        param_name = f"filter_{idx}"
        condition_parts.append(f"{field_meta['name']} {operator} :{param_name}")
        params[param_name] = param_value

    where_sql = " WHERE " + " AND ".join(condition_parts)
    return where_sql, params
