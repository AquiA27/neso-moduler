"""
Utility functions for common operations
"""
from typing import Any, Dict, Optional, Union


def record_to_dict(record: Any) -> Dict[str, Any]:
    """
    Record objesini dict'e çevir.
    
    Args:
        record: Database record objesi (Record, dict, veya başka bir obje)
    
    Returns:
        dict: Record'ın dict karşılığı, yoksa boş dict
    """
    if not record:
        return {}
    
    if hasattr(record, 'keys'):
        try:
            return dict(record)
        except (TypeError, ValueError):
            return {}
    
    if isinstance(record, dict):
        return record
    
    return {}


def safe_get(record: Any, key: str, default: Any = None) -> Any:
    """
    Record veya dict'ten güvenli şekilde değer al.
    
    Args:
        record: Database record objesi veya dict
        key: Alınacak key
        default: Key bulunamazsa döndürülecek varsayılan değer
    
    Returns:
        Key'in değeri veya default değer
    """
    if not record:
        return default
    
    # Önce dict'e çevir
    record_dict = record_to_dict(record)
    
    # Dict ise .get() kullan
    if isinstance(record_dict, dict):
        return record_dict.get(key, default)
    
    # Değilse getattr dene
    return getattr(record, key, default)


def safe_get_bool(record: Any, key: str, default: bool = False) -> bool:
    """
    Record veya dict'ten boolean değer al.
    
    Args:
        record: Database record objesi veya dict
        key: Alınacak key
        default: Key bulunamazsa döndürülecek varsayılan değer
    
    Returns:
        Boolean değer
    """
    value = safe_get(record, key, default)
    
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 't', 'y')
    
    return bool(value) if value is not None else default


def safe_get_int(record: Any, key: str, default: int = 0) -> int:
    """
    Record veya dict'ten integer değer al.
    
    Args:
        record: Database record objesi veya dict
        key: Alınacak key
        default: Key bulunamazsa döndürülecek varsayılan değer
    
    Returns:
        Integer değer
    """
    value = safe_get(record, key, default)
    
    if isinstance(value, int):
        return value
    
    if isinstance(value, str):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default

