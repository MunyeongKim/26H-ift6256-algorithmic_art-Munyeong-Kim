#!/usr/bin/env python
"""Two-place pipeline: sketch base then sun overlay with multi-reference inputs."""

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
TARGET_RULE_PREFIX = (
    "중요 규칙: 첨부 이미지가 여러 장이면 반드시 첫 번째 이미지만 편집 대상이다. "
    "두 번째 이후 이미지는 스타일/조건 참조용이며, 구도/물체를 복사하지 마. "
    "출력 결과는 첫 번째 이미지와 동일한 장면이어야 한다. "
)

STEP1_FIRST_TEMPLATE = (
    "입력 이미지들과 레퍼런스를 참고해서 이 장면을 "
    "'단일 펜 미니멀 라인 스케치' 베이스로 생성해줘. "
    "검은 선+흰 배경의 흑백 스케치로만 만들고, 디테일은 단순화해줘. "
    "반드시 원본 사진의 구도/시점/원근/수평선/지형/건물 배치를 유지해줘. "
    "레퍼런스 이미지는 선 스타일(선 두께, 단순화, 질감)만 참고하고, "
    "레퍼런스의 구도나 물체 형태를 복사하지 마. "
    "이 단계는 순수 베이스 단계이므로 해/햇빛/색상은 넣지 말아줘."
)

STEP2_FIRST_TEMPLATE = (
    "이 이미지는 이미 완성된 흑백 스케치 베이스야. "
    "기존 검은 선, 구도, 물체 형태는 절대 바꾸지 말고 유지해줘. "
    "원본 사진과 레퍼런스(포항 스타일)를 참고해서 {sun_event} 연출의 해/햇빛만 빨간색으로 추가해줘. "
    "추가는 반드시 선 기반(펜 스트로크)으로만 하고, 면 채움/에어브러시/안개형 글로우/그라데이션은 금지. "
    "해의 중심 x 좌표는 화면 정중앙에 맞춰줘. "
    "해의 y 좌표는 가능한 한 지평선/수평선에 반쯤 걸치게 배치해줘. "
    "중앙 방향에 해가 들어갈 하늘 공간이 없으면 해 원판은 생략하고 "
    "붉은 선 해칭/짧은 선광/얇은 반사선만 추가해줘. "
    "다른 모든 색은 금지."
)

STEP1_SECOND_TEMPLATE = (
    "레퍼런스 이미지들과 이전에 만든 해 없는 스케치를 참고해서 "
    "현재 장면을 같은 스타일의 '단일 펜 미니멀 라인 스케치' 베이스로 만들어줘. "
    "검은 선+흰 배경의 흑백만 사용하고 디테일은 단순화해줘. "
    "반드시 현재 원본 사진의 구도/시점/원근/수평선/지형/건물 배치를 유지해줘. "
    "레퍼런스와 이전 스케치는 스타일 일치용으로만 참고하고, "
    "그들의 구도나 물체 배치를 복사하지 마. "
    "이 단계는 해/햇빛/색상 없이 순수 베이스만 생성해줘."
)

STEP2_SECOND_TEMPLATE = (
    "이 이미지는 둘째 장소의 흑백 스케치 베이스야. "
    "레퍼런스(포항 스타일), 첫 장소 스케치들, 원본 사진을 참고해서 "
    "첫 장소와 같은 방식으로 {sun_event} 해/햇빛만 빨간색으로 추가해줘. "
    "기존 검은 선, 구도, 물체 형태는 절대 바꾸지 말아줘. "
    "추가는 반드시 선 기반(펜 스트로크)으로만 하고, 면 채움/에어브러시/안개형 글로우/그라데이션은 금지. "
    "해의 중심 x 좌표는 화면 정중앙에 맞춰줘. "
    "해의 y 좌표는 가능한 한 지평선/수평선에 반쯤 걸치게 배치해줘. "
    "중앙 방향에 해가 들어갈 하늘 공간이 없으면 해 원판은 생략하고 "
    "붉은 선 해칭/짧은 선광/얇은 반사선만 추가해줘. "
    "다른 색은 절대 사용하지 마."
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
            msg = err.get("message")
            if isinstance(msg, str) and msg.strip():
                return msg
            return json.dumps(err, ensure_ascii=False)
        return json.dumps(payload, ensure_ascii=False)
    return str(payload)


def _decode_image_from_payload(payload: dict[str, Any]) -> bytes:
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError("OpenAI response missing data list.")
    item = data[0]
    if not isinstance(item, dict):
        raise RuntimeError("OpenAI response data item has unexpected type.")

    b64 = item.get("b64_json")
    if isinstance(b64, str) and b64:
        return base64.b64decode(b64)

    url = item.get("url")
    if isinstance(url, str) and url:
        resp = requests.get(url, timeout=180)
        if resp.status_code >= 400:
            raise RuntimeError(f"Image url download failed: HTTP {resp.status_code}")
        return resp.content

    raise RuntimeError("OpenAI response missing b64_json/url.")


def _summarize_openai_response(payload: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in ("created", "output_format", "quality", "size", "usage", "background"):
        if key in payload:
            summary[key] = payload[key]
    data = payload.get("data")
    if isinstance(data, list):
        items: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            current: dict[str, Any] = {}
            for k, v in item.items():
                if k == "b64_json" and isinstance(v, str):
                    current[k] = f"<omitted base64: {len(v)} chars>"
                else:
                    current[k] = v
            items.append(current)
        if items:
            summary["data"] = items
    return summary


def _event_ko(event: str) -> str:
    return {"sunrise": "일출", "sunset": "일몰"}.get(event.lower(), event)


def _fill(template: str, event: str) -> str:
    return template.replace("{sun_event}", _event_ko(event))


def _with_target_rule(prompt: str) -> str:
    return TARGET_RULE_PREFIX + prompt


def edit_images_openai(
    *,
    image_paths: list[Path],
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
    for path in image_paths:
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {path}")

    headers = {"Authorization": f"Bearer {api_key}"}
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
        files: list[tuple[str, tuple[str, bytes, str]]] = []
        for path in image_paths:
            files.append((image_field, (path.name, path.read_bytes(), _guess_mime(path))))

        response = requests.post(
            OPENAI_IMAGE_EDIT_URL,
            headers=headers,
            data=data,
            files=files,
            timeout=timeout,
        )
        if response.status_code < 400:
            payload = response.json()
            return _decode_image_from_payload(payload), payload
        last_error = f"HTTP {response.status_code} ({image_field}): {_extract_error_text(response)}"

    raise RuntimeError(f"OpenAI images edit failed: {last_error}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Multi-reference step1/step2 generation for two locations."
    )
    parser.add_argument(
        "--style-reference-step1",
        default="HW3/style_reference_oratory.png",
        help="Style reference image path for step1 base generation",
    )
    parser.add_argument(
        "--style-reference-step2",
        default="HW3/style_reference_pohang.png",
        help="Style reference image path for step2 sun overlay",
    )
    parser.add_argument("--input-first", required=True, help="First location original photo")
    parser.add_argument("--event-first", choices=["sunrise", "sunset"], default="sunrise", help="Sun event for first location")
    parser.add_argument("--input-second", required=True, help="Second location original photo")
    parser.add_argument("--event-second", choices=["sunrise", "sunset"], default="sunset", help="Sun event for second location")
    parser.add_argument("--outdir", default="HW3/streetview_outputs/pohang_montreal/openai_sketches", help="Output directory")
    parser.add_argument("--suffix", default="_openai", help="Suffix for output files")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI image model")
    parser.add_argument("--size", default="1024x1024", help="Output image size")
    parser.add_argument("--quality", default="high", help="Image quality")
    parser.add_argument("--input-fidelity", default="high", help="Input fidelity")
    parser.add_argument("--output-format", choices=["png", "jpeg", "webp"], default="png", help="Output format")
    parser.add_argument("--output-compression", type=int, default=90, help="jpeg/webp compression")
    parser.add_argument("--timeout", type=float, default=240.0, help="HTTP timeout seconds")
    parser.add_argument("--api-key", default=None, help="OPENAI_API_KEY override")
    parser.add_argument("--dry-run", action="store_true", help="Skip API and copy originals")
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    _load_env_file([Path("HW3/.env"), Path(".env")])
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    if not args.dry_run and not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY.")

    style_ref_step1 = Path(args.style_reference_step1)
    style_ref_step2 = Path(args.style_reference_step2)
    first_original = Path(args.input_first)
    second_original = Path(args.input_second)
    for path in (style_ref_step1, style_ref_step2, first_original, second_original):
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    ext = ".png" if args.output_format == "png" else f".{args.output_format}"
    first_step1 = outdir / f"{first_original.stem}{args.suffix}_step1{ext}"
    first_step2 = outdir / f"{first_original.stem}{args.suffix}{ext}"
    second_step1 = outdir / f"{second_original.stem}{args.suffix}_step1{ext}"
    second_step2 = outdir / f"{second_original.stem}{args.suffix}{ext}"
    meta_path = outdir / f"pipeline{args.suffix}_meta.json"

    meta: dict[str, Any] = {
        "style_reference_step1": str(style_ref_step1),
        "style_reference_step2": str(style_ref_step2),
        "first_original": str(first_original),
        "second_original": str(second_original),
        "event_first": args.event_first,
        "event_second": args.event_second,
        "model": args.model,
        "size": args.size,
        "quality": args.quality,
        "input_fidelity": args.input_fidelity,
        "output_format": args.output_format,
        "dry_run": bool(args.dry_run),
        "steps": [],
    }

    def run_step(
        *,
        name: str,
        inputs: list[Path],
        output: Path,
        prompt: str,
    ) -> None:
        if args.dry_run:
            shutil.copyfile(inputs[0], output)
            payload: dict[str, Any] = {"dry_run": True}
        else:
            output_bytes, payload = edit_images_openai(
                image_paths=inputs,
                api_key=api_key or "",
                prompt=prompt,
                model=args.model,
                size=args.size,
                quality=args.quality,
                input_fidelity=args.input_fidelity,
                output_format=args.output_format,
                output_compression=args.output_compression,
                timeout=args.timeout,
            )
            output.write_bytes(output_bytes)

        meta["steps"].append(
            {
                "name": name,
                "inputs": [str(p) for p in inputs],
                "output": str(output),
                "prompt": prompt,
                "openai_response": _summarize_openai_response(payload),
            }
        )
        print(f"[OK] {name}: {output}")

    run_step(
        name="step1_first_base",
        inputs=[first_original, style_ref_step1],
        output=first_step1,
        prompt=_with_target_rule(_fill(STEP1_FIRST_TEMPLATE, args.event_first)),
    )
    run_step(
        name="step2_first_sun_overlay",
        inputs=[first_step1, first_original, style_ref_step2],
        output=first_step2,
        prompt=_with_target_rule(_fill(STEP2_FIRST_TEMPLATE, args.event_first)),
    )
    run_step(
        name="step1_second_base",
        inputs=[second_original, first_step1, first_step2, style_ref_step1],
        output=second_step1,
        prompt=_with_target_rule(_fill(STEP1_SECOND_TEMPLATE, args.event_second)),
    )
    run_step(
        name="step2_second_sun_overlay",
        inputs=[second_step1, second_original, first_step2, first_step1, style_ref_step2],
        output=second_step2,
        prompt=_with_target_rule(_fill(STEP2_SECOND_TEMPLATE, args.event_second)),
    )

    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] meta: {meta_path}")


if __name__ == "__main__":
    main()
