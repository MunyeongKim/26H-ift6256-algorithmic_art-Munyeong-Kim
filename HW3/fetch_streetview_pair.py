#!/usr/bin/env python
"""Fetch Street View images for two locations using Google Street View Static API."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

STREETVIEW_IMAGE_URL = "https://maps.googleapis.com/maps/api/streetview"
STREETVIEW_METADATA_URL = "https://maps.googleapis.com/maps/api/streetview/metadata"


def _safe_name(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip())
    return cleaned.strip("_") or "location"


def _load_env_file(paths: list[Path]) -> None:
    """Load simple KEY=VALUE pairs from .env file if present."""
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


def _get_json(url: str, params: dict[str, Any], timeout: float = 20.0) -> dict[str, Any]:
    full_url = f"{url}?{urlencode(params)}"
    req = Request(full_url, headers={"User-Agent": "HW3-streetview-fetch/1.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Failed to connect to Google API: {exc}") from exc


def _get_bytes(url: str, params: dict[str, Any], timeout: float = 25.0) -> bytes:
    full_url = f"{url}?{urlencode(params)}"
    req = Request(full_url, headers={"User-Agent": "HW3-streetview-fetch/1.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Failed to connect to Google API: {exc}") from exc


def fetch_metadata(
    *,
    lat: float,
    lon: float,
    api_key: str,
    radius: int,
    source: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "location": f"{lat},{lon}",
        "radius": radius,
        "key": api_key,
    }
    if source:
        params["source"] = source
    payload = _get_json(STREETVIEW_METADATA_URL, params)
    return payload


def fetch_streetview_image(
    *,
    lat: float,
    lon: float,
    heading: float,
    pitch: float,
    fov: int,
    size: str,
    api_key: str,
    radius: int,
    source: str | None,
) -> bytes:
    params: dict[str, Any] = {
        "size": size,
        "location": f"{lat},{lon}",
        "heading": heading,
        "pitch": pitch,
        "fov": fov,
        "radius": radius,
        "return_error_code": "true",
        "key": api_key,
    }
    if source:
        params["source"] = source
    return _get_bytes(STREETVIEW_IMAGE_URL, params)


def save_pair(
    *,
    name_a: str,
    lat_a: float,
    lon_a: float,
    heading_a: float,
    pitch_a: float,
    name_b: str,
    lat_b: float,
    lon_b: float,
    heading_b: float,
    pitch_b: float,
    fov: int,
    size: str,
    radius: int,
    source: str | None,
    api_key: str,
    outdir: Path,
) -> tuple[Path, Path]:
    outdir.mkdir(parents=True, exist_ok=True)

    records: list[tuple[str, float, float, float, float]] = [
        (name_a, lat_a, lon_a, heading_a, pitch_a),
        (name_b, lat_b, lon_b, heading_b, pitch_b),
    ]
    saved_paths: list[Path] = []

    for name, lat, lon, heading, pitch in records:
        safe = _safe_name(name)
        metadata = fetch_metadata(
            lat=lat,
            lon=lon,
            api_key=api_key,
            radius=radius,
            source=source,
        )
        status = metadata.get("status", "")
        if status != "OK":
            raise RuntimeError(
                f"Metadata check failed for '{name}' ({lat},{lon}): status={status}, "
                f"message={metadata.get('error_message', '')}"
            )

        image_bytes = fetch_streetview_image(
            lat=lat,
            lon=lon,
            heading=heading,
            pitch=pitch,
            fov=fov,
            size=size,
            api_key=api_key,
            radius=radius,
            source=source,
        )

        image_path = outdir / f"{safe}_streetview.jpg"
        meta_path = outdir / f"{safe}_metadata.json"
        request_path = outdir / f"{safe}_request.json"

        image_path.write_bytes(image_bytes)
        meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        request_path.write_text(
            json.dumps(
                {
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "heading": heading,
                    "pitch": pitch,
                    "fov": fov,
                    "size": size,
                    "radius": radius,
                    "source": source,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        saved_paths.append(image_path)
        print(f"[OK] saved image: {image_path}")
        print(f"[OK] saved metadata: {meta_path}")

    return saved_paths[0], saved_paths[1]


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Download two Street View images (with metadata validation)."
    )
    p.add_argument(
        "--api-key",
        default=None,
        help="Google Maps API key. If omitted, read GOOGLE_MAPS_API_KEY (.env supported).",
    )

    p.add_argument("--name-a", required=True, help="Name label for location A")
    p.add_argument("--lat-a", required=True, type=float, help="Latitude for location A")
    p.add_argument("--lon-a", required=True, type=float, help="Longitude for location A")
    p.add_argument("--heading-a", type=float, default=0.0, help="Camera heading for location A")
    p.add_argument("--pitch-a", type=float, default=0.0, help="Camera pitch for location A")

    p.add_argument("--name-b", required=True, help="Name label for location B")
    p.add_argument("--lat-b", required=True, type=float, help="Latitude for location B")
    p.add_argument("--lon-b", required=True, type=float, help="Longitude for location B")
    p.add_argument("--heading-b", type=float, default=0.0, help="Camera heading for location B")
    p.add_argument("--pitch-b", type=float, default=0.0, help="Camera pitch for location B")

    p.add_argument("--size", default="640x640", help="Image size (default: 640x640)")
    p.add_argument("--fov", type=int, default=90, help="Field of view (10~120)")
    p.add_argument("--radius", type=int, default=50, help="Search radius in meters")
    p.add_argument(
        "--source",
        choices=["default", "outdoor"],
        default="outdoor",
        help="Street View source filter",
    )
    p.add_argument("--outdir", default="HW3/streetview_outputs", help="Output directory")
    return p


def main() -> None:
    args = _parser().parse_args()

    _load_env_file([Path("HW3/.env"), Path(".env")])
    api_key = args.api_key or os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing API key. Set GOOGLE_MAPS_API_KEY or pass --api-key."
        )

    source = None if args.source == "default" else args.source
    img_a, img_b = save_pair(
        name_a=args.name_a,
        lat_a=args.lat_a,
        lon_a=args.lon_a,
        heading_a=args.heading_a,
        pitch_a=args.pitch_a,
        name_b=args.name_b,
        lat_b=args.lat_b,
        lon_b=args.lon_b,
        heading_b=args.heading_b,
        pitch_b=args.pitch_b,
        fov=args.fov,
        size=args.size,
        radius=args.radius,
        source=source,
        api_key=api_key,
        outdir=Path(args.outdir),
    )
    print(f"[DONE] A image: {img_a}")
    print(f"[DONE] B image: {img_b}")


if __name__ == "__main__":
    main()
