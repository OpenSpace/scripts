#!/usr/bin/env python3
"""Create RGB channel-mapping previews from an existing NISAR RGBA GeoTIFF."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
from typing import Sequence

import numpy as np
import rasterio
from rasterio.enums import ColorInterp
from rasterio.windows import Window

from nisar_to_geotiff import BLOCK_SIZE, _lua_string, _write_global_vrt


VARIANTS: tuple[tuple[str, str, tuple[int, int, int] | None], ...] = (
    ("hh-hv-ratio", "HH red, HV green, ratio blue", (0, 1, 2)),
    ("hh-ratio-hv", "HH red, ratio green, HV blue", (0, 2, 1)),
    ("hv-hh-ratio", "HV red, HH green, ratio blue", (1, 0, 2)),
    ("hv-ratio-hh", "HV red, ratio green, HH blue", (1, 2, 0)),
    ("ratio-hh-hv", "Ratio red, HH green, HV blue", (2, 0, 1)),
    ("ratio-hv-hh", "Ratio red, HV green, HH blue", (2, 1, 0)),
    ("hh-grayscale", "HH backscatter grayscale", (0, 0, 0)),
    ("hv-grayscale", "HV backscatter grayscale", (1, 1, 1)),
    ("ratio-grayscale", "HH/HV ratio grayscale", (2, 2, 2)),
    ("all-components-grayscale", "Mean HH, HV, and ratio grayscale", None),
)
SOURCE_CHANNELS = ("HH backscatter", "HV backscatter", "HH/HV ratio")


def _date_and_resolution(path: Path) -> tuple[str, str]:
    date_match = re.search(r"_(\d{4})(\d{2})(\d{2})T\d{6}_", path.name)
    date = (
        f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        if date_match
        else path.stem
    )
    resolution_match = re.search(r"_(\d+(?:\.\d+)?)pct(?:_|$)", path.stem)
    resolution = f"{resolution_match.group(1)}%" if resolution_match else "100%"
    return date, resolution


def _write_info(
    info_path: Path,
    vrt_path: Path,
    date: str,
    resolution: str,
    variant: str,
    description: str,
) -> None:
    content = "\n".join(
        (
            f"Name = {_lua_string(f'NISAR {date} ({resolution}) - {variant}')}",
            f"Identifier = {_lua_string('NISAR_' + info_path.stem)}",
            f"Description = {_lua_string(description)}",
            f"ColorFile = {_lua_string(vrt_path.name)}",
            'BlendMode = "Normal"',
            "",
        )
    )
    temporary = info_path.with_name(f"{info_path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, info_path)


def create_color_variants(
    input_path: Path, output_directory: Path, overwrite: bool = False
) -> list[Path]:
    input_path = input_path.expanduser().resolve()
    output_directory = output_directory.expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input GeoTIFF does not exist: {input_path}")

    outputs = [
        output_directory / f"nisar_{slug}_5pct.tif"
        for slug, _, _ in VARIANTS
    ]
    sidecars = [
        sidecar
        for output in outputs
        for sidecar in (output, output.with_suffix(".vrt"), output.with_suffix(".info"))
    ]
    existing = [path for path in sidecars if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "Refusing to overwrite existing color variants (use --overwrite): "
            + ", ".join(str(path) for path in existing)
        )

    output_directory.mkdir(parents=True, exist_ok=True)
    date, resolution = _date_and_resolution(input_path)
    temporary_outputs = [
        output.with_name(f"{output.stem}.tmp{output.suffix}") for output in outputs
    ]
    try:
        with rasterio.open(input_path) as source:
            if source.count != 4:
                raise ValueError("The input GeoTIFF must have four RGBA bands")
            if source.colorinterp[3] != ColorInterp.alpha:
                raise ValueError("The input GeoTIFF's fourth band must be alpha")
            if source.crs != rasterio.crs.CRS.from_epsg(4326):
                raise ValueError("The input GeoTIFF must use EPSG:4326")

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
            writers: list[rasterio.io.DatasetWriter] = []
            try:
                for temporary, (_, variant, indices) in zip(
                    temporary_outputs, VARIANTS
                ):
                    writer = rasterio.open(temporary, "w", **profile)
                    writer.colorinterp = (
                        ColorInterp.red,
                        ColorInterp.green,
                        ColorInterp.blue,
                        ColorInterp.alpha,
                    )
                    for band, color in enumerate(("red", "green", "blue"), start=1):
                        component = (
                            "mean of HH, HV, and HH/HV"
                            if indices is None
                            else SOURCE_CHANNELS[indices[band - 1]]
                        )
                        writer.set_band_description(band, f"{component} -> {color}")
                    writer.set_band_description(4, "Valid-data alpha")
                    writers.append(writer)

                for row in range(0, source.height, BLOCK_SIZE):
                    height = min(BLOCK_SIZE, source.height - row)
                    for column in range(0, source.width, BLOCK_SIZE):
                        width = min(BLOCK_SIZE, source.width - column)
                        window = Window(column, row, width, height)
                        source_data = source.read(
                            indexes=(1, 2, 3, 4), window=window
                        )
                        for writer, (_, _, indices) in zip(writers, VARIANTS):
                            if indices is None:
                                gray = np.rint(
                                    source_data[:3].astype(np.float32).mean(axis=0)
                                ).astype(np.uint8)
                                rgb = np.stack((gray, gray, gray))
                            else:
                                rgb = source_data[np.asarray(indices)]
                            rgba = np.concatenate((rgb, source_data[3:4]), axis=0)
                            writer.write(rgba, window=window)
            finally:
                for writer in writers:
                    writer.close()

        for temporary, output in zip(temporary_outputs, outputs):
            os.replace(temporary, output)
    except Exception:
        for temporary in temporary_outputs:
            if temporary.exists():
                temporary.unlink()
        raise

    for output, (slug, variant, indices) in zip(outputs, VARIANTS):
        mapped_channels = (
            "the mean of HH, HV, and HH/HV is repeated across RGB"
            if indices is None
            else "; ".join(
                f"{color} is {SOURCE_CHANNELS[channel]}"
                for color, channel in zip(("red", "green", "blue"), indices)
            )
        )
        vrt_path = output.with_suffix(".vrt")
        _write_global_vrt(output, vrt_path)
        _write_info(
            output.with_suffix(".info"),
            vrt_path,
            date,
            resolution,
            variant,
            f"September 30 NISAR RGB color-mapping preview at {resolution}: "
            f"{mapped_channels}. Uses the source preview's existing display "
            "stretches; only channel assignments change.",
        )

    return outputs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create ten RGB/grayscale color-mapping previews from an existing "
            "NISAR RGBA GeoTIFF without reading the original HDF5."
        )
    )
    parser.add_argument("input", type=Path, help="Existing 5-percent RGBA GeoTIFF")
    parser.add_argument("output_directory", type=Path, help="Variant output folder")
    parser.add_argument(
        "--overwrite", action="store_true", help="Replace existing variant files"
    )
    args = parser.parse_args(argv)

    try:
        outputs = create_color_variants(
            args.input, args.output_directory, overwrite=args.overwrite
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
