"""Schema registry loader for customer assistant data layer.

Provides cached access to field metadata, alias resolution and basic validation
for the JSON registry defined in ``schema_registry.json``.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


class SchemaRegistryError(RuntimeError):
    """Base error for schema registry issues."""


class DomainNotFoundError(SchemaRegistryError):
    """Raised when the requested domain is not defined in the registry."""


class FieldNotFoundError(SchemaRegistryError):
    """Raised when the requested field or alias is missing."""


_REGISTRY_FILE = Path(__file__).resolve().with_name("schema_registry.json")
_REQUIRED_DOMAIN_KEYS = {"table", "primary_key", "fields"}
_REQUIRED_FIELD_KEYS = {"name", "type", "description"}


@lru_cache(maxsize=1)
def _load_registry() -> Dict[str, Any]:
    if not _REGISTRY_FILE.exists():
        raise SchemaRegistryError(f"Schema registry bulunamadı: {_REGISTRY_FILE}")

    try:
        with _REGISTRY_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise SchemaRegistryError(
            f"Schema registry JSON formatı geçersiz: {exc}"
        ) from exc

    _validate_registry(data)
    return data


def _validate_registry(data: Dict[str, Any]) -> None:
    if "domains" not in data or not isinstance(data["domains"], dict):
        raise SchemaRegistryError("Schema registry 'domains' alanı eksik veya hatalı")

    for domain_name, domain_info in data["domains"].items():
        missing = _REQUIRED_DOMAIN_KEYS - set(domain_info.keys())
        if missing:
            raise SchemaRegistryError(
                f"'{domain_name}' domain'i için eksik zorunlu anahtarlar: {sorted(missing)}"
            )

        fields = domain_info.get("fields", [])
        if not isinstance(fields, list) or not fields:
            raise SchemaRegistryError(f"'{domain_name}' domain'i için alan listesi boş")

        for field in fields:
            missing_field_keys = _REQUIRED_FIELD_KEYS - set(field.keys())
            if missing_field_keys:
                raise SchemaRegistryError(
                    f"'{domain_name}.{field.get('name', '<unknown>')}' alanı için eksik "
                    f"anahtarlar: {sorted(missing_field_keys)}"
                )


def get_registry() -> Dict[str, Any]:
    """Return the full registry dictionary (cached)."""
    return _load_registry()


def list_domains() -> List[str]:
    """Return available domain names."""
    return sorted(get_registry()["domains"].keys())


def get_domain(domain: str) -> Dict[str, Any]:
    """Return metadata for the given domain."""
    registry = get_registry()
    try:
        return registry["domains"][domain]
    except KeyError as exc:
        raise DomainNotFoundError(f"Tanımsız domain: {domain}") from exc


def iter_fields(domain: str) -> Iterable[Dict[str, Any]]:
    """Yield field dictionaries for the given domain."""
    return get_domain(domain)["fields"]


def _alias_matches(field: Dict[str, Any], alias: str) -> bool:
    if field["name"] == alias:
        return True
    aliases = field.get("aliases", [])
    return isinstance(aliases, list) and alias in aliases


def find_field(domain: str, alias: str) -> Dict[str, Any]:
    """Find field metadata by name or alias within a domain."""
    alias_lower = alias.lower()
    for field in iter_fields(domain):
        candidates = [field["name"].lower()]
        aliases = field.get("aliases", [])
        if isinstance(aliases, list):
            candidates.extend(str(a).lower() for a in aliases)
        if alias_lower in candidates:
            return field
    raise FieldNotFoundError(f"'{domain}' domain'inde '{alias}' alanı bulunamadı")


def resolve_alias(alias: str) -> Tuple[str, Dict[str, Any]]:
    """Resolve an alias across all domains.

    Returns a tuple of (domain, field_metadata).
    """
    alias_lower = alias.lower()
    for domain in list_domains():
        for field in iter_fields(domain):
            names = [field["name"].lower()]
            aliases = field.get("aliases", [])
            if isinstance(aliases, list):
                names.extend(str(a).lower() for a in aliases)
            if alias_lower in names:
                return domain, field
    raise FieldNotFoundError(f"Alias '{alias}' hiçbir domain'de bulunamadı")


def get_relationships() -> List[Dict[str, Any]]:
    """Return the relationship definitions."""
    registry = get_registry()
    rels = registry.get("relationships", [])
    if not isinstance(rels, list):
        raise SchemaRegistryError("relationships alanı list olmadığından okunamadı")
    return rels


def get_metadata() -> Dict[str, Any]:
    """Return top-level metadata information."""
    registry = get_registry()
    return registry.get("metadata", {})



