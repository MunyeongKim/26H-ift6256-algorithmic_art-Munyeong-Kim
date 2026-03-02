#!/usr/bin/env python
"""Create a croquis-like sketch by combining soft lines and preserved tone."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, sobel

from xdog_pen_illustration import to_grayscale_array, xdog


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert an image to a croquis-like grayscale sketch."
    )
    parser.add_argument("-i", "--input", required=True, help="Input image path.")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output image path (default: <input_stem>_croquis.png).",
    )

    parser.add_argument(
        "--line-blur",
        type=float,
        default=0.8,
        help="Pre-blur for gradient-based line extraction.",
    )
    parser.add_argument(
        "--line-gain",
        type=float,
        default=1.5,
        help="Line strength from gradient edges.",
    )
    parser.add_argument(
        "--line-mix",
        type=float,
        default=0.55,
        help="Mix ratio of gradient lines vs XDoG lines (0~1).",
    )

    parser.add_argument(
        "--tone-sigma",
        type=float,
        default=1.4,
        help="Blur for soft tone preservation.",
    )
    parser.add_argument(
        "--tone-gamma",
        type=float,
        default=1.15,
        help="Gamma for tone darkening (>1 darkens mid-tones).",
    )
    parser.add_argument(
        "--blend",
        type=float,
        default=0.45,
        help="Blend amount for stylized sketch over original luminance (0~1).",
    )
    return parser.parse_args()


def gradient_line_map(gray: np.ndarray, blur_sigma: float, gain: float) -> np.ndarray:
    base = gaussian_filter(gray, blur_sigma)
    gx = sobel(base, axis=1, mode="reflect")
    gy = sobel(base, axis=0, mode="reflect")
    grad = np.hypot(gx, gy)
    scale = np.percentile(grad, 99.5) + 1e-8
    grad = np.clip(grad / scale, 0.0, 1.0)
    return 1.0 - np.clip(grad * gain, 0.0, 1.0)


def tone_map(gray: np.ndarray, sigma: float, gamma: float) -> np.ndarray:
    soft = gaussian_filter(gray, sigma)
    tone = np.clip(0.7 * gray + 0.3 * soft, 0.0, 1.0)
    return np.clip(tone, 0.0, 1.0) ** gamma


def save_grayscale(arr: np.ndarray, output_path: Path) -> None:
    out = (np.clip(arr, 0.0, 1.0) * 255.0).astype(np.uint8)
    Image.fromarray(out, mode="L").save(output_path)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_name(f"{input_path.stem}_croquis.png")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    gray = to_grayscale_array(input_path)
    grad_lines = gradient_line_map(gray, args.line_blur, args.line_gain)
    xdog_lines = xdog(
        gray,
        sigma=1.0,
        k=1.6,
        tau=0.98,
        epsilon=0.0,
        phi=10.0,
        smooth_sigma=1.2,
    )
    lines = np.clip(
        (1.0 - args.line_mix) * xdog_lines + args.line_mix * grad_lines, 0.0, 1.0
    )
    tone = tone_map(gray, sigma=args.tone_sigma, gamma=args.tone_gamma)

    blend = np.clip(args.blend, 0.0, 1.0)
    sketch = np.clip((1.0 - blend) * gray + blend * (tone * lines), 0.0, 1.0)
    save_grayscale(sketch, output_path)

    print(f"Saved croquis sketch: {output_path}")
    print(
        "Params:"
        f" line_blur={args.line_blur}, line_gain={args.line_gain},"
        f" line_mix={args.line_mix}, tone_sigma={args.tone_sigma},"
        f" tone_gamma={args.tone_gamma}, blend={args.blend}"
    )


if __name__ == "__main__":
    main()
