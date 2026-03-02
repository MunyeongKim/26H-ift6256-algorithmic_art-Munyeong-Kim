#!/usr/bin/env python
"""Utilities for sunrise/sunset retrieval using Open-Meteo free APIs."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"


def _to_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _request_json(url: str, params: dict[str, Any], timeout: float = 20.0) -> dict[str, Any]:
    query = urlencode(params)
    full_url = f"{url}?{query}"
    request = Request(full_url, headers={"User-Agent": "HW3-open-meteo-sun/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from Open-Meteo: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Failed to reach Open-Meteo: {exc}") from exc

    if payload.get("error"):
        raise RuntimeError(f"Open-Meteo API error: {payload.get('reason', 'unknown error')}")
    return payload


def _fetch_segment(
    endpoint: str,
    latitude: float,
    longitude: float,
    start: date,
    end: date,
    timezone: str,
    timeout: float,
) -> list[dict[str, str]]:
    payload = _request_json(
        endpoint,
        {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": "sunrise,sunset",
            "timezone": timezone,
        },
        timeout=timeout,
    )
    daily = payload.get("daily", {})
    times = daily.get("time", [])
    sunrises = daily.get("sunrise", [])
    sunsets = daily.get("sunset", [])

    if not (len(times) == len(sunrises) == len(sunsets)):
        raise RuntimeError("Unexpected Open-Meteo response shape: daily arrays have different lengths.")

    rows: list[dict[str, str]] = []
    for d, sr, ss in zip(times, sunrises, sunsets):
        rows.append({"date": d, "sunrise": sr, "sunset": ss})
    return rows


def fetch_open_meteo_sun_times(
    latitude: float,
    longitude: float,
    start_date: str | date,
    end_date: str | date | None = None,
    timezone: str = "GMT",
    timeout: float = 20.0,
) -> list[dict[str, str]]:
    """
    Return sunrise/sunset rows from Open-Meteo free APIs.

    Each row has:
      - date: YYYY-MM-DD
      - sunrise: YYYY-MM-DDTHH:MM (in requested timezone)
      - sunset: YYYY-MM-DDTHH:MM (in requested timezone)
    """
    start = _to_date(start_date)
    end = _to_date(end_date) if end_date is not None else start
    if end < start:
        raise ValueError("end_date must be >= start_date")

    today = date.today()
    rows_by_date: dict[str, dict[str, str]] = {}

    if start <= today:
        past_end = min(end, today)
        for row in _fetch_segment(
            ARCHIVE_API_URL,
            latitude=latitude,
            longitude=longitude,
            start=start,
            end=past_end,
            timezone=timezone,
            timeout=timeout,
        ):
            rows_by_date[row["date"]] = row

    if end > today:
        future_start = max(start, today + timedelta(days=1))
        for row in _fetch_segment(
            FORECAST_API_URL,
            latitude=latitude,
            longitude=longitude,
            start=future_start,
            end=end,
            timezone=timezone,
            timeout=timeout,
        ):
            rows_by_date[row["date"]] = row

    return [rows_by_date[d] for d in sorted(rows_by_date)]


def fetch_open_meteo_sun_time_for_day(
    latitude: float,
    longitude: float,
    day: str | date,
    timezone: str = "GMT",
    timeout: float = 20.0,
) -> dict[str, str]:
    rows = fetch_open_meteo_sun_times(
        latitude=latitude,
        longitude=longitude,
        start_date=day,
        end_date=day,
        timezone=timezone,
        timeout=timeout,
    )
    if not rows:
        raise RuntimeError("No data returned for the requested day.")
    return rows[0]


def save_sun_times_csv(rows: list[dict[str, str]], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "sunrise", "sunset"])
        writer.writeheader()
        writer.writerows(rows)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch sunrise/sunset from Open-Meteo free API and optionally save CSV."
    )
    parser.add_argument("--lat", type=float, required=True, help="Latitude")
    parser.add_argument("--lon", type=float, required=True, help="Longitude")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="End date (YYYY-MM-DD), default=start")
    parser.add_argument("--timezone", default="GMT", help="Open-Meteo timezone parameter")
    parser.add_argument("--output", default=None, help="CSV output path")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    rows = fetch_open_meteo_sun_times(
        latitude=args.lat,
        longitude=args.lon,
        start_date=args.start,
        end_date=args.end,
        timezone=args.timezone,
    )
    if args.output:
        save_sun_times_csv(rows, args.output)
        print(f"Saved {len(rows)} rows to {args.output}")
    else:
        for row in rows:
            print(f"{row['date']}, sunrise={row['sunrise']}, sunset={row['sunset']}")


if __name__ == "__main__":
    main()
