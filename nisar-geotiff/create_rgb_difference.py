#!/usr/bin/env python3
"""Create absolute and signed RGB differences between two NISAR RGB rasters."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re

import numpy as np
import rasterio
from rasterio.enums import ColorInterp, Resampling
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window, from_bounds

from nisar_to_geotiff import BLOCK_SIZE, _lua_string, _write_global_vrt


def _write_info(info_path: Path, vrt_path: Path, name: str, description: str) -> None:
    identifier = f"NISAR_{info_path.stem}".replace("-", "_")
    content = "\n".join(
        (
            f"Name = {_lua_string(name)}",
            f"Identifier = {_lua_string(identifier)}",
            f"Description = {_lua_string(description)}",
            f"ColorFile = {_lua_string(vrt_path.name)}",
            'BlendMode = "Normal"',
            "",
        )
    )
    temporary = info_path.with_name(f"{info_path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, info_path)


def _date_label(path: Path) -> str:
    match = re.search(r"_(\d{4})(\d{2})(\d{2})T\d{6}_", path.name)
    if match is None:
        return path.stem
    year, month, day = match.groups()
    return f"{year}-{month}-{day}"


def _resolution_label(path: Path) -> str:
    match = re.search(r"_(\d+(?:\.\d+)?)pct(?:_|$)", path.stem)
    return f"{match.group(1)}%" if match else "100%"


def _make_difference(
    earlier: np.ndarray,
    later: np.ndarray,
    valid: np.ndarray,
    *,
    signed: bool,
) -> np.ndarray:
    earlier_rgb = earlier[:3].astype(np.int16)
    later_rgb = later[:3].astype(np.int16)
    if signed:
        rgb = 128 + np.rint((later_rgb - earlier_rgb) / 2.0).astype(np.int16)
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    else:
        rgb = np.abs(later_rgb - earlier_rgb).astype(np.uint8)

    rgb[:, ~valid] = 0
    alpha = valid.astype(np.uint8) * 255
    return np.concatenate((rgb, alpha[np.newaxis, :, :]), axis=0)


def create_differences(
    earlier_path: Path,
    later_path: Path,
    output_prefix: Path,
    overwrite: bool,
    threshold: int = 40,
) -> list[Path]:
    if not 0 <= threshold <= 255:
        raise ValueError("The RGB difference threshold must be between 0 and 255")

    threshold_suffix = f"_threshold{threshold}" if threshold else ""
    outputs = [
        output_prefix.with_name(
            f"{output_prefix.name}{threshold_suffix}_absolute.tif"
        ),
        output_prefix.with_name(
            f"{output_prefix.name}{threshold_suffix}_signed.tif"
        ),
    ]
    sidecars = [
        suffix
        for output in outputs
        for suffix in (output, output.with_suffix(".vrt"), output.with_suffix(".info"))
    ]
    existing = [path for path in sidecars if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "Refusing to overwrite existing outputs (use --overwrite): "
            + ", ".join(str(path) for path in existing)
        )

    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(earlier_path) as earlier, rasterio.open(later_path) as later:
        if earlier.count < 4 or later.count < 4:
            raise ValueError("Both input RGB GeoTIFFs must have RGBA bands")
        if earlier.colorinterp[3] != ColorInterp.alpha:
            raise ValueError(f"Earlier raster has no alpha fourth band: {earlier_path}")
        if later.colorinterp[3] != ColorInterp.alpha:
            raise ValueError(f"Later raster has no alpha fourth band: {later_path}")
        if earlier.crs != later.crs:
            raise ValueError("Input rasters must use the same CRS")
        if earlier.crs != rasterio.crs.CRS.from_epsg(4326):
            raise ValueError("Input rasters must be in EPSG:4326")

        overlap_bounds = (
            max(earlier.bounds.left, later.bounds.left),
            max(earlier.bounds.bottom, later.bounds.bottom),
            min(earlier.bounds.right, later.bounds.right),
            min(earlier.bounds.top, later.bounds.top),
        )
        if (
            overlap_bounds[0] >= overlap_bounds[2]
            or overlap_bounds[1] >= overlap_bounds[3]
        ):
            raise ValueError("The input scenes have no overlapping geographic extent")

        crop_window = from_bounds(*overlap_bounds, transform=earlier.transform)
        crop_window = crop_window.round_offsets().round_lengths().intersection(
            Window(0, 0, earlier.width, earlier.height)
        )
        if crop_window.width < 1 or crop_window.height < 1:
            raise ValueError("The scenes' overlap does not cover any reference pixels")
        output_transform = earlier.window_transform(crop_window)
        output_width = int(crop_window.width)
        output_height = int(crop_window.height)

        warped_options = {
            "crs": earlier.crs,
            "transform": output_transform,
            "width": output_width,
            "height": output_height,
            "resampling": Resampling.bilinear,
            "dtype": "uint8",
            "init_dest_nodata": True,
        }
        with WarpedVRT(later, **warped_options) as aligned_later:
            profile = earlier.profile.copy()
            profile.update(
                driver="GTiff",
                width=output_width,
                height=output_height,
                transform=output_transform,
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

            temporary_outputs = [
                path.with_name(f"{path.stem}.tmp{path.suffix}") for path in outputs
            ]
            try:
                with (
                    rasterio.open(temporary_outputs[0], "w", **profile) as absolute,
                    rasterio.open(temporary_outputs[1], "w", **profile) as signed,
                ):
                    for destination in (absolute, signed):
                        destination.colorinterp = (
                            ColorInterp.red,
                            ColorInterp.green,
                            ColorInterp.blue,
                            ColorInterp.alpha,
                        )
                        destination.set_band_description(
                            1, "Absolute RGB difference"
                            if destination is absolute
                            else "Signed RGB difference (later minus earlier)"
                        )
                        destination.set_band_description(
                            4, "Overlap validity alpha"
                        )

                    for row in range(0, output_height, BLOCK_SIZE):
                        height = min(BLOCK_SIZE, output_height - row)
                        for column in range(0, output_width, BLOCK_SIZE):
                            width = min(BLOCK_SIZE, output_width - column)
                            window = Window(column, row, width, height)
                            earlier_window = Window(
                                crop_window.col_off + column,
                                crop_window.row_off + row,
                                width,
                                height,
                            )
                            earlier_data = earlier.read(
                                indexes=(1, 2, 3, 4), window=earlier_window
                            )
                            later_data = aligned_later.read(
                                indexes=(1, 2, 3, 4), window=window
                            )
                            valid = (earlier_data[3] > 127) & (later_data[3] > 127)
                            rgb_change = np.abs(
                                later_data[:3].astype(np.int16)
                                - earlier_data[:3].astype(np.int16)
                            )
                            valid &= np.max(rgb_change, axis=0) >= threshold

                            absolute_data = _make_difference(
                                earlier_data, later_data, valid, signed=False
                            )
                            signed_data = _make_difference(
                                earlier_data, later_data, valid, signed=True
                            )
                            absolute.write(absolute_data, window=window)
                            signed.write(signed_data, window=window)
            except Exception:
                for temporary in temporary_outputs:
                    if temporary.exists():
                        temporary.unlink()
                raise

    for temporary, output in zip(temporary_outputs, outputs):
        os.replace(temporary, output)

    earlier_label = _date_label(earlier_path)
    later_label = _date_label(later_path)
    resolution_label = _resolution_label(earlier_path)
    for output, kind, description in (
        (
            outputs[0],
            "Absolute",
            "Absolute per-channel RGB difference; black is no change, brighter "
            "colors indicate larger channel changes.",
        ),
        (
            outputs[1],
            "Signed",
            "Signed per-channel RGB difference encoded around neutral gray "
            "(128): later minus earlier; values below 128 are decreases and "
            "values above 128 are increases.",
        ),
    ):
        vrt_path = output.with_suffix(".vrt")
        _write_global_vrt(output, vrt_path)
        _write_info(
            output.with_suffix(".info"),
            vrt_path,
            f"NISAR {kind} RGB Difference {earlier_label} to "
            f"{later_label} ({resolution_label}, threshold {threshold}/255)",
            f"{description} Values compare the {later_label} scene against "
            f"{earlier_label}. The output is transparent outside the valid "
            f"overlap of both scenes and where all RGB changes are below "
            f"{threshold}/255.",
        )

    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create absolute and signed RGB difference GeoTIFFs from aligned "
            "NISAR RGBA GeoTIFF scenes."
        )
    )
    parser.add_argument("earlier", type=Path, help="Earlier RGBA EPSG:4326 GeoTIFF")
    parser.add_argument("later", type=Path, help="Later RGBA EPSG:4326 GeoTIFF")
    parser.add_argument(
        "--output-prefix",
        type=Path,
        default=Path("nisar_rgb_difference"),
        help="Output name prefix and directory (default: current directory)",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Replace existing outputs"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=40,
        metavar="LEVEL",
        help=(
            "Keep a pixel only if at least one RGB channel changes by this "
            "many byte levels (0-255; default: 40)"
        ),
    )
    args = parser.parse_args()

    for input_path in (args.earlier, args.later):
        if not input_path.is_file():
            parser.error(f"input file does not exist: {input_path}")
    try:
        outputs = create_differences(
            args.earlier.resolve(),
            args.later.resolve(),
            args.output_prefix.expanduser().resolve(),
            args.overwrite,
            args.threshold,
        )
    except (FileExistsError, ValueError) as error:
        parser.error(str(error))

    for output in outputs:
        print(f"GeoTIFF: {output}")
        print(f"OpenSpace VRT: {output.with_suffix('.vrt')}")
        print(f"OpenSpace info: {output.with_suffix('.info')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
