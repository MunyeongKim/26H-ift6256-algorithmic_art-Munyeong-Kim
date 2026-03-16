#!/usr/bin/env python
"""Run the HW3 pipeline end-to-end inside a single structured run folder."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

from fetch_streetview_pair import _load_env_file, _safe_name, save_pair
from find_and_fetch_sun_streetview import _extract_lat_lon_from_google_maps_url, _parse_utc_iso_minute
from find_shared_sun_instants import default_search_window, find_shared_sun_instants, save_matches_csv
from openai_transform_sketch import transform_images
from openai_transform_sketch_v7 import DEFAULT_MODEL as DEFAULT_IMAGE_MODEL
from openai_transform_sketch_v7 import transform_pair_v7
from juxtapose_images import DEFAULT_FONT, compose_images
from utils.normalize_address_llm import DEFAULT_MODEL as DEFAULT_TEXT_MODEL
from utils.normalize_address_llm import _summarize_openai_response
from utils.normalize_address_llm import normalize_reverse_geocode_with_openai
from utils.reverse_geocode import resolve_language_choice, reverse_geocode

UNICODE_FONT = "/Library/Fonts/Arial Unicode.ttf"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _relative_to(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _resolve_run_dir(run_root: Path, requested_run_id: str | None) -> tuple[str, Path]:
    if requested_run_id:
        run_id = requested_run_id
        return run_id, run_root / run_id

    base_run_id = datetime.now().strftime("%Y%m%d%H%M")
    run_dir = run_root / base_run_id
    if not run_dir.exists():
        return base_run_id, run_dir

    suffix = 1
    while True:
        run_id = f"{base_run_id}_{suffix:02d}"
        run_dir = run_root / run_id
        if not run_dir.exists():
            return run_id, run_dir
        suffix += 1


def _resolve_compose_order(
    *,
    event_a: str,
    event_b: str,
    image_a: Path,
    image_b: Path,
    label_a: str,
    label_b: str,
    line2_a: str,
    line2_b: str,
) -> dict[str, str | Path]:
    a = {
        "event": event_a,
        "image": image_a,
        "label": label_a,
        "line2": line2_a,
    }
    b = {
        "event": event_b,
        "image": image_b,
        "label": label_b,
        "line2": line2_b,
    }

    if event_a == "sunrise" and event_b == "sunset":
        left = b
        right = a
    else:
        left = a
        right = b

    return {
        "left_image": left["image"],
        "right_image": right["image"],
        "left_label": left["label"],
        "right_label": right["label"],
        "left_line2": left["line2"],
        "right_line2": right["line2"],
        "left_event": left["event"],
        "right_event": right["event"],
    }


def _build_parser() -> argparse.ArgumentParser:
    default_start, default_end = default_search_window()
    parser = argparse.ArgumentParser(description="Run the HW3 sun-match pipeline in one shot.")
    parser.add_argument("--name-a", default="location_a", help="Label for location A")
    parser.add_argument("--maps-url-a", required=True, help="Google Maps URL for location A")
    parser.add_argument("--event-a", choices=["sunrise", "sunset"], default="sunrise")
    parser.add_argument("--tz-a", default="UTC", help="IANA timezone for location A local display")
    parser.add_argument(
        "--address-lang-a",
        choices=["none", "en", "fr", "other"],
        default="en",
        help="Reverse-geocoded address language option for location A",
    )
    parser.add_argument("--address-lang-code-a", default=None, help="Language code when A uses other")

    parser.add_argument("--name-b", default="location_b", help="Label for location B")
    parser.add_argument("--maps-url-b", required=True, help="Google Maps URL for location B")
    parser.add_argument("--event-b", choices=["sunrise", "sunset"], default="sunset")
    parser.add_argument("--tz-b", default="UTC", help="IANA timezone for location B local display")
    parser.add_argument(
        "--address-lang-b",
        choices=["none", "en", "fr", "other"],
        default="en",
        help="Reverse-geocoded address language option for location B",
    )
    parser.add_argument("--address-lang-code-b", default=None, help="Language code when B uses other")

    parser.add_argument("--start", default=default_start, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=default_end, help="End date (YYYY-MM-DD)")
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
        "--google-api-key",
        default=None,
        help="Google Maps API key. If omitted, read GOOGLE_MAPS_API_KEY (.env supported).",
    )
    parser.add_argument("--pitch-a", type=float, default=0.0, help="Camera pitch for location A")
    parser.add_argument("--pitch-b", type=float, default=0.0, help="Camera pitch for location B")
    parser.add_argument("--streetview-size", default="640x640", help="Street View size")
    parser.add_argument("--fov", type=int, default=90, help="Street View field of view")
    parser.add_argument("--radius", type=int, default=50, help="Street View search radius")
    parser.add_argument(
        "--source",
        choices=["default", "outdoor"],
        default="default",
        help="Street View source filter",
    )

    parser.add_argument(
        "--openai-api-key",
        default=None,
        help="OpenAI API key. If omitted, read OPENAI_API_KEY (.env supported).",
    )
    parser.add_argument(
        "--normalize-addresses",
        action="store_true",
        help="Normalize reverse-geocoded labels with OpenAI text API.",
    )
    parser.add_argument("--normalize-model", default=DEFAULT_TEXT_MODEL, help="OpenAI text model.")
    parser.add_argument("--normalize-timeout", type=float, default=90.0, help="Text API timeout seconds.")

    parser.add_argument(
        "--skip-transform",
        action="store_true",
        help="Skip the OpenAI transform step and compose raw Street View images.",
    )
    parser.add_argument(
        "--transform-pipeline",
        choices=["v1", "v7"],
        default="v7",
        help="Transform pipeline to use when OpenAI rendering is enabled.",
    )
    parser.add_argument(
        "--style-reference-step1",
        default="HW3/style_reference_oratory.png",
        help="Style reference image path for v7 step1 base generation",
    )
    parser.add_argument(
        "--style-reference-step2",
        default="HW3/style_reference_pohang.png",
        help="Style reference image path for v7 step2 sun overlay",
    )
    parser.add_argument("--transform-model", default=DEFAULT_IMAGE_MODEL, help="OpenAI image model.")
    parser.add_argument("--transform-size", default="1024x1024", help="Transform output size")
    parser.add_argument("--transform-quality", default="high", help="OpenAI image quality")
    parser.add_argument(
        "--transform-input-fidelity",
        default="high",
        help="How strongly to preserve the input composition",
    )
    parser.add_argument(
        "--transform-output-format",
        choices=["png", "jpeg", "webp"],
        default="png",
        help="Transform output format",
    )
    parser.add_argument(
        "--transform-output-compression",
        type=int,
        default=90,
        help="Compression for jpeg/webp outputs",
    )
    parser.add_argument(
        "--transform-alpha-retry-threshold",
        type=float,
        default=20.0,
        help="Retry v7 outputs when non-opaque pixels exceed this percentage.",
    )
    parser.add_argument(
        "--transform-max-alpha-retries",
        type=int,
        default=2,
        help="Maximum automatic retries for transparent v7 outputs.",
    )
    parser.add_argument(
        "--transform-white-background-min-pct",
        type=float,
        default=85.0,
        help="Retry v7 outputs when near-white background coverage drops below this percentage.",
    )
    parser.add_argument("--transform-timeout", type=float, default=240.0, help="Image API timeout seconds.")
    parser.add_argument(
        "--dry-run-openai",
        action="store_true",
        help="Copy images instead of calling OpenAI for transform testing.",
    )

    parser.add_argument("--skip-compose", action="store_true", help="Skip final juxtapose output.")
    parser.add_argument("--compose-gap", type=int, default=0, help="Gap between left and right images")
    parser.add_argument("--compose-bg", default="white", help="Compose background color")
    parser.add_argument(
        "--compose-frame-ratio",
        type=float,
        default=1.41421356,
        help="Per-image frame ratio for juxtapose",
    )
    parser.add_argument("--compose-image-border", type=int, default=5, help="Border thickness in pixels")
    parser.add_argument(
        "--compose-outer-pad",
        type=int,
        default=-1,
        help="Outer padding in pixels; -1 means auto-match the per-side frame padding",
    )
    parser.add_argument("--compose-note-size", type=int, default=27, help="Label font size")
    parser.add_argument("--compose-note-pad", type=int, default=8, help="Label pad below the frame")
    parser.add_argument("--compose-note-font", default=None, help="Override note font path")

    parser.add_argument("--run-root", default="HW3/runs", help="Root directory for one-shot runs")
    parser.add_argument("--run-id", default=None, help="Optional custom run folder name")
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    _load_env_file([Path("HW3/.env"), Path(".env")])
    google_api_key = args.google_api_key or os.getenv("GOOGLE_MAPS_API_KEY")
    openai_api_key = args.openai_api_key or os.getenv("OPENAI_API_KEY")

    if not google_api_key:
        raise RuntimeError("Missing Google Maps API key. Set GOOGLE_MAPS_API_KEY or pass --google-api-key.")
    if (args.normalize_addresses or not args.skip_transform) and not args.dry_run_openai and not openai_api_key:
        raise RuntimeError("Missing OPENAI_API_KEY. Set it in HW3/.env or pass --openai-api-key.")

    run_root = Path(args.run_root)
    run_id, run_dir = _resolve_run_dir(run_root, args.run_id)
    inputs_dir = run_dir / "00_inputs"
    parsed_dir = run_dir / "01_parsed"
    match_dir = run_dir / "02_match"
    streetview_dir = run_dir / "03_streetview"
    geocode_dir = run_dir / "04_geocode"
    render_dir = run_dir / "05_render"
    compose_dir = run_dir / "06_compose"
    for path in (inputs_dir, parsed_dir, match_dir, streetview_dir, geocode_dir, render_dir, compose_dir):
        path.mkdir(parents=True, exist_ok=True)

    manifest_path = run_dir / "manifest.json"
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "run_root": str(run_dir),
        "steps": {},
    }

    request_payload = {
        "name_a": args.name_a,
        "maps_url_a": args.maps_url_a,
        "event_a": args.event_a,
        "tz_a": args.tz_a,
        "address_lang_a": args.address_lang_a,
        "address_lang_code_a": args.address_lang_code_a,
        "name_b": args.name_b,
        "maps_url_b": args.maps_url_b,
        "event_b": args.event_b,
        "tz_b": args.tz_b,
        "address_lang_b": args.address_lang_b,
        "address_lang_code_b": args.address_lang_code_b,
        "start": args.start,
        "end": args.end,
        "tol_min": args.tol_min,
        "match_index": args.match_index,
        "reference_utc": args.reference_utc,
        "allow_future_matches": args.allow_future_matches,
        "pitch_a": args.pitch_a,
        "pitch_b": args.pitch_b,
        "streetview_size": args.streetview_size,
        "fov": args.fov,
        "radius": args.radius,
        "source": args.source,
        "normalize_addresses": args.normalize_addresses,
        "skip_transform": args.skip_transform,
        "transform_pipeline": args.transform_pipeline,
        "style_reference_step1": args.style_reference_step1,
        "style_reference_step2": args.style_reference_step2,
        "transform_alpha_retry_threshold": args.transform_alpha_retry_threshold,
        "transform_max_alpha_retries": args.transform_max_alpha_retries,
        "transform_white_background_min_pct": args.transform_white_background_min_pct,
        "dry_run_openai": args.dry_run_openai,
        "skip_compose": args.skip_compose,
    }
    _write_json(inputs_dir / "request.json", request_payload)
    (inputs_dir / "maps_links.txt").write_text(
        (
            f"{args.name_a}\n{args.maps_url_a}\n\n"
            f"{args.name_b}\n{args.maps_url_b}\n"
        ),
        encoding="utf-8",
    )
    manifest["steps"]["inputs"] = {
        "request_json": _relative_to(inputs_dir / "request.json", run_dir),
        "maps_links_txt": _relative_to(inputs_dir / "maps_links.txt", run_dir),
    }
    _write_json(manifest_path, manifest)

    lat_a, lon_a = _extract_lat_lon_from_google_maps_url(args.maps_url_a)
    lat_b, lon_b = _extract_lat_lon_from_google_maps_url(args.maps_url_b)
    parsed_payload = {
        "location_a": {
            "name": args.name_a,
            "maps_url": args.maps_url_a,
            "lat": lat_a,
            "lon": lon_a,
            "event": args.event_a,
            "timezone": args.tz_a,
        },
        "location_b": {
            "name": args.name_b,
            "maps_url": args.maps_url_b,
            "lat": lat_b,
            "lon": lon_b,
            "event": args.event_b,
            "timezone": args.tz_b,
        },
    }
    parsed_path = parsed_dir / "parsed_locations.json"
    _write_json(parsed_path, parsed_payload)
    manifest["steps"]["parsed"] = {"parsed_locations_json": _relative_to(parsed_path, run_dir)}
    _write_json(manifest_path, manifest)

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
    matches_csv_path = match_dir / "matches.csv"
    save_matches_csv(matches, matches_csv_path)

    matches_with_az = [
        match
        for match in matches
        if match.get("a_azimuth_deg") is not None and match.get("b_azimuth_deg") is not None
    ]
    if not matches_with_az:
        raise RuntimeError(
            f"No matches with azimuth data found between {args.start} and {args.end}. "
            "Try widening the range or allowing future matches."
        )
    if args.match_index < 1 or args.match_index > len(matches_with_az):
        raise ValueError(
            f"--match-index must be between 1 and {len(matches_with_az)} (got {args.match_index})"
        )

    selected = matches_with_az[args.match_index - 1]
    heading_a = float(selected["a_azimuth_deg"]) % 360.0
    heading_b = float(selected["b_azimuth_deg"]) % 360.0
    selected_path = match_dir / "selected_match.json"
    _write_json(
        selected_path,
        {
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
                    else None
                ),
                "allow_future_matches": args.allow_future_matches,
            },
            "selected_match": selected,
            "headings": {
                "location_a": heading_a,
                "location_b": heading_b,
            },
        },
    )
    manifest["steps"]["match"] = {
        "matches_csv": _relative_to(matches_csv_path, run_dir),
        "selected_match_json": _relative_to(selected_path, run_dir),
    }
    _write_json(manifest_path, manifest)

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
        size=args.streetview_size,
        radius=args.radius,
        source=source,
        api_key=google_api_key,
        outdir=streetview_dir,
    )
    manifest["steps"]["streetview"] = {
        "image_a": _relative_to(img_a, run_dir),
        "image_b": _relative_to(img_b, run_dir),
        "metadata_a": _relative_to(streetview_dir / f"{_safe_name(args.name_a)}_metadata.json", run_dir),
        "metadata_b": _relative_to(streetview_dir / f"{_safe_name(args.name_b)}_metadata.json", run_dir),
        "request_a": _relative_to(streetview_dir / f"{_safe_name(args.name_a)}_request.json", run_dir),
        "request_b": _relative_to(streetview_dir / f"{_safe_name(args.name_b)}_request.json", run_dir),
    }
    _write_json(manifest_path, manifest)

    address_language_a = resolve_language_choice(args.address_lang_a, args.address_lang_code_a)
    address_language_b = resolve_language_choice(args.address_lang_b, args.address_lang_code_b)
    reverse_geocode_a = None
    reverse_geocode_b = None
    normalized_payload: dict[str, Any] = {}

    if address_language_a:
        reverse_geocode_a = reverse_geocode(
            lat=lat_a,
            lon=lon_a,
            api_key=google_api_key,
            language=address_language_a,
        )
        _write_json(geocode_dir / "reverse_geocode_a.json", reverse_geocode_a)
    if address_language_b:
        reverse_geocode_b = reverse_geocode(
            lat=lat_b,
            lon=lon_b,
            api_key=google_api_key,
            language=address_language_b,
        )
        _write_json(geocode_dir / "reverse_geocode_b.json", reverse_geocode_b)

    if args.normalize_addresses:
        if reverse_geocode_a:
            normalized_a, payload_a = normalize_reverse_geocode_with_openai(
                reverse_geocode_payload=reverse_geocode_a,
                requested_language=address_language_a or "en",
                api_key=openai_api_key or "",
                model=args.normalize_model,
                timeout=args.normalize_timeout,
            )
            normalized_payload["location_a"] = {
                "normalized": normalized_a,
                "openai": _summarize_openai_response(payload_a),
            }
        if reverse_geocode_b:
            normalized_b, payload_b = normalize_reverse_geocode_with_openai(
                reverse_geocode_payload=reverse_geocode_b,
                requested_language=address_language_b or "en",
                api_key=openai_api_key or "",
                model=args.normalize_model,
                timeout=args.normalize_timeout,
            )
            normalized_payload["location_b"] = {
                "normalized": normalized_b,
                "openai": _summarize_openai_response(payload_b),
            }
        if normalized_payload:
            _write_json(geocode_dir / "normalized_labels.json", normalized_payload)

    geocode_summary = {
        "location_a": {
            "address_language": address_language_a,
            "reverse_geocode": reverse_geocode_a,
            "normalized": normalized_payload.get("location_a", {}).get("normalized"),
        },
        "location_b": {
            "address_language": address_language_b,
            "reverse_geocode": reverse_geocode_b,
            "normalized": normalized_payload.get("location_b", {}).get("normalized"),
        },
    }
    geocode_summary_path = geocode_dir / "geocode_summary.json"
    _write_json(geocode_summary_path, geocode_summary)
    manifest["steps"]["geocode"] = {
        "geocode_summary_json": _relative_to(geocode_summary_path, run_dir),
        "reverse_geocode_a_json": _relative_to(geocode_dir / "reverse_geocode_a.json", run_dir)
        if reverse_geocode_a
        else None,
        "reverse_geocode_b_json": _relative_to(geocode_dir / "reverse_geocode_b.json", run_dir)
        if reverse_geocode_b
        else None,
        "normalized_labels_json": _relative_to(geocode_dir / "normalized_labels.json", run_dir)
        if normalized_payload
        else None,
    }
    _write_json(manifest_path, manifest)

    compose_left = img_a
    compose_right = img_b
    if not args.skip_transform:
        if args.transform_pipeline == "v7":
            render_result = transform_pair_v7(
                style_reference_step1=Path(args.style_reference_step1),
                style_reference_step2=Path(args.style_reference_step2),
                input_first=img_a,
                event_first=args.event_a,
                input_second=img_b,
                event_second=args.event_b,
                outdir=render_dir,
                suffix="_openai_sketch",
                model=args.transform_model,
                size=args.transform_size,
                quality=args.transform_quality,
                input_fidelity=args.transform_input_fidelity,
                output_format=args.transform_output_format,
                output_compression=args.transform_output_compression,
                alpha_retry_threshold=args.transform_alpha_retry_threshold,
                max_alpha_retries=args.transform_max_alpha_retries,
                white_background_min_pct=args.transform_white_background_min_pct,
                timeout=args.transform_timeout,
                api_key=openai_api_key,
                dry_run=args.dry_run_openai,
            )
            compose_left = Path(render_result["output_first"])
            compose_right = Path(render_result["output_second"])
            manifest["steps"]["render"] = {
                "pipeline": "v7",
                "output_a": _relative_to(compose_left, run_dir),
                "output_b": _relative_to(compose_right, run_dir),
                "step1_a": _relative_to(Path(render_result["step1_first"]), run_dir),
                "step1_b": _relative_to(Path(render_result["step1_second"]), run_dir),
                "pipeline_metadata": _relative_to(Path(render_result["metadata_path"]), run_dir),
                "style_reference_step1": args.style_reference_step1,
                "style_reference_step2": args.style_reference_step2,
                "alpha_retry_threshold": args.transform_alpha_retry_threshold,
                "max_alpha_retries": args.transform_max_alpha_retries,
                "white_background_min_pct": args.transform_white_background_min_pct,
            }
        else:
            render_results = transform_images(
                input_paths=[img_a, img_b],
                outdir=render_dir,
                suffix="_openai_sketch",
                sun_events=[args.event_a, args.event_b],
                model=args.transform_model,
                size=args.transform_size,
                quality=args.transform_quality,
                input_fidelity=args.transform_input_fidelity,
                output_format=args.transform_output_format,
                output_compression=args.transform_output_compression,
                timeout=args.transform_timeout,
                api_key=openai_api_key,
                dry_run=args.dry_run_openai,
            )
            compose_left = Path(render_results[0]["output_path"])
            compose_right = Path(render_results[1]["output_path"])
            manifest["steps"]["render"] = {
                "pipeline": "v1",
                "output_a": _relative_to(compose_left, run_dir),
                "output_b": _relative_to(compose_right, run_dir),
                "step1_a": _relative_to(Path(render_results[0]["step1_output_path"]), run_dir),
                "step1_b": _relative_to(Path(render_results[1]["step1_output_path"]), run_dir),
                "metadata_a": _relative_to(Path(render_results[0]["metadata_path"]), run_dir),
                "metadata_b": _relative_to(Path(render_results[1]["metadata_path"]), run_dir),
            }
    else:
        manifest["steps"]["render"] = None
    _write_json(manifest_path, manifest)

    if args.skip_compose:
        print(f"[DONE] run folder: {run_dir}")
        print(f"[DONE] manifest: {manifest_path}")
        return

    label_a = (
        normalized_payload.get("location_a", {}).get("normalized", {}).get("normalized_label")
        or (reverse_geocode_a or {}).get("district_label")
        or args.name_a
    )
    label_b = (
        normalized_payload.get("location_b", {}).get("normalized", {}).get("normalized_label")
        or (reverse_geocode_b or {}).get("district_label")
        or args.name_b
    )
    line2_a = f"({lat_a}, {lon_a}), {selected['a_local'].replace('T', ' ')}"
    line2_b = f"({lat_b}, {lon_b}), {selected['b_local'].replace('T', ' ')}"
    compose_order = _resolve_compose_order(
        event_a=args.event_a,
        event_b=args.event_b,
        image_a=compose_left,
        image_b=compose_right,
        label_a=label_a,
        label_b=label_b,
        line2_a=line2_a,
        line2_b=line2_b,
    )
    compose_left = Path(compose_order["left_image"])
    compose_right = Path(compose_order["right_image"])
    left_note = f"{compose_order['left_label']}\n{compose_order['left_line2']}"
    right_note = f"{compose_order['right_label']}\n{compose_order['right_line2']}"

    compose_note_font = args.compose_note_font
    if not compose_note_font:
        compose_note_font = UNICODE_FONT if Path(UNICODE_FONT).exists() else DEFAULT_FONT

    outer_pad = args.compose_outer_pad
    if outer_pad < 0:
        with Image.open(compose_left) as sample:
            outer_pad = max(
                0,
                (max(sample.width, int(round(sample.width * args.compose_frame_ratio))) - sample.width) // 2,
            )

    final_path = compose_images(
        left_path=compose_left,
        right_path=compose_right,
        output_path=compose_dir / "juxtapose.png",
        gap=args.compose_gap,
        bg=args.compose_bg,
        left_note=left_note,
        right_note=right_note,
        note_font=compose_note_font,
        note_size=args.compose_note_size,
        note_pad=args.compose_note_pad,
        frame_ratio=args.compose_frame_ratio,
        image_border=args.compose_image_border,
        outer_pad=outer_pad,
    )
    compose_meta = {
        "left_image": str(compose_left),
        "right_image": str(compose_right),
        "left_event": compose_order["left_event"],
        "right_event": compose_order["right_event"],
        "output_path": str(final_path),
        "left_note": left_note,
        "right_note": right_note,
        "font": compose_note_font,
        "note_size": args.compose_note_size,
        "note_pad": args.compose_note_pad,
        "gap": args.compose_gap,
        "frame_ratio": args.compose_frame_ratio,
        "image_border": args.compose_image_border,
        "outer_pad": outer_pad,
    }
    compose_meta_path = compose_dir / "compose_metadata.json"
    _write_json(compose_meta_path, compose_meta)
    manifest["steps"]["compose"] = {
        "juxtapose_png": _relative_to(final_path, run_dir),
        "compose_metadata_json": _relative_to(compose_meta_path, run_dir),
    }
    _write_json(manifest_path, manifest)

    print(f"[DONE] run folder: {run_dir}")
    print(f"[DONE] manifest: {manifest_path}")
    print(f"[DONE] final image: {final_path}")


if __name__ == "__main__":
    main()
