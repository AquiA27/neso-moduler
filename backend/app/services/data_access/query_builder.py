"""Intent tabanlı sorgu oluşturucu."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.config.schema_registry_loader import find_field
from .exceptions import UnknownIntentError

# Intent -> view tanımları. İlk sprintte ana örnekler ekleniyor.
INTENT_QUERY_MAP: Dict[str, Dict[str, Any]] = {
    "menu_liste": {
        "view": "vw_ai_menu_stock",
        "domain": "menu",
        "default_limit": 50,
        "order_by": "kategori, urun_adi",
    },
    "stok_durumu": {
        "view": "vw_ai_menu_stock",
        "domain": "menu",
        "default_limit": 50,
        "order_by": "stok_kritik DESC, urun_adi",
    },
    "aktif_adisyonlar": {
        "view": "vw_ai_active_sessions",
        "domain": "satis",
        "default_limit": 20,
        "order_by": "acilis_zamani DESC",
    },
    "satis_ozet": {
        "view": "vw_ai_sales_summary",
        "domain": "satis",
        "default_limit": 30,
        "order_by": "gun DESC",
    },
}


def build_select_clause(intent: str, fields: List[str] | None = None) -> Tuple[str, List[str]]:
    intent_def = INTENT_QUERY_MAP.get(intent)
    if not intent_def:
        raise UnknownIntentError(f"Desteklenmeyen intent: {intent}")

    view_name = intent_def["view"]
    if not fields:
        return f"SELECT * FROM {view_name}", []

    resolved_fields: List[str] = []
    domain = intent_def.get("domain") or guess_domain_from_view(view_name)
    if not domain:
        raise UnknownIntentError(
            f"Intent '{intent}' için domain belirlenemedi; alan seçimi yapılamıyor"
        )

    for alias in fields:
        field_meta = find_field(domain, alias)
        resolved_fields.append(field_meta["name"])

    select_clause = f"SELECT {', '.join(resolved_fields)} FROM {view_name}"
    return select_clause, resolved_fields


def guess_domain_from_view(view_name: str) -> str | None:
    """Basit eşleme: view adı domain adı içeriyorsa tahmin et."""
    mapping = {
        "menu_stock": "menu",
        "sales_summary": "satis",
        "active_sessions": "satis",
    }
    for key, domain in mapping.items():
        if key in view_name:
            return domain
    return None


def build_order_clause(intent: str, custom_order: str | None = None) -> str:
    intent_def = INTENT_QUERY_MAP.get(intent)
    if not intent_def:
        raise UnknownIntentError(f"Desteklenmeyen intent: {intent}")
    order = custom_order or intent_def.get("order_by")
    return f" ORDER BY {order}" if order else ""


def build_limit_clause(intent: str, limit: int | None) -> str:
    intent_def = INTENT_QUERY_MAP.get(intent)
    if not intent_def:
        raise UnknownIntentError(f"Desteklenmeyen intent: {intent}")

    default_limit = intent_def.get("default_limit", 50)
    final_limit = min(limit, 200) if limit else default_limit
    return f" LIMIT {int(final_limit)}"
