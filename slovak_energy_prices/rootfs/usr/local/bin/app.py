#!/usr/bin/env python3
"""Small API service for Slovak energy price data."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


OPTIONS_PATH = Path("/data/options.json")
CUSTOM_PRICES_PATH = Path("/data/custom_prices.json")
PRESETS_PATH = Path(__file__).with_name("provider_presets.json")
DEFAULT_PORT = 8099
DEFAULT_TIMEZONE = "Europe/Bratislava"
OKTE_DAM_URL = "https://isot.okte.sk/api/v1/dam/results"
VALID_ELECTRICITY_MODES = {"household_fixed", "spot_okte", "manual"}
VALID_GAS_MODES = {"household_fixed", "manual"}
VALID_WATER_MODES = {"household_fixed", "manual"}
VALID_CHARGE_STRUCTURES = {"total", "split"}


@dataclass
class AppConfig:
    port: int = DEFAULT_PORT
    timezone: str = DEFAULT_TIMEZONE
    okte_enabled: bool = True
    urso_enabled: bool = False
    electricity_pricing_mode: str = "household_fixed"
    electricity_preset_id: str = ""
    electricity_charge_structure: str = "total"
    electricity_fixed_price_eur_per_kwh: float = 0.18
    electricity_fixed_monthly_fee_eur: float = 0.0
    electricity_commodity_price_eur_per_kwh: float = 0.18
    electricity_distribution_price_eur_per_kwh: float = 0.0
    electricity_taxes_price_eur_per_kwh: float = 0.0
    electricity_other_price_eur_per_kwh: float = 0.0
    electricity_supplier_fixed_monthly_fee_eur: float = 0.0
    electricity_distribution_fixed_monthly_fee_eur: float = 0.0
    electricity_tax_fixed_monthly_fee_eur: float = 0.0
    electricity_other_fixed_monthly_fee_eur: float = 0.0
    gas_pricing_mode: str = "household_fixed"
    gas_preset_id: str = ""
    gas_charge_structure: str = "total"
    gas_fixed_price_eur_per_kwh: float = 0.065
    gas_fixed_monthly_fee_eur: float = 0.0
    gas_commodity_price_eur_per_kwh: float = 0.065
    gas_distribution_price_eur_per_kwh: float = 0.0
    gas_taxes_price_eur_per_kwh: float = 0.0
    gas_other_price_eur_per_kwh: float = 0.0
    gas_supplier_fixed_monthly_fee_eur: float = 0.0
    gas_distribution_fixed_monthly_fee_eur: float = 0.0
    gas_tax_fixed_monthly_fee_eur: float = 0.0
    gas_other_fixed_monthly_fee_eur: float = 0.0
    water_pricing_mode: str = "household_fixed"
    water_preset_id: str = ""
    water_supply_price_eur_per_m3: float = 1.2
    water_wastewater_price_eur_per_m3: float = 1.1
    water_fixed_monthly_fee_eur: float = 0.0


class DataSourceError(RuntimeError):
    """Raised when an external data source cannot be read."""


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataSourceError(f"Invalid JSON in {path}") from exc


def load_config() -> AppConfig:
    payload = load_json_file(OPTIONS_PATH)
    config = AppConfig(
        port=int(payload.get("port", DEFAULT_PORT)),
        timezone=str(payload.get("timezone", DEFAULT_TIMEZONE)),
        okte_enabled=bool(payload.get("okte_enabled", True)),
        urso_enabled=bool(payload.get("urso_enabled", False)),
        electricity_pricing_mode=str(payload.get("electricity_pricing_mode", "household_fixed")),
        electricity_preset_id=str(payload.get("electricity_preset_id", "")).strip(),
        electricity_charge_structure=str(payload.get("electricity_charge_structure", "total")),
        electricity_fixed_price_eur_per_kwh=float(payload.get("electricity_fixed_price_eur_per_kwh", 0.18)),
        electricity_fixed_monthly_fee_eur=float(payload.get("electricity_fixed_monthly_fee_eur", 0.0)),
        electricity_commodity_price_eur_per_kwh=float(payload.get("electricity_commodity_price_eur_per_kwh", 0.18)),
        electricity_distribution_price_eur_per_kwh=float(payload.get("electricity_distribution_price_eur_per_kwh", 0.0)),
        electricity_taxes_price_eur_per_kwh=float(payload.get("electricity_taxes_price_eur_per_kwh", 0.0)),
        electricity_other_price_eur_per_kwh=float(payload.get("electricity_other_price_eur_per_kwh", 0.0)),
        electricity_supplier_fixed_monthly_fee_eur=float(payload.get("electricity_supplier_fixed_monthly_fee_eur", 0.0)),
        electricity_distribution_fixed_monthly_fee_eur=float(payload.get("electricity_distribution_fixed_monthly_fee_eur", 0.0)),
        electricity_tax_fixed_monthly_fee_eur=float(payload.get("electricity_tax_fixed_monthly_fee_eur", 0.0)),
        electricity_other_fixed_monthly_fee_eur=float(payload.get("electricity_other_fixed_monthly_fee_eur", 0.0)),
        gas_pricing_mode=str(payload.get("gas_pricing_mode", "household_fixed")),
        gas_preset_id=str(payload.get("gas_preset_id", "")).strip(),
        gas_charge_structure=str(payload.get("gas_charge_structure", "total")),
        gas_fixed_price_eur_per_kwh=float(payload.get("gas_fixed_price_eur_per_kwh", 0.065)),
        gas_fixed_monthly_fee_eur=float(payload.get("gas_fixed_monthly_fee_eur", 0.0)),
        gas_commodity_price_eur_per_kwh=float(payload.get("gas_commodity_price_eur_per_kwh", 0.065)),
        gas_distribution_price_eur_per_kwh=float(payload.get("gas_distribution_price_eur_per_kwh", 0.0)),
        gas_taxes_price_eur_per_kwh=float(payload.get("gas_taxes_price_eur_per_kwh", 0.0)),
        gas_other_price_eur_per_kwh=float(payload.get("gas_other_price_eur_per_kwh", 0.0)),
        gas_supplier_fixed_monthly_fee_eur=float(payload.get("gas_supplier_fixed_monthly_fee_eur", 0.0)),
        gas_distribution_fixed_monthly_fee_eur=float(payload.get("gas_distribution_fixed_monthly_fee_eur", 0.0)),
        gas_tax_fixed_monthly_fee_eur=float(payload.get("gas_tax_fixed_monthly_fee_eur", 0.0)),
        gas_other_fixed_monthly_fee_eur=float(payload.get("gas_other_fixed_monthly_fee_eur", 0.0)),
        water_pricing_mode=str(payload.get("water_pricing_mode", "household_fixed")),
        water_preset_id=str(payload.get("water_preset_id", "")).strip(),
        water_supply_price_eur_per_m3=float(payload.get("water_supply_price_eur_per_m3", 1.2)),
        water_wastewater_price_eur_per_m3=float(payload.get("water_wastewater_price_eur_per_m3", 1.1)),
        water_fixed_monthly_fee_eur=float(payload.get("water_fixed_monthly_fee_eur", 0.0)),
    )
    validate_config(config)
    return config


def validate_config(config: AppConfig) -> None:
    if config.electricity_pricing_mode not in VALID_ELECTRICITY_MODES:
        raise DataSourceError(
            "Invalid electricity_pricing_mode. Use household_fixed, spot_okte, or manual."
        )
    if config.gas_pricing_mode not in VALID_GAS_MODES:
        raise DataSourceError("Invalid gas_pricing_mode. Use household_fixed or manual.")
    if config.water_pricing_mode not in VALID_WATER_MODES:
        raise DataSourceError("Invalid water_pricing_mode. Use household_fixed or manual.")
    if config.electricity_charge_structure not in VALID_CHARGE_STRUCTURES:
        raise DataSourceError("Invalid electricity_charge_structure. Use total or split.")
    if config.gas_charge_structure not in VALID_CHARGE_STRUCTURES:
        raise DataSourceError("Invalid gas_charge_structure. Use total or split.")


def fetch_json(url: str, params: dict[str, str]) -> Any:
    full_url = f"{url}?{urlencode(params)}"
    request = Request(
        full_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "ha-slovak-energy-prices/0.1.0",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise DataSourceError(f"HTTP {exc.code} from {url}") from exc
    except URLError as exc:
        raise DataSourceError(f"Network error calling {url}: {exc.reason}") from exc


def load_provider_presets() -> dict[str, Any]:
    payload = load_json_file(PRESETS_PATH)
    return {
        "electricity": payload.get("electricity", {}),
        "gas": payload.get("gas", {}),
        "water": payload.get("water", {}),
    }


def get_provider_preset(presets: dict[str, Any], utility: str, preset_id: str) -> dict[str, Any] | None:
    if not preset_id:
        return None
    preset = presets.get(utility, {}).get(preset_id)
    if not isinstance(preset, dict):
        raise DataSourceError(f"Unknown preset '{preset_id}' for utility '{utility}'")
    return preset


def build_total_structure(unit: str, variable_price: float, fixed_monthly_fee: float, source: str) -> dict[str, Any]:
    return {
        "charge_structure": "total",
        "unit": unit,
        "current_price": round(variable_price, 6),
        "fixed_monthly_fee_eur": round(fixed_monthly_fee, 6),
        "source": source,
        "components": {
            "variable": {
                "total_eur_per_kwh": round(variable_price, 6),
            },
            "fixed_monthly": {
                "total_eur": round(fixed_monthly_fee, 6),
            },
        },
    }


def build_split_structure(
    unit: str,
    commodity: float,
    distribution: float,
    taxes: float,
    other: float,
    supplier_fixed: float,
    distribution_fixed: float,
    tax_fixed: float,
    other_fixed: float,
    source: str,
) -> dict[str, Any]:
    variable_total = commodity + distribution + taxes + other
    fixed_total = supplier_fixed + distribution_fixed + tax_fixed + other_fixed
    return {
        "charge_structure": "split",
        "unit": unit,
        "current_price": round(variable_total, 6),
        "fixed_monthly_fee_eur": round(fixed_total, 6),
        "source": source,
        "components": {
            "variable": {
                "commodity_eur_per_kwh": round(commodity, 6),
                "distribution_eur_per_kwh": round(distribution, 6),
                "taxes_eur_per_kwh": round(taxes, 6),
                "other_eur_per_kwh": round(other, 6),
                "total_eur_per_kwh": round(variable_total, 6),
            },
            "fixed_monthly": {
                "supplier_eur": round(supplier_fixed, 6),
                "distribution_eur": round(distribution_fixed, 6),
                "tax_eur": round(tax_fixed, 6),
                "other_eur": round(other_fixed, 6),
                "total_eur": round(fixed_total, 6),
            },
        },
    }


def build_fixed_price_payload(
    utility: str,
    unit: str,
    charge_structure: str,
    source: str,
    metadata: dict[str, Any],
    total_variable_price: float | None = None,
    total_fixed_monthly_fee: float | None = None,
    commodity: float = 0.0,
    distribution: float = 0.0,
    taxes: float = 0.0,
    other: float = 0.0,
    supplier_fixed: float = 0.0,
    distribution_fixed: float = 0.0,
    tax_fixed: float = 0.0,
    other_fixed: float = 0.0,
) -> dict[str, Any]:
    payload = {
        "utility": utility,
        "pricing_mode": "household_fixed",
        "price_type": "fixed",
    }
    payload.update(metadata)
    if charge_structure == "split":
        payload.update(
            build_split_structure(
                unit,
                commodity,
                distribution,
                taxes,
                other,
                supplier_fixed,
                distribution_fixed,
                tax_fixed,
                other_fixed,
                source,
            )
        )
    else:
        payload.update(
            build_total_structure(
                unit,
                total_variable_price or 0.0,
                total_fixed_monthly_fee or 0.0,
                source,
            )
        )
    return payload


def normalize_okte_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = []
    prices = []

    for row in rows:
        price_eur_per_mwh = float(row["price"])
        price_eur_per_kwh = round(price_eur_per_mwh / 1000.0, 6)
        prices.append(price_eur_per_mwh)
        normalized.append(
            {
                "delivery_day": row["deliveryDay"],
                "period": row["period"],
                "delivery_start": row["deliveryStart"],
                "delivery_end": row["deliveryEnd"],
                "publication_status": row.get("publicationStatus"),
                "price_eur_per_mwh": price_eur_per_mwh,
                "price_eur_per_kwh": price_eur_per_kwh,
            }
        )

    if not normalized:
        raise DataSourceError("OKTE returned no DAM rows")

    return {
        "source": "okte",
        "market": "electricity",
        "unit": "EUR/MWh",
        "unit_cost": "EUR/kWh",
        "delivery_day_from": normalized[0]["delivery_day"],
        "delivery_day_to": normalized[-1]["delivery_day"],
        "evaluation_period_minutes": _guess_period_minutes(normalized),
        "min_price_eur_per_mwh": min(prices),
        "max_price_eur_per_mwh": max(prices),
        "avg_price_eur_per_mwh": round(sum(prices) / len(prices), 4),
        "rows": normalized,
    }


def _guess_period_minutes(rows: list[dict[str, Any]]) -> int:
    if len(rows) < 2:
        return 60
    start_a = datetime.fromisoformat(rows[0]["delivery_start"].replace("Z", "+00:00"))
    start_b = datetime.fromisoformat(rows[1]["delivery_start"].replace("Z", "+00:00"))
    return int((start_b - start_a).total_seconds() / 60)


def fetch_okte_day_ahead(day_from: str, day_to: str) -> dict[str, Any]:
    payload = fetch_json(
        OKTE_DAM_URL,
        {
            "deliveryDayFrom": day_from,
            "deliveryDayTo": day_to,
        },
    )
    if not isinstance(payload, list):
        raise DataSourceError("Unexpected OKTE response shape")
    return normalize_okte_rows(payload)


def load_custom_prices() -> dict[str, Any]:
    payload = load_json_file(CUSTOM_PRICES_PATH)
    if not payload:
        return {
            "source": "manual",
            "note": "No /data/custom_prices.json found",
            "gas": None,
            "water": None,
            "electricity": None,
        }
    return payload


def _require_manual_section(custom_prices: dict[str, Any], key: str) -> dict[str, Any]:
    section = custom_prices.get(key)
    if not isinstance(section, dict):
        raise DataSourceError(
            f"Manual pricing for {key} requires /data/custom_prices.json with a '{key}' object"
        )
    return section


def build_manual_price_payload(utility: str, section: dict[str, Any], default_unit: str) -> dict[str, Any]:
    charge_structure = str(section.get("charge_structure", "total"))
    if charge_structure not in VALID_CHARGE_STRUCTURES:
        raise DataSourceError(
            f"Manual pricing for {utility} must use charge_structure 'total' or 'split'"
        )

    metadata = {
        "supplier": section.get("supplier"),
        "contract_name": section.get("contract_name"),
    }

    return {
        **build_fixed_price_payload(
            utility=utility,
            unit=str(section.get("unit", default_unit)),
            charge_structure=charge_structure,
            source=section.get("source", "custom_prices"),
            metadata=metadata,
            total_variable_price=float(section.get("price", 0.0)),
            total_fixed_monthly_fee=float(section.get("fixed_monthly_fee_eur", 0.0)),
            commodity=float(section.get("commodity_price_eur_per_kwh", 0.0)),
            distribution=float(section.get("distribution_price_eur_per_kwh", 0.0)),
            taxes=float(section.get("taxes_price_eur_per_kwh", 0.0)),
            other=float(section.get("other_price_eur_per_kwh", 0.0)),
            supplier_fixed=float(section.get("supplier_fixed_monthly_fee_eur", 0.0)),
            distribution_fixed=float(section.get("distribution_fixed_monthly_fee_eur", 0.0)),
            tax_fixed=float(section.get("tax_fixed_monthly_fee_eur", 0.0)),
            other_fixed=float(section.get("other_fixed_monthly_fee_eur", 0.0)),
        ),
        "pricing_mode": "manual",
        "price_type": "manual",
        "details": section,
    }


def build_water_price_payload(
    pricing_mode: str,
    source: str,
    unit: str,
    vodne: float,
    stocne: float,
    vodne_fixed_monthly_fee: float,
    stocne_fixed_monthly_fee: float,
    operator_fixed_monthly_fee: float,
    metadata: dict[str, Any],
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fixed_total = vodne_fixed_monthly_fee + stocne_fixed_monthly_fee + operator_fixed_monthly_fee
    payload = {
        "utility": "water",
        "pricing_mode": pricing_mode,
        "price_type": "manual" if pricing_mode == "manual" else "fixed",
        "unit": unit,
        "fixed_monthly_fee_eur": round(fixed_total, 6),
        "source": source,
        "components": {
            "fixed_monthly": {
                "vodne_eur": round(vodne_fixed_monthly_fee, 6),
                "stocne_eur": round(stocne_fixed_monthly_fee, 6),
                "operator_eur": round(operator_fixed_monthly_fee, 6),
                "total_eur": round(fixed_total, 6),
            }
        },
        "vodne": {
            "name": "vodne",
            "unit": unit,
            "current_price": round(vodne, 6),
            "fixed_monthly_fee_eur": round(vodne_fixed_monthly_fee, 6),
        },
        "stocne": {
            "name": "stocne",
            "unit": unit,
            "current_price": round(stocne, 6),
            "fixed_monthly_fee_eur": round(stocne_fixed_monthly_fee, 6),
        },
        "combined": {
            "name": "water_total",
            "unit": unit,
            "current_price": round(vodne + stocne, 6),
            "fixed_monthly_fee_eur": round(fixed_total, 6),
        },
    }
    payload.update(metadata)
    if details is not None:
        payload["details"] = details
    return payload


def get_effective_electricity_price(config: AppConfig, custom_prices: dict[str, Any]) -> dict[str, Any]:
    presets = load_provider_presets()
    if config.electricity_pricing_mode == "household_fixed":
        preset = get_provider_preset(presets, "electricity", config.electricity_preset_id)
        if preset:
            return build_fixed_price_payload(
                utility="electricity",
                unit=preset["unit"],
                charge_structure=preset.get("charge_structure", "total"),
                source="provider_preset",
                metadata={
                    "preset_id": config.electricity_preset_id,
                    "provider": preset["provider"],
                    "tariff": preset["tariff"],
                    "band": preset.get("band"),
                    "effective_from": preset.get("effective_from"),
                    "source_url": preset.get("source_url"),
                },
                total_variable_price=preset.get("current_price"),
                total_fixed_monthly_fee=preset.get("fixed_monthly_fee_eur"),
                commodity=preset.get("commodity_price_eur_per_kwh", 0.0),
                distribution=preset.get("distribution_price_eur_per_kwh", 0.0),
                taxes=preset.get("taxes_price_eur_per_kwh", 0.0),
                other=preset.get("other_price_eur_per_kwh", 0.0),
                supplier_fixed=preset.get("supplier_fixed_monthly_fee_eur", 0.0),
                distribution_fixed=preset.get("distribution_fixed_monthly_fee_eur", 0.0),
                tax_fixed=preset.get("tax_fixed_monthly_fee_eur", 0.0),
                other_fixed=preset.get("other_fixed_monthly_fee_eur", 0.0),
            )
        return build_fixed_price_payload(
            utility="electricity",
            unit="EUR/kWh",
            charge_structure=config.electricity_charge_structure,
            source="addon_options",
            metadata={},
            total_variable_price=config.electricity_fixed_price_eur_per_kwh,
            total_fixed_monthly_fee=config.electricity_fixed_monthly_fee_eur,
            commodity=config.electricity_commodity_price_eur_per_kwh,
            distribution=config.electricity_distribution_price_eur_per_kwh,
            taxes=config.electricity_taxes_price_eur_per_kwh,
            other=config.electricity_other_price_eur_per_kwh,
            supplier_fixed=config.electricity_supplier_fixed_monthly_fee_eur,
            distribution_fixed=config.electricity_distribution_fixed_monthly_fee_eur,
            tax_fixed=config.electricity_tax_fixed_monthly_fee_eur,
            other_fixed=config.electricity_other_fixed_monthly_fee_eur,
        )

    if config.electricity_pricing_mode == "manual":
        section = _require_manual_section(custom_prices, "electricity")
        return build_manual_price_payload("electricity", section, "EUR/kWh")

    if not config.okte_enabled:
        raise DataSourceError("OKTE provider is disabled in add-on options")

    today = date.today().isoformat()
    payload = fetch_okte_day_ahead(today, today)
    now_utc = datetime.now(UTC)
    current_row = next(
        (
            row
            for row in payload["rows"]
            if datetime.fromisoformat(row["delivery_start"].replace("Z", "+00:00"))
            <= now_utc
            < datetime.fromisoformat(row["delivery_end"].replace("Z", "+00:00"))
        ),
        payload["rows"][0],
    )
    return {
        "utility": "electricity",
        "pricing_mode": "spot_okte",
        "price_type": "spot",
        "charge_structure": "spot",
        "unit": "EUR/kWh",
        "current_price": current_row["price_eur_per_kwh"],
        "fixed_monthly_fee_eur": config.electricity_fixed_monthly_fee_eur,
        "source": "okte",
        "evaluation_period_minutes": payload["evaluation_period_minutes"],
        "current_period": current_row,
        "avg_price_today_eur_per_kwh": round(payload["avg_price_eur_per_mwh"] / 1000.0, 6),
    }


def get_effective_gas_price(config: AppConfig, custom_prices: dict[str, Any]) -> dict[str, Any]:
    presets = load_provider_presets()
    if config.gas_pricing_mode == "household_fixed":
        preset = get_provider_preset(presets, "gas", config.gas_preset_id)
        if preset:
            return build_fixed_price_payload(
                utility="gas",
                unit=preset["unit"],
                charge_structure=preset.get("charge_structure", "total"),
                source="provider_preset",
                metadata={
                    "preset_id": config.gas_preset_id,
                    "provider": preset["provider"],
                    "tariff": preset["tariff"],
                    "effective_from": preset.get("effective_from"),
                    "source_url": preset.get("source_url"),
                },
                total_variable_price=preset.get("current_price"),
                total_fixed_monthly_fee=preset.get("fixed_monthly_fee_eur"),
                commodity=preset.get("commodity_price_eur_per_kwh", 0.0),
                distribution=preset.get("distribution_price_eur_per_kwh", 0.0),
                taxes=preset.get("taxes_price_eur_per_kwh", 0.0),
                other=preset.get("other_price_eur_per_kwh", 0.0),
                supplier_fixed=preset.get("supplier_fixed_monthly_fee_eur", 0.0),
                distribution_fixed=preset.get("distribution_fixed_monthly_fee_eur", 0.0),
                tax_fixed=preset.get("tax_fixed_monthly_fee_eur", 0.0),
                other_fixed=preset.get("other_fixed_monthly_fee_eur", 0.0),
            )
        return build_fixed_price_payload(
            utility="gas",
            unit="EUR/kWh",
            charge_structure=config.gas_charge_structure,
            source="addon_options",
            metadata={},
            total_variable_price=config.gas_fixed_price_eur_per_kwh,
            total_fixed_monthly_fee=config.gas_fixed_monthly_fee_eur,
            commodity=config.gas_commodity_price_eur_per_kwh,
            distribution=config.gas_distribution_price_eur_per_kwh,
            taxes=config.gas_taxes_price_eur_per_kwh,
            other=config.gas_other_price_eur_per_kwh,
            supplier_fixed=config.gas_supplier_fixed_monthly_fee_eur,
            distribution_fixed=config.gas_distribution_fixed_monthly_fee_eur,
            tax_fixed=config.gas_tax_fixed_monthly_fee_eur,
            other_fixed=config.gas_other_fixed_monthly_fee_eur,
        )

    section = _require_manual_section(custom_prices, "gas")
    return build_manual_price_payload("gas", section, "EUR/kWh")


def get_effective_water_price(config: AppConfig, custom_prices: dict[str, Any]) -> dict[str, Any]:
    if config.water_pricing_mode == "household_fixed":
        return build_water_price_payload(
            pricing_mode="household_fixed",
            source="addon_options",
            unit="EUR/m3",
            vodne=config.water_supply_price_eur_per_m3,
            stocne=config.water_wastewater_price_eur_per_m3,
            vodne_fixed_monthly_fee=0.0,
            stocne_fixed_monthly_fee=0.0,
            operator_fixed_monthly_fee=config.water_fixed_monthly_fee_eur,
            metadata={"preset_id": config.water_preset_id or None},
        )

    section = _require_manual_section(custom_prices, "water")
    return build_water_price_payload(
        pricing_mode="manual",
        source=section.get("source", "custom_prices"),
        unit=str(section.get("unit", "EUR/m3")),
        vodne=float(section.get("water_supply_price", 0.0)),
        stocne=float(section.get("wastewater_price", 0.0)),
        vodne_fixed_monthly_fee=float(section.get("water_supply_fixed_monthly_fee_eur", 0.0)),
        stocne_fixed_monthly_fee=float(section.get("wastewater_fixed_monthly_fee_eur", 0.0)),
        operator_fixed_monthly_fee=float(
            section.get("operator_fixed_monthly_fee_eur", section.get("fixed_monthly_fee_eur", 0.0))
        ),
        metadata={"operator": section.get("operator")},
        details=section,
    )


def get_effective_prices(config: AppConfig) -> dict[str, Any]:
    custom_prices = load_custom_prices()
    return {
        "electricity": get_effective_electricity_price(config, custom_prices),
        "gas": get_effective_gas_price(config, custom_prices),
        "water": get_effective_water_price(config, custom_prices),
    }


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "SlovakEnergyPrices/0.1.0"

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=True, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        logging.info("%s - %s", self.address_string(), fmt % args)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        try:
            if parsed.path == "/health":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "status": "ok",
                        "service": "slovak_energy_prices",
                        "config": asdict(self.server.app_config),
                    },
                )
                return

            if parsed.path == "/api/v1/prices/electricity/day-ahead":
                if not self.server.app_config.okte_enabled:
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {"error": "OKTE provider is disabled in add-on options"},
                    )
                    return

                today = date.today().isoformat()
                day_from = query.get("date_from", [today])[0]
                day_to = query.get("date_to", [day_from])[0]
                payload = fetch_okte_day_ahead(day_from, day_to)
                self._send_json(HTTPStatus.OK, payload)
                return

            if parsed.path == "/api/v1/prices/custom":
                self._send_json(HTTPStatus.OK, load_custom_prices())
                return

            if parsed.path == "/api/v1/presets":
                self._send_json(HTTPStatus.OK, load_provider_presets())
                return

            if parsed.path == "/api/v1/prices/effective":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "pricing_modes": {
                            "electricity": self.server.app_config.electricity_pricing_mode,
                            "gas": self.server.app_config.gas_pricing_mode,
                            "water": self.server.app_config.water_pricing_mode,
                        },
                        "prices": get_effective_prices(self.server.app_config),
                    },
                )
                return

            if parsed.path == "/api/v1/prices/snapshot":
                today = date.today()
                tomorrow = today + timedelta(days=1)
                snapshot: dict[str, Any] = {
                    "electricity_day_ahead": None,
                    "custom_prices": load_custom_prices(),
                    "effective_prices": get_effective_prices(self.server.app_config),
                }
                if self.server.app_config.okte_enabled:
                    snapshot["electricity_day_ahead"] = fetch_okte_day_ahead(
                        today.isoformat(),
                        tomorrow.isoformat(),
                    )
                self._send_json(HTTPStatus.OK, snapshot)
                return

            self._send_json(
                HTTPStatus.NOT_FOUND,
                {
                    "error": "Unknown endpoint",
                    "paths": [
                        "/health",
                        "/api/v1/prices/electricity/day-ahead",
                        "/api/v1/prices/custom",
                        "/api/v1/presets",
                        "/api/v1/prices/effective",
                        "/api/v1/prices/snapshot",
                    ],
                },
            )
        except DataSourceError as exc:
            logging.exception("Data source error")
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
        except Exception as exc:  # pragma: no cover
            logging.exception("Unhandled server error")
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})


class AppServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_cls: type[BaseHTTPRequestHandler], app_config: AppConfig):
        super().__init__(server_address, handler_cls)
        self.app_config = app_config


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    config = load_config()
    server = AppServer(("0.0.0.0", config.port), RequestHandler, config)
    logging.info("Starting server on port %s", config.port)
    server.serve_forever()


if __name__ == "__main__":
    main()
