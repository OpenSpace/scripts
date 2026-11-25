#!/usr/bin/env python
# SPDX-License-Identifier: GPL-3.0-only
#
# Part of the SITELLE Crab Nebula OpenSpace asset. It produces data derived from
# https://github.com/thomasorb/M1_paper (GNU General Public License v3.0) and is distributed under the same
# license: the GNU General Public License, version 3. The license text is in LICENSE (next to the generated
# data) and in LICENSE_M1_paper.txt. See NOTICE.txt and SOURCE.txt for what was changed and where it came from.
"""Convert the SITELLE 3D maps of the Crab Nebula (M1) into an OpenSpace asset.

Data: Martin, Milisavljevic & Drissen (2021), "3D mapping of the Crab Nebula with
SITELLE. I. Deconvolution and kinematic reconstruction", MNRAS, doi:10.1093/mnras/staa4046
(arXiv:2101.02709). The FITS files come from https://github.com/thomasorb/M1_paper
(GNU GPL v3.0) and are expected in ./data (see --data); data/ is not committed to git. The generated
files are derived from them and are therefore also GPL-3.0. Every run writes output/LICENSE (the upstream
license text, kept here as LICENSE_M1_paper.txt), output/NOTICE.txt (what was changed, and when) and
output/SOURCE.txt (sources and credits), so output/ is self-contained and is what gets distributed.

Each 3dmap_XYZ*.fits file is an N x 4 float array: (col0, col1, col2, value), with
positions in parsecs relative to the expansion center (RA 83.63781644, Dec 22.01879988).
Verified against the data: col2 is the line of sight (value of the velocity map is exactly
-1116 km/s per pc * col2, i.e. positive col2 = approaching). col0/col1 are the sky axes,
but the files don't document which is RA/Dec. Determined by matching against Figure 7 of the paper (and
confirmed on the live render): east = -col0, north = +col1 (the SITELLE detector frame: x runs west, y north),
with col2 toward the observer. That is a proper rotation, no mirror needed. A residual roll below ~1 degree
is not resolved (the detector grid is tilted 0.86 deg from RA/Dec); use --roll if a small correction is wanted.

Output (./output): sitelle-crabnebula.csv (one row per voxel: x, y, z in the data frame in parsecs from the
expansion center, then flux, velocity, nii_ha, sii_ha, sii_sii and the formula-based hubble and jwst
palette positions, plus flux_size, a point-size factor), crab_hubble.cmap and crab_jwst.cmap (their palettes), sitelle-crabnebula.asset
(an OpenSpace RenderablePointCloud node with its rotation, actions and color options), LICENSE,
NOTICE.txt, SOURCE.txt and source/ (copies of these scripts, the corresponding source). The node is placed at the Crab's distance (--distance, default 1930 pc) and rotated into the
sky; see the comments in the generated asset.

Usage:
    python sitelle_crab.py [--data data] [--out output] [--sky east=-0,north=+1]
"""
import argparse
import datetime
import math
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PALETTE_SIZE = 2048  # colors per custom look (Hubble / JWST); each voxel gets exactly one of them
CENTER_RA, CENTER_DEC = 83.63781644, 22.01879988  # deg, ICRS (from the paper's notebook)
NATIVE_DISTANCE_PC = 2000.0  # distance the paper (and its notebook) used to turn pixels into parsecs
# Distance used to place the node: the Digital Universe supernova-remnants speck
# (digitaluniverse_supernovaremnants_speck, snr.speck, "G184.6-05.8 | SN 1054 - Crab Nebula": 6294.8 ly = 1930.0 pc,
# direction within 0.013 deg of the paper's expansion center), so the cloud sits where that dataset puts the Crab.
DISTANCE_PC = 1930.0
PC_M = 3.0856775814913673e16
MAPS = {  # column name -> file
    "flux": "3dmap_XYZflux.fits",
    "velocity": "3dmap_XYZvel.fits",
    "nii_ha": "3dmap_XYZnii_ha.fits",
    "sii_ha": "3dmap_XYZsii_ha.fits",
    "sii_sii": "3dmap_XYZsii_sii.fits",  # covers a subset of the voxels
}
# Color-mapping options exposed in the OpenSpace GUI: (CSV column, value range used when selected,
# Lua expression for the color map that column's action switches to, and whether that map is inverted so that
# high values are bright on a black background). First entry is the default.
# Ranges: velocity and flux follow the paper's Figure 7 colorbars; the two heavy-tailed ratio maps use roughly the
# data's 5th-95th percentile; sii_sii spans the data's full range.
# The "hubble" and "jwst" columns are not measurements: they hold palette indices (see crab_coloring.py and
# quantize_palette below) and their color maps are generated files, so their range is 0..1 and "{file}" is
# replaced by the generated file name.
COLOR_PARAMS = [
    ("velocity", (-1500, 1500), "colormaps.Diverging.RdBu", False),
    ("flux", (1.81, 18.17), "colormaps.Sequential2.Pink", False),
    ("nii_ha", (0.5, 10.0), "colormaps.Misc.Ocean", False),
    ("sii_ha", (0.4, 7.0), "colormaps.Misc.CMRmap", False),
    ("sii_sii", (0.4, 1.4), "colormaps.Sequential.BuPu", True),
    ("hubble", (0.0, 1.0), 'asset.resource("{file}")', False),
    ("jwst", (0.0, 1.0), 'asset.resource("{file}")', False),
]
BASENAME = "sitelle-crabnebula"  # file name (without extension) of the generated asset and CSV
ASSET_VERSION = "1.0.0"  # shown in the GUI; bump it when the published asset or its data change
LOOK_TITLES = {"hubble": "Hubble", "jwst": "JWST"}
DEFAULT_COLORING = "hubble"  # the COLOR_PARAMS entry the asset opens with (its parameter, range and color map)
ICRS_TO_GAL = np.array([
    [-0.0548755604162154, -0.8734370902348850, -0.4838350155487132],
    [+0.4941094278755837, -0.4448296299600112, +0.7469822444972189],
    [-0.8676661490190047, -0.1980763734312015, +0.4559837761750669],
])


def read_fits(path):
    """Minimal primary-HDU reader (big-endian float32), so only numpy is needed."""
    raw = Path(path).read_bytes()
    hdr, i = {}, 0
    while True:
        card = raw[i:i + 80].decode("ascii")
        i += 80
        if card.startswith("END"):
            break
        if card[8] == "=":
            hdr[card[:8].strip()] = card[10:].split("/")[0].strip()
    if int(hdr["BITPIX"]) != -32:
        raise ValueError(f"{path}: expected BITPIX=-32, got {hdr['BITPIX']}")
    shape = [int(hdr[f"NAXIS{k}"]) for k in range(int(hdr["NAXIS"]), 0, -1)]
    offset = -(-i // 2880) * 2880
    return np.frombuffer(raw, ">f4", offset=offset, count=int(np.prod(shape))).reshape(shape).astype(np.float64)


def parse_sky(s):
    """'east=-0,north=+1' -> ((col, sign), (col, sign))."""
    d = dict(p.split("=") for p in s.split(","))
    out = []
    for key in ("east", "north"):
        v = d[key]
        out.append((int(v[-1]), -1.0 if v[0] == "-" else 1.0))
    if {out[0][0], out[1][0]} != {0, 1}:
        raise ValueError("--sky must use col 0 and col 1 once each")
    return out


def crab_frame(distance=DISTANCE_PC):
    """Crab position (galactic, pc) and unit vectors east, north, toward-observer (galactic)."""
    ra, dec = math.radians(CENTER_RA), math.radians(CENTER_DEC)
    r = np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)])
    east = np.array([-math.sin(ra), math.cos(ra), 0.0])
    north = np.cross(r, east)
    g = lambda v: ICRS_TO_GAL @ v
    return g(r) * distance, g(east), g(north), g(-r)


def quantize_palette(rgb, n=PALETTE_SIZE):
    """Median-cut an (N, 3) array of 0..1 colors into at most n palette colors.

    Returns (palette, value): palette (m, 3) sorted by luminance, and per-sample values in 0..1 that sit at the center
    of the sample's palette entry, (rank + 0.5) / m, so that a color map built from the palette returns exactly that
    entry (OpenSpace samples the map's texture at (value - min) / (max - min)).
    """
    boxes = [np.arange(len(rgb))]
    spread = lambda idx: float((rgb[idx].max(0) - rgb[idx].min(0)).max())
    scores = [len(boxes[0]) * spread(boxes[0])]
    while len(boxes) < n:
        i = int(np.argmax(scores))
        if scores[i] <= 0:
            break  # every remaining box is a single color
        idx = boxes[i]
        channel = int(np.argmax(rgb[idx].max(0) - rgb[idx].min(0)))
        order = idx[np.argsort(rgb[idx, channel], kind="stable")]
        half = len(order) // 2
        boxes[i], new = order[:half], order[half:]
        scores[i] = len(boxes[i]) * spread(boxes[i])
        boxes.append(new)
        scores.append(len(new) * spread(new))
    palette = np.array([rgb[b].mean(0) for b in boxes])
    rank = np.empty(len(boxes), dtype=int)
    rank[np.argsort(palette @ np.array([0.299, 0.587, 0.114]), kind="stable")] = np.arange(len(boxes))
    box_of = np.empty(len(rgb), dtype=int)
    for k, b in enumerate(boxes):
        box_of[b] = rank[k]
    palette_sorted = np.empty_like(palette)
    palette_sorted[rank] = palette
    return palette_sorted, (box_of + 0.5) / len(boxes)


def write_plain(directory, stem, suffix, data):
    """Write data (bytes) as <stem><suffix>, and remove older hashed copies from a previous naming scheme."""
    for old in directory.glob(f"{stem}_*{suffix}"):
        old.unlink()
    (directory / f"{stem}{suffix}").write_bytes(data)
    return f"{stem}{suffix}"


def clear_openspace_cache(cache_dir, names):
    """OpenSpace caches loaded files by path, so a regenerated file with an unchanged name would load a stale copy.
    Remove the cache entries of the files just written (best effort; skipped if there is no such cache folder)."""
    for name in names:
        entry = Path(cache_dir) / name
        if entry.is_dir():
            shutil.rmtree(entry)
            print(f"cleared OpenSpace cache entry {entry}")


UPSTREAM_REPO = "https://github.com/thomasorb/M1_paper"
UPSTREAM_COMMIT = "af491d4a13d408464ffb3ea75e6a424f6ef5d140"  # master when the FITS files were downloaded (2026-11-17)
PAPER = ('Martin, T., Milisavljevic, D. and Drissen, L. (2021), "3D mapping of the Crab Nebula with SITELLE. '
         'I. Deconvolution and kinematic reconstruction", MNRAS, doi:10.1093/mnras/staa4046 (arXiv:2101.02709)')


def write_distribution_files(data_dir, out_dir, distance, lateral):
    """Write LICENSE, NOTICE.txt and SOURCE.txt into the output folder, which is what gets distributed.

    The generated files are derived from GPL-3.0 data, so they are distributed under GPL-3.0 as well (GPL section 5
    asks for the license text and a prominent notice that the work was modified, with a date). The upstream license
    text is kept next to the scripts (LICENSE_M1_paper.txt) so a fresh checkout, which has no data/ folder, can still
    write output/LICENSE.
    """
    for candidate in (HERE / "LICENSE_M1_paper.txt", data_dir / "LICENSE"):
        if candidate.exists():
            shutil.copyfile(candidate, out_dir / "LICENSE")
            break
    else:
        print("WARNING: no copy of the upstream license text found (LICENSE_M1_paper.txt), so output/LICENSE was not "
              f"written; download it from {UPSTREAM_REPO}")
    # The scripts that produced these files travel with them, as the corresponding source of the generated data.
    source_dir = out_dir / "source"
    source_dir.mkdir(exist_ok=True)
    for name in ("sitelle_crab.py", "crab_coloring.py", "LICENSE_M1_paper.txt"):
        src = HERE / name
        if src.exists() and src.resolve() != (source_dir / name).resolve():
            shutil.copyfile(src, source_dir / name)
    scaling = (f"The lateral coordinates (x and y, from col0 and col1) were multiplied by {lateral:.5f} "
               f"(= {distance:g} pc / {NATIVE_DISTANCE_PC:g} pc) so the cloud keeps its angular size at the distance "
               "used here; z (depth) is unchanged." if lateral != 1.0 else
               "The coordinates were not rescaled.")
    today = datetime.date.today().isoformat()
    (out_dir / "NOTICE.txt").write_text(f"""SITELLE 3D map of the Crab Nebula for OpenSpace: generated files
================================================================

These files are a modified version of data published with

  {PAPER},

which is distributed at {UPSTREAM_REPO} (commit
{UPSTREAM_COMMIT}, 2020-09-07) under the GNU General Public License v3.0. These
files are therefore distributed under the same license; its text is in the LICENSE file in this folder,
copied unchanged from that repository. Sources and credits are in SOURCE.txt in this folder.

Version {ASSET_VERSION}. Modified {today}. Changes relative to the upstream files:
  - The five 3dmap_XYZ*.fits point clouds were merged into one table ({BASENAME}.csv) with the
    columns flux, velocity, nii_ha, sii_ha and sii_sii; voxels were matched by coordinates (sii_sii covers a subset).
  - {scaling}
  - Three columns, flux_size, hubble and jwst, and the color maps crab_hubble.cmap and crab_jwst.cmap
    were added. flux_size is a point-size factor derived from flux; hubble and jwst are formula-based
    palettes written for this project (crab_coloring.py). None of them are measurements, and none
    contain image data.
  - {BASENAME}.asset is an OpenSpace asset written for this project that places, rotates and displays the data.

Corresponding source: the upstream FITS files (see SOURCE.txt) and the scripts that produced these files,
sitelle_crab.py and crab_coloring.py, which are in the source/ folder next to this notice and are provided under
the same license. To regenerate the files, put the five FITS files in a folder and run
    python source/sitelle_crab.py --data <that folder> --out <new output folder>
(Python 3 with numpy).
""", encoding="utf8")
    (out_dir / "SOURCE.txt").write_text(f"""Sources and credits: SITELLE 3D map of the Crab Nebula for OpenSpace
====================================================================

The data (the point clouds in {BASENAME}.csv)
  Files:      3dmap_XYZflux.fits, 3dmap_XYZvel.fits, 3dmap_XYZnii_ha.fits, 3dmap_XYZsii_ha.fits,
              3dmap_XYZsii_sii.fits
  Upstream:   {UPSTREAM_REPO}
              master, commit {UPSTREAM_COMMIT} (2020-09-07);
              retrieved 2026-11-17 from https://raw.githubusercontent.com/thomasorb/M1_paper/master/<file>
  License:    GNU General Public License v3.0 (GitHub API: GPL-3.0). LICENSE in this folder is the upstream license
              text, unchanged.
  Paper:      {PAPER}
  Note:       the paper's data statement says the data underlying the article are shared on reasonable request; the
              license of the repository above is what applies to the files taken from it.
  Position:   the expansion center (RA 83.63781644, Dec 22.01879988, ICRS) is taken from the repository's notebook.

Placement and orientation
  Distance:   {distance:g} pc, the Crab's distance in the Digital Universe supernova-remnants data (snr.speck, entry
              "G184.6-05.8 | SN 1054 - Crab Nebula", 6294.8 ly). The paper adopts {NATIVE_DISTANCE_PC:g} pc; see NOTICE.txt for
              the rescaling. No data from that file is included here.
  Orientation: east = -col0, north = +col1, col2 toward the observer; determined by matching against Figure 7 of the
              paper. The files themselves do not state the sky orientation.

Inspiration for the "hubble" and "jwst" palettes (no image data is used or included; the palettes were designed by
hand by formula, see crab_coloring.py)
  Hubble:     ESA/Hubble heic0515a, https://esahubble.org/images/heic0515a/
              Credit: NASA, ESA and Allison Loll/Jeff Hester (Arizona State University). Acknowledgement:
              Davide De Martin (ESA/Hubble). Creative Commons Attribution 4.0 International (CC BY 4.0).
  JWST:       NASA/ESA/CSA/STScI STScI-2023-137, https://science.nasa.gov/asset/webb/crab-nebula-nircam-and-miri-image
              Credit: NASA, ESA, CSA, STScI, Tea Temim (Princeton University); Image Processing: Joseph DePasquale
              (STScI). Terms were not verified; see the STScI image use policy.
""", encoding="utf8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=HERE / "data")
    ap.add_argument("--out", type=Path, default=HERE / "output")
    ap.add_argument("--sky", default="east=-0,north=+1",
                    help="which cloud column/sign is east and north (default verified against the paper's Figure 7)")
    ap.add_argument("--center", choices=["bbox", "centroid", "origin"], default="origin",
                    help="keep the paper's expansion center (origin, default), or recenter the cloud "
                         "on its bounding-box midpoint or centroid (bbox/centroid; this was found to break the placement)")
    ap.add_argument("--openspace-cache", type=Path, default=Path("C:/OpenSpace/OpenSpace/cache"),
                    help="OpenSpace's cache folder; cache entries of the regenerated crab_*.cmap files are removed there")
    ap.add_argument("--distance", type=float, default=DISTANCE_PC,
                    help="distance to the Crab in pc (default: the Digital Universe SNR speck's 1930 pc)")
    ap.add_argument("--no-rescale", action="store_true",
                    help="don't rescale the lateral axes (col0, col1) by distance/2000; the cloud then appears "
                         "larger or smaller on the sky than the real nebula by that factor")
    ap.add_argument("--mirror-x", action="store_true",
                    help="negate col0 in the CSV (a reflection; combine with --roll to get any mirrored orientation)")
    ap.add_argument("--roll", type=float, default=0.0,
                    help="extra spin of the cloud about the line of sight, degrees, counter-clockwise as "
                         "seen by the observer")
    ap.add_argument("--euler", help="override the cloud's rotation: 'rx,ry,rz' in radians (use the values "
                                    "tuned live in OpenSpace)")
    args = ap.parse_args()
    (e_col, e_sign), (n_col, n_sign) = parse_sky(args.sky)

    base = read_fits(args.data / MAPS["flux"])
    coords = base[:, :3]
    key = lambda c: tuple(np.round(c, 6))
    index = {key(c): i for i, c in enumerate(coords)}
    cols = {}
    for name, fn in MAPS.items():
        a = read_fits(args.data / fn)
        v = np.full(len(coords), np.nan)
        for row in a:
            i = index.get(key(row[:3]))
            if i is None:
                raise ValueError(f"{fn}: voxel {row[:3]} not present in the flux map")
            v[i] = row[3]
        cols[name] = v

    # Recenter in the data frame (before rotation) so the node origin sits at the cloud's middle.
    shift = {
        "origin": np.zeros(3),  # keep the paper's expansion center
        "bbox": (coords.min(0) + coords.max(0)) / 2,
        "centroid": coords.mean(0),
    }[args.center]
    coords = coords - shift
    print(f"center={args.center}: shifted data by {shift.round(3)} pc (cols 0,1,2)")

    pos, east, north, toward = crab_frame(args.distance)
    # The CSV keeps the raw data frame (x,y,z = col0,col1,col2, parsecs). The node's StaticRotation
    # turns that into galactic: raw col i -> direction `dirs[i]`. Euler angles are radians for
    # glm::quat(euler), i.e. R = Rz(c) Ry(b) Rx(a); tune live via Scene.CrabNebulaSITELLE.Rotation.Rotation.
    dirs = [None, None, toward]
    dirs[e_col], dirs[n_col] = e_sign * east, n_sign * north
    M = np.column_stack(dirs)
    print(f"sky mapping det(M)={np.linalg.det(M):+.3f} (must be +1; -1 would need a mirror)")
    if args.roll:
        # spin about the line of sight; positive = counter-clockwise as seen by the observer (the
        # rotation axis points from the Crab toward the observer)
        k, t = toward, math.radians(args.roll)
        K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
        M = (np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K) @ M
    if args.euler:
        euler = np.array([float(v) for v in args.euler.split(",")])
    else:
        euler = np.array([math.atan2(M[2, 1], M[2, 2]), -math.asin(M[2, 0]), math.atan2(M[1, 0], M[0, 0])])
    xyz = coords.copy()
    # The data's lateral parsecs (col0, col1) were computed by the authors at 2000 pc, so they scale with the
    # distance to keep the angular size; the depth (col2, from velocity / expansion rate) does not.
    lateral = 1.0 if args.no_rescale else args.distance / NATIVE_DISTANCE_PC
    xyz[:, :2] *= lateral
    print(f"distance {args.distance:g} pc; lateral axes (col0, col1) scaled by {lateral:.5f}, depth (col2) unchanged")
    if args.mirror_x:
        xyz[:, 0] *= -1  # a reflection can't be done by a rotation; this mirrors east<->west, depth unchanged
    print("rotation euler (rad) = {:.9f}, {:.9f}, {:.9f}".format(*euler))

    args.out.mkdir(exist_ok=True)

    # Formula-based looks (crab_coloring.py): per-voxel RGB -> a palette of PALETTE_SIZE colors, written as a color
    # map, plus a column holding each voxel's palette position. (Per-point RGB columns are not available in the
    # OpenSpace v0.22.1 point cloud; a palette lookup gives each voxel exactly its own color.)
    sys.path.insert(0, str(HERE))  # so the sibling module is found even under `python -I`
    import crab_coloring
    cmap_files = {}
    cols["flux_size"] = crab_coloring.flux_size(cols["flux"])  # point-size factor for the GUI's size mapping
    for look, formula in crab_coloring.LOOKS.items():
        rgb = formula(cols["flux"], cols["nii_ha"], cols["sii_ha"], coords)
        palette, value = quantize_palette(rgb)
        text = (f"# {LOOK_TITLES[look]}-like palette from crab_coloring.py ({len(palette)} colors)\n{len(palette)}\n"
                + "".join(f"{r:.6f} {g:.6f} {b:.6f} 1.0\n" for r, g, b in palette))
        cmap_files[look] = write_plain(args.out, f"crab_{look}", ".cmap", text.encode())
        err = np.abs(palette[np.clip((value * len(palette)).astype(int), 0, len(palette) - 1)] - rgb).mean()
        print(f"{look}: {len(palette)} palette colors, mean quantization error {err:.4f} (of 1.0) -> {cmap_files[look]}")
        cols[look] = value
    col_names = set(cols)

    names = list(cols)
    lines = ["# SITELLE 3D map of the Crab Nebula, Martin et al. 2021 (arXiv:2101.02709)\n",
             "# x,y,z: parsecs from the expansion center in the data frame (col0,col1,col2; col2 = toward\n",
             "# observer); the asset's rotation orients it. velocity km/s (+ = receding)\n",
             "# flux_size, hubble, jwst: not measurements; a point-size factor and palette positions, see crab_coloring.py\n"]
    if lateral != 1.0:
        lines.append(f"# NOTE: x and y (col0, col1) are scaled by {lateral:.5f} (= {args.distance:g} / "
                     f"{NATIVE_DISTANCE_PC:g} pc) relative to the FITS files; z is unchanged\n")
    if args.mirror_x:
        lines.append("# NOTE: x is -col0 (mirrored, --mirror-x)\n")
    lines.append("x,y,z," + ",".join(names) + "\n")
    for i in range(len(xyz)):
        vals = ",".join("" if np.isnan(cols[n][i]) else (f"{cols[n][i]:.6f}" if n in crab_coloring.LOOKS or n == "flux_size" else f"{cols[n][i]:.6g}")
                        for n in names)
        lines.append(f"{xyz[i, 0]:.6f},{xyz[i, 1]:.6f},{xyz[i, 2]:.6f},{vals}\n")
    csv_name = write_plain(args.out, BASENAME, ".csv", "".join(lines).encode())
    clear_openspace_cache(args.openspace_cache, [csv_name, *cmap_files.values()])

    missing = [n for n, *_ in COLOR_PARAMS if n not in cols]
    assert not missing, f"COLOR_PARAMS names not in the CSV: {missing}"
    options_lua = ",\n".join(
        f'          {{ Key = "{n}", Range = {{ {lo}, {hi} }} }}' for n, (lo, hi), _cm, _inv in COLOR_PARAMS if n in col_names)
    # One "Color by ..." action per parameter: sets the parameter (by its index in ParameterOptions,
    # which also applies its range) and that parameter's color map.
    color_actions_lua = "".join(
        f'''  {{
    Identifier = "crab_sitelle.{'coloring' if n in LOOK_TITLES else 'color'}_{n}",
    Name = "{f'Switch to {LOOK_TITLES[n]} Like Coloring' if n in LOOK_TITLES else f'Color by {n}'}",
    GuiPath = "/Milky Way/Nebulae/Crab Nebula",
    IsLocal = true,
    Command = colorCommand({i}, {cm.replace('{file}', cmap_files.get(n, ''))}, {str(inv).lower()})
  }},
''' for i, (n, _rng, cm, inv) in enumerate(p_ for p_ in COLOR_PARAMS if p_[0] in col_names))
    # "Orient view from Earth": the camera is anchored to the Crab and placed on the Earth side of it, looking at
    # it, so you see the nebula from the direction of Earth (north up, east left, as in the sky) while staying
    # at the nebula. `toward` is the unit vector from the Crab toward the Sun/Earth. The navigation state looks at
    # its anchor, so with Up = north and no yaw/pitch the right-hand direction is west and east is on the left.
    fmt3 = lambda v, k="": "{ " + ", ".join(f"{c:.9f}{k}" for c in v) + " }"

    default = next(e for e in COLOR_PARAMS if e[0] == DEFAULT_COLORING)
    default_file = default[2].replace('{file}', cmap_files.get(default[0], ''))
    default_invert = "Invert = true,\n        " if default[3] else ""

    p = pos * PC_M
    asset = f"""-- SITELLE 3D map of the Crab Nebula (M1)
-- Martin, Milisavljevic & Drissen (2021), arXiv:2101.02709
-- Generated by sitelle_crab.py. Sky orientation (--sky {args.sky}) verified against Figure 7 of the paper.
-- Data derived from https://github.com/thomasorb/M1_paper (GNU GPL v3.0); this asset and its data files are
-- distributed under the same license. See LICENSE and NOTICE.txt in this folder.
local colormaps = asset.require("util/default_colormaps")

-- Shown twice in the GUI (the node's About row and the asset's About row), as plain text: the GUI does not make
-- links or line breaks out of it, so it is continuous prose with the URLs written out. The one clickable link is
-- asset.meta.URL below.
local Description = [[A 3D kinematic reconstruction of the Crab Nebula (M1) from SITELLE imaging Fourier-transform
  spectroscopy at the CFHT: {len(xyz):,} voxels of H-alpha, [N II] and [S II] emission (647-685 nm). Each voxel's
  sky position comes from the image and its depth from the line's velocity, assuming homologous expansion from the
  expansion center. The cloud is placed at {args.distance:g} pc, the Crab's distance in the Digital Universe
  supernova-remnants data, and oriented as seen from Earth (north up, east left). Color it by velocity (km/s,
  positive is receding), flux (the five lines summed), nii_ha and sii_ha (line ratios to H-alpha, assumed) or
  sii_sii (the [S II] doublet ratio, measured for part of the nebula only) under Coloring > Color Mapping, or use
  the hubble and jwst look-alike palettes, which are made by formula from this data and are neither measurements
  nor the real telescope colors; the asset opens with the {DEFAULT_COLORING} coloring. Points can also be sized by
  flux under Sizing > Size Mapping (off by default). The Actions panel (Milky Way > Nebulae > Crab Nebula) has
  "Orient view from Earth (fade)", a "Color by ..." action for each measured parameter, and "Switch to Hubble Like
  Coloring" and "Switch to JWST Like Coloring". Data: Martin, Milisavljevic and Drissen (2021),
  doi:10.1093/mnras/staa4046 (https://arxiv.org/abs/2101.02709), from https://github.com/thomasorb/M1_paper (GNU
  GPL v3.0). Modified here (the five point clouds were merged, the lateral coordinates were rescaled to the
  distance used here, and size and palette columns were added) and distributed under the same license; see
  NOTICE.txt and SOURCE.txt.]]

local Crab = {{
  Identifier = "CrabNebulaSITELLE",
  Parent = "Root",
  Transform = {{
    Translation = {{
      Type = "StaticTranslation",
      Position = {{ {p[0]:.6e}, {p[1]:.6e}, {p[2]:.6e} }}
    }},
    -- Rotation: Euler angles (x, y, z) in radians, applied as Rz * Ry * Rx (x first, like glm::quat).
    -- It turns the CSV's raw data frame (x = col0, y = col1, z = col2) into the scene's galactic
    -- frame so that, as seen from Earth:  east = -col0,  north = +col1,  toward us = +col2.
    -- Mapping used: {args.sky}, extra roll about the line of sight: {args.roll} deg.
    -- The values are not tidy because the sky at the Crab (galactic l=184.56, b=-5.78) is tilted
    -- relative to the scene axes.
    Rotation = {{
      Type = "StaticRotation",
      Rotation = {{ {euler[0]:.9f}, {euler[1]:.9f}, {euler[2]:.9f} }} -- Euler angles (radians)
    }}
  }},
  Renderable = {{
    Type = "RenderablePointCloud",
    File = asset.resource("{csv_name}"),
    -- OpenSpace's dataset and color map caches are keyed by file path, not content. sitelle_crab.py clears the cache
    -- entries of {BASENAME}.csv and crab_*.cmap each time it regenerates them. If you edit one of these files by hand,
    -- or regenerate on another machine, delete its folder under the OpenSpace cache directory (or set UseCaching to
    -- false), or OpenSpace will load the old copy.
    UseCaching = true,
    Unit = "pc",
    Texture = {{ Enabled = false }},
    Opacity = 0.5,
    Coloring = {{
      ColorMapping = {{
        File = {default_file},
        {default_invert}
        -- Parameters offered in the GUI, each with the value range used when it is selected.
        -- (One color map applies at a time; the "Color by ..." actions switch parameter and color map together.)
        ParameterOptions = {{
{options_lua}
        }},
        Parameter = "{DEFAULT_COLORING}",
        ShowMissingData = false  -- sii_sii covers only ~29% of the voxels; missing ones are not drawn
      }}
    }},
    SizeSettings = {{
      -- Optional: scale each point by flux (the flux_size column, 0.4x to 2x the base size). Off by default; turn it
      -- on in the GUI under Sizing > Size Mapping.
      SizeMapping = {{
        Enabled = false,
        ParameterOptions = {{ "flux_size" }},
        Parameter = "flux_size"
      }},
      ScaleFactor = 1.5,
      ScaleExponent = 14.0,
      EnableMaxSizeControl = false,
      MaxSize = 0.01
    }}
  }},
  GUI = {{
    Name = "Crab Nebula (SITELLE 3D)",
    Path = "/Milky Way/Nebulae",
    Description = Description
  }}
}}

-- Actions (Actions panel, under "Milky Way/Nebulae/Crab Nebula")
local colorPath = "Scene.CrabNebulaSITELLE.Renderable.Coloring.ColorMapping"
-- Each "Color by ..." action hides the cloud while it changes, so the intermediate state is never seen:
--   1. fade out; when the fade has finished (postscript) ->
--   2. un-invert and switch the color map; then, after a short delay ->
--   3. set the parameter (which also applies its own value range), invert the map if it needs it, and fade in.
-- Two OpenSpace behaviours force this order. Changing the color map file reloads it and resets the parameter
-- to the asset's default, so the parameter has to be set after the reload. And "Invert" just reverses the
-- entries currently loaded (a freshly loaded map is never inverted), so it is cleared before the file
-- changes and applied again once the new map is in.
local nodeRenderable = "Scene.CrabNebulaSITELLE.Renderable"
local FadeTime = 0.3  -- seconds, for both the fade out and the fade in
local Delay = 0.05    -- seconds between switching the color map and setting the parameter
local function colorCommand(index, colormap, invert)
  local file = string.gsub(colormap, string.char(92), "/")
  local stepParameterAndFadeIn = string.format(
    'openspace.setPropertyValueSingle("%s.Parameter", %d) ' ..
    'openspace.setPropertyValueSingle("%s.Invert", %s) ' ..
    'openspace.setPropertyValueSingle("%s.Fade", 1.0, %g)',
    colorPath, index, colorPath, tostring(invert), nodeRenderable, FadeTime
  )
  local stepColorMap = string.format(
    'openspace.setPropertyValueSingle("%s.Invert", false) ' ..
    'openspace.setPropertyValueSingle("%s.File", "%s") ' ..
    'openspace.scheduleScript([=[%s]=], %g)',
    colorPath, colorPath, file, stepParameterAndFadeIn, Delay
  )
  return string.format(
    'openspace.setPropertyValueSingle("%s.Fade", 0.0, %g, "Linear", [==[%s]==])',
    nodeRenderable, FadeTime, stepColorMap
  )
end

-- Fade the cloud out, run `script`, then fade it back in, so a camera jump is never seen.
local function fadedCommand(script)
  return string.format(
    'openspace.setPropertyValueSingle("%s.Fade", 0.0, %g, "Linear", [==[%s openspace.setPropertyValueSingle("%s.Fade", 1.0, %g)]==])',
    nodeRenderable, FadeTime, script, nodeRenderable, FadeTime
  )
end

-- Anchors the camera to the Crab, on the Earth side of it, looking at it with north up and east left.
-- Keeps the current distance if already anchored to the Crab, otherwise 3 pc. Does not touch the field of view.
local orientFromEarth = [=[
      local s = openspace.navigation.getNavigationState()
      local dist = 3.0 * 3.0856775814913673e16
      if s.Anchor == "CrabNebulaSITELLE" then
        local p = s.Position
        dist = math.sqrt(p[1] * p[1] + p[2] * p[2] + p[3] * p[3])
      end
      openspace.navigation.setNavigationState({{
        Anchor = "CrabNebulaSITELLE",
        ReferenceFrame = "Root",
        Position = {fmt3(toward, " * dist")},
        Up = {fmt3(north)},
        Yaw = 0.0,
        Pitch = 0.0
      }})
]=]

local actions = {{
  {{
    Identifier = "crab_sitelle.orient_from_earth",
    Name = "Orient view from Earth (fade)",
    GuiPath = "/Milky Way/Nebulae/Crab Nebula",
    IsLocal = true,
    Command = fadedCommand(orientFromEarth)
  }},
{color_actions_lua}}}

asset.onInitialize(function()
  openspace.addSceneGraphNode(Crab)
  for _, a in ipairs(actions) do openspace.action.registerAction(a) end
end)
asset.onDeinitialize(function()
  for i = #actions, 1, -1 do openspace.action.removeAction(actions[i].Identifier) end
  openspace.removeSceneGraphNode(Crab.Identifier)
end)

asset.export(Crab)  -- registers the node's identifier, which is how the GUI ties the node to the asset info below

asset.meta = {{
  Name = "Crab Nebula (SITELLE 3D)",
  Version = "{ASSET_VERSION}",
  Description = Description,
  Author = "Data: T. Martin, D. Milisavljevic and L. Drissen (2021). Asset: generated by sitelle_crab.py",
  URL = "https://arxiv.org/abs/2101.02709",
  License = "GNU General Public License v3.0 (data derived from https://github.com/thomasorb/M1_paper)"
}}
"""
    (args.out / f"{BASENAME}.asset").write_text(asset)
    write_distribution_files(args.data, args.out, args.distance, lateral)
    l = math.degrees(math.atan2(pos[1], pos[0])) % 360
    b = math.degrees(math.asin(pos[2] / args.distance))
    print(f"{len(xyz)} voxels -> {args.out}; Crab at l={l:.2f} b={b:.2f} (expect ~184.56, -5.78)")


if __name__ == "__main__":
    main()
