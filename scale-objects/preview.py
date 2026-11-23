"""Quick offline preview of every style for one region (matplotlib, not OpenSpace).

This approximates colors, opacity and shapes so a style can be picked without starting
OpenSpace; the real look (lighting, terrain, atmosphere) needs a check in OpenSpace.

  python preview.py "New York" --body Earth --out build/style_preview.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from generate import REFERENCE_RADIUS, select
from scaleobjects import geometry as geo
from scaleobjects.parts import prepare
from scaleobjects.sources import USStates
from scaleobjects.styles import STYLES

GROUND = (0.22, 0.30, 0.22)
SUN = np.array([0.4, -0.6, 0.7]) / np.linalg.norm([0.4, -0.6, 0.7])


def to_view(p: np.ndarray, exaggerate: float) -> np.ndarray:
    """Model (x east, y up, z south) -> plot (east, north, up*exaggerate) in km."""
    return np.column_stack([p[:, 0], -p[:, 2], p[:, 1] * exaggerate]) / 1000.0


def face_colors(mesh: geo.Mesh3D, part, tile_m: float) -> np.ndarray:
    n = len(mesh.triangles)
    rgb = np.tile(np.array(part.color, dtype=float), (n, 1))
    if part.texture == "grid100km":
        uv = mesh.uvs[mesh.triangles].mean(axis=1)
        frac = np.abs(uv - np.round(uv))
        line = (frac < 0.03).any(axis=1)
        rgb = np.where(line[:, None], [1.0, 1.0, 1.0], [0.92, 0.47, 0.1])
    if part.shading:
        nrm = mesh.normals[mesh.triangles].mean(axis=1)
        nrm = np.column_stack([nrm[:, 0], -nrm[:, 2], nrm[:, 1]])
        light = 0.35 + 0.65 * np.clip(np.abs(nrm @ SUN), 0, 1)
        rgb = rgb * light[:, None]
    return np.column_stack([np.clip(rgb, 0, 1), np.full(n, part.opacity)])


def draw(ax, region, style, radius: float, exaggerate: float) -> None:
    prepared = prepare(region.geometry, style)
    planar = prepared.planar

    # Ground: the body's sphere, slightly larger than the region, as a dull surface.
    minx, miny, maxx, maxy = planar.polygon.bounds
    pad = 0.15 * max(maxx - minx, maxy - miny)
    gx, gy = np.meshgrid(np.linspace(minx - pad, maxx + pad, 30), np.linspace(miny - pad, maxy + pad, 30))
    g = to_view(geo.enu_to_model(geo.lift_to_sphere(np.column_stack([gx.ravel(), gy.ravel()]), -50.0, radius)), exaggerate)
    ax.plot_surface(g[:, 0].reshape(gx.shape), g[:, 1].reshape(gx.shape), g[:, 2].reshape(gx.shape),
                    color=GROUND, shade=False, linewidth=0, alpha=1.0, zorder=0)

    for z, (mesh, part) in enumerate(prepared.meshes(radius).values(), start=1):
        v = to_view(mesh.positions, exaggerate)[mesh.triangles]
        fc = face_colors(mesh, part, style.texture_tile)
        if part.wireframe:
            pc = Poly3DCollection(v, facecolors=(0, 0, 0, 0), edgecolors=fc, linewidths=0.15, zorder=z)
        else:
            pc = Poly3DCollection(v, facecolors=fc, edgecolors="none", zorder=z)
        ax.add_collection3d(pc)

    ax.set_xlim(g[:, 0].min(), g[:, 0].max())
    ax.set_ylim(g[:, 1].min(), g[:, 1].max())
    ax.set_zlim(g[:, 2].min(), max(g[:, 2].max(), 30 * exaggerate))
    ax.set_box_aspect((1, np.ptp(g[:, 1]) / np.ptp(g[:, 0]), 0.25))
    ax.view_init(elev=38, azim=-70)
    ax.set_axis_off()
    ax.set_title(f"{style.name}\n{style.description}", fontsize=8, wrap=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("region", nargs="?", default="New York")
    p.add_argument("--exaggerate", type=float, default=8.0, help="vertical exaggeration")
    p.add_argument("--out", type=Path, default=Path("build/style_preview.png"))
    a = p.parse_args()

    region = select(USStates().regions(), [a.region])[0]
    fig = plt.figure(figsize=(15, 9), facecolor="black")
    for i, style in enumerate(STYLES.values()):
        ax = fig.add_subplot(2, 3, i + 1, projection="3d", facecolor="black", computed_zorder=False)
        draw(ax, region, style, REFERENCE_RADIUS, a.exaggerate)
        ax.title.set_color("white")
    fig.suptitle(f"{region.name} - style options (heights x{a.exaggerate:g})", color="white")
    fig.tight_layout()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.out, dpi=110, facecolor="black")
    print(f"Wrote {a.out.resolve()}")


if __name__ == "__main__":
    main()
