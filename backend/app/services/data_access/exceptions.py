"""Özel data-access hataları."""
from __future__ import annotations


class DataAccessError(RuntimeError):
    """Veri erişim sürecinde meydana gelen genel hata."""


class UnknownIntentError(DataAccessError):
    """Bilinmeyen veya desteklenmeyen intent talep edildiğinde fırlatılır."""


class EntityNotFoundError(DataAccessError):
    """Beklenen entity veya alias bulunamadığında fırlatılır."""


class InvalidFilterError(DataAccessError):
    """Filtre parametreleri desteklenmediğinde fırlatılır."""



