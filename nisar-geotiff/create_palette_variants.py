#!/usr/bin/env python3
"""Create NISAR RGB palette previews by varying per-channel gamma."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Sequence

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window

from nisar_to_geotiff import BLOCK_SIZE, _lua_string, _write_global_vrt
from create_color_variants import _date_and_resolution


PALETTE_PRESETS: tuple[
    tuple[str, float, float, tuple[float, float, float]], ...
] = (
    ("portal-balanced", 2.0, 98.0, (0.55, 0.55, 0.55)),
    ("portal-soft", 1.0, 99.0, (0.65, 0.65, 0.65)),
    ("portal-pale", 1.0, 90.0, (0.60, 0.60, 0.60)),
    ("portal-high-key", 0.5, 85.0, (0.70, 0.70, 0.70)),
    ("portal-detail", 3.0, 99.0, (0.50, 0.50, 0.50)),
    ("portal-mint", 2.0, 98.0, (0.60, 0.48, 0.60)),
    ("portal-magenta", 2.0, 98.0, (0.48, 0.60, 0.48)),
    ("portal-green-detail", 1.0, 95.0, (0.70, 0.50, 0.70)),
    ("portal-pink-detail", 1.0, 95.0, (0.50, 0.70, 0.50)),
    ("portal-neutral-detail", 1.0, 95.0, (0.65, 0.65, 0.65)),
)
PORTAL_HUE_ROTATION = 60.0
PORTAL_SATURATION = 0.30


def _write_info(
    info_path: Path,
    vrt_path: Path,
    date: str,
    resolution: str,
    preset_name: str,
    low_percentile: float,
    high_percentile: float,
    stretch_bounds: tuple[tuple[int, int], tuple[int, int], tuple[int, int]],
    gamma: tuple[float, float, float],
    stretch_source_names: Sequence[str] = (),
) -> None:
    gamma_text = ", ".join(f"{value:g}" for value in gamma)
    bounds_text = ", ".join(f"{low}-{high}" for low, high in stretch_bounds)
    sources_text = (
        f" of the combined stretch sources ({', '.join(stretch_source_names)})"
        if stretch_source_names
        else ""
    )
    name_suffix = ", shared stretch" if stretch_source_names else ""
    description = (
        f"Maps HH, HV, and HH/HV ratio to the starting RGB channels, applies "
        f"gamma values ({gamma_text}) after independently stretching each "
        f"channel between "
        f"the {low_percentile:g}th and {high_percentile:g}th valid-pixel "
        f"percentiles{sources_text} (byte bounds: {bounds_text}), then rotates "
        f"hue by {PORTAL_HUE_ROTATION:g} degrees at {PORTAL_SATURATION:.0%} "
        "saturation."
    )
    contents = "\n".join(
        (
            f"Name = {_lua_string(f'NISAR {date} ({resolution}) - {preset_name}{name_suffix}')}",
            f"Identifier = {_lua_string('NISAR_' + date.replace('-', '') + '_' + info_path.stem)}",
            f"Description = {_lua_string(description)}",
            f"ColorFile = {_lua_string(vrt_path.name)}",
            'BlendMode = "Normal"',
            "",
        )
    )
    temporary = info_path.with_name(f"{info_path.name}.tmp")
    temporary.write_text(contents, encoding="utf-8")
    os.replace(temporary, info_path)


def _percentile_bound(histogram: np.ndarray, percentile: float) -> int:
    count = int(histogram.sum())
    rank = int(round((count - 1) * percentile / 100.0))
    return int(np.searchsorted(np.cumsum(histogram), rank + 1))


def _stretch_bounds(
    histograms: np.ndarray, low_percentile: float, high_percentile: float
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    if not 0 <= low_percentile < high_percentile <= 100:
        raise ValueError("Stretch percentiles must satisfy 0 <= low < high <= 100")
    bounds = [
        (
            _percentile_bound(histograms[channel], low_percentile),
            _percentile_bound(histograms[channel], high_percentile),
        )
        for channel in range(3)
    ]
    return bounds[0], bounds[1], bounds[2]


def _apply_palette(
    rgb: np.ndarray,
    stretch_bounds: tuple[tuple[int, int], tuple[int, int], tuple[int, int]],
    gamma: tuple[float, float, float],
) -> np.ndarray:
    corrected = np.empty_like(rgb)
    for channel, (low, high) in enumerate(stretch_bounds):
        if high <= low:
            corrected[channel] = 0
            continue
        normalized = np.clip(
            (rgb[channel].astype(np.float32) - low) / (high - low),
            0.0,
            1.0,
        )
        exponent = gamma[channel]
        corrected[channel] = np.rint(
            np.power(normalized, exponent) * 255.0
        ).astype(np.uint8)
    return corrected


def _rotate_hue(
    rgb: np.ndarray, degrees: float, saturation: float
) -> np.ndarray:
    normalized = rgb.astype(np.float32) / 255.0
    maximum = normalized.max(axis=0)
    minimum = normalized.min(axis=0)
    delta = maximum - minimum
    red, green, blue = normalized
    hue = np.zeros_like(maximum)
    non_gray = delta > 0
    red_max = non_gray & (red == maximum)
    green_max = non_gray & (green == maximum)
    blue_max = non_gray & (blue == maximum)
    hue[red_max] = ((green[red_max] - blue[red_max]) / delta[red_max]) % 6
    hue[green_max] = (
        (blue[green_max] - red[green_max]) / delta[green_max] + 2
    )
    hue[blue_max] = (
        (red[blue_max] - green[blue_max]) / delta[blue_max] + 4
    )
    hue = (hue * 60 + degrees) % 360
    chroma = delta
    second_component = chroma * (1 - np.abs((hue / 60) % 2 - 1))
    sector = (hue // 60).astype(np.int8)
    red_component = np.choose(
        sector, (chroma, second_component, 0, 0, second_component, chroma)
    )
    green_component = np.choose(
        sector, (second_component, chroma, chroma, second_component, 0, 0)
    )
    blue_component = np.choose(
        sector, (0, 0, second_component, chroma, chroma, second_component)
    )
    rotated = np.stack((red_component, green_component, blue_component))
    rotated += minimum[None, :, :]
    luminance = (
        0.2126 * rotated[0] + 0.7152 * rotated[1] + 0.0722 * rotated[2]
    )
    rotated = luminance[None, :, :] + (
        rotated - luminance[None, :, :]
    ) * saturation
    return np.rint(np.clip(rotated, 0.0, 1.0) * 255.0).astype(np.uint8)


def _scene_label(path: Path) -> str:
    """Return cycle, track, direction, and start time from a NISAR filename."""
    match = re.search(
        r"_(\d{3})_(\d{3})_([AD])_\d{3}_.*?_(\d{8}T\d{6})_", path.name
    )
    if match is None:
        return path.stem
    return "_".join(match.groups())


def _valid_histograms(path: Path) -> np.ndarray:
    """Count RGB byte values over the valid (nonzero-alpha) pixels of a GeoTIFF."""
    histograms = np.zeros((3, 256), dtype=np.int64)
    with rasterio.Env(GDAL_NUM_THREADS="ALL_CPUS"), rasterio.open(path) as source:
        if source.count != 4 or source.colorinterp[3].name != "alpha":
            raise ValueError(f"Stretch source must be a four-band RGBA GeoTIFF: {path}")
        # Read full-width strips so GDAL decodes their blocks in parallel.
        for row in range(0, source.height, BLOCK_SIZE):
            height = min(BLOCK_SIZE, source.height - row)
            window = Window(0, row, source.width, height)
            rgba = source.read(indexes=(1, 2, 3, 4), window=window)
            valid = rgba[3] > 0
            for channel in range(3):
                histograms[channel] += np.bincount(
                    rgba[channel][valid], minlength=256
                )
    return histograms


def _palette_lookup(
    stretch_bounds: tuple[tuple[int, int], tuple[int, int], tuple[int, int]],
    gamma: tuple[float, float, float],
) -> np.ndarray:
    """Tabulate the palette for every 24-bit RGB input, as a (3, 2**24) array."""
    lookup = np.empty((3, 1 << 24), dtype=np.uint8)
    chunk = 1 << 20
    for start in range(0, 1 << 24, chunk):
        codes = np.arange(start, start + chunk, dtype=np.uint32)
        rgb = np.stack(
            ((codes >> 16) & 255, (codes >> 8) & 255, codes & 255)
        ).astype(np.uint8)[:, None, :]
        lookup[:, start : start + chunk] = _rotate_hue(
            _apply_palette(rgb, stretch_bounds, gamma),
            PORTAL_HUE_ROTATION,
            PORTAL_SATURATION,
        )[:, 0, :]
    return lookup


def _rgb_codes(rgb: np.ndarray) -> np.ndarray:
    return (
        (rgb[0].astype(np.uint32) << 16)
        | (rgb[1].astype(np.uint32) << 8)
        | rgb[2]
    )


def create_palette_variants(
    input_path: Path,
    output_directory: Path,
    overwrite: bool = False,
    preset_names: Sequence[str] | None = None,
    stretch_sources: Sequence[Path] | None = None,
) -> list[Path]:
    input_path = input_path.expanduser().resolve()
    output_directory = output_directory.expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input GeoTIFF does not exist: {input_path}")
    # Percentile bounds come from the combined histogram of these rasters, so
    # scenes rendered with the same stretch sources share identical bounds.
    stretch_paths = [
        path.expanduser().resolve() for path in (stretch_sources or [input_path])
    ]
    for path in stretch_paths:
        if not path.is_file():
            raise FileNotFoundError(f"Stretch source GeoTIFF does not exist: {path}")

    date, resolution = _date_and_resolution(input_path)
    requested_presets = set(preset_names) if preset_names is not None else None
    unknown_presets = (
        requested_presets
        - {preset_name for preset_name, _, _, _ in PALETTE_PRESETS}
        if requested_presets is not None
        else set()
    )
    if unknown_presets:
        raise ValueError(
            "Unknown palette preset(s): " + ", ".join(sorted(unknown_presets))
        )
    presets = [
        preset
        for preset in PALETTE_PRESETS
        if requested_presets is None or preset[0] in requested_presets
    ]
    if not presets:
        raise ValueError("At least one palette preset must be selected")
    resolution_suffix = f"{resolution.rstrip('%')}pct"
    scene = _scene_label(input_path)
    stretch_suffix = "_shared-stretch" if stretch_sources else ""
    outputs = [
        output_directory
        / f"nisar_{scene}_{preset_name}{stretch_suffix}_{resolution_suffix}.tif"
        for preset_name, _, _, _ in presets
    ]
    sidecars = [
        path
        for output in outputs
        for path in (output, output.with_suffix(".vrt"), output.with_suffix(".info"))
    ]
    existing = [path for path in sidecars if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "Refusing to overwrite existing palette variants (use --overwrite): "
            + ", ".join(str(path) for path in existing)
        )

    output_directory.mkdir(parents=True, exist_ok=True)
    temporary_outputs = [
        output.with_name(f"{output.stem}.tmp{output.suffix}") for output in outputs
    ]
    preset_bounds: dict[
        str, tuple[tuple[int, int], tuple[int, int], tuple[int, int]]
    ] = {}
    try:
        with rasterio.Env(GDAL_NUM_THREADS="ALL_CPUS"), rasterio.open(
            input_path
        ) as source:
            if source.count != 4 or source.colorinterp[3].name != "alpha":
                raise ValueError("Input must be a four-band RGBA GeoTIFF")
            if source.crs != rasterio.crs.CRS.from_epsg(4326):
                raise ValueError("Input GeoTIFF must use EPSG:4326")

            profile = source.profile.copy()
            profile.update(
                driver="GTiff",
                count=4,
                dtype="uint8",
                nodata=None,
                tiled=True,
                blockxsize=BLOCK_SIZE,
                blockysize=BLOCK_SIZE,
                compress="deflate",
                predictor=2,
                bigtiff="IF_SAFER",
            )

            histograms = sum(_valid_histograms(path) for path in stretch_paths)

            for preset_name, low_pct, high_pct, _ in presets:
                preset_bounds[preset_name] = _stretch_bounds(
                    histograms, low_pct, high_pct
                )

            writers = []
            try:
                for temporary, (preset_name, low_pct, high_pct, gamma) in zip(
                    temporary_outputs, presets
                ):
                    writer = rasterio.open(temporary, "w", **profile)
                    writer.colorinterp = source.colorinterp
                    writer.set_band_description(1, f"HH backscatter, gamma {gamma[0]:g}")
                    writer.set_band_description(2, f"HV backscatter, gamma {gamma[1]:g}")
                    writer.set_band_description(3, f"HH/HV ratio, gamma {gamma[2]:g}")
                    writer.set_band_description(4, "Valid-data alpha")
                    writer.update_tags(
                        palette_preset=preset_name,
                        gamma_rgb=",".join(f"{value:g}" for value in gamma),
                        hue_rotation_degrees=f"{PORTAL_HUE_ROTATION:g}",
                        saturation=f"{PORTAL_SATURATION:g}",
                        stretch_percentiles=f"{low_pct:g},{high_pct:g}",
                        stretch_sources=";".join(path.name for path in stretch_paths),
                        stretch_bounds_rgb=";".join(
                            f"{low}-{high}"
                            for low, high in preset_bounds[preset_name]
                        ),
                    )
                    writers.append(writer)

                lookups = [
                    _palette_lookup(preset_bounds[preset_name], gamma)
                    for preset_name, _, _, gamma in presets
                ]
                for row in range(0, source.height, BLOCK_SIZE):
                    height = min(BLOCK_SIZE, source.height - row)
                    window = Window(0, row, source.width, height)
                    rgba = source.read(indexes=(1, 2, 3, 4), window=window)
                    codes = _rgb_codes(rgba[:3])
                    for writer, lookup in zip(writers, lookups):
                        adjusted = rgba.copy()
                        adjusted[:3] = lookup[:, codes]
                        writer.write(adjusted, window=window)
            finally:
                for writer in writers:
                    writer.close()

        for temporary, output in zip(temporary_outputs, outputs):
            os.replace(temporary, output)
        for output in outputs:
            with rasterio.Env(GDAL_NUM_THREADS="ALL_CPUS"), rasterio.open(
                output, "r+"
            ) as dataset:
                factors = [
                    factor
                    for factor in (2, 4, 8, 16, 32, 64)
                    if dataset.width // factor > 1
                    and dataset.height // factor > 1
                ]
                if factors:
                    dataset.build_overviews(factors, Resampling.average)
                    dataset.update_tags(ns="rio_overview", resampling="average")
    except Exception:
        for temporary in temporary_outputs:
            if temporary.exists():
                temporary.unlink()
        raise

    for output, (preset_name, low_pct, high_pct, gamma) in zip(outputs, presets):
        vrt_path = output.with_suffix(".vrt")
        _write_global_vrt(output, vrt_path)
        _write_info(
            output.with_suffix(".info"),
            vrt_path,
            date,
            resolution,
            preset_name,
            low_pct,
            high_pct,
            preset_bounds[preset_name],
            gamma,
            [path.name for path in stretch_paths] if stretch_sources else (),
        )

    return outputs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create ten HH-red/HV-green/ratio-blue palette previews from an "
            "existing RGB GeoTIFF."
        )
    )
    parser.add_argument("input", type=Path, help="Existing RGBA GeoTIFF")
    parser.add_argument("output_directory", type=Path, help="Palette output folder")
    parser.add_argument(
        "--overwrite", action="store_true", help="Replace existing palette files"
    )
    parser.add_argument(
        "--preset",
        action="append",
        choices=[preset_name for preset_name, _, _, _ in PALETTE_PRESETS],
        help="Generate only this preset; may be supplied more than once",
    )
    parser.add_argument(
        "--stretch-from",
        action="append",
        type=Path,
        metavar="GEOTIFF",
        help=(
            "Compute stretch percentiles from the combined histogram of these "
            "RGBA GeoTIFFs instead of the input; may be supplied more than once. "
            "Use the same list for several scenes to give them matching stretches."
        ),
    )
    args = parser.parse_args(argv)
    try:
        outputs = create_palette_variants(
            args.input,
            args.output_directory,
            overwrite=args.overwrite,
            preset_names=args.preset,
            stretch_sources=args.stretch_from,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as error:
        parser.error(str(error))

    for output in outputs:
        print(f"GeoTIFF: {output}")
        print(f"OpenSpace VRT: {output.with_suffix('.vrt')}")
        print(f"OpenSpace info: {output.with_suffix('.info')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
