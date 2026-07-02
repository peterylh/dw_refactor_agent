"""
Business semantics catalog loading and domain definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from . import core

BUSINESS_SEMANTICS_FILE_NAME = "business_semantics.yaml"

_business_semantics_cache = {}


@dataclass
class DomainDef:
    id: str
    code: str
    name: str
    desc: str = ""
    keywords: list[str] = field(default_factory=list)


@dataclass
class BusinessAreaDef:
    id: str
    code: str
    name: str
    desc: str = ""
    keywords: list[str] = field(default_factory=list)


@dataclass
class BusinessDomainConfig:
    domains: dict[str, DomainDef]
    business_areas: dict[str, BusinessAreaDef]

    @property
    def domain_ids(self) -> list[str]:
        return sorted(self.domains)

    @property
    def business_area_codes(self) -> list[str]:
        return sorted(self.business_areas)

    def is_valid_domain(self, value: str) -> bool:
        return str(value or "").strip() in self.domains

    def is_valid_business_area(self, value: str) -> bool:
        return str(value or "").strip().upper() in self.business_areas

    def normalize_business_area(self, value: str) -> str:
        return str(value or "").strip().upper()

    def normalize_domain(self, value: str) -> str:
        raw = str(value or "").strip()
        if raw in self.domains:
            return raw
        if raw.isdigit():
            padded = raw.zfill(2)
            if padded in self.domains:
                return padded
        upper = raw.upper()
        for domain in self.domains.values():
            if upper == domain.code:
                return domain.id
        return raw

    def prompt_options(self) -> dict:
        return {
            "domains": [
                {
                    "id": domain.id,
                    "code": domain.code,
                    "name": domain.name,
                    "description": domain.desc,
                }
                for domain in self.domains.values()
            ],
            "business_areas": [
                {
                    "id": area.id,
                    "code": area.code,
                    "name": area.name,
                    "description": area.desc,
                }
                for area in self.business_areas.values()
            ],
        }


def clear_business_semantics_cache() -> None:
    _business_semantics_cache.clear()


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _as_keywords(value) -> list[str]:
    return [str(item).strip() for item in _as_list(value) if str(item).strip()]


def dictionary_entries(raw_dictionary) -> list[dict]:
    if not raw_dictionary:
        return []
    values = (
        raw_dictionary.get("values")
        if isinstance(raw_dictionary, dict) and "values" in raw_dictionary
        else raw_dictionary
    )
    if isinstance(values, list):
        return [item for item in values if isinstance(item, dict)]
    if isinstance(values, dict):
        entries = []
        for key, cfg in values.items():
            if not isinstance(cfg, dict):
                continue
            entry = dict(cfg)
            entry.setdefault("id", str(key))
            entry.setdefault("code", str(key))
            entries.append(entry)
        return entries
    return []


def business_semantics_dictionaries(catalog: dict) -> dict:
    if not isinstance(catalog, dict) or not catalog:
        return {}
    dictionaries = {}
    data_domains = [
        dict(entry)
        for entry in dictionary_entries(catalog.get("data_domains"))
    ]
    business_areas = [
        dict(entry)
        for entry in dictionary_entries(catalog.get("business_areas"))
    ]
    if data_domains:
        dictionaries["data_domains"] = {"values": data_domains}
    if business_areas:
        dictionaries["business_areas"] = {"values": business_areas}
    return dictionaries


def _load_domain_defs(raw_domains) -> dict[str, DomainDef]:
    domains = {}
    for cfg in dictionary_entries(raw_domains):
        domain_id = str(cfg.get("id") or "").strip()
        if not domain_id:
            continue
        domain_code = str(cfg.get("code") or domain_id).strip().upper()
        domains[domain_id] = DomainDef(
            id=domain_id,
            code=domain_code,
            name=str(cfg.get("name") or domain_code),
            desc=str(cfg.get("desc") or cfg.get("description") or ""),
            keywords=_as_keywords(cfg.get("keywords")),
        )
    return domains


def _load_business_area_defs(raw_areas) -> dict[str, BusinessAreaDef]:
    business_areas = {}
    for cfg in dictionary_entries(raw_areas):
        area_code = str(cfg.get("code") or "").strip().upper()
        if not area_code:
            continue
        business_areas[area_code] = BusinessAreaDef(
            id=str(cfg.get("id") or area_code),
            code=area_code,
            name=str(cfg.get("name") or area_code),
            desc=str(cfg.get("desc") or cfg.get("description") or ""),
            keywords=_as_keywords(cfg.get("keywords")),
        )
    return business_areas


def business_domain_config_from_dictionaries(
    raw_dictionaries: dict,
) -> Optional[BusinessDomainConfig]:
    raw_domains = (raw_dictionaries or {}).get("data_domains")
    raw_areas = (raw_dictionaries or {}).get("business_areas")
    if not raw_domains or not raw_areas:
        return None
    domains = _load_domain_defs(raw_domains)
    business_areas = _load_business_area_defs(raw_areas)
    if not domains or not business_areas:
        return None
    return BusinessDomainConfig(domains=domains, business_areas=business_areas)


def business_semantics_path(project: str) -> Optional[Path]:
    cfg = core.PROJECT_CONFIG.get(project)
    if not cfg:
        return None
    return core.PROJECT_ROOT / cfg["dir"] / BUSINESS_SEMANTICS_FILE_NAME


def load_business_semantics_catalog(project: str) -> dict:
    path = business_semantics_path(project)
    if not path:
        return {}
    cache_key = f"{project}:{path}"
    if cache_key in _business_semantics_cache:
        return _business_semantics_cache[cache_key]
    if not path.exists():
        _business_semantics_cache[cache_key] = {}
        return {}
    raw = yaml.safe_load(path.read_text(encoding=core.TEXT_ENCODING)) or {}
    if not isinstance(raw, dict):
        raw = {}
    _business_semantics_cache[cache_key] = raw
    return raw


def business_domain_config_from_semantics_catalog(
    catalog: dict,
) -> Optional[BusinessDomainConfig]:
    if not catalog:
        return None
    domains = _load_domain_defs(catalog.get("data_domains"))
    business_areas = _load_business_area_defs(catalog.get("business_areas"))
    if not domains or not business_areas:
        return None
    return BusinessDomainConfig(domains=domains, business_areas=business_areas)


def get_business_domain_config(
    project: str = None,
) -> Optional[BusinessDomainConfig]:
    if project:
        catalog_config = business_domain_config_from_semantics_catalog(
            load_business_semantics_catalog(project)
        )
        if catalog_config:
            return catalog_config

    from .naming import get_naming_config

    return get_naming_config(project).business_domain_config
