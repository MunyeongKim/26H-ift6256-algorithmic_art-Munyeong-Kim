#!/usr/bin/env python
"""Place two images side-by-side (left then right), with optional scaling and labels."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DEFAULT_FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Juxtapose two images horizontally.")
    parser.add_argument("--left", required=True, help="Left image path")
    parser.add_argument("--right", required=True, help="Right image path")
    parser.add_argument("--output", required=True, help="Output image path")
    parser.add_argument("--gap", type=int, default=0, help="Gap width in pixels")
    parser.add_argument("--bg", default="white", help="Background color")
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Scale factor for each image before compose (e.g. 0.5 -> quarter area).",
    )
    parser.add_argument("--left-note", default=None, help="One-line note at bottom-right of left image")
    parser.add_argument("--right-note", default=None, help="One-line note at bottom-right of right image")
    parser.add_argument("--note-font", default=DEFAULT_FONT, help="Path to note font")
    parser.add_argument("--note-size", type=int, default=18, help="Note font size")
    parser.add_argument("--note-pad", type=int, default=12, help="Padding for note box")
    parser.add_argument(
        "--canvas-size",
        default=None,
        help="Optional final canvas size WxH (e.g. 2048x1024). Composed strip is centered.",
    )
    parser.add_argument(
        "--frame-ratio",
        type=float,
        default=1.0,
        help="Per-image frame size ratio (e.g. 1.41421356 for sqrt(2) white frame).",
    )
    parser.add_argument(
        "--image-border",
        type=int,
        default=0,
        help="Black border thickness around each image (pixels).",
    )
    parser.add_argument(
        "--outer-pad",
        type=int,
        default=0,
        help="Extra padding added around the final composed image.",
    )
    return parser


def _parse_size(value: str) -> tuple[int, int]:
    raw = value.lower().strip()
    if "x" not in raw:
        raise ValueError(f"Invalid size format: {value}")
    w_str, h_str = raw.split("x", 1)
    w = int(w_str)
    h = int(h_str)
    if w <= 0 or h <= 0:
        raise ValueError(f"Invalid size value: {value}")
    return w, h


def _annotate_bottom_right(
    img: Image.Image,
    text: str | None,
    *,
    font_path: str,
    font_size: int,
    pad: int,
    anchor_right: int | None = None,
    anchor_bottom: int | None = None,
) -> Image.Image:
    if not text:
        return img

    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.multiline_textbbox((0, 0), text, font=font, align="right")
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (anchor_right - text_w) if anchor_right is not None else (img.width - text_w - pad)
    y = (anchor_bottom + pad) if anchor_bottom is not None else (img.height - text_h - pad)
    x = max(pad, x)
    y = max(pad, y)
    draw.multiline_text((x, y), text, fill=(0, 0, 0), font=font, align="right")
    return img


def _frame_image(
    img: Image.Image,
    *,
    frame_ratio: float,
    border_px: int,
    frame_bg: str,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    ratio = max(1.0, frame_ratio)
    fw = max(img.width, int(round(img.width * ratio)))
    fh = max(img.height, int(round(img.height * ratio)))

    framed = Image.new("RGB", (fw, fh), color=frame_bg)
    x = (fw - img.width) // 2
    y = (fh - img.height) // 2
    framed.paste(img, (x, y))

    if border_px > 0:
        draw = ImageDraw.Draw(framed)
        for i in range(border_px):
            draw.rectangle(
                (x - i, y - i, x + img.width - 1 + i, y + img.height - 1 + i),
                outline=(0, 0, 0),
            )
    return framed, (x, y, img.width, img.height)


def main() -> None:
    args = _build_parser().parse_args()
    left_path = Path(args.left)
    right_path = Path(args.right)
    output_path = Path(args.output)

    left = Image.open(left_path).convert("RGB")
    right = Image.open(right_path).convert("RGB")

    scale = max(0.05, float(args.scale))
    if scale != 1.0:
        left = left.resize(
            (max(1, round(left.width * scale)), max(1, round(left.height * scale))),
            Image.LANCZOS,
        )
        right = right.resize(
            (max(1, round(right.width * scale)), max(1, round(right.height * scale))),
            Image.LANCZOS,
        )

    target_h = max(left.height, right.height)
    if left.height != target_h:
        left = left.resize((round(left.width * target_h / left.height), target_h), Image.LANCZOS)
    if right.height != target_h:
        right = right.resize((round(right.width * target_h / right.height), target_h), Image.LANCZOS)

    left, left_inner = _frame_image(
        left,
        frame_ratio=float(args.frame_ratio),
        border_px=max(0, int(args.image_border)),
        frame_bg=args.bg,
    )
    right, right_inner = _frame_image(
        right,
        frame_ratio=float(args.frame_ratio),
        border_px=max(0, int(args.image_border)),
        frame_bg=args.bg,
    )
    left = _annotate_bottom_right(
        left,
        args.left_note,
        font_path=args.note_font,
        font_size=args.note_size,
        pad=max(4, args.note_pad),
        anchor_right=left_inner[0] + left_inner[2],
        anchor_bottom=left_inner[1] + left_inner[3],
    )
    right = _annotate_bottom_right(
        right,
        args.right_note,
        font_path=args.note_font,
        font_size=args.note_size,
        pad=max(4, args.note_pad),
        anchor_right=right_inner[0] + right_inner[2],
        anchor_bottom=right_inner[1] + right_inner[3],
    )

    gap = max(0, args.gap)
    target_h = max(left.height, right.height)
    canvas_w = left.width + gap + right.width
    strip = Image.new("RGB", (canvas_w, target_h), color=args.bg)
    strip.paste(left, (0, 0))
    strip.paste(right, (left.width + gap, 0))

    if args.canvas_size:
        final_w, final_h = _parse_size(args.canvas_size)
        if final_w < strip.width or final_h < strip.height:
            raise ValueError(
                f"canvas-size {final_w}x{final_h} is smaller than composed content {strip.width}x{strip.height}"
            )
        canvas = Image.new("RGB", (final_w, final_h), color=args.bg)
        x = (final_w - strip.width) // 2
        y = (final_h - strip.height) // 2
        canvas.paste(strip, (x, y))
    else:
        canvas = strip

    outer_pad = max(0, int(args.outer_pad))
    if outer_pad > 0:
        padded = Image.new(
            "RGB",
            (canvas.width + outer_pad * 2, canvas.height + outer_pad * 2),
            color=args.bg,
        )
        padded.paste(canvas, (outer_pad, outer_pad))
        canvas = padded

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    print(f"[OK] saved: {output_path} ({canvas.width}x{canvas.height})")


if __name__ == "__main__":
    main()
