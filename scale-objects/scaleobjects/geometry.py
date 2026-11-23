"""Turn a lon/lat outline into curved meshes for a scale-comparison region.

Pipeline
--------
1. Find the region's center and project it with a spherical Lambert azimuthal
   equal-area (LAEA) projection centered there. Area is preserved exactly on the
   plane, shape distortion is small for anything country-sized or smaller, and
   pieces split at the antimeridian join up again on the plane.
2. Mesh the plane polygon: clip it against a square grid so no triangle is larger
   than one grid cell, triangulate each clipped cell with earcut and weld vertices.
3. Lift the plane mesh onto a sphere of the *target* body's radius with the inverse
   LAEA. That keeps the area exact on whatever body the region is placed on, and
   curves the mesh so it hugs that body's surface instead of floating above it at the
   edges (Texas laid out flat would sit ~28 km above Earth at its edges, ~53 km above Mars).

The lifted mesh is expressed in a local frame at the region's center: east, north,
up (meters), origin on the sphere's surface. Mapping that to the model axes that
OpenSpace's GlobeRotation expects is done in `enu_to_model`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import mapbox_earcut as earcut
import numpy as np
import shapely
from shapely.geometry import MultiPolygon, Polygon

# Authalic (equal-area) radius of the WGS84 ellipsoid. Using it for the forward
# projection means areas on the plane match areas on the real Earth.
EARTH_AUTHALIC_RADIUS = 6371007.2


# --------------------------------------------------------------------------------------
# Projection
# --------------------------------------------------------------------------------------
def laea_forward(lon, lat, lon0, lat0, radius=EARTH_AUTHALIC_RADIUS):
    """Spherical LAEA, degrees in, meters out (x east, y north)."""
    lam = np.radians(np.asarray(lon, dtype=float) - lon0)
    phi = np.radians(np.asarray(lat, dtype=float))
    phi0 = np.radians(lat0)
    cos_c = np.sin(phi0) * np.sin(phi) + np.cos(phi0) * np.cos(phi) * np.cos(lam)
    k = np.sqrt(2.0 / np.maximum(1.0 + cos_c, 1e-12))
    x = radius * k * np.cos(phi) * np.sin(lam)
    y = radius * k * (np.cos(phi0) * np.sin(phi) - np.sin(phi0) * np.cos(phi) * np.cos(lam))
    return x, y


def laea_inverse(x, y, lon0, lat0, radius=EARTH_AUTHALIC_RADIUS):
    """Inverse of `laea_forward`, meters in, degrees out."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    rho = np.hypot(x, y)
    c = 2.0 * np.arcsin(np.clip(rho / (2.0 * radius), -1.0, 1.0))
    phi0 = np.radians(lat0)
    safe_rho = np.where(rho == 0, 1.0, rho)
    phi = np.arcsin(np.cos(c) * np.sin(phi0) + y * np.sin(c) * np.cos(phi0) / safe_rho)
    lam = np.arctan2(
        x * np.sin(c), safe_rho * np.cos(phi0) * np.cos(c) - y * np.sin(phi0) * np.sin(c)
    )
    phi = np.where(rho == 0, phi0, phi)
    lam = np.where(rho == 0, 0.0, lam)
    lon = (np.degrees(lam) + lon0 + 180.0) % 360.0 - 180.0
    return lon, np.degrees(phi)


def lift_to_sphere(xy: np.ndarray, height: float | np.ndarray, radius: float) -> np.ndarray:
    """Plane LAEA coordinates -> local ENU on a sphere of `radius`.

    The origin is the sphere surface under the projection center; `height` is
    meters above that sphere. Returns (N, 3) east, north, up.
    """
    rho = np.hypot(xy[:, 0], xy[:, 1])
    c = 2.0 * np.arcsin(np.clip(rho / (2.0 * radius), 0.0, 1.0))
    safe = np.where(rho == 0, 1.0, rho)
    dx, dy = xy[:, 0] / safe, xy[:, 1] / safe
    r = radius + np.broadcast_to(height, rho.shape)
    s = r * np.sin(c)
    return np.column_stack([s * dx, s * dy, r * np.cos(c) - radius])


def enu_to_model(enu: np.ndarray) -> np.ndarray:
    """Local east/north/up -> model axes used by RenderableModel under GlobeRotation.

    Measured in OpenSpace 0.22.1 from the world rotation of a GlobeRotation node:
    +Y is the surface normal, +X points south and +Z points west.
    """
    e, n, u = enu[:, 0], enu[:, 1], enu[:, 2]
    return np.column_stack([-n, u, -e])


# --------------------------------------------------------------------------------------
# Planar region
# --------------------------------------------------------------------------------------
@dataclass
class PlanarRegion:
    """A region projected to its own LAEA plane."""

    polygon: MultiPolygon  # meters, x east / y north
    center_lon: float
    center_lat: float

    @property
    def area_m2(self) -> float:
        return float(self.polygon.area)

    @property
    def max_radius_m(self) -> float:
        """Farthest point from the center, used to check it fits on a small body."""
        coords = shapely.get_coordinates(self.polygon)
        return float(np.hypot(coords[:, 0], coords[:, 1]).max())


def _as_multipolygon(geom) -> MultiPolygon:
    polys = [g for g in getattr(geom, "geoms", [geom]) if isinstance(g, (Polygon, MultiPolygon))]
    flat = []
    for p in polys:
        flat.extend(p.geoms if isinstance(p, MultiPolygon) else [p])
    return MultiPolygon([p for p in flat if not p.is_empty and p.area > 0])


def _project(geom_lonlat, lon0: float, lat0: float):
    def fn(coords):
        x, y = laea_forward(coords[:, 0], coords[:, 1], lon0, lat0)
        return np.column_stack([x, y])

    return shapely.transform(geom_lonlat, fn)


def drop_far_parts(geom_lonlat, max_gap_km: float, archipelago_share: float = 0.5):
    """Leave out parts more than `max_gap_km` from the rest of a region.

    Starting from the largest part, any part within the gap of a part already kept is
    kept too, so island chains stay together. Regions whose largest part is less than
    `archipelago_share` of the land (Kiribati, Indonesia) keep everything: they have no
    mainland to measure from. Distances are measured on an LAEA plane centered on the
    largest part. Returns (geometry, dropped area in km2).
    """
    parts = list(getattr(geom_lonlat, "geoms", [geom_lonlat]))
    if len(parts) < 2:
        return geom_lonlat, 0.0
    main = max(range(len(parts)), key=lambda i: parts[i].area)
    c = parts[main].representative_point()
    plane = [_project(p, c.x, c.y) for p in parts]
    areas = np.array([p.area for p in plane])
    if areas[main] < archipelago_share * areas.sum():
        return geom_lonlat, 0.0

    tree = shapely.STRtree(plane)
    keep, todo = {main}, [main]
    while todo:
        i = todo.pop()
        for j in tree.query(plane[i], predicate="dwithin", distance=max_gap_km * 1000.0):
            if int(j) not in keep:
                keep.add(int(j))
                todo.append(int(j))
    dropped = float(sum(areas[i] for i in range(len(parts)) if i not in keep)) / 1e6
    return MultiPolygon([parts[i] for i in sorted(keep)]), dropped


SIMPLIFY_M = 250.0


def project_region(geom_lonlat, simplify: float = SIMPLIFY_M) -> PlanarRegion:
    """Project a lon/lat (Multi)Polygon to an LAEA plane centered on its area centroid.

    The border is then simplified by `simplify` meters (Douglas-Peucker, topology kept).
    250 m is below the accuracy of 1:5M-1:10M boundary data, changes areas by at most
    ~0.01 %, and drops 30-90 % of the border points, which drive the outline's size.
    """
    # First guess: mean of vertex unit vectors (robust across the antimeridian).
    coords = np.radians(shapely.get_coordinates(geom_lonlat))
    v = np.column_stack(
        [np.cos(coords[:, 1]) * np.cos(coords[:, 0]),
         np.cos(coords[:, 1]) * np.sin(coords[:, 0]),
         np.sin(coords[:, 1])]
    ).mean(axis=0)
    lon0 = float(np.degrees(np.arctan2(v[1], v[0])))
    lat0 = float(np.degrees(np.arcsin(v[2] / np.linalg.norm(v))))

    # Refine twice with the true area centroid on the plane (vertex density biases
    # the first guess toward detailed coastlines).
    for _ in range(2):
        plane = shapely.make_valid(_project(geom_lonlat, lon0, lat0))
        plane = shapely.union_all(plane)  # also merges antimeridian-split pieces
        cx, cy = plane.centroid.x, plane.centroid.y
        lon, lat = laea_inverse(cx, cy, lon0, lat0)
        lon0, lat0 = float(lon), float(lat)

    plane = shapely.union_all(shapely.make_valid(_project(geom_lonlat, lon0, lat0)))
    if simplify > 0:
        plane = shapely.make_valid(shapely.simplify(plane, simplify, preserve_topology=True))
    return PlanarRegion(_as_multipolygon(plane), lon0, lat0)


MAX_SAG_M = 8.0


def default_cell_size(radius: float = 6_371_008.8, max_sag: float = MAX_SAG_M) -> float:
    """Grid cell size in meters, from how far a triangle may dip below the sphere.

    The only reason the interior is split into cells is curvature: a chord of length L
    sags L^2 / (8 R) below the sphere. 8 m of sag on the reference sphere gives ~20 km
    cells; the runtime vertical scale multiplies the sag by R_ref / R_globe, so ~30 m on
    the Moon and ~15 m on Mars, far below the 500 m the regions float above the ground.
    The border keeps all of its own points regardless of the cell size.
    """
    return float(np.sqrt(8.0 * radius * max_sag))


# --------------------------------------------------------------------------------------
# Meshing (on the plane)
# --------------------------------------------------------------------------------------
@dataclass
class PlaneMesh:
    vertices: np.ndarray  # (N, 2) plane meters
    triangles: np.ndarray  # (M, 3) int


@dataclass
class RimMesh:
    """Boundary rings, densified, for the wall/fence along the border."""

    rings: list[np.ndarray] = field(default_factory=list)  # each (K, 2), closed


def _earcut_polygon(poly: Polygon):
    rings = [np.asarray(poly.exterior.coords)[:-1]]
    rings += [np.asarray(r.coords)[:-1] for r in poly.interiors]
    rings = [r for r in rings if len(r) >= 3]
    if not rings:
        return None, None
    verts = np.vstack(rings)
    ends = np.cumsum([len(r) for r in rings]).astype(np.uint32)
    tris = earcut.triangulate_float64(verts, ends).reshape(-1, 3)
    return verts, tris


def mesh_plane(region: PlanarRegion, cell: float) -> PlaneMesh:
    poly = region.polygon
    shapely.prepare(poly)
    minx, miny, maxx, maxy = poly.bounds
    xs = np.arange(np.floor(minx / cell) * cell, maxx + cell, cell)
    ys = np.arange(np.floor(miny / cell) * cell, maxy + cell, cell)
    gx, gy = np.meshgrid(xs[:-1], ys[:-1])
    gx, gy = gx.ravel(), gy.ravel()
    boxes = shapely.box(gx, gy, gx + cell, gy + cell)

    inside = shapely.contains_properly(poly, boxes)
    partial = shapely.intersects(poly, boxes) & ~inside

    all_verts: list[np.ndarray] = []
    all_tris: list[np.ndarray] = []
    offset = 0

    # Whole cells: two triangles each, done in bulk.
    if inside.any():
        x0, y0 = gx[inside], gy[inside]
        n = len(x0)
        quad = np.stack(
            [np.column_stack([x0, y0]), np.column_stack([x0 + cell, y0]),
             np.column_stack([x0 + cell, y0 + cell]), np.column_stack([x0, y0 + cell])],
            axis=1,
        ).reshape(-1, 2)
        base = np.arange(n)[:, None] * 4
        tris = np.concatenate([base + [0, 1, 2], base + [0, 2, 3]])
        all_verts.append(quad)
        all_tris.append(tris)
        offset += len(quad)

    # Cells cut by the border: clip and triangulate.
    for piece in shapely.intersection(boxes[partial], poly):
        for p in _as_multipolygon(piece).geoms:
            verts, tris = _earcut_polygon(p)
            if verts is None or len(tris) == 0:
                continue
            all_verts.append(verts)
            all_tris.append(tris + offset)
            offset += len(verts)

    verts = np.vstack(all_verts)
    tris = np.vstack(all_tris)

    # Weld shared vertices (cell corners, border crossings) to 1 mm.
    key = np.round(verts * 1000.0).astype(np.int64)
    _, first, inverse = np.unique(key, axis=0, return_index=True, return_inverse=True)
    verts = verts[first]
    tris = inverse.reshape(-1)[tris]
    # Drop triangles that collapsed in welding.
    ok = (tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 0] != tris[:, 2])
    return PlaneMesh(verts, tris[ok])


def rim_rings(region: PlanarRegion, cell: float) -> RimMesh:
    """Border rings densified to `cell` so the wall follows the curvature too."""
    dense = _as_multipolygon(shapely.segmentize(region.polygon, cell))
    rings = []
    for p in dense.geoms:
        rings.append(np.asarray(p.exterior.coords))
        rings.extend(np.asarray(r.coords) for r in p.interiors)
    return RimMesh(rings)


# --------------------------------------------------------------------------------------
# 3D meshes on a target body
# --------------------------------------------------------------------------------------
@dataclass
class Mesh3D:
    positions: np.ndarray  # (N, 3) model space, meters
    normals: np.ndarray  # (N, 3)
    uvs: np.ndarray  # (N, 2)
    triangles: np.ndarray  # (M, 3)


def _sphere_normals(enu: np.ndarray, radius: float) -> np.ndarray:
    p = enu + np.array([0.0, 0.0, radius])
    return p / np.linalg.norm(p, axis=1, keepdims=True)


def build_fill(plane: PlaneMesh, radius: float, height: float, uv_scale: float) -> Mesh3D:
    """Top surface draped at `height` m above a sphere of `radius`.

    UVs are plane meters / `uv_scale`, so a texture repeats every `uv_scale` meters,
    keeping the pattern the same real-world size on every region.
    """
    enu = lift_to_sphere(plane.vertices, height, radius)
    pos = enu_to_model(enu)
    nrm = enu_to_model(_sphere_normals(enu, radius))
    uv = plane.vertices / uv_scale
    return Mesh3D(pos, nrm, uv, plane.triangles.copy())


def build_rim(rim: RimMesh, radius: float, bottom: float, top: float) -> Mesh3D:
    """A wall along the border between heights `bottom` and `top` (meters).

    V runs 0 (bottom) -> 1 (top); U is distance along the border in km.
    """
    positions, normals, uvs, tris = [], [], [], []
    offset = 0
    for ring in rim.rings:
        n = len(ring)
        if n < 2:
            continue
        lo = lift_to_sphere(ring, bottom, radius)
        hi = lift_to_sphere(ring, top, radius)
        # Outward horizontal normal from the edge direction (rings may be either
        # winding; rendering is two-sided so only shading direction is affected).
        d = np.gradient(ring, axis=0)
        out2 = np.column_stack([d[:, 1], -d[:, 0]])
        out2 /= np.maximum(np.linalg.norm(out2, axis=1, keepdims=True), 1e-9)
        nrm_enu = np.column_stack([out2, np.zeros(n)])
        along = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(ring, axis=0).T))]) / 1000.0

        positions += [enu_to_model(lo), enu_to_model(hi)]
        normals += [enu_to_model(nrm_enu)] * 2
        uvs += [np.column_stack([along, np.zeros(n)]), np.column_stack([along, np.ones(n)])]
        i = np.arange(n - 1)
        a, b, c, d_ = offset + i, offset + i + 1, offset + n + i + 1, offset + n + i
        tris.append(np.concatenate([np.column_stack([a, b, c]), np.column_stack([a, c, d_])]))
        offset += 2 * n
    return Mesh3D(np.vstack(positions), np.vstack(normals), np.vstack(uvs), np.vstack(tris))


def grid_region(region: PlanarRegion, spacing: float, width: float) -> PlanarRegion | None:
    """Strips `width` wide every `spacing` meters (through the center), clipped to the region.

    Returned as a PlanarRegion so it is meshed and draped exactly like the fill.
    """
    minx, miny, maxx, maxy = region.polygon.bounds
    h = width / 2.0
    strips = []
    for k in range(int(np.floor(minx / spacing)), int(np.ceil(maxx / spacing)) + 1):
        x = k * spacing
        strips.append(shapely.box(x - h, miny - h, x + h, maxy + h))
    for k in range(int(np.floor(miny / spacing)), int(np.ceil(maxy / spacing)) + 1):
        y = k * spacing
        strips.append(shapely.box(minx - h, y - h, maxx + h, y + h))
    lines = shapely.intersection(shapely.union_all(strips), region.polygon)
    lines = _as_multipolygon(lines)
    if lines.is_empty:
        return None
    return PlanarRegion(lines, region.center_lon, region.center_lat)


def default_outline_width(region: PlanarRegion, lo: float = 1_500.0, hi: float = 6_000.0) -> float:
    """~1% of the region's size, kept between `lo` and `hi` meters."""
    return float(np.clip(np.sqrt(region.area_m2) / 100.0, lo, hi))


def outline_band(region: PlanarRegion, width: float, simplify: float = SIMPLIFY_M) -> PlanarRegion | None:
    """A flat strip `width` meters wide running just inside the border."""
    # The inner edge only needs to look parallel to the border: mitred corners instead
    # of round ones, then the same simplification the border had.
    inner = region.polygon.buffer(-width, join_style="mitre", mitre_limit=2.0)
    inner = shapely.simplify(inner, simplify, preserve_topology=True)
    band = _as_multipolygon(shapely.make_valid(region.polygon.difference(inner)))
    if band.is_empty:
        return None
    return PlanarRegion(band, region.center_lon, region.center_lat)
