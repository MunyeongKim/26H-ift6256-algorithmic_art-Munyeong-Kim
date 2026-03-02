#!/usr/bin/env python
"""Reverse geocode latitude/longitude into a district-level location label."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

DISTRICT_TYPES = [
    "sublocality_level_5",
    "sublocality_level_4",
    "sublocality_level_3",
    "sublocality_level_2",
    "sublocality_level_1",
    "sublocality",
    "neighborhood",
    "administrative_area_level_4",
    "administrative_area_level_3",
    "administrative_area_level_2",
]

CITY_TYPES = [
    "locality",
    "postal_town",
    "administrative_area_level_3",
    "administrative_area_level_2",
]

ADMIN1_TYPES = ["administrative_area_level_1"]
COUNTRY_TYPES = ["country"]


def _get_json(url: str, params: dict[str, Any], timeout: float = 20.0) -> dict[str, Any]:
    full_url = f"{url}?{urlencode(params)}"
    req = Request(full_url, headers={"User-Agent": "HW3-reverse-geocode/1.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Failed to connect to Geocoding API: {exc}") from exc


def resolve_language_choice(choice: str, other_code: str | None = None) -> str | None:
    normalized = (choice or "none").strip().lower()
    if normalized == "none":
        return None
    if normalized in {"en", "fr"}:
        return normalized
    if normalized != "other":
        raise ValueError(f"Unsupported address language option: {choice}")
    code = (other_code or "").strip()
    if not code:
        raise ValueError("address language 'other' requires a language code.")
    return code


def _collect_component_index(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for result in results:
        components = result.get("address_components")
        if not isinstance(components, list):
            continue
        for component in components:
            if not isinstance(component, dict):
                continue
            types = component.get("types")
            if not isinstance(types, list):
                continue
            for component_type in types:
                if isinstance(component_type, str) and component_type not in indexed:
                    indexed[component_type] = component
    return indexed


def _pick_component(indexed: dict[str, dict[str, Any]], type_order: list[str]) -> dict[str, Any] | None:
    for component_type in type_order:
        component = indexed.get(component_type)
        if component:
            return component
    return None


def _normalize_component(component: dict[str, Any] | None) -> dict[str, Any] | None:
    if not component:
        return None
    types = component.get("types")
    return {
        "long_name": component.get("long_name"),
        "short_name": component.get("short_name"),
        "types": types if isinstance(types, list) else [],
    }


def _component_name(component: dict[str, Any] | None, *, allow_short: bool = False) -> str | None:
    if not component:
        return None
    long_name = component.get("long_name")
    short_name = component.get("short_name")
    if allow_short and isinstance(short_name, str) and short_name.strip():
        return short_name.strip()
    if isinstance(long_name, str) and long_name.strip():
        return long_name.strip()
    if isinstance(short_name, str) and short_name.strip():
        return short_name.strip()
    return None


def _build_district_label(
    *,
    district: dict[str, Any] | None,
    city: dict[str, Any] | None,
    admin1: dict[str, Any] | None,
    country: dict[str, Any] | None,
) -> str:
    parts = [
        _component_name(district),
        _component_name(city),
        _component_name(admin1, allow_short=True),
        _component_name(country),
    ]
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        if not part:
            continue
        key = part.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(part)
    return ", ".join(ordered)


def reverse_geocode(
    *,
    lat: float,
    lon: float,
    api_key: str,
    language: str | None = None,
    result_type: str | None = "political",
    timeout: float = 20.0,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "latlng": f"{lat},{lon}",
        "key": api_key,
    }
    if language:
        params["language"] = language
    if result_type:
        params["result_type"] = result_type

    payload = _get_json(GEOCODE_URL, params, timeout=timeout)
    status = payload.get("status", "")
    if status != "OK":
        raise RuntimeError(
            f"Reverse geocoding failed for ({lat}, {lon}): status={status}, "
            f"message={payload.get('error_message', '')}"
        )

    results = payload.get("results")
    if not isinstance(results, list) or not results:
        raise RuntimeError(f"Reverse geocoding returned no results for ({lat}, {lon}).")

    indexed = _collect_component_index(results)
    district = _pick_component(indexed, DISTRICT_TYPES)
    city = _pick_component(indexed, CITY_TYPES)
    admin1 = _pick_component(indexed, ADMIN1_TYPES)
    country = _pick_component(indexed, COUNTRY_TYPES)
    primary = results[0] if isinstance(results[0], dict) else {}

    return {
        "query": {
            "lat": lat,
            "lon": lon,
            "language": language,
            "result_type": result_type,
        },
        "formatted_address": primary.get("formatted_address"),
        "district_label": _build_district_label(
            district=district,
            city=city,
            admin1=admin1,
            country=country,
        ),
        "components": {
            "district": _normalize_component(district),
            "city": _normalize_component(city),
            "admin1": _normalize_component(admin1),
            "country": _normalize_component(country),
        },
        "place_id": primary.get("place_id"),
        "result_types": primary.get("types", []),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reverse geocode a coordinate into a district-level address label."
    )
    parser.add_argument("--lat", required=True, type=float, help="Latitude")
    parser.add_argument("--lon", required=True, type=float, help="Longitude")
    parser.add_argument("--api-key", required=True, help="Google Maps API key")
    parser.add_argument(
        "--language-choice",
        choices=["none", "en", "fr", "other"],
        default="none",
        help="Preset address language option",
    )
    parser.add_argument("--language-code", default=None, help="Used when --language-choice=other")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout seconds")
    parser.add_argument("--output", default=None, help="Optional JSON output path")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    language = resolve_language_choice(args.language_choice, args.language_code)
    payload = reverse_geocode(
        lat=args.lat,
        lon=args.lon,
        api_key=args.api_key,
        language=language,
        timeout=args.timeout,
    )
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"[OK] saved: {args.output}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
