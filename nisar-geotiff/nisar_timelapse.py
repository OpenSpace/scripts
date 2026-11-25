#!/usr/bin/env python3
"""Build a co-registered HH backscatter time series from NISAR GCOV products.

Recreates the look of NASA SVS 5675 (Krasheninnikov volcano time-lapse): every
input GCOV file is cropped to the same geographic box, warped onto one shared
EPSG:4326 grid, and stretched with one shared dB range, so frames can be
compared (or flipped through) in OpenSpace without shifting or flickering.
Each frame gets a GeoTIFF, a whole-globe VRT, and an OpenSpace .info file.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import h5py
import numpy as np
import rasterio
import rasterio.shutil
import rasterio.windows
from rasterio.enums import ColorInterp, Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds

from nisar_to_geotiff import (
    BLOCK_SIZE,
    GCOV_GRID_PATH,
    _lua_string,
    _regular_axis,
    _source_transform,
    _write_global_vrt,
)

# Krasheninnikov volcano, Kamchatka (summit area / northern crater).
DEFAULT_CENTER = (160.27, 54.59)  # lon, lat
FILENAME_RE = re.compile(
    r"GCOV_(?P<cycle>\d{3})_(?P<track>\d{3})_(?P<direction>[AD])_.*?_(?P<date>\d{8})T\d{6}_"
)


@dataclass(frozen=True)
class Scene:
    path: Path
    date: str  # YYYYMMDD
    track: str
    direction: str

    @property
    def stem(self) -> str:
        return f"nisar_hh_{self.date}_t{self.track}{self.direction}"


def parse_scene(path: Path) -> Scene:
    match = FILENAME_RE.search(path.name)
    if match is None:
        raise ValueError(f"Not a NISAR GCOV filename: {path.name}")
    return Scene(path, match["date"], match["track"], match["direction"])


def find_scenes(inputs: Sequence[Path]) -> list[Scene]:
    files: list[Path] = []
    for item in inputs:
        files.extend(sorted(item.glob("*GCOV*.h5")) if item.is_dir() else [item])
    scenes = [parse_scene(path) for path in files]
    return sorted(scenes, key=lambda scene: (scene.date, scene.track))


def output_grid(
    center: tuple[float, float], half_size_km: float, pixel_m: float
) -> tuple[rasterio.Affine, int, int]:
    """Shared EPSG:4326 grid: pixels are ~pixel_m metres on the ground."""
    lon, lat = center
    km_per_deg_lat = 111.32
    y_step = pixel_m / 1000.0 / km_per_deg_lat
    x_step = y_step / math.cos(math.radians(lat))
    half_lat = half_size_km / km_per_deg_lat
    half_lon = half_lat / math.cos(math.radians(lat))
    width = max(1, round(2 * half_lon / x_step))
    height = max(1, round(2 * half_lat / y_step))
    transform = from_origin(lon - half_lon, lat + half_lat, x_step, y_step)
    return transform, width, height


def read_db_frame(
    scene: Scene,
    transform: rasterio.Affine,
    width: int,
    height: int,
    frequency: str,
    polarization: str,
) -> np.ndarray | None:
    """HH power in dB on the shared grid (NaN where invalid); None if no overlap."""
    group_path = f"{GCOV_GRID_PATH}/frequency{frequency}"
    with h5py.File(scene.path, "r") as product:
        if group_path not in product:
            raise ValueError(f"{scene.path.name}: {group_path} not found")
        group = product[group_path]
        if polarization not in group:
            raise ValueError(f"{scene.path.name}: {polarization} not found")
        source_transform, crs = _source_transform(group)
        dataset = group[polarization]
        src_height, src_width = dataset.shape

        west, north = transform @ (0, 0)
        east, south = transform @ (width, height)
        bounds = transform_bounds(
            rasterio.crs.CRS.from_epsg(4326), crs, west, south, east, north,
            densify_pts=21,
        )
        window = rasterio.windows.from_bounds(*bounds, transform=source_transform)
        window = window.round_offsets(op="floor").round_lengths(op="ceil")
        bounds_window = rasterio.windows.Window(0, 0, src_width, src_height)
        try:
            window = window.intersection(bounds_window)
        except rasterio.errors.WindowError:
            return None
        if window.width < 2 or window.height < 2:
            return None

        rows = slice(int(window.row_off), int(window.row_off + window.height))
        cols = slice(int(window.col_off), int(window.col_off + window.width))
        values = dataset[rows, cols].astype(np.float32)
        mask = group["mask"][rows, cols]
        window_transform = rasterio.windows.transform(window, source_transform)

    valid = np.isfinite(values) & (values > 0) & (mask > 0) & (mask < 255)
    db = np.full(values.shape, np.nan, dtype=np.float32)
    db[valid] = 10.0 * np.log10(values[valid])

    destination = np.full((height, width), np.nan, dtype=np.float32)
    reproject(
        source=db,
        destination=destination,
        src_transform=window_transform,
        src_crs=crs,
        src_nodata=np.nan,
        dst_transform=transform,
        dst_crs=rasterio.crs.CRS.from_epsg(4326),
        dst_nodata=np.nan,
        resampling=Resampling.average,
        init_dest_nodata=True,
    )
    return destination


def stretch_to_rgba(db: np.ndarray, db_range: tuple[float, float]) -> np.ndarray:
    low, high = db_range
    valid = np.isfinite(db)
    scaled = np.clip((np.nan_to_num(db, nan=low) - low) / (high - low), 0.0, 1.0)
    gray = np.rint(scaled * 255).astype(np.uint8)
    gray[~valid] = 0
    alpha = valid.astype(np.uint8) * 255
    return np.stack([gray, gray, gray, alpha])


def write_geotiff(
    path: Path,
    rgba: np.ndarray,
    transform: rasterio.Affine,
    description: str,
) -> None:
    _, height, width = rgba.shape
    temporary = path.with_name(f"{path.stem}.tmp.tif")
    with rasterio.open(
        temporary,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=4,
        dtype="uint8",
        crs="EPSG:4326",
        transform=transform,
        tiled=True,
        blockxsize=BLOCK_SIZE,
        blockysize=BLOCK_SIZE,
        compress="deflate",
        predictor=2,
        photometric="RGB",
        alpha="YES",
    ) as destination:
        destination.write(rgba)
        destination.colorinterp = (
            ColorInterp.red,
            ColorInterp.green,
            ColorInterp.blue,
            ColorInterp.alpha,
        )
        destination.update_tags(
            DESCRIPTION=description, TIFFTAG_IMAGEDESCRIPTION=description
        )
    temporary.replace(path)


def write_info(info_path: Path, vrt_path: Path, scene: Scene, db_range, label: str) -> None:
    date = f"{scene.date[:4]}-{scene.date[4:6]}-{scene.date[6:]}"
    description = (
        f"NISAR L-band HH backscatter from {scene.path.name} (track {scene.track}, "
        f"{'ascending' if scene.direction == 'A' else 'descending'}). Shared stretch "
        f"{db_range[0]:g} to {db_range[1]:g} dB across the whole series; bright = "
        "strong radar return (e.g. fresh lava)."
    )
    identifier = re.sub(r"[^A-Za-z0-9_-]", "_", f"NISAR_{info_path.stem}")
    info_path.write_text(
        "\n".join(
            (
                f"Name = {_lua_string(f'NISAR {label} HH {date}')}",
                f"Identifier = {_lua_string(identifier)}",
                f"Description = {_lua_string(description)}",
                f"ColorFile = {_lua_string(vrt_path.name)}",
                'BlendMode = "Normal"',
                "",
            )
        ),
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs", nargs="+", type=Path,
        help="NISAR GCOV .h5 files and/or folders containing them",
    )
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--center", nargs=2, type=float, metavar=("LON", "LAT"),
                        default=DEFAULT_CENTER, help="Crop center (default: Krasheninnikov)")
    parser.add_argument("--half-size-km", type=float, default=12.0,
                        help="Half the crop box width/height in km (default 12)")
    parser.add_argument("--pixel-m", type=float, default=10.0,
                        help="Output pixel size in metres (default 10)")
    parser.add_argument("--frequency", choices=("A", "B"), default="A")
    parser.add_argument("--polarization", default="HHHH")
    parser.add_argument("--db-range", nargs=2, type=float, metavar=("LOW", "HIGH"),
                        help="Fixed dB stretch for every frame (default: pooled "
                             "2nd-99.5th percentile of all frames)")
    parser.add_argument("--track", help="Only use this track number, e.g. 060")
    parser.add_argument("--direction", choices=("A", "D"),
                        help="Only use ascending or descending passes")
    parser.add_argument("--label", default="Krasheninnikov",
                        help="Name used in OpenSpace layer names")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    scenes = find_scenes(args.inputs)
    if args.track:
        scenes = [s for s in scenes if s.track == args.track.zfill(3)]
    if args.direction:
        scenes = [s for s in scenes if s.direction == args.direction]
    if not scenes:
        parser.error("no matching NISAR GCOV files found")
    geometries = {(s.track, s.direction) for s in scenes}
    if len(geometries) > 1:
        print(
            f"warning: {len(geometries)} different track/direction combinations "
            f"{sorted(geometries)}; radar geometry (and shadow/layover) differs "
            "between them. Use --track/--direction for a clean time series.",
            file=sys.stderr,
        )

    transform, width, height = output_grid(
        tuple(args.center), args.half_size_km, args.pixel_m
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)

    frames: list[tuple[Scene, np.ndarray]] = []
    for scene in scenes:
        print(f"reading {scene.path.name}")
        db = read_db_frame(
            scene, transform, width, height, args.frequency, args.polarization
        )
        if db is None or not np.isfinite(db).any():
            print(f"  skipped: no valid data over the crop box", file=sys.stderr)
            continue
        frames.append((scene, db))
    if not frames:
        print("error: no scene covers the crop box", file=sys.stderr)
        return 1

    if args.db_range:
        db_range = tuple(args.db_range)
    else:
        pooled = np.concatenate([db[np.isfinite(db)][::7] for _, db in frames])
        db_range = (float(np.percentile(pooled, 2)), float(np.percentile(pooled, 99.5)))
        print(f"pooled stretch: {db_range[0]:.1f} to {db_range[1]:.1f} dB")
    if db_range[1] <= db_range[0]:
        parser.error("--db-range HIGH must exceed LOW")

    manifest = []
    for scene, db in frames:
        tif = args.output_dir / f"{scene.stem}.tif"
        vrt = tif.with_suffix(".vrt")
        info = tif.with_suffix(".info")
        if tif.exists() and not args.overwrite:
            print(f"  exists, skipping (use --overwrite): {tif.name}")
        else:
            write_geotiff(tif, stretch_to_rgba(db, db_range), transform,
                          f"NISAR HH {scene.date} from {scene.path.name}")
            _write_global_vrt(tif, vrt)
            write_info(info, vrt, scene, db_range, args.label)
            print(f"wrote {tif.name}")
        manifest.append(
            {"date": scene.date, "track": scene.track, "direction": scene.direction,
             "source": scene.path.name, "geotiff": tif.name, "info": info.name}
        )

    (args.output_dir / "manifest.json").write_text(
        json.dumps(
            {"center_lonlat": list(args.center), "half_size_km": args.half_size_km,
             "pixel_m": args.pixel_m, "db_range": list(db_range), "frames": manifest},
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
