#!/usr/bin/env python3
"""Convert a NISAR GCOV HDF5 product to a GeoTIFF and OpenSpace VRT."""

from __future__ import annotations

import argparse
import itertools
import math
import os
import re
import tempfile
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path
from typing import Sequence
import xml.etree.ElementTree as ET

import h5py
import numpy as np
import rasterio
import rasterio.shutil
from affine import Affine
from rasterio.enums import ColorInterp, Resampling
from rasterio.warp import calculate_default_transform, reproject


GCOV_GRID_PATH = "/science/LSAR/GCOV/grids"
BLOCK_SIZE = 512


def _regular_axis(axis: np.ndarray, name: str) -> float:
    if axis.ndim != 1 or axis.size < 2:
        raise ValueError(f"{name} must be a one-dimensional coordinate array")

    differences = np.diff(axis)
    step = float(differences[0])
    if step == 0 or not np.allclose(differences, step, rtol=1e-6, atol=1e-8):
        raise ValueError(f"{name} must have regularly spaced coordinates")
    return step


def _source_transform(
    group: h5py.Group, pixel_step: int = 1
) -> tuple[Affine, rasterio.crs.CRS]:
    missing = {"xCoordinates", "yCoordinates", "projection"} - set(group.keys())
    if missing:
        raise ValueError(
            f"GCOV grid is missing georeferencing datasets: {', '.join(sorted(missing))}"
        )
    x = group["xCoordinates"][:]
    y = group["yCoordinates"][:]
    x_step = _regular_axis(x, "xCoordinates")
    y_step = _regular_axis(y, "yCoordinates")
    epsg = int(group["projection"].attrs["epsg_code"])
    x_resolution = x_step * pixel_step
    y_resolution = y_step * pixel_step
    transform = Affine(
        x_resolution,
        0,
        float(x[0]) - x_resolution / 2,
        0,
        y_resolution,
        float(y[0]) - y_resolution / 2,
    )
    return transform, rasterio.crs.CRS.from_epsg(epsg)


def _to_byte_db(values: np.ndarray, low_db: float, high_db: float) -> np.ndarray:
    db = np.full(values.shape, low_db, dtype=np.float32)
    positive = np.isfinite(values) & (values > 0)
    db[positive] = 10.0 * np.log10(values[positive])
    scaled = np.clip((db - low_db) / (high_db - low_db), 0.0, 1.0)
    return np.rint(scaled * 255).astype(np.uint8)


_worker_group: h5py.Group | None = None


def _open_worker_group(input_path: Path, group_path: str) -> None:
    global _worker_group
    _worker_group = h5py.File(input_path, "r")[group_path]


def _convert_strip(
    row: int,
    height: int,
    width: int,
    pixel_step: int,
    mode: str,
    polarization: str,
    db_range: tuple[float, float],
    ratio_range: tuple[float, float],
) -> np.ndarray:
    """Convert one BLOCK_SIZE-row strip of the output grid to output bands."""
    group = _worker_group
    reference = group[polarization if mode == "single" else "HHHH"]
    source_height, source_width = reference.shape
    rows = min(row + BLOCK_SIZE, height) - row
    if mode == "single":
        strip = np.empty((1, rows, width), dtype=np.float32)
    else:
        strip = np.empty((4, rows, width), dtype=np.uint8)

    source_rows = slice(
        row * pixel_step,
        min((row + BLOCK_SIZE) * pixel_step, source_height),
        pixel_step,
    )
    for column in range(0, width, BLOCK_SIZE):
        columns = slice(column, min(column + BLOCK_SIZE, width))
        source_columns = slice(
            column * pixel_step,
            min((column + BLOCK_SIZE) * pixel_step, source_width),
            pixel_step,
        )
        sample_mask = group["mask"][source_rows, source_columns]
        valid = (sample_mask > 0) & (sample_mask < 255)

        if mode == "single":
            values = reference[source_rows, source_columns]
            valid &= np.isfinite(values)
            values = values.astype(np.float32, copy=False)
            values[~valid] = np.nan
            strip[0, :, columns] = values
            continue

        hh = group["HHHH"][source_rows, source_columns]
        hv = group["HVHV"][source_rows, source_columns]
        valid &= (
            np.isfinite(hh)
            & np.isfinite(hv)
            & (hh > 0)
            & (hv > 0)
        )
        red = _to_byte_db(hh, *db_range)
        green = _to_byte_db(hv, *db_range)
        ratio_db = np.zeros(hh.shape, dtype=np.float32)
        ratio_db[valid] = 10.0 * (
            np.log10(hh[valid]) - np.log10(hv[valid])
        )
        blue = np.rint(
            np.clip(
                (ratio_db - ratio_range[0])
                / (ratio_range[1] - ratio_range[0]),
                0.0,
                1.0,
            )
            * 255
        ).astype(np.uint8)
        red[~valid] = 0
        green[~valid] = 0
        blue[~valid] = 0
        strip[0, :, columns] = red
        strip[1, :, columns] = green
        strip[2, :, columns] = blue
        strip[3, :, columns] = valid.astype(np.uint8) * 255
    return strip


def _write_source(
    input_path: Path,
    temporary_path: Path,
    frequency: str,
    mode: str,
    polarization: str,
    db_range: tuple[float, float],
    ratio_range: tuple[float, float],
    resolution_percent: float,
    workers: int | None = None,
) -> tuple[int, int, rasterio.crs.CRS]:
    group_path = f"{GCOV_GRID_PATH}/frequency{frequency}"
    pixel_step = max(1, round(100.0 / resolution_percent))
    with h5py.File(input_path, "r") as product:
        if group_path not in product:
            raise ValueError(f"GCOV grid {group_path} was not found in {input_path}")
        group = product[group_path]
        transform, crs = _source_transform(group, pixel_step)
        if "mask" not in group:
            raise ValueError(f"GCOV grid {group_path} has no sample mask")

        if mode == "single":
            if polarization not in group:
                raise ValueError(
                    f"Polarization {polarization!r} was not found in {group_path}"
                )
            datasets = [group[polarization]]
            count = 1
            dtype = "float32"
            nodata = float("nan")
        else:
            for name in ("HHHH", "HVHV"):
                if name not in group:
                    raise ValueError(
                        f"Polarimetric RGB output requires {name} in {group_path}"
                    )
            datasets = [group["HHHH"], group["HVHV"]]
            count = 4
            dtype = "uint8"
            nodata = None

        source_height, source_width = datasets[0].shape
        if any(dataset.shape != (source_height, source_width) for dataset in datasets):
            raise ValueError("GCOV polarization grids have mismatched dimensions")
        height = math.ceil(source_height / pixel_step)
        width = math.ceil(source_width / pixel_step)

        profile = {
            "driver": "GTiff",
            "width": width,
            "height": height,
            "count": count,
            "dtype": dtype,
            "crs": crs,
            "transform": transform,
            "tiled": True,
            "blockxsize": BLOCK_SIZE,
            "blockysize": BLOCK_SIZE,
            # The source is a short-lived intermediate, so skip compression.
            "bigtiff": "IF_SAFER",
            "nodata": nodata,
        }
        with rasterio.open(temporary_path, "w", **profile) as destination:
            if mode == "rgb":
                destination.colorinterp = (
                    ColorInterp.red,
                    ColorInterp.green,
                    ColorInterp.blue,
                    ColorInterp.alpha,
                )
                destination.set_band_description(1, "HH backscatter (dB)")
                destination.set_band_description(2, "HV backscatter (dB)")
                destination.set_band_description(3, "HH/HV ratio (dB)")
                destination.set_band_description(4, "Valid-data alpha")
            else:
                destination.colorinterp = (ColorInterp.gray,)
                destination.set_band_description(1, polarization)

            # h5py serializes reads behind a global lock, so decode strips in
            # worker processes. Keep a bounded number of strips in flight.
            rows = list(range(0, height, BLOCK_SIZE))
            workers = max(1, min(workers or os.cpu_count() or 1, len(rows)))
            convert = partial(
                _convert_strip,
                height=height,
                width=width,
                pixel_step=pixel_step,
                mode=mode,
                polarization=polarization,
                db_range=db_range,
                ratio_range=ratio_range,
            )
            with ProcessPoolExecutor(
                max_workers=workers,
                initializer=_open_worker_group,
                initargs=(input_path, group_path),
            ) as executor:
                pending: deque = deque()
                next_row = iter(rows)
                for row in itertools.islice(next_row, workers + 2):
                    pending.append((row, executor.submit(convert, row)))
                while pending:
                    row, future = pending.popleft()
                    strip = future.result()
                    window = rasterio.windows.Window(0, row, width, strip.shape[1])
                    destination.write(strip, window=window)
                    for row in itertools.islice(next_row, 1):
                        pending.append((row, executor.submit(convert, row)))

    return width, height, crs


def _warp_to_geotiff(
    source_path: Path, temporary_output: Path, mode: str
) -> None:
    destination_crs = rasterio.crs.CRS.from_epsg(4326)
    with rasterio.open(source_path) as source:
        transform, width, height = calculate_default_transform(
            source.crs,
            destination_crs,
            source.width,
            source.height,
            *source.bounds,
        )
        profile = source.profile.copy()
        profile.update(
            crs=destination_crs,
            transform=transform,
            width=width,
            height=height,
            tiled=True,
            blockxsize=BLOCK_SIZE,
            blockysize=BLOCK_SIZE,
            bigtiff="IF_SAFER",
        )
        profile.pop("compress", None)

        # The warper rewrites tiles, and GDAL appends each rewritten compressed
        # tile, orphaning the old bytes. Warp uncompressed, then compress once.
        warped_path = source_path.with_name("warped.tif")
        with rasterio.open(warped_path, "w", **profile) as destination:
            destination.colorinterp = source.colorinterp
            # Warp the RGB bands together; only the alpha band needs nearest.
            band_groups = (
                [((1, 2, 3), Resampling.bilinear), ((4,), Resampling.nearest)]
                if mode == "rgb"
                else [((1,), Resampling.bilinear)]
            )
            for bands, resampling in band_groups:
                reproject(
                    source=rasterio.band(source, bands),
                    destination=rasterio.band(destination, bands),
                    src_transform=source.transform,
                    src_crs=source.crs,
                    src_nodata=source.nodata,
                    dst_transform=transform,
                    dst_crs=destination_crs,
                    dst_nodata=source.nodata,
                    resampling=resampling,
                    init_dest_nodata=True,
                    num_threads=os.cpu_count() or 1,
                    warp_mem_limit=1024,
                )
            for band in range(1, source.count + 1):
                description = source.descriptions[band - 1]
                if description:
                    destination.set_band_description(band, description)

    rasterio.shutil.copy(
        warped_path,
        temporary_output,
        driver="GTiff",
        tiled=True,
        blockxsize=BLOCK_SIZE,
        blockysize=BLOCK_SIZE,
        compress="deflate",
        predictor=3 if mode == "single" else 2,
        bigtiff="IF_SAFER",
        **({"photometric": "RGB", "alpha": "YES"} if mode == "rgb" else {}),
    )


def _append_source(
    parent: ET.Element,
    band_number: int,
    source_filename: str,
    source_size: tuple[int, int],
    source_dtype: str,
    source_transform: Affine,
    vrt_resolution: tuple[float, float],
    *,
    source_band: str | int | None = None,
    nodata: str | None = None,
) -> None:
    source = ET.SubElement(parent, "ComplexSource")
    ET.SubElement(source, "SourceFilename", relativeToVRT="1").text = source_filename
    ET.SubElement(source, "SourceBand").text = str(source_band or band_number)
    width, height = source_size
    ET.SubElement(
        source,
        "SourceProperties",
        RasterXSize=str(width),
        RasterYSize=str(height),
        DataType=source_dtype,
        BlockXSize=str(BLOCK_SIZE),
        BlockYSize=str(BLOCK_SIZE),
    )
    ET.SubElement(
        source,
        "SrcRect",
        xOff="0",
        yOff="0",
        xSize=str(width),
        ySize=str(height),
    )
    x_resolution, y_resolution = vrt_resolution
    ET.SubElement(
        source,
        "DstRect",
        xOff=f"{(source_transform.c + 180.0) / x_resolution:.12g}",
        yOff=f"{(90.0 - source_transform.f) / y_resolution:.12g}",
        xSize=f"{width * source_transform.a / x_resolution:.12g}",
        ySize=f"{height * abs(source_transform.e) / y_resolution:.12g}",
    )
    if nodata is not None:
        ET.SubElement(source, "NODATA").text = nodata


def _write_global_vrt(geotiff_path: Path, vrt_path: Path) -> None:
    with rasterio.open(geotiff_path) as source:
        if source.crs != rasterio.crs.CRS.from_epsg(4326):
            raise ValueError("The OpenSpace VRT requires an EPSG:4326 GeoTIFF")
        x_resolution = source.transform.a
        y_resolution = abs(source.transform.e)
        if x_resolution <= 0 or y_resolution <= 0:
            raise ValueError("The GeoTIFF must have a north-up geographic transform")

        global_width = max(1, round(360.0 / x_resolution))
        global_height = max(1, round(180.0 / y_resolution))
        vrt_x_resolution = 360.0 / global_width
        vrt_y_resolution = 180.0 / global_height
        root = ET.Element(
            "VRTDataset",
            rasterXSize=str(global_width),
            rasterYSize=str(global_height),
        )
        ET.SubElement(root, "SRS").text = "EPSG:4326"
        ET.SubElement(root, "GeoTransform").text = (
            f"-180,{vrt_x_resolution:.16g},0,90,0,{-vrt_y_resolution:.16g}"
        )

        vrt_band_count = 2 if source.count == 1 else source.count
        for band_number in range(1, vrt_band_count + 1):
            is_single_alpha = source.count == 1 and band_number == 2
            source_band: str | int = (
                "mask,1" if is_single_alpha else band_number
            )
            source_dtype = (
                "Byte"
                if is_single_alpha
                else {
                    "uint8": "Byte",
                    "float32": "Float32",
                }[source.dtypes[band_number - 1]]
            )
            band = ET.SubElement(
                root,
                "VRTRasterBand",
                dataType=source_dtype,
                band=str(band_number),
            )
            if is_single_alpha:
                color = "Alpha"
            elif source.count == 4:
                color = ("Red", "Green", "Blue", "Alpha")[band_number - 1]
            else:
                color = "Gray"
                ET.SubElement(band, "NoDataValue").text = "nan"
            ET.SubElement(band, "ColorInterp").text = color
            _append_source(
                band,
                band_number,
                geotiff_path.name,
                (source.width, source.height),
                source_dtype,
                source.transform,
                (vrt_x_resolution, vrt_y_resolution),
                source_band=source_band,
                nodata="nan" if source.count == 1 and not is_single_alpha else None,
            )

    tree = ET.ElementTree(root)
    temporary_vrt = vrt_path.with_name(f"{vrt_path.name}.tmp")
    tree.write(temporary_vrt, encoding="UTF-8", xml_declaration=True)
    os.replace(temporary_vrt, vrt_path)


def _lua_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _write_info_file(
    info_path: Path,
    vrt_path: Path,
    input_path: Path,
    frequency: str,
    mode: str,
    polarization: str,
    resolution_percent: float,
) -> None:
    acquisition_date = re.search(r"_(\d{8})T\d{6}_", input_path.name)
    if acquisition_date is None:
        raise ValueError(
            f"Cannot find the NISAR acquisition date in input filename: {input_path.name}"
        )
    date = acquisition_date.group(1)
    percentage = f"{resolution_percent:g}%"
    layer_name = f"NISAR {date[:4]}-{date[4:6]}-{date[6:]} ({percentage})"

    if mode == "rgb":
        description = (
            f"False-color composite from {input_path.name}: "
            "red is HH backscatter, green is HV backscatter, and blue is the "
            "HH/HV backscatter ratio."
        )
    else:
        description = (
            f"Single-band {polarization} covariance from {input_path.name}; "
            "pixel values are linear GCOV power."
        )

    identifier = re.sub(r"[^A-Za-z0-9_-]", "_", f"NISAR_{info_path.stem}")
    contents = "\n".join(
        (
            f"Name = {_lua_string(layer_name)}",
            f"Identifier = {_lua_string(identifier)}",
            f"Description = {_lua_string(description)}",
            f"ColorFile = {_lua_string(vrt_path.name)}",
            'BlendMode = "Normal"',
            "",
        )
    )
    temporary_info = info_path.with_name(f"{info_path.name}.tmp")
    temporary_info.write_text(contents, encoding="utf-8")
    os.replace(temporary_info, info_path)


def _parse_range(values: Sequence[float], name: str) -> tuple[float, float]:
    low, high = values
    if not math.isfinite(low) or not math.isfinite(high) or low >= high:
        raise ValueError(f"{name} must be finite and low < high")
    return low, high


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert a NISAR GCOV HDF5 file to a georeferenced GeoTIFF."
    )
    parser.add_argument("input", type=Path, help="NISAR L2 GCOV .h5 file")
    parser.add_argument("output", type=Path, help="Output .tif/.tiff path")
    parser.add_argument(
        "--frequency", choices=("A", "B"), default="A", help="GCOV frequency (default: A)"
    )
    parser.add_argument(
        "--mode",
        choices=("rgb", "single"),
        default="rgb",
        help="RGB false-color composite or single-band backscatter (default: rgb)",
    )
    parser.add_argument(
        "--polarization",
        default="HHHH",
        help="Single-band covariance term, e.g. HHHH or HVHV (default: HHHH)",
    )
    parser.add_argument(
        "--db-range",
        nargs=2,
        type=float,
        metavar=("MIN", "MAX"),
        default=(-30.0, 0.0),
        help="RGB HH/HV display stretch in dB (default: -30 0)",
    )
    parser.add_argument(
        "--ratio-range",
        nargs=2,
        type=float,
        metavar=("MIN", "MAX"),
        default=(0.0, 20.0),
        help="RGB HH/HV ratio display stretch in dB (default: 0 20)",
    )
    parser.add_argument(
        "--resolution-percent",
        type=float,
        default=100.0,
        metavar="PERCENT",
        help=(
            "Output linear resolution as a percentage of the source grid "
            "(1-100; default: 100). Lower values sample fewer source pixels."
        ),
    )
    parser.add_argument(
        "--no-vrt",
        action="store_true",
        help="Do not create the companion whole-globe OpenSpace VRT",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Replace existing output files"
    )
    args = parser.parse_args(argv)

    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    vrt_path = output_path.with_suffix(".vrt")
    info_path = output_path.with_suffix(".info")
    if not input_path.is_file():
        parser.error(f"input file does not exist: {input_path}")
    if input_path == output_path:
        parser.error("input and output paths must be different")
    if output_path.suffix.lower() not in (".tif", ".tiff"):
        parser.error("output must have a .tif or .tiff extension")
    try:
        db_range = _parse_range(args.db_range, "--db-range")
        ratio_range = _parse_range(args.ratio_range, "--ratio-range")
    except ValueError as error:
        parser.error(str(error))
    if (
        not math.isfinite(args.resolution_percent)
        or not 0 < args.resolution_percent <= 100
    ):
        parser.error("--resolution-percent must be greater than 0 and at most 100")
    if output_path.exists() and not args.overwrite:
        parser.error(f"output already exists (use --overwrite): {output_path}")
    if not args.no_vrt and vrt_path.exists() and not args.overwrite:
        parser.error(f"VRT already exists (use --overwrite): {vrt_path}")
    if not args.no_vrt and info_path.exists() and not args.overwrite:
        parser.error(f"OpenSpace info file already exists (use --overwrite): {info_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output_path.with_name(f"{output_path.stem}.tmp{output_path.suffix}")
    try:
        with rasterio.Env(GDAL_NUM_THREADS="ALL_CPUS"), tempfile.TemporaryDirectory(
            prefix="nisar-geotiff-"
        ) as temporary_directory:
            source_path = Path(temporary_directory) / "source.tif"
            _write_source(
                input_path,
                source_path,
                args.frequency,
                args.mode,
                args.polarization,
                db_range,
                ratio_range,
                args.resolution_percent,
            )
            _warp_to_geotiff(source_path, temporary_output, args.mode)

        os.replace(temporary_output, output_path)
        if not args.no_vrt:
            _write_global_vrt(output_path, vrt_path)
            _write_info_file(
                info_path,
                vrt_path,
                input_path,
                args.frequency,
                args.mode,
                args.polarization,
                args.resolution_percent,
            )
    finally:
        if temporary_output.exists():
            temporary_output.unlink()

    print(f"GeoTIFF: {output_path}")
    if not args.no_vrt:
        print(f"OpenSpace VRT: {vrt_path}")
        print(f"OpenSpace info: {info_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
