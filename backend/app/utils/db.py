"""
backend/app/utils/db.py
-----------------------
Database utility helpers.

Bu modül, codebase genelinde tekrar eden DB record → dict dönüşüm
pattern'lerini merkezileştirir.

Kullanım:
    from app.utils.db import record_to_dict, records_to_list

    user = await db.fetch_one(query)
    user_dict = record_to_dict(user)

    users = await db.fetch_all(query)
    users_list = records_to_list(users)
"""
from typing import Any, Dict, List, Optional, Union


def record_to_dict(record: Any) -> Optional[Dict[str, Any]]:
    """
    DB record'unu (asyncpg Record, databases Row, dict, vb.) güvenli şekilde
    dict'e çevirir. None gelirse None döner.

    Args:
        record: DB'den gelen herhangi bir row objesi.

    Returns:
        Dict[str, Any] | None
    """
    if record is None:
        return None
    if isinstance(record, dict):
        return record
    if hasattr(record, "_mapping"):
        # SQLAlchemy Row
        return dict(record._mapping)
    if hasattr(record, "keys"):
        # asyncpg Record, databases Row
        return dict(record)
    if hasattr(record, "__dict__"):
        # Pydantic model veya dataclass
        return {k: v for k, v in record.__dict__.items() if not k.startswith("_")}
    # Son çare: nesneyi olduğu gibi dön
    return record  # type: ignore[return-value]


def records_to_list(records: Any) -> List[Dict[str, Any]]:
    """
    DB kayıt listesini dict listesine çevirir. None veya boş gelirse [] döner.

    Args:
        records: DB'den gelen kayıt listesi.

    Returns:
        List[Dict[str, Any]]
    """
    if not records:
        return []
    return [record_to_dict(r) for r in records if r is not None]


def safe_int(value: Any, default: int = 0) -> int:
    """
    Güvenli integer dönüşümü. Dönüşüm başarısız olursa default döner.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """
    Güvenli string dönüşümü. None gelirse default döner.
    """
    if value is None:
        return default
    return str(value)
