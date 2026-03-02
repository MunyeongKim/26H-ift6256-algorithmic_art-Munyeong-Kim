#!/usr/bin/env python
"""Place two images side-by-side (left then right)."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Juxtapose two images horizontally.")
    parser.add_argument("--left", required=True, help="Left image path")
    parser.add_argument("--right", required=True, help="Right image path")
    parser.add_argument("--output", required=True, help="Output image path")
    parser.add_argument("--gap", type=int, default=0, help="Gap width in pixels")
    parser.add_argument("--bg", default="white", help="Background color")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    left_path = Path(args.left)
    right_path = Path(args.right)
    output_path = Path(args.output)

    left = Image.open(left_path).convert("RGB")
    right = Image.open(right_path).convert("RGB")

    target_h = max(left.height, right.height)
    if left.height != target_h:
        left = left.resize((round(left.width * target_h / left.height), target_h), Image.LANCZOS)
    if right.height != target_h:
        right = right.resize((round(right.width * target_h / right.height), target_h), Image.LANCZOS)

    gap = max(0, args.gap)
    canvas_w = left.width + gap + right.width
    canvas = Image.new("RGB", (canvas_w, target_h), color=args.bg)
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left.width + gap, 0))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    print(f"[OK] saved: {output_path} ({canvas.width}x{canvas.height})")


if __name__ == "__main__":
    main()
