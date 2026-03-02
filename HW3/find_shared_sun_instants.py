#!/usr/bin/env python
"""Find near-simultaneous sunrise/sunset instants between two locations."""

from __future__ import annotations

import argparse
import csv
from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from utils.met_sun import fetch_met_sun_times

UTC = timezone.utc


def _parse_utc_iso_minute(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _utc_now_minute() -> datetime:
    return datetime.now(UTC).replace(second=0, microsecond=0)


def _parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _to_local_iso(value_utc: datetime, tz_name: str) -> str:
    return value_utc.astimezone(ZoneInfo(tz_name)).isoformat(timespec="minutes")


def _event_points(
    rows: list[dict[str, str]],
    event_key: str,
    name: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        ts = _parse_utc_iso_minute(row.get(event_key))
        if ts is None:
            continue
        out.append(
            {
                "name": name,
                "event": event_key,
                "source_date": row.get("date", ""),
                "ts_utc": ts,
                "azimuth_deg": _parse_float(row.get(f"{event_key}_azimuth")),
            }
        )
    out.sort(key=lambda x: x["ts_utc"])
    return out


def find_shared_sun_instants(
    *,
    name_a: str,
    lat_a: float,
    lon_a: float,
    event_a: str,
    tz_a: str,
    name_b: str,
    lat_b: float,
    lon_b: float,
    event_b: str,
    tz_b: str,
    start_date: str,
    end_date: str,
    tolerance_minutes: int = 10,
    reference_utc: datetime | None = None,
    allow_future_matches: bool = False,
) -> list[dict[str, Any]]:
    rows_a = fetch_met_sun_times(
        latitude=lat_a,
        longitude=lon_a,
        start_date=start_date,
        end_date=end_date,
        offset="+00:00",
    )
    rows_b = fetch_met_sun_times(
        latitude=lat_b,
        longitude=lon_b,
        start_date=start_date,
        end_date=end_date,
        offset="+00:00",
    )

    points_a = _event_points(rows_a, event_a, name_a)
    points_b = _event_points(rows_b, event_b, name_b)

    b_ts = [p["ts_utc"] for p in points_b]
    tol = timedelta(minutes=tolerance_minutes)
    matches: list[dict[str, Any]] = []

    cutoff_utc = reference_utc or _utc_now_minute()

    for a in points_a:
        left = bisect_left(b_ts, a["ts_utc"] - tol)
        right = bisect_right(b_ts, a["ts_utc"] + tol)
        for b in points_b[left:right]:
            diff_seconds = abs((a["ts_utc"] - b["ts_utc"]).total_seconds())
            diff_min = diff_seconds / 60.0
            diff_min_rounded = int(round(diff_min))
            recent_ts = a["ts_utc"] if a["ts_utc"] >= b["ts_utc"] else b["ts_utc"]
            midpoint_ts = a["ts_utc"] + (b["ts_utc"] - a["ts_utc"]) / 2
            is_future = midpoint_ts > cutoff_utc

            if is_future and not allow_future_matches:
                continue

            matches.append(
                {
                    "sort_is_future": 1 if is_future else 0,
                    "sort_year": recent_ts.year,
                    "sort_recent_epoch": recent_ts.timestamp(),
                    "sort_diff_min": diff_min_rounded,
                    "sort_midpoint_epoch": midpoint_ts.timestamp(),
                    "shared_midpoint_utc": midpoint_ts.isoformat(timespec="minutes").replace("+00:00", "Z"),
                    "recent_utc": recent_ts.isoformat(timespec="minutes").replace("+00:00", "Z"),
                    "diff_min": diff_min_rounded,
                    "a_name": a["name"],
                    "a_event": a["event"],
                    "a_source_date": a["source_date"],
                    "a_utc": a["ts_utc"].isoformat(timespec="minutes").replace("+00:00", "Z"),
                    "a_local": _to_local_iso(a["ts_utc"], tz_a),
                    "a_azimuth_deg": a["azimuth_deg"],
                    "b_name": b["name"],
                    "b_event": b["event"],
                    "b_source_date": b["source_date"],
                    "b_utc": b["ts_utc"].isoformat(timespec="minutes").replace("+00:00", "Z"),
                    "b_local": _to_local_iso(b["ts_utc"], tz_b),
                    "b_azimuth_deg": b["azimuth_deg"],
                }
            )

    # Sort rule:
    # 1) past matches before future matches (future usually filtered out),
    # 2) latest year first,
    # 3) smaller diff first,
    # 4) if diff ties, more recent instant first.
    matches.sort(
        key=lambda x: (
            x["sort_is_future"],
            -x["sort_year"],
            x["sort_diff_min"],
            -x["sort_recent_epoch"],
        )
    )
    return matches


def save_matches_csv(matches: list[dict[str, Any]], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "shared_midpoint_utc",
        "recent_utc",
        "diff_min",
        "a_name",
        "a_event",
        "a_source_date",
        "a_utc",
        "a_local",
        "a_azimuth_deg",
        "b_name",
        "b_event",
        "b_source_date",
        "b_utc",
        "b_local",
        "b_azimuth_deg",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for m in matches:
            writer.writerow({k: m[k] for k in fields})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Find near-simultaneous sunrise/sunset instants between two locations "
            "using MET Norway Sunrise API data."
        )
    )
    parser.add_argument("--name-a", required=True, help="Label for location A")
    parser.add_argument("--lat-a", required=True, type=float, help="Latitude for location A")
    parser.add_argument("--lon-a", required=True, type=float, help="Longitude for location A")
    parser.add_argument(
        "--event-a",
        required=True,
        choices=["sunrise", "sunset"],
        help="Event for location A",
    )
    parser.add_argument("--tz-a", default="UTC", help="IANA timezone for location A local display")

    parser.add_argument("--name-b", required=True, help="Label for location B")
    parser.add_argument("--lat-b", required=True, type=float, help="Latitude for location B")
    parser.add_argument("--lon-b", required=True, type=float, help="Longitude for location B")
    parser.add_argument(
        "--event-b",
        required=True,
        choices=["sunrise", "sunset"],
        help="Event for location B",
    )
    parser.add_argument("--tz-b", default="UTC", help="IANA timezone for location B local display")

    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--tol-min",
        type=int,
        default=10,
        help="Match tolerance in minutes (default: 10)",
    )
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
        "--limit",
        type=int,
        default=20,
        help="How many sorted matches to print (default: 20)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional CSV output path for all matches",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    matches = find_shared_sun_instants(
        name_a=args.name_a,
        lat_a=args.lat_a,
        lon_a=args.lon_a,
        event_a=args.event_a,
        tz_a=args.tz_a,
        name_b=args.name_b,
        lat_b=args.lat_b,
        lon_b=args.lon_b,
        event_b=args.event_b,
        tz_b=args.tz_b,
        start_date=args.start,
        end_date=args.end,
        tolerance_minutes=args.tol_min,
        reference_utc=_parse_utc_iso_minute(args.reference_utc) if args.reference_utc else None,
        allow_future_matches=args.allow_future_matches,
    )

    if args.output:
        save_matches_csv(matches, args.output)
        print(f"Saved {len(matches)} matches to {args.output}")
    else:
        print(f"Total matches: {len(matches)}")

    print_count = min(args.limit, len(matches))
    for i in range(print_count):
        m = matches[i]
        print(
            f"{i+1:02d}. year={m['sort_year']}, diff={m['diff_min']} min, "
            f"mid={m['shared_midpoint_utc']}, "
            f"{m['a_name']}({m['a_event']})={m['a_utc']} az={m['a_azimuth_deg']}, "
            f"{m['b_name']}({m['b_event']})={m['b_utc']} az={m['b_azimuth_deg']}"
        )


if __name__ == "__main__":
    main()
