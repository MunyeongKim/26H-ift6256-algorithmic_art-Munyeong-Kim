#!/usr/bin/env python
"""Normalize reverse-geocoded address payloads with OpenAI into district-level labels."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import requests

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-4o-mini"

ADDRESS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "district": {"type": "string"},
        "subcity": {"type": "string"},
        "city": {"type": "string"},
        "admin1": {"type": "string"},
        "country": {"type": "string"},
        "normalized_label": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "notes": {"type": "string"},
    },
    "required": [
        "district",
        "subcity",
        "city",
        "admin1",
        "country",
        "normalized_label",
        "confidence",
        "notes",
    ],
}

DEVELOPER_PROMPT = """You normalize reverse-geocoded locations into district-level labels.

Rules:
- Use only the provided metadata. Do not use web search or outside facts.
- Prefer the smallest administratively meaningful area available.
- If a road/street name appears but a neighborhood/dong/ward/gu/borough/district can be inferred from formatted_address or components, prefer the neighborhood-style administrative unit instead of the road.
- Include an intermediate sub-city administrative area when it is meaningful and available, such as gu/ward/borough/arrondissement.
- Keep the output in the requested language/script.
- normalized_label format must be: district, subcity, city, admin1, country
- If subcity is not available, return an empty string for subcity and omit it from normalized_label.
- Be conservative. Do not invent missing administrative areas.
- notes must briefly explain why the chosen district is better than the raw district_label when relevant.
"""


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


def _extract_error_text(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:1000]

    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            message = err.get("message")
            if isinstance(message, str) and message.strip():
                return message
            return json.dumps(err, ensure_ascii=False)
        return json.dumps(payload, ensure_ascii=False)
    return str(payload)


def _extract_output_text(payload: dict[str, Any]) -> str:
    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for chunk in content:
                if not isinstance(chunk, dict):
                    continue
                if chunk.get("type") == "output_text" and isinstance(chunk.get("text"), str):
                    return chunk["text"]
                if chunk.get("type") == "text" and isinstance(chunk.get("text"), str):
                    return chunk["text"]
    raise RuntimeError("OpenAI response did not include output text.")


def normalize_reverse_geocode_with_openai(
    *,
    reverse_geocode_payload: dict[str, Any],
    requested_language: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
    timeout: float = 90.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    user_payload = {
        "requested_language": requested_language,
        "reverse_geocode": reverse_geocode_payload,
    }
    request_payload = {
        "model": model,
        "input": [
            {
                "role": "developer",
                "content": [{"type": "input_text", "text": DEVELOPER_PROMPT}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Return JSON only. Normalize this reverse-geocoded location into a "
                            "district-level administrative label.\n\n"
                            f"{json.dumps(user_payload, ensure_ascii=False, indent=2)}"
                        ),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "normalized_address",
                "schema": ADDRESS_SCHEMA,
                "strict": True,
            }
        },
    }
    response = requests.post(
        OPENAI_RESPONSES_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=request_payload,
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"OpenAI address normalization failed: HTTP {response.status_code}: "
            f"{_extract_error_text(response)}"
        )
    payload = response.json()
    text = _extract_output_text(payload)
    return json.loads(text), payload


def _summarize_openai_response(payload: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in ("id", "model", "status", "created_at", "usage"):
        if key in payload:
            summary[key] = payload[key]
    return summary


def _normalize_summary_in_place(
    *,
    summary_path: Path,
    api_key: str,
    model: str,
    timeout: float,
) -> None:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    for location_key in ("location_a", "location_b"):
        location = summary.get(location_key)
        if not isinstance(location, dict):
            continue
        reverse_geocode = location.get("reverse_geocode")
        if not isinstance(reverse_geocode, dict):
            continue
        requested_language = str(location.get("address_language") or "en")
        normalized, payload = normalize_reverse_geocode_with_openai(
            reverse_geocode_payload=reverse_geocode,
            requested_language=requested_language,
            api_key=api_key,
            model=model,
            timeout=timeout,
        )
        location["llm_normalized_address"] = normalized
        location["llm_normalized_address_openai"] = _summarize_openai_response(payload)
        print(f"[OK] {location_key}: {normalized['normalized_label']}")

    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] saved: {summary_path}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize reverse-geocoded location labels with OpenAI."
    )
    parser.add_argument(
        "--summary",
        required=True,
        help="Summary JSON path containing location_a/location_b reverse_geocode payloads.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI text model.")
    parser.add_argument("--timeout", type=float, default=90.0, help="HTTP timeout seconds.")
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenAI API key. If omitted, read OPENAI_API_KEY (.env supported).",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    _load_env_file([Path("HW3/.env"), Path(".env")])
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY. Set it in HW3/.env or pass --api-key.")

    _normalize_summary_in_place(
        summary_path=Path(args.summary),
        api_key=api_key,
        model=args.model,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
