"""Build a region's Fill / Grid / Outline meshes for a style.

The planar work (projection, clipping, triangulation) is done once per region; only
the cheap lift onto a sphere is repeated per body.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import geometry as geo
from .styles import Part, Style

PART_NAMES = ("Fill", "Grid", "Outline")


@dataclass
class PreparedRegion:
    planar: geo.PlanarRegion
    style: Style
    cell: float
    fill: geo.PlaneMesh | None
    grid: geo.PlaneMesh | None
    outline_band: geo.PlaneMesh | None
    outline_wall: geo.RimMesh | None

    def meshes(self, radius: float) -> dict[str, tuple[geo.Mesh3D, Part]]:
        s = self.style
        out = {}
        if self.fill is not None:
            out["Fill"] = (geo.build_fill(self.fill, radius, s.fill_height, s.texture_tile), s.fill)
        if self.grid is not None:
            out["Grid"] = (geo.build_fill(self.grid, radius, s.fill_height + s.grid_lift, s.texture_tile), s.grid)
        if self.outline_band is not None:
            out["Outline"] = (
                geo.build_fill(self.outline_band, radius, s.fill_height + s.outline_lift, s.texture_tile),
                s.outline,
            )
        elif self.outline_wall is not None:
            out["Outline"] = (geo.build_rim(self.outline_wall, radius, s.outline_bottom, s.outline_top), s.outline)
        return out


def prepare(geometry_lonlat, style: Style, cell: float | None = None) -> PreparedRegion:
    planar = geo.project_region(geometry_lonlat, style.simplify)
    cell = cell or geo.default_cell_size()

    fill = geo.mesh_plane(planar, cell) if style.fill.enabled else None

    grid = None
    if style.grid.enabled:
        g = geo.grid_region(planar, style.grid_spacing, style.grid_width)
        if g is not None:
            grid = geo.mesh_plane(g, cell)

    band = wall = None
    if style.outline.enabled:
        if style.outline_mode == "band":
            width = style.outline_width or geo.default_outline_width(
                planar, style.outline_min, style.outline_max
            )
            b = geo.outline_band(planar, width, style.simplify)
            if b is not None:
                band = geo.mesh_plane(b, cell)
        elif style.outline_mode == "wall":
            wall = geo.rim_rings(planar, cell)
        else:
            raise ValueError(f"unknown outline_mode {style.outline_mode!r}")

    return PreparedRegion(planar, style, cell, fill, grid, band, wall)
