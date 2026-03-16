#!/usr/bin/env python
"""Transform input photos into line-sketch style images using OpenAI Images API."""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
from pathlib import Path
from typing import Any

import requests

OPENAI_IMAGE_EDIT_URL = "https://api.openai.com/v1/images/edits"
DEFAULT_MODEL = "gpt-image-1"
DEFAULT_STEP1_PROMPT_TEMPLATE = (
    "이 사진을 '추상화된 크로키, 단일 펜 미니멀 라인 스케치' 스타일의 베이스로 변환해줘. "
    "흰 배경 위에 단일 펜 느낌의 검은 선으로 표현하고 디테일은 최소화해줘. "
    "카메라 방향은 의도적으로 맞춰 둔 구도이므로 원근과 수평선 방향을 유지해줘. "
    "이 단계에서는 해, 햇빛, 컬러 효과를 추가하지 말고 순수 흑백 스케치만 만들어줘."
)
DEFAULT_PROMPT_TEMPLATE = (
    "이 이미지는 이미 완성된 흑백 단일 펜 미니멀 라인 스케치야. "
    "기존 선화, 구도, 원근, 물체 형태는 절대 바꾸지 말고 그대로 유지해줘. "
    "이번 단계에서는 {sun_event} 연출을 위해 해/햇빛 관련 요소만 빨간색으로 얹어줘. "
    "해 원판은 이미지 정중앙 방향의 지평선(또는 수평선) 근처에 배치해줘. "
    "단, 그 방향에 해가 보일 하늘 공간이 없으면 해 원판은 추가하지 말고, "
    "붉은 기/은은한 광채/약한 반사광만 표현해줘. "
    "검은 선 스케치 자체는 수정하지 말고, 다른 색은 절대 사용하지 마."
)


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


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    return "image/png"


def _extract_error_text(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:500]

    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            message = err.get("message")
            if isinstance(message, str) and message.strip():
                return message
            return json.dumps(err, ensure_ascii=False)
        return json.dumps(payload, ensure_ascii=False)
    return str(payload)


def _decode_image_from_payload(payload: dict[str, Any]) -> bytes:
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError("OpenAI Images response did not include a non-empty data list.")
    item = data[0]
    if not isinstance(item, dict):
        raise RuntimeError("OpenAI Images response had an unexpected data item type.")

    b64 = item.get("b64_json")
    if isinstance(b64, str) and b64:
        return base64.b64decode(b64)

    url = item.get("url")
    if isinstance(url, str) and url:
        image_resp = requests.get(url, timeout=180)
        if image_resp.status_code >= 400:
            raise RuntimeError(
                f"OpenAI returned URL output but download failed: HTTP {image_resp.status_code}"
            )
        return image_resp.content

    raise RuntimeError("OpenAI Images response did not include b64_json or url output.")


def _summarize_openai_response(payload: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in ("created", "output_format", "quality", "size", "usage", "background"):
        if key in payload:
            summary[key] = payload[key]

    data_items = payload.get("data")
    summarized_items: list[dict[str, Any]] = []
    if isinstance(data_items, list):
        for item in data_items:
            if not isinstance(item, dict):
                continue
            new_item: dict[str, Any] = {}
            for k, v in item.items():
                if k == "b64_json" and isinstance(v, str):
                    new_item[k] = f"<omitted base64: {len(v)} chars>"
                else:
                    new_item[k] = v
            summarized_items.append(new_item)
    if summarized_items:
        summary["data"] = summarized_items
    return summary


def edit_image_openai(
    *,
    image_path: Path,
    api_key: str,
    prompt: str,
    model: str,
    size: str,
    quality: str,
    input_fidelity: str,
    output_format: str,
    output_compression: int,
    timeout: float,
) -> tuple[bytes, dict[str, Any]]:
    headers = {"Authorization": f"Bearer {api_key}"}
    image_bytes = image_path.read_bytes()
    mime = _guess_mime(image_path)

    data: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "input_fidelity": input_fidelity,
        "output_format": output_format,
    }
    if output_format in {"jpeg", "webp"}:
        data["output_compression"] = output_compression

    last_error: str | None = None
    for image_field in ("image[]", "image"):
        files = [(image_field, (image_path.name, image_bytes, mime))]
        response = requests.post(
            OPENAI_IMAGE_EDIT_URL,
            headers=headers,
            data=data,
            files=files,
            timeout=timeout,
        )
        if response.status_code < 400:
            payload = response.json()
            output_bytes = _decode_image_from_payload(payload)
            return output_bytes, payload
        last_error = (
            f"HTTP {response.status_code} ({image_field}): {_extract_error_text(response)}"
        )

    raise RuntimeError(f"OpenAI image edit failed for {image_path}: {last_error}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Transform one or more photos into sketch style using OpenAI Images API."
    )
    parser.add_argument(
        "--input",
        nargs="+",
        required=True,
        help="Input image path(s).",
    )
    parser.add_argument(
        "--outdir",
        default="HW3/streetview_outputs/openai_sketches",
        help="Output directory for transformed images.",
    )
    parser.add_argument(
        "--suffix",
        default="_openai_sketch",
        help="Suffix for output file names.",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Fixed image edit prompt for all inputs.",
    )
    parser.add_argument(
        "--prompt-template",
        default=DEFAULT_PROMPT_TEMPLATE,
        help="Prompt template when --prompt is not provided. Supports {sun_event}.",
    )
    parser.add_argument(
        "--sun-events",
        nargs="+",
        default=None,
        help=(
            "Per-image sun events (e.g. sunset sunrise). "
            "If omitted, infer from file names."
        ),
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI image model.")
    parser.add_argument("--size", default="1024x1024", help="Output image size (default: 1024x1024).")
    parser.add_argument("--quality", default="high", help="Image quality setting.")
    parser.add_argument(
        "--input-fidelity",
        default="high",
        help="How strongly to preserve the input composition.",
    )
    parser.add_argument(
        "--output-format",
        choices=["png", "jpeg", "webp"],
        default="png",
        help="Output image format.",
    )
    parser.add_argument(
        "--output-compression",
        type=int,
        default=90,
        help="Compression level for jpeg/webp (0-100).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=240.0,
        help="HTTP timeout seconds.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenAI API key. If omitted, read OPENAI_API_KEY (.env supported).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip API call and just copy input files to output for path testing.",
    )
    return parser


def _infer_sun_event(input_path: Path) -> str:
    name = input_path.stem.lower()
    if "sunrise" in name:
        return "sunrise"
    if "sunset" in name:
        return "sunset"
    return "sunrise or sunset"


def _resolve_sun_events(input_paths: list[Path], raw_events: list[str] | None) -> list[str]:
    if not raw_events:
        return [_infer_sun_event(path) for path in input_paths]

    normalized = [value.strip().lower() for value in raw_events if value.strip()]
    if not normalized:
        return [_infer_sun_event(path) for path in input_paths]
    if len(normalized) == 1:
        return normalized * len(input_paths)
    if len(normalized) != len(input_paths):
        raise ValueError(
            f"--sun-events count must be 1 or match --input count ({len(input_paths)})."
        )
    return normalized


def _prompt_for_image(
    *,
    fixed_prompt: str | None,
    prompt_template: str,
    sun_event: str,
) -> str:
    if fixed_prompt:
        return fixed_prompt
    event_ko = {"sunrise": "일출", "sunset": "일몰"}.get(sun_event.lower(), sun_event)
    return prompt_template.replace("{sun_event}", event_ko)


def transform_images(
    *,
    input_paths: list[Path],
    outdir: Path,
    suffix: str = "_openai_sketch",
    fixed_prompt: str | None = None,
    prompt_template: str = DEFAULT_PROMPT_TEMPLATE,
    sun_events: list[str] | None = None,
    model: str = DEFAULT_MODEL,
    size: str = "1024x1024",
    quality: str = "high",
    input_fidelity: str = "high",
    output_format: str = "png",
    output_compression: int = 90,
    timeout: float = 240.0,
    api_key: str | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    outdir.mkdir(parents=True, exist_ok=True)
    resolved_events = _resolve_sun_events(input_paths, sun_events)
    results: list[dict[str, Any]] = []

    for input_path, sun_event in zip(input_paths, resolved_events):
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        step1_prompt = _prompt_for_image(
            fixed_prompt=None,
            prompt_template=DEFAULT_STEP1_PROMPT_TEMPLATE,
            sun_event=sun_event,
        )
        step2_prompt = _prompt_for_image(
            fixed_prompt=fixed_prompt,
            prompt_template=prompt_template,
            sun_event=sun_event,
        )

        ext = ".png" if output_format == "png" else f".{output_format}"
        output_path = outdir / f"{input_path.stem}{suffix}{ext}"
        step1_path = outdir / f"{input_path.stem}{suffix}_step1{ext}"
        meta_path = outdir / f"{input_path.stem}{suffix}_meta.json"

        if dry_run:
            shutil.copyfile(input_path, step1_path)
            shutil.copyfile(step1_path, output_path)
            payload_step1: dict[str, Any] = {"dry_run": True}
            payload_step2: dict[str, Any] = {"dry_run": True}
        else:
            step1_bytes, payload_step1 = edit_image_openai(
                image_path=input_path,
                api_key=api_key or "",
                prompt=step1_prompt,
                model=model,
                size=size,
                quality=quality,
                input_fidelity=input_fidelity,
                output_format=output_format,
                output_compression=output_compression,
                timeout=timeout,
            )
            step1_path.write_bytes(step1_bytes)

            final_bytes, payload_step2 = edit_image_openai(
                image_path=step1_path,
                api_key=api_key or "",
                prompt=step2_prompt,
                model=model,
                size=size,
                quality=quality,
                input_fidelity=input_fidelity,
                output_format=output_format,
                output_compression=output_compression,
                timeout=timeout,
            )
            output_path.write_bytes(final_bytes)

        meta = {
            "input_path": str(input_path),
            "step1_output_path": str(step1_path),
            "output_path": str(output_path),
            "metadata_path": str(meta_path),
            "sun_event": sun_event,
            "step1_prompt_template": DEFAULT_STEP1_PROMPT_TEMPLATE,
            "step1_prompt": step1_prompt,
            "step2_prompt": step2_prompt,
            "step2_prompt_template": prompt_template,
            "model": model,
            "size": size,
            "quality": quality,
            "input_fidelity": input_fidelity,
            "output_format": output_format,
            "dry_run": bool(dry_run),
            "openai_response_step1": _summarize_openai_response(payload_step1),
            "openai_response_step2": _summarize_openai_response(payload_step2),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] step1: {step1_path}")
        print(f"[OK] transformed: {output_path}")
        print(f"[OK] metadata: {meta_path}")
        results.append(meta)

    return results


def main() -> None:
    args = _build_parser().parse_args()

    _load_env_file([Path("HW3/.env"), Path(".env")])
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    if not args.dry_run and not api_key:
        raise RuntimeError(
            "Missing OpenAI key. Set OPENAI_API_KEY in HW3/.env or pass --api-key."
        )

    input_paths = [Path(raw_input) for raw_input in args.input]
    transform_images(
        input_paths=input_paths,
        outdir=Path(args.outdir),
        suffix=args.suffix,
        fixed_prompt=args.prompt,
        prompt_template=args.prompt_template,
        sun_events=args.sun_events,
        model=args.model,
        size=args.size,
        quality=args.quality,
        input_fidelity=args.input_fidelity,
        output_format=args.output_format,
        output_compression=args.output_compression,
        timeout=args.timeout,
        api_key=api_key,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
