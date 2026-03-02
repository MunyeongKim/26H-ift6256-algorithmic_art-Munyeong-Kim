#!/usr/bin/env python
"""Utilities for sunrise/sunset retrieval using MET Norway Sunrise API."""

from __future__ import annotations

import argparse
import csv
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://api.met.no/weatherapi/sunrise/3.0/sun"
DEFAULT_USER_AGENT = "HW3-met-sun/1.0 (+https://github.com/KimMunyeong/algorithmic-art)"


def _to_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _date_range(start: date, end: date) -> list[date]:
    out: list[date] = []
    current = start
    while current <= end:
        out.append(current)
        current += timedelta(days=1)
    return out


def _request_json(
    *,
    latitude: float,
    longitude: float,
    day: date,
    offset: str,
    timeout: float,
    user_agent: str,
) -> dict[str, Any]:
    params = {
        "lat": latitude,
        "lon": longitude,
        "date": day.isoformat(),
        "offset": offset,
    }
    full_url = f"{API_URL}?{urlencode(params)}"
    request = Request(full_url, headers={"User-Agent": user_agent})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from MET Sunrise API: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Failed to reach MET Sunrise API: {exc}") from exc
    return payload


def _to_number_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return f"{value:.2f}"
    return str(value)


def _fetch_day(
    *,
    latitude: float,
    longitude: float,
    day: date,
    offset: str,
    timeout: float,
    user_agent: str,
) -> dict[str, str]:
    payload = _request_json(
        latitude=latitude,
        longitude=longitude,
        day=day,
        offset=offset,
        timeout=timeout,
        user_agent=user_agent,
    )
    properties = payload.get("properties", {})
    sunrise = properties.get("sunrise", {}) or {}
    sunset = properties.get("sunset", {}) or {}

    return {
        "date": day.isoformat(),
        "sunrise": sunrise.get("time") or "",
        "sunrise_azimuth": _to_number_string(sunrise.get("azimuth")),
        "sunset": sunset.get("time") or "",
        "sunset_azimuth": _to_number_string(sunset.get("azimuth")),
    }


def _fetch_day_with_retry(
    *,
    latitude: float,
    longitude: float,
    day: date,
    offset: str,
    timeout: float,
    user_agent: str,
    retries: int,
    retry_backoff_sec: float,
) -> dict[str, str]:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return _fetch_day(
                latitude=latitude,
                longitude=longitude,
                day=day,
                offset=offset,
                timeout=timeout,
                user_agent=user_agent,
            )
        except RuntimeError as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(retry_backoff_sec * (2**attempt))

    raise RuntimeError(
        f"Failed to fetch MET sun data for {day.isoformat()} after {retries + 1} attempts: {last_error}"
    ) from last_error


def fetch_met_sun_times(
    latitude: float,
    longitude: float,
    start_date: str | date,
    end_date: str | date | None = None,
    offset: str = "+00:00",
    timeout: float = 20.0,
    user_agent: str = DEFAULT_USER_AGENT,
    max_workers: int = 6,
    retries: int = 2,
    retry_backoff_sec: float = 0.4,
) -> list[dict[str, str]]:
    """
    Return sunrise/sunset rows from MET Sunrise API.

    Each row has:
      - date: YYYY-MM-DD
      - sunrise: ISO datetime string with offset, or empty string
      - sunrise_azimuth: azimuth degrees at sunrise, or empty string
      - sunset: ISO datetime string with offset, or empty string
      - sunset_azimuth: azimuth degrees at sunset, or empty string
    """
    start = _to_date(start_date)
    end = _to_date(end_date) if end_date is not None else start
    if end < start:
        raise ValueError("end_date must be >= start_date")
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")
    if retries < 0:
        raise ValueError("retries must be >= 0")

    days = _date_range(start, end)
    rows_by_date: dict[str, dict[str, str]] = {}

    if max_workers == 1:
        for day in days:
            row = _fetch_day_with_retry(
                latitude=latitude,
                longitude=longitude,
                day=day,
                offset=offset,
                timeout=timeout,
                user_agent=user_agent,
                retries=retries,
                retry_backoff_sec=retry_backoff_sec,
            )
            rows_by_date[row["date"]] = row
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_day = {
                executor.submit(
                    _fetch_day_with_retry,
                    latitude=latitude,
                    longitude=longitude,
                    day=day,
                    offset=offset,
                    timeout=timeout,
                    user_agent=user_agent,
                    retries=retries,
                    retry_backoff_sec=retry_backoff_sec,
                ): day
                for day in days
            }
            for future in as_completed(future_to_day):
                day = future_to_day[future]
                try:
                    row = future.result()
                except Exception as exc:  # pragma: no cover - defensive enrichment
                    raise RuntimeError(
                        f"Failed while fetching MET sun data for {day.isoformat()}: {exc}"
                    ) from exc
                rows_by_date[row["date"]] = row

    return [rows_by_date[d.isoformat()] for d in days]


def fetch_met_sun_time_for_day(
    latitude: float,
    longitude: float,
    day: str | date,
    offset: str = "+00:00",
    timeout: float = 20.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, str]:
    rows = fetch_met_sun_times(
        latitude=latitude,
        longitude=longitude,
        start_date=day,
        end_date=day,
        offset=offset,
        timeout=timeout,
        user_agent=user_agent,
        max_workers=1,
    )
    if not rows:
        raise RuntimeError("No data returned for the requested day.")
    return rows[0]


def save_sun_times_csv(rows: list[dict[str, str]], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["date", "sunrise", "sunrise_azimuth", "sunset", "sunset_azimuth"],
        )
        writer.writeheader()
        writer.writerows(rows)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch sunrise/sunset from MET Sunrise API and optionally save CSV."
    )
    parser.add_argument("--lat", type=float, required=True, help="Latitude")
    parser.add_argument("--lon", type=float, required=True, help="Longitude")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="End date (YYYY-MM-DD), default=start")
    parser.add_argument(
        "--offset",
        default="+00:00",
        help="Timezone offset for returned times, e.g. +00:00",
    )
    parser.add_argument("--workers", type=int, default=6, help="Parallel request workers")
    parser.add_argument("--output", default=None, help="CSV output path")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    rows = fetch_met_sun_times(
        latitude=args.lat,
        longitude=args.lon,
        start_date=args.start,
        end_date=args.end,
        offset=args.offset,
        max_workers=args.workers,
    )
    if args.output:
        save_sun_times_csv(rows, args.output)
        print(f"Saved {len(rows)} rows to {args.output}")
    else:
        for row in rows:
            print(
                f"{row['date']}, sunrise={row['sunrise']} (az={row['sunrise_azimuth']}), "
                f"sunset={row['sunset']} (az={row['sunset_azimuth']})"
            )


if __name__ == "__main__":
    main()
