#!/usr/bin/env python3
"""
Evaluation scaffold for image generation quality.

Usage examples:
  python scripts/evaluate.py \
    --reference-dir /data/eval/ref \
    --generated-dir /data/eval/gen \
    --metrics ssim lpips fid kid \
    --output /data/eval/report.json

  # Only validate file pairing and dataset layout
  python scripts/evaluate.py --reference-dir ./ref --generated-dir ./gen --dry-run

Notes:
- This file is intentionally a scaffold.
- Fill in metric implementations in:
  - metric_ssim
  - metric_lpips
  - metric_fid
  - metric_kid
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
PAIRWISE_METRICS = {"ssim", "lpips"}
DISTRIBUTION_METRICS = {"fid", "kid"}
ALL_METRICS = ["ssim", "lpips", "fid", "kid"]


@dataclass(frozen=True)
class ImagePair:
    reference: Path
    generated: Path


@dataclass
class EvalConfig:
    reference_dir: str
    generated_dir: str
    metrics: list[str]
    image_size: int | None
    batch_size: int
    device: str
    strict_pairing: bool


@dataclass
class EvalReport:
    config: EvalConfig
    reference_count: int
    generated_count: int
    paired_count: int
    metrics: dict[str, float | None]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluation scaffold for generated images.")
    parser.add_argument("--reference-dir", type=Path, required=True, help="Directory containing GT/reference images.")
    parser.add_argument("--generated-dir", type=Path, required=True, help="Directory containing generated images.")
    parser.add_argument(
        "--metrics",
        nargs="+",
        choices=ALL_METRICS,
        default=ALL_METRICS,
        help="Metrics to compute.",
    )
    parser.add_argument("--image-size", type=int, default=None, help="Optional resize size, e.g. 512/768.")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size for metric computation.")
    parser.add_argument("--device", type=str, default="cuda", help="Device, e.g. cuda/cpu.")
    parser.add_argument(
        "--strict-pairing",
        action="store_true",
        help="Require reference/generated filename sets to be identical.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Output report JSON path.")
    parser.add_argument("--dry-run", action="store_true", help="Only validate dataset layout and pairing.")
    return parser.parse_args()


def list_images(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Directory not found: {root}")
    files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
    files.sort()
    return files


def filename_index(paths: Iterable[Path]) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for p in paths:
        key = p.name
        if key in index:
            raise ValueError(f"Duplicate filename found (must be unique): {key}")
        index[key] = p
    return index


def build_pairs(ref_paths: list[Path], gen_paths: list[Path], strict: bool) -> list[ImagePair]:
    ref_index = filename_index(ref_paths)
    gen_index = filename_index(gen_paths)

    ref_names = set(ref_index.keys())
    gen_names = set(gen_index.keys())

    if strict and ref_names != gen_names:
        missing_in_generated = sorted(ref_names - gen_names)
        missing_in_reference = sorted(gen_names - ref_names)
        raise ValueError(
            "Strict pairing failed. "
            f"Missing in generated: {missing_in_generated[:10]} "
            f"Missing in reference: {missing_in_reference[:10]}"
        )

    matched = sorted(ref_names & gen_names)
    return [ImagePair(reference=ref_index[name], generated=gen_index[name]) for name in matched]


def metric_ssim(pairs: list[ImagePair], image_size: int | None, batch_size: int, device: str) -> float:
    """
    TODO:
    - Implement SSIM (higher is better).
    - Typical: mean SSIM over paired images.
    - Input: pairs (reference/generated), optional resize/image preprocessing.
    """
    raise NotImplementedError("Implement metric_ssim().")


def metric_lpips(pairs: list[ImagePair], image_size: int | None, batch_size: int, device: str) -> float:
    """
    TODO:
    - Implement LPIPS (lower is better).
    - Typical: mean LPIPS over paired images.
    """
    raise NotImplementedError("Implement metric_lpips().")


def metric_fid(
    reference_paths: list[Path],
    generated_paths: list[Path],
    image_size: int | None,
    batch_size: int,
    device: str,
) -> float:
    """
    TODO:
    - Implement FID (lower is better).
    - Dataset-level metric, not pairwise.
    """
    raise NotImplementedError("Implement metric_fid().")


def metric_kid(
    reference_paths: list[Path],
    generated_paths: list[Path],
    image_size: int | None,
    batch_size: int,
    device: str,
) -> float:
    """
    TODO:
    - Implement KID (lower is better).
    - Dataset-level metric, not pairwise.
    """
    raise NotImplementedError("Implement metric_kid().")


def main() -> int:
    args = parse_args()

    ref_paths = list_images(args.reference_dir)
    gen_paths = list_images(args.generated_dir)
    pairs = build_pairs(ref_paths=ref_paths, gen_paths=gen_paths, strict=args.strict_pairing)

    config = EvalConfig(
        reference_dir=str(args.reference_dir.resolve()),
        generated_dir=str(args.generated_dir.resolve()),
        metrics=list(args.metrics),
        image_size=args.image_size,
        batch_size=args.batch_size,
        device=args.device,
        strict_pairing=args.strict_pairing,
    )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "config": asdict(config),
                    "reference_count": len(ref_paths),
                    "generated_count": len(gen_paths),
                    "paired_count": len(pairs),
                    "status": "ok",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not pairs and any(m in PAIRWISE_METRICS for m in args.metrics):
        print("No paired files found for pairwise metrics.", file=sys.stderr)
        return 2

    metric_values: dict[str, float | None] = {m: None for m in args.metrics}

    for metric in args.metrics:
        if metric == "ssim":
            metric_values[metric] = metric_ssim(
                pairs=pairs,
                image_size=args.image_size,
                batch_size=args.batch_size,
                device=args.device,
            )
        elif metric == "lpips":
            metric_values[metric] = metric_lpips(
                pairs=pairs,
                image_size=args.image_size,
                batch_size=args.batch_size,
                device=args.device,
            )
        elif metric == "fid":
            metric_values[metric] = metric_fid(
                reference_paths=ref_paths,
                generated_paths=gen_paths,
                image_size=args.image_size,
                batch_size=args.batch_size,
                device=args.device,
            )
        elif metric == "kid":
            metric_values[metric] = metric_kid(
                reference_paths=ref_paths,
                generated_paths=gen_paths,
                image_size=args.image_size,
                batch_size=args.batch_size,
                device=args.device,
            )

    report = EvalReport(
        config=config,
        reference_count=len(ref_paths),
        generated_count=len(gen_paths),
        paired_count=len(pairs),
        metrics=metric_values,
    )

    report_json = json.dumps(asdict(report), ensure_ascii=False, indent=2)
    print(report_json)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report_json, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
