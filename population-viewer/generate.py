"""Population Viewer: GeoNames cities as glass columns on Earth, for OpenSpace.

Every place with 1,000+ people is a 2 km x 2 km column standing on Earth at its
location, as tall as its population (default 10 m per 1,000 people, so a city of
1 million is 10 km tall); scales 5x and 10x make them taller and somewhat wider.
Places are split into population bands (10M+, 1M-10M, ... 1k-5k); each band is one
merged model (glass faces and edge frames as two materials) in Earth's body-fixed
frame, so each scale is 8 models no matter how many cities it holds.

  python generate.py                      # scales 1x, 5x, 10x
  python generate.py --meters-per-1000 20 # twice as tall
  python generate.py --no-edges           # faces only (much smaller files)
  python generate.py --scales 1 10:2      # only 1x, and 10x as tall + 2x as wide

Output goes to build/: population-viewer.asset, models/, LICENSE.md. Copy build/ into
${USER_ASSETS}/population-viewer/ (keeping the layout), or pass --out.
"""
from __future__ import annotations

import argparse
import json
import shutil
import struct
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
DATA_URL = "https://download.geonames.org/export/dump/cities1000.zip"
DATA_FILE = ROOT / "data" / "cities1000.zip"

# OpenSpace's Earth (0.22: scene/solarsystem/planets/earth/globe.asset) is the WGS84
# ellipsoid, and its body-fixed frame is the usual ECEF one (x: lat 0 lon 0, z: north
# pole), matching openspace.navigation.localPositionFromGeo. The models are baked
# against these radii; the asset warns at load time if Earth's differ.
EARTH_RADII = (6_378_137.0, 6_356_752.314245)  # equatorial, polar

# Population bands, largest first: (key, lower bound, label). A band holds places from
# its bound up to the next larger band's bound.
BANDS = [
    ("10M", 10_000_000, "10M+"),
    ("1M", 1_000_000, "1M+"),
    ("500k", 500_000, "500k+"),
    ("100k", 100_000, "100k+"),
    ("50k", 50_000, "50k+"),
    ("10k", 10_000, "10k+"),
    ("5k", 5_000, "5k+"),
    ("1k", 1_000, "1k+"),
]

# GeoNames feature codes left out: sections of other places (PPLX: neighborhoods,
# boroughs), and historical, abandoned, destroyed places.
EXCLUDED_CODES = {"PPLX", "PPLH", "PPLQ", "PPLW", "PPLCH"}

# Places whose population figure already includes other listed places. The container
# is kept; the places inside it are dropped so people are not counted twice.
#   geonameid of the container -> rule selecting the places it contains
CONTAINERS = {
    # New York City (8.8M) and its five boroughs (PPLA2)
    5128581: lambda r: r.id in {5110266, 5110302, 5125771, 5133273, 5139568},
    # Shanghai (24.9M, the whole municipality) and every place in it (admin1 23)
    1796236: lambda r: r.country == "CN" and r.admin1 == "23",
}

# Glass look, like scale-objects (translucent faces, brighter edges), but crimson rather
# than cyan: cyan was lost against the ocean, and gold (and coral, white) against the
# deserts of the western US. Baked into each model as two materials (RGBA, alpha =
# opacity); override with --color / --edge-color.
FILL_COLOR = (0.95, 0.2, 0.25, 0.3)
EDGE_COLOR = (1.0, 0.55, 0.55, 0.6)


# --------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------
@dataclass
class Place:
    id: int
    name: str
    code: str
    country: str
    admin1: str
    lat: float
    lon: float
    population: int
    elevation: float  # m, GeoNames "dem" (SRTM3 / GTOPO30); 0 over water


def download() -> Path:
    if not DATA_FILE.exists():
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {DATA_URL}")
        urllib.request.urlretrieve(DATA_URL, DATA_FILE)
    return DATA_FILE


def data_date() -> str:
    """Date GeoNames exported the cities1000 file (from the zip entry), YYYY-MM-DD."""
    with zipfile.ZipFile(download()) as z:
        y, m, d, *_ = z.getinfo("cities1000.txt").date_time
    return f"{y:04d}-{m:02d}-{d:02d}"


def load_places(min_population: int) -> tuple[list[Place], list[Place]]:
    """(places kept, places dropped because a larger place already counts them)."""
    places = []
    with zipfile.ZipFile(download()) as z, z.open("cities1000.txt") as f:
        for line in f:
            c = line.decode("utf-8").rstrip("\n").split("\t")
            pop = int(c[14] or 0)
            if pop < min_population or c[7] in EXCLUDED_CODES:
                continue
            dem = int(c[16]) if c[16] else 0
            places.append(Place(
                id=int(c[0]), name=c[1], code=c[7], country=c[8], admin1=c[10],
                lat=float(c[4]), lon=float(c[5]), population=pop,
                elevation=0.0 if dem == -9999 else float(dem),
            ))
    ids = {p.id for p in places}
    dropped = [
        p for p in places
        if any(cid in ids and cid != p.id and rule(p) for cid, rule in CONTAINERS.items())
    ]
    if dropped:
        drop = {p.id for p in dropped}
        places = [p for p in places if p.id not in drop]
        print(f"Dropped {len(dropped)} places counted in a larger place "
              f"({sum(p.population for p in dropped):,} people)")
    return places, dropped


# --------------------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------------------
# Corners of a column, in local (east, north) units of half its width: bottom 0-3, top
# 4-7, counter-clockwise from south-west seen from above.
SQUARE = np.array([(-1, -1), (1, -1), (1, 1), (-1, 1)], dtype=float)

# Faces with the corner indices around them (no bottom face: it is underground).
FACES = [(4, 5, 6, 7)] + [(i, (i + 1) % 4, (i + 1) % 4 + 4, i + 4) for i in range(4)]


def frames(places: list[Place], radii: tuple[float, float]):
    """Center (on the ellipsoid, height 0) and east / north / up unit vectors of every
    place, in the body-fixed frame (x: lat 0 lon 0, z: north pole). Latitudes are
    geodetic and "up" is the ellipsoid normal, as in OpenSpace's globes."""
    a, b = radii
    e2 = 1.0 - (b / a) ** 2
    lat = np.radians([p.lat for p in places])
    lon = np.radians([p.lon for p in places])
    n = a / np.sqrt(1.0 - e2 * np.sin(lat) ** 2)  # prime vertical radius of curvature
    center = np.stack([n * np.cos(lat) * np.cos(lon), n * np.cos(lat) * np.sin(lon),
                       n * (1.0 - e2) * np.sin(lat)], 1)
    up = np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], 1)
    east = np.stack([-np.sin(lon), np.cos(lon), np.zeros_like(lon)], 1)
    north = np.cross(up, east)
    return center, east, north, up


def local_to_world(center, east, north, up, x, y, z):
    """Local (x east, y north, z up) offsets per place, shape (n, k) -> (n, k, 3)."""
    return (center[:, None, :] + x[..., None] * east[:, None, :]
            + y[..., None] * north[:, None, :] + z[..., None] * up[:, None, :])


def columns(places, heights, args):
    """(positions (n, 8, 3), bottom (n,), top (n,)) of every column, in meters."""
    center, east, north, up = frames(places, args.radii)
    elevation = np.array([p.elevation for p in places])
    bottom = elevation - args.sink
    top = elevation + heights
    half = args.width / 2
    x = np.tile(SQUARE[:, 0] * half, (len(places), 2))
    y = np.tile(SQUARE[:, 1] * half, (len(places), 2))
    z = np.concatenate([np.repeat(bottom[:, None], 4, 1), np.repeat(top[:, None], 4, 1)], 1)
    return local_to_world(center, east, north, up, x, y, z), (center, east, north, up, x, y, z)


def fill_mesh(corners: np.ndarray):
    """Top and side faces of every column: 8 vertices and 10 triangles each."""
    n = len(corners)
    tris = []
    for a, b, c, d in FACES:
        tris += [(a, b, c), (a, c, d)]
    tris = np.array(tris)
    index = tris[None] + 8 * np.arange(n)[:, None, None]
    return corners.reshape(-1, 3), index.reshape(-1, 3)


def edges_mesh(local, heights, args):
    """A frame (band along the border) on each face of every column, so the columns read
    as glass boxes. Per column: the 8 corners plus 4 inner corners per face (28
    vertices), and 8 triangles per face (40).

    The frames float `edge_lift` off their faces (outward on the sides, up on top).
    Coplanar with the faces they z-fight, flickering as the camera moves."""
    center, east, north, up, x, y, z = local
    n = len(x)
    w = args.edge_width
    lift = args.edge_lift
    half = args.width / 2
    # Vertical inset on the side faces: no wider than a third of the visible height.
    wv = np.minimum(w, np.maximum(heights, 0.0) / 3)

    # Outer corners, pushed out of every face they belong to: horizontally away from
    # the column's axis, and the top ones up.
    ox = x + np.sign(x) * lift
    oy = y + np.sign(y) * lift
    oz = z + np.concatenate([np.zeros((n, 4)), np.full((n, 4), lift)], 1)
    xs, ys, zs = [ox], [oy], [oz]  # outer corners first (0-7)
    for fi, face in enumerate(FACES):
        fx, fy, fz = x[:, face], y[:, face], z[:, face]
        # Move each corner towards the face's center: by w along the face's horizontal
        # direction, and (side faces) by wv vertically / (top face) by w along the other
        # horizontal direction. Then lift it off the face along the face's normal.
        cx, cy, cz = fx.mean(1, keepdims=True), fy.mean(1, keepdims=True), fz.mean(1, keepdims=True)
        sx, sy, sz = np.sign(cx - fx), np.sign(cy - fy), np.sign(cz - fz)
        if fi == 0:
            ix, iy, iz = fx + sx * w, fy + sy * w, fz + lift
        else:
            ix, iy = fx + sx * min(w, half), fy + sy * min(w, half)
            iz = fz + sz * wv[:, None]
            # The face's constant coordinate (x or y) is where it sits; push outward.
            ix = ix + (sx == 0) * np.sign(fx) * lift
            iy = iy + (sy == 0) * np.sign(fy) * lift
        xs.append(ix)
        ys.append(iy)
        zs.append(iz)
    vx, vy, vz = (np.concatenate(a, 1) for a in (xs, ys, zs))  # (n, 28)

    tris = []
    for fi, face in enumerate(FACES):
        inner = [8 + 4 * fi + k for k in range(4)]
        for k in range(4):
            q0, q1 = face[k], face[(k + 1) % 4]
            i0, i1 = inner[k], inner[(k + 1) % 4]
            tris += [(q0, q1, i1), (q0, i1, i0)]
    tris = np.array(tris)
    pos = local_to_world(center, east, north, up, vx, vy, vz)
    index = tris[None] + 28 * np.arange(n)[:, None, None]
    return pos.reshape(-1, 3), index.reshape(-1, 3)


# --------------------------------------------------------------------------------------
# GLB
# --------------------------------------------------------------------------------------
@dataclass
class GlbPart:
    """One part of a model: its own material, so parts keep their own color."""
    positions: np.ndarray
    triangles: np.ndarray
    verts_per_col: int  # every column has this many contiguous vertices
    color: tuple[float, float, float, float]  # RGBA, alpha = opacity
    name: str


def write_glb(path: Path, parts: list[GlbPart]) -> None:
    """Positions + indices only (unlit), one material per part. Parts are split into
    primitives of at most 65,536 vertices so indices fit in uint16; splits fall between
    columns."""
    blobs: list[bytes] = []
    views, accessors, primitives, materials = [], [], [], []

    def add(data: np.ndarray, target: int, accessor: dict) -> int:
        offset = sum(len(b) for b in blobs)
        raw = data.tobytes()
        blobs.append(raw + b"\x00" * (-len(raw) % 4))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(raw), "target": target})
        accessors.append({"bufferView": len(views) - 1, **accessor})
        return len(accessors) - 1

    for part in parts:
        materials.append({
            "name": part.name,
            "pbrMetallicRoughness": {
                "baseColorFactor": list(part.color), "metallicFactor": 0.0,
                "roughnessFactor": 1.0,
            },
            "alphaMode": "BLEND" if part.color[3] < 1.0 else "OPAQUE",
            "doubleSided": True,
        })
        vpc = part.verts_per_col
        ncols = len(part.positions) // vpc
        if ncols == 0:
            continue
        k = 65536 // vpc
        tris_per_col = len(part.triangles) // ncols
        for start in range(0, ncols, k):
            stop = min(ncols, start + k)
            pos = np.ascontiguousarray(part.positions[start * vpc:stop * vpc], np.float32)
            tri = part.triangles[start * tris_per_col:stop * tris_per_col] - start * vpc
            idx = np.ascontiguousarray(tri, np.uint16).ravel()
            p = add(pos, 34962, {
                "componentType": 5126, "count": len(pos), "type": "VEC3",
                "min": pos.min(0).tolist(), "max": pos.max(0).tolist(),
            })
            i = add(idx, 34963, {"componentType": 5123, "count": len(idx), "type": "SCALAR"})
            primitives.append({
                "attributes": {"POSITION": p}, "indices": i, "material": len(materials) - 1,
            })

    binary = b"".join(blobs)
    gltf = {
        "asset": {"version": "2.0", "generator": "population-viewer"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": path.stem}],
        "meshes": [{"name": path.stem, "primitives": primitives}],
        "materials": materials,
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": views,
        "accessors": accessors,
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(binary)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(binary), 0x004E4942) + binary)


# --------------------------------------------------------------------------------------
# Asset
# --------------------------------------------------------------------------------------
def lua(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        return repr(round(float(v), 6))
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(v, (list, tuple)):
        return "{ " + ", ".join(lua(x) for x in v) + " }"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {lua(x)}" for k, x in v.items()) + " }"
    raise TypeError(type(v))


def parse_scale(text: str) -> tuple[float, float]:
    """"100:10" -> (100, 10): height and width factors. "10" -> (10, 1)."""
    height, _, width = text.partition(":")
    return float(height), float(width or 1)


def fmt_pop(n: int) -> str:
    for div, suffix in ((1_000_000, "M"), (1_000, "k")):
        if n >= div:
            v = n / div
            return f"{v:.0f}{suffix}" if v == int(v) else f"{v:.1f}{suffix}"
    return str(n)


def write_asset(out: Path, bands: list[dict], args) -> None:
    template = (ROOT / "lua" / "population-viewer.asset").read_text(encoding="utf-8")
    rows = ",\n".join("  " + lua(b) for b in bands)
    text = (template
            .replace("--[[BANDS]]", rows)
            .replace("--[[RADII]]", lua(list(args.radii)))
            .replace("--[[METERS_PER_1000]]", lua(args.meters_per_1000))
            .replace("--[[WIDTH]]", lua(args.width))
            .replace("--[[DEFAULT_SCALE]]",
                     lua(1 + [h for h, _ in args.scales].index(args.default_scale)))
            .replace("--[[SCALES]]", lua([
                {"Height": float(h), "Width": float(w)} for h, w in args.scales
            ])))
    (out / "population-viewer.asset").write_text(text, encoding="utf-8")


def write_license(out: Path) -> None:
    (out / "LICENSE.md").write_text(
        "# Population Viewer: licenses\n\n"
        "The OpenSpace asset (`population-viewer.asset`) is released under the MIT\n"
        "license, like OpenSpace itself.\n\n"
        "## Population data (`models/`)\n\n"
        "- Source: GeoNames, `cities1000` (all places with 1,000+ people)\n"
        f"- Download: {DATA_URL}\n"
        "- Terms: Creative Commons Attribution 4.0 (CC BY 4.0),\n"
        "  https://creativecommons.org/licenses/by/4.0/\n"
        "- Attribution: population data from GeoNames (https://www.geonames.org/),\n"
        "  licensed under CC BY 4.0. The models are an adaptation: each place is drawn as\n"
        "  a column whose height is proportional to its population.\n",
        encoding="utf-8",
    )


def write_readme(out: Path, bands: list[dict], places: list[Place], dropped: list[Place],
                 args) -> None:
    """README.md for people installing the built asset (e.g. from the OpenSpace hub):
    what it shows, how to use it, and where the data comes from."""
    default = next((h, w) for h, w in args.scales if h == args.default_scale)
    scale_rows = "\n".join(
        f"| {h:g}x{' (default)' if (h, w) == default else ''} | "
        f"{args.width * w / 1000:g} km | {args.meters_per_1000 * h:g} m | "
        f"{args.meters_per_1000 * h:g} km |"
        for h, w in args.scales
    )
    band_rows = "\n".join(
        f"| {b['Range']} | {b['Count']:,} | {b['Largest']} |" for b in bands
    )
    containers = [p for p in places if p.id in CONTAINERS]
    lines = f"""# Population Viewer

Every place on Earth with at least 1,000 people, {len(places):,} in all, drawn as a
translucent crimson column standing at its location, as tall as its population. Dense
regions build up where columns overlap, so you can read population density at a glance.

## Installing

Copy this folder into `${{USER_ASSETS}}/population-viewer/` (keep `models/` next to the
asset) and add `${{USER_ASSETS}}/population-viewer/population-viewer` in OpenSpace. Built
for OpenSpace 0.22 and its WGS84 Earth (`scene/solarsystem/planets/earth/globe`); the
asset warns on load if Earth's shape differs.

## Using it

Everything starts hidden. Actions under **Population Viewer**:

- **Show cities with 10M+ / 1M+ / 500k+ / 100k+ / 50k+ / 10k+ / 5k+ / 1k+ people**:
  shows every place at or above that population and hides smaller ones.
- **Hide all cities**
- **Settings > Scale 1x / 5x / 10x (Locks Rendering)**: column size. Larger scales can
  be seen from further out. Switching loads new models, so rendering pauses briefly.

| Scale | Width | Height per 1,000 people | A city of 1 million |
|---|---|---|---|
{scale_rows}

Height is proportional to population, so columns compare directly: a city twice as
large is twice as tall. Each column starts at the ground elevation of its place.

## Data

**Source:** GeoNames, `cities1000`: all populated places with at least 1,000 people.

- Download: {DATA_URL}
- Version used: the file GeoNames exported on {data_date()}. GeoNames rebuilds it daily;
  the populations inside are not all that recent, but from censuses and estimates of
  many different years (e.g. New York City's is the 2020 US census count).
- License: Creative Commons Attribution 4.0 (CC BY 4.0),
  https://creativecommons.org/licenses/by/4.0/ (see `LICENSE.md`)
- Attribution: *Population data from GeoNames (https://www.geonames.org/), CC BY 4.0.*
  The columns are an adaptation of it: positions, populations and ground elevations
  are GeoNames' own; the shapes and heights are derived from them.

Each place uses GeoNames' latitude and longitude, its population, and its ground
elevation (GeoNames' `dem` field, from SRTM3 or GTOPO30 elevation data).

**Left out:**

- Sections of other places (feature code `PPLX`, e.g. neighborhoods and boroughs), and
  historical, abandoned or destroyed places (`PPLH`, `PPLQ`, `PPLW`, `PPLCH`).
- Places under 1,000 people.
- {len(dropped)} places inside {" and ".join(f"{c.name} ({c.population:,})" for c in containers)},
  whose populations already include them (e.g. New York's five boroughs), so no one is
  counted twice.

**Caveats:** GeoNames populations come from many sources and years, and do not all mean
the same thing. Some are city proper (Tokyo's 9.7 million is only its 23 wards), others
whole municipalities or prefectures (Chongqing's 22 million covers an area the size of
a province). Neighboring cities in one metro area (Cairo and Giza, Mumbai and Thane) are
separate columns. Read the columns as an overview of where people live, not a census.

**Places by population band:**

| Population | Places | Largest |
|---|---|---|
{band_rows}

Generated by `population-viewer/generate.py` (OpenSpace scripts repository).
"""
    (out / "README.md").write_text(lines, encoding="utf-8")


# --------------------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--meters-per-1000", type=float, default=10.0,
                   help="column height per 1,000 people at scale 1, m (default 10: 1M people = 10 km)")
    p.add_argument("--width", type=float, default=2000.0, help="column width at scale 1, m")
    p.add_argument("--sink", type=float, default=200.0,
                   help="m the columns reach below the ground, so uneven terrain never "
                        "shows a gap under them")
    p.add_argument("--edge-width", type=float, default=80.0, help="width of the edge bands at scale 1, m")
    p.add_argument("--edge-lift", type=float, default=40.0,
                   help="how far the edge frames float off the faces at scale 1, m; keeps "
                        "them from z-fighting with the faces (flicker)")
    p.add_argument("--no-edges", action="store_true", help="fill only")
    p.add_argument("--color", type=float, nargs=4, default=FILL_COLOR, metavar=("R", "G", "B", "A"),
                   help="face color and opacity, 0-1 (default crimson, 0.3 opaque)")
    p.add_argument("--edge-color", type=float, nargs=4, default=EDGE_COLOR, metavar=("R", "G", "B", "A"),
                   help="edge frame color and opacity, 0-1 (default light red, 0.6 opaque)")
    p.add_argument("--scales", type=parse_scale, nargs="+",
                   default=[(1, 1), (5, 2.5), (10, 5)],
                   help="column scales to build, switchable at runtime, as HEIGHT:WIDTH "
                        "factors (default 1:1 5:2.5 10:5, i.e. 10x as tall and 5x as "
                        "wide); HEIGHT alone keeps the width")
    p.add_argument("--default-scale", type=float, default=10.0,
                   help="height factor of the scale loaded with the asset (default 10)")
    p.add_argument("--radii", type=float, nargs=2, default=EARTH_RADII,
                   metavar=("EQUATORIAL", "POLAR"),
                   help="radii of OpenSpace's Earth, m (default WGS84; give the same "
                        "value twice for a sphere)")
    p.add_argument("--out", type=Path, default=ROOT / "build")
    args = p.parse_args()
    heights = [h for h, _ in args.scales]
    if args.default_scale not in heights:
        p.error(f"--default-scale {args.default_scale:g} is not one of the --scales heights "
                f"({', '.join(f'{h:g}' for h in heights)})")

    places, dropped = load_places(BANDS[-1][1])
    print(f"{len(places):,} places with {BANDS[-1][1]:,}+ people")

    if args.out.exists():
        shutil.rmtree(args.out)
    models = args.out / "models"
    models.mkdir(parents=True)

    bands = []
    upper = None
    for key, lower, label in BANDS:
        members = [q for q in places if q.population >= lower and (upper is None or q.population < upper)]
        members.sort(key=lambda q: -q.population)
        heights = np.array([q.population for q in members], float) * args.meters_per_1000 / 1000

        # One set of models per scale: height times `scale`, width (and edges) times
        # `widen`. The sink grows by how far the ground curves away below the column's
        # corners, so wide columns still reach into the ground.
        files = {}
        for scale, widen in args.scales:
            half_diagonal = args.width * widen / np.sqrt(2)
            s = argparse.Namespace(**{
                **vars(args),
                "width": args.width * widen,
                "edge_width": args.edge_width * widen,
                "edge_lift": args.edge_lift * widen,
                "sink": args.sink + half_diagonal ** 2 / (2 * args.radii[1]),
            })
            corners, local = columns(members, heights * scale, s)
            # Faces first, then the edge frames drawn over them (same planes).
            pos, tri = fill_mesh(corners)
            parts = [GlbPart(pos, tri, 8, tuple(args.color), "fill")]
            if not args.no_edges:
                pos, tri = edges_mesh(local, heights * scale, s)
                parts.append(GlbPart(pos, tri, 28, tuple(args.edge_color), "edges"))
            name = f"cities_{key.lower()}_x{scale:g}.glb"
            write_glb(models / name, parts)
            files[f"x{scale:g}"] = name

        rng = f"{fmt_pop(lower)}+" if upper is None else f"{fmt_pop(lower)} to {fmt_pop(upper)}"
        largest = ", ".join(q.name for q in members[:3])
        size = sum((models / f).stat().st_size for f in files.values()) / 1e6
        print(f"  {label:>6}: {len(members):>6,} places ({rng}), {size:6.1f} MB. {largest}")
        bands.append({
            "Key": key,
            "Label": label,
            "Lower": lower,
            "Range": rng,
            "Count": len(members),
            "Largest": largest,
            "Models": files,
        })
        upper = lower

    write_asset(args.out, bands, args)
    write_license(args.out)
    write_readme(args.out, bands, places, dropped, args)
    total = sum(f.stat().st_size for f in models.iterdir()) / 1e6
    print(f"Wrote {args.out / 'population-viewer.asset'} ({total:.0f} MB of models)")


if __name__ == "__main__":
    main()
