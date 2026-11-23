"""Generate true-scale region models (US states, later countries) for OpenSpace.

Examples
--------
  # All 50 states, default (glass) style
  python generate.py us-states

  # A few states
  python generate.py us-states --only "New York" TX

  # Every style for one region, side by side across the US, for picking a look
  python generate.py style-test --only "New York"

Output goes to build/: scale_locations.asset (shared runtime code and settings) plus one
folder per set, e.g. build/us_states/ with models/, one asset per group (northeast.asset,
...) and us_states.asset, which loads every group. Copy build/ into ${USER_ASSETS}
(keeping the layout), or pass --out to write straight there.
"""
from __future__ import annotations

import argparse
import shutil
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from scaleobjects import geometry as geo
from scaleobjects.parts import prepare
from scaleobjects.sources import SOURCES, Region, Source
from scaleobjects.styles import STYLES, Style
from scaleobjects.textures import write_texture
from scaleobjects.writers import (
    RegionEntry, write_glb, write_group_asset, write_license, write_obj, write_set_asset,
    write_shared_asset,
)

ROOT = Path(__file__).resolve().parent

# Models are curved for a sphere of this radius (Earth's mean radius). When a region is
# placed on another globe, OpenSpace squashes it vertically by
# ReferenceRadius / globe radius, which for a region small next to the body is very
# close to the true curvature. That keeps one set of models usable on any globe.
REFERENCE_RADIUS = 6_371_008.8


def build_region(
    region: Region,
    style: Style,
    models_dir: Path,
    file_prefix: str,
    cell: float | None,
    textures: set[str],
) -> RegionEntry:
    t0 = time.perf_counter()
    prepared = prepare(region.geometry, style, cell)

    models: dict[str, str] = {}
    for part_name, (mesh, part) in prepared.meshes(REFERENCE_RADIUS).items():
        if part.texture and part.texture not in textures:
            write_texture(part.texture, models_dir)
            textures.add(part.texture)
        stem = f"{file_prefix}{region.key}_{part_name.lower()}"
        if part.texture:  # textures go through OBJ + MTL
            name = stem + ".obj"
            write_obj(models_dir / name, mesh, f"{part.texture}.png")
        else:
            name = stem + ".glb"
            write_glb(models_dir / name, mesh, normals=part.shading)
        models[part_name] = name

    planar = prepared.planar
    area_km2 = planar.area_m2 / 1e6
    print(
        f"  {region.name}: {area_km2:,.0f} km2, cell {prepared.cell / 1000:.1f} km, "
        f"{time.perf_counter() - t0:.1f}s"
    )
    return RegionEntry(
        key=region.key,
        name=region.name,
        latitude=planar.center_lat,
        longitude=planar.center_lon,
        area_km2=area_km2,
        models=models,
        note=region.info.get("note", ""),
    )


def select(regions: list[Region], only: list[str] | None) -> list[Region]:
    if not only:
        return regions
    wanted = {o.lower() for o in only}

    def names(r: Region) -> set[str]:
        return {r.name.lower(), r.key.lower(), r.info.get("abbreviation", "").lower()}

    picked = [r for r in regions if names(r) & wanted]
    missing = wanted - set().union(*(names(r) for r in picked)) if picked else wanted
    if missing:
        raise SystemExit(f"Unknown region(s): {', '.join(sorted(missing))}")
    return picked


def fresh_dir(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    (path / "models").mkdir(parents=True)
    return path


def generate_set(source: Source, args) -> None:
    """Models for every region in one shared models/ folder, one asset per group and a
    set asset that requires all groups."""
    style = replace(STYLES[args.style], **source.style_overrides)
    set_dir = source.folder  # e.g. us_states
    out = fresh_dir(args.out / set_dir)
    write_shared_asset(args.out)
    write_license(args.out, [cls() for cls in SOURCES.values()])
    regions = select(source.regions(), args.only)
    print(f"{source.title}: {len(regions)} regions, style '{style.name}'")
    textures: set[str] = set()
    entries = {
        r.key: build_region(r, style, out / "models", "", args.cell, textures) for r in regions
    }

    prefix = f"Scale_{source.key}"
    written = []
    for group in source.groups:
        members = [entries[r.key] for r in regions if r.group == group.key]
        if not members:
            continue
        stem = group.key.lower()
        write_group_asset(
            out / f"{stem}.asset", prefix=prefix, group_name=group.name,
            gui_path=f"/Scale Objects/{source.title}", style=style,
            regions=members, attribution=source.attribution,
            reference_radius=REFERENCE_RADIUS,
        )
        written.append((stem, group.name))
        print(f"  {stem}.asset: {group.name}, {len(members)} regions")

    if len(source.groups) == 1:
        # One group is the whole set: its asset (named after the set) is all there is.
        assert written == [(set_dir, source.groups[0].name)], "single group must be named like the set"
        print(f"Wrote {out / (set_dir + '.asset')}")
        return
    write_set_asset(
        out / f"{set_dir}.asset", set_title=source.title, groups=written,
        attribution=source.attribution,
    )
    print(f"Wrote {out / (set_dir + '.asset')} (+ {len(written)} group assets)")


def generate_style_test(source: Source, args) -> None:
    """Each style becomes its own small asset; copies sit side by side, west of home."""
    regions = select(source.regions(), args.only or ["New York"])
    if len(regions) != 1:
        raise SystemExit("style-test takes exactly one region")
    region = regions[0]
    out = fresh_dir(args.out / "style_test")
    write_shared_asset(args.out)
    textures: set[str] = set()

    planar = geo.project_region(region.geometry)
    minx, _, maxx, _ = planar.polygon.bounds
    spacing_deg = np.degrees(
        (maxx - minx) * 1.3 / (REFERENCE_RADIUS * np.cos(np.radians(planar.center_lat)))
    )

    children = []
    for i, style in enumerate(STYLES.values()):
        key = style.name.replace("-", "")
        entry = build_region(region, style, out / "models", f"{key}_", args.cell, textures)
        entry = replace(entry, longitude=entry.longitude - i * spacing_deg)
        name = f"style_{key}"
        write_group_asset(
            out / f"{name}.asset", prefix=f"ScaleStyle_{key}",
            group_name=f"Style test: {style.name}",
            gui_path=f"/Scale Objects/Style test/{style.name}", style=style, regions=[entry],
            attribution=source.attribution, reference_radius=REFERENCE_RADIUS,
            start_enabled=True,
        )
        children.append(name)
        print(f"    {style.name:<10} at lon {entry.longitude:7.2f}: {style.description}")

    (out / "style_test.asset").write_text(
        "-- Loads every style variant of one region, side by side and visible.\n"
        + "".join(f'asset.require("./{c}")\n' for c in children),
        encoding="utf-8",
    )
    print(f"Wrote {out / 'style_test.asset'}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("set", choices=[*SOURCES, "style-test"])
    p.add_argument("--source", default="us-states", choices=SOURCES, help="data for style-test")
    p.add_argument("--only", nargs="+", help="region names, keys or abbreviations")
    p.add_argument("--style", default="glass", choices=STYLES)
    p.add_argument("--cell", type=float, help="mesh grid cell in meters (default: ~20 km, 8 m of chord sag)")
    p.add_argument("--out", type=Path, default=ROOT / "build")
    args = p.parse_args()

    if args.set == "style-test":
        generate_style_test(SOURCES[args.source](), args)
    else:
        generate_set(SOURCES[args.set](), args)


if __name__ == "__main__":
    main()
