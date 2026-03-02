#!/usr/bin/env python
"""Apply XDoG (eXtended Difference of Gaussians) pen-illustration stylization."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert an image to pen-illustration style with XDoG."
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input image path.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output image path (default: <input_stem>_xdog.png).",
    )
    parser.add_argument(
        "--sigma",
        type=float,
        default=0.8,
        help="Base Gaussian sigma.",
    )
    parser.add_argument(
        "--k",
        type=float,
        default=1.6,
        help="Multiplier for second Gaussian sigma.",
    )
    parser.add_argument(
        "--tau",
        type=float,
        default=0.98,
        help="Second Gaussian weight in DoG.",
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=0.01,
        help="XDoG threshold.",
    )
    parser.add_argument(
        "--phi",
        type=float,
        default=20.0,
        help="Steepness for soft-threshold transition.",
    )
    parser.add_argument(
        "--smooth-sigma",
        type=float,
        default=0.7,
        help="Optional pre-smoothing sigma to reduce texture noise.",
    )
    return parser.parse_args()


def to_grayscale_array(image_path: Path) -> np.ndarray:
    image = Image.open(image_path).convert("L")
    arr = np.asarray(image, dtype=np.float32) / 255.0
    return arr


def xdog(
    gray: np.ndarray,
    sigma: float,
    k: float,
    tau: float,
    epsilon: float,
    phi: float,
    smooth_sigma: float,
) -> np.ndarray:
    if smooth_sigma > 0:
        gray = gaussian_filter(gray, smooth_sigma)

    g1 = gaussian_filter(gray, sigma=sigma)
    g2 = gaussian_filter(gray, sigma=sigma * k)
    dog = g1 - tau * g2

    stylized = np.where(dog >= epsilon, 1.0, 1.0 + np.tanh(phi * (dog - epsilon)))
    return np.clip(stylized, 0.0, 1.0)


def save_grayscale(arr: np.ndarray, output_path: Path) -> None:
    out = (arr * 255.0).astype(np.uint8)
    Image.fromarray(out, mode="L").save(output_path)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_name(f"{input_path.stem}_xdog.png")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    gray = to_grayscale_array(input_path)
    stylized = xdog(
        gray=gray,
        sigma=args.sigma,
        k=args.k,
        tau=args.tau,
        epsilon=args.epsilon,
        phi=args.phi,
        smooth_sigma=args.smooth_sigma,
    )
    save_grayscale(stylized, output_path)

    print(f"Saved XDoG output: {output_path}")
    print(
        "Params:"
        f" sigma={args.sigma}, k={args.k}, tau={args.tau},"
        f" epsilon={args.epsilon}, phi={args.phi}, smooth_sigma={args.smooth_sigma}"
    )


if __name__ == "__main__":
    main()
