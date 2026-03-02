#!/usr/bin/env python
"""Find shared sunrise/sunset instants and fetch aligned Street View images."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from fetch_streetview_pair import save_pair
from find_shared_sun_instants import find_shared_sun_instants, save_matches_csv

sys.path.append(str(Path(__file__).resolve().parent / "utils"))
from reverse_geocode import reverse_geocode, resolve_language_choice

_AT_COORD_RE = re.compile(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")
_PLACE_COORD_RE = re.compile(r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)")
UTC = timezone.utc


def _load_env_file(paths: list[Path]) -> None:
    for path in paths:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        return


def _extract_lat_lon_from_google_maps_url(url: str) -> tuple[float, float]:
    for pattern in (_AT_COORD_RE, _PLACE_COORD_RE):
        match = pattern.search(url)
        if match:
            return float(match.group(1)), float(match.group(2))
    raise ValueError("Could not parse latitude/longitude from the Google Maps URL.")


def _resolve_coords(
    *,
    lat: float | None,
    lon: float | None,
    maps_url: str | None,
) -> tuple[float, float]:
    if lat is not None and lon is not None:
        return lat, lon
    if maps_url:
        return _extract_lat_lon_from_google_maps_url(maps_url)
    raise ValueError("Provide either (--lat, --lon) pair or --maps-url.")


def _parse_utc_iso_minute(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _build_parser() -> argparse.ArgumentParser:
    current_year = date.today().year
    parser = argparse.ArgumentParser(
        description=(
            "Find near-simultaneous sun events and fetch Street View images pointed "
            "to that date's sunrise/sunset azimuth."
        )
    )
    parser.add_argument("--name-a", required=True, help="Label for location A")
    parser.add_argument("--name-b", required=True, help="Label for location B")

    parser.add_argument("--lat-a", type=float, default=None, help="Latitude for location A")
    parser.add_argument("--lon-a", type=float, default=None, help="Longitude for location A")
    parser.add_argument("--maps-url-a", default=None, help="Google Maps URL for location A")

    parser.add_argument("--lat-b", type=float, default=None, help="Latitude for location B")
    parser.add_argument("--lon-b", type=float, default=None, help="Longitude for location B")
    parser.add_argument("--maps-url-b", default=None, help="Google Maps URL for location B")

    parser.add_argument("--event-a", choices=["sunrise", "sunset"], default="sunrise")
    parser.add_argument("--event-b", choices=["sunrise", "sunset"], default="sunset")
    parser.add_argument("--tz-a", default="UTC", help="IANA timezone for location A local display")
    parser.add_argument("--tz-b", default="UTC", help="IANA timezone for location B local display")
    parser.add_argument(
        "--address-lang-a",
        choices=["none", "en", "fr", "other"],
        default="none",
        help="Reverse-geocoded address language option for location A",
    )
    parser.add_argument(
        "--address-lang-code-a",
        default=None,
        help="Custom language code when --address-lang-a=other",
    )
    parser.add_argument(
        "--address-lang-b",
        choices=["none", "en", "fr", "other"],
        default="none",
        help="Reverse-geocoded address language option for location B",
    )
    parser.add_argument(
        "--address-lang-code-b",
        default=None,
        help="Custom language code when --address-lang-b=other",
    )

    parser.add_argument("--start", default=f"{current_year}-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=f"{current_year}-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument("--tol-min", type=int, default=10, help="Match tolerance in minutes")
    parser.add_argument("--match-index", type=int, default=1, help="1-based index in sorted matches")
    parser.add_argument(
        "--reference-utc",
        default=None,
        help="Reference UTC cutoff for past-only filtering (ISO 8601, default: current UTC minute)",
    )
    parser.add_argument(
        "--allow-future-matches",
        action="store_true",
        help="Allow future shared instants instead of filtering them out.",
    )
    parser.add_argument(
        "--matches-csv",
        default=None,
        help="Optional path to save all matched instants as CSV",
    )

    parser.add_argument(
        "--api-key",
        default=None,
        help="Google Maps API key. If omitted, read GOOGLE_MAPS_API_KEY (.env supported).",
    )
    parser.add_argument("--pitch-a", type=float, default=0.0, help="Camera pitch for location A")
    parser.add_argument("--pitch-b", type=float, default=0.0, help="Camera pitch for location B")
    parser.add_argument("--size", default="640x640", help="Image size (default: 640x640)")
    parser.add_argument("--fov", type=int, default=90, help="Field of view (10~120)")
    parser.add_argument("--radius", type=int, default=50, help="Search radius in meters")
    parser.add_argument(
        "--source",
        choices=["default", "outdoor"],
        default="default",
        help="Street View source filter",
    )
    parser.add_argument("--outdir", default="HW3/streetview_outputs", help="Output directory")
    parser.add_argument(
        "--summary-json",
        default=None,
        help="Optional summary json path (default: <outdir>/sun_aligned_summary.json)",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    lat_a, lon_a = _resolve_coords(lat=args.lat_a, lon=args.lon_a, maps_url=args.maps_url_a)
    lat_b, lon_b = _resolve_coords(lat=args.lat_b, lon=args.lon_b, maps_url=args.maps_url_b)

    matches = find_shared_sun_instants(
        name_a=args.name_a,
        lat_a=lat_a,
        lon_a=lon_a,
        event_a=args.event_a,
        tz_a=args.tz_a,
        name_b=args.name_b,
        lat_b=lat_b,
        lon_b=lon_b,
        event_b=args.event_b,
        tz_b=args.tz_b,
        start_date=args.start,
        end_date=args.end,
        tolerance_minutes=args.tol_min,
        reference_utc=_parse_utc_iso_minute(args.reference_utc) if args.reference_utc else None,
        allow_future_matches=args.allow_future_matches,
    )
    if args.matches_csv:
        save_matches_csv(matches, args.matches_csv)
        print(f"[OK] saved matches csv: {args.matches_csv}")

    matches_with_az = [
        m
        for m in matches
        if m.get("a_azimuth_deg") is not None and m.get("b_azimuth_deg") is not None
    ]
    if not matches_with_az:
        raise RuntimeError("No matches with azimuth data found in the requested date range.")

    if args.match_index < 1 or args.match_index > len(matches_with_az):
        raise ValueError(
            f"--match-index must be between 1 and {len(matches_with_az)} (got {args.match_index})"
        )

    selected = matches_with_az[args.match_index - 1]
    heading_a = float(selected["a_azimuth_deg"]) % 360.0
    heading_b = float(selected["b_azimuth_deg"]) % 360.0

    _load_env_file([Path("HW3/.env"), Path(".env")])
    api_key = args.api_key or os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("Missing API key. Set GOOGLE_MAPS_API_KEY or pass --api-key.")

    outdir = Path(args.outdir)
    source = None if args.source == "default" else args.source
    img_a, img_b = save_pair(
        name_a=args.name_a,
        lat_a=lat_a,
        lon_a=lon_a,
        heading_a=heading_a,
        pitch_a=args.pitch_a,
        name_b=args.name_b,
        lat_b=lat_b,
        lon_b=lon_b,
        heading_b=heading_b,
        pitch_b=args.pitch_b,
        fov=args.fov,
        size=args.size,
        radius=args.radius,
        source=source,
        api_key=api_key,
        outdir=outdir,
    )

    address_language_a = resolve_language_choice(args.address_lang_a, args.address_lang_code_a)
    address_language_b = resolve_language_choice(args.address_lang_b, args.address_lang_code_b)
    reverse_geocode_a = None
    reverse_geocode_b = None
    if address_language_a:
        reverse_geocode_a = reverse_geocode(
            lat=lat_a,
            lon=lon_a,
            api_key=api_key,
            language=address_language_a,
        )
    if address_language_b:
        reverse_geocode_b = reverse_geocode(
            lat=lat_b,
            lon=lon_b,
            api_key=api_key,
            language=address_language_b,
        )

    summary_path = Path(args.summary_json) if args.summary_json else outdir / "sun_aligned_summary.json"
    summary_payload = {
        "selection": {
            "match_index": args.match_index,
            "total_matches": len(matches),
            "total_matches_with_azimuth": len(matches_with_az),
            "start": args.start,
            "end": args.end,
            "tolerance_minutes": args.tol_min,
            "reference_utc": (
                _parse_utc_iso_minute(args.reference_utc).isoformat(timespec="minutes").replace("+00:00", "Z")
                if args.reference_utc
                else datetime.now(UTC).replace(second=0, microsecond=0).isoformat(timespec="minutes").replace("+00:00", "Z")
            ),
            "allow_future_matches": args.allow_future_matches,
        },
        "location_a": {
            "name": args.name_a,
            "lat": lat_a,
            "lon": lon_a,
            "event": args.event_a,
            "timezone": args.tz_a,
            "heading_deg": heading_a,
            "pitch_deg": args.pitch_a,
            "image_path": str(img_a),
            "address_language": address_language_a,
            "reverse_geocode": reverse_geocode_a,
        },
        "location_b": {
            "name": args.name_b,
            "lat": lat_b,
            "lon": lon_b,
            "event": args.event_b,
            "timezone": args.tz_b,
            "heading_deg": heading_b,
            "pitch_deg": args.pitch_b,
            "image_path": str(img_b),
            "address_language": address_language_b,
            "reverse_geocode": reverse_geocode_b,
        },
        "selected_match": selected,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[DONE] selected match: {selected['shared_midpoint_utc']} (diff={selected['diff_min']} min)")
    print(f"[DONE] heading A ({args.name_a}): {heading_a:.2f} deg")
    print(f"[DONE] heading B ({args.name_b}): {heading_b:.2f} deg")
    if reverse_geocode_a:
        print(f"[DONE] address A ({args.name_a}): {reverse_geocode_a['district_label']}")
    if reverse_geocode_b:
        print(f"[DONE] address B ({args.name_b}): {reverse_geocode_b['district_label']}")
    print(f"[DONE] summary json: {summary_path}")


if __name__ == "__main__":
    main()
