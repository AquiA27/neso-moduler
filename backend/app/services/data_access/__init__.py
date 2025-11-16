"""Data access service package for the customer assistant.

This package converts intent/entity tabanlı sorguları SQL ifadelerine çevirerek
veritabanından sonuç döndürmeyi hedefler. Şimdilik temel oluşturucu ve çözümleyici
fonksiyonları dışa aktarır.
"""
from .exceptions import DataAccessError, UnknownIntentError, EntityNotFoundError
from .resolver import resolve_data_query, DataQueryRequest, DataQueryResult

__all__ = [
    "DataAccessError",
    "UnknownIntentError",
    "EntityNotFoundError",
    "DataQueryRequest",
    "DataQueryResult",
    "resolve_data_query",
]



