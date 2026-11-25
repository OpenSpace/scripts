#!/usr/bin/env python
"""Register the Hubble and JWST images of the Crab onto the SITELLE sky projection.

The registration (a small JSON file) is what lets sitelle_crab.py give every voxel the color of the real image at
its sky position. Each image's published WCS (AVM metadata from astropix.org) is the starting point; then the fit is
refined by correlating the image's filaments with the filaments of the cloud's own flux map, because the published
WCS is only good to a few arcseconds and some of its conventions (rotation sign, y origin) are ambiguous. All
variants of the ambiguous conventions are tried and the best is kept.

Requires numpy and Pillow. Usage:
    python register_reference_images.py [--out data/reference/registration.json] [--preview DIR]

Reference images (download once, see data/reference/*/SOURCE.txt):
    data/reference/hubble/heic0515a.jpg           Credit: NASA, ESA and Allison Loll/Jeff Hester (Arizona State
                                                  University). Acknowledgement: Davide De Martin (ESA/Hubble). CC BY 4.0
    data/reference/jwst/stsci_2023-137a_3000.jpg  Credit: NASA, ESA, CSA, STScI, Tea Temim (Princeton University);
                                                  Image Processing: Joseph DePasquale (STScI)
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sitelle_crab as sc  # noqa: E402

ARCSEC_PER_RAD = 206264.806
ARCSEC_PER_NATIVE_PC = ARCSEC_PER_RAD / sc.NATIVE_DISTANCE_PC  # the data's parsecs were computed at 2000 pc
GRID, CELL = 800, 0.5   # model grid: 800 x 800 cells of 0.5 arcsec, centered on the expansion center
REDUCE = 4              # block-average the reference images by this factor for the fit

# AVM positional metadata from astropix.org (reference pixel in pixels of the FULL-size image, y from the bottom).
REFS = {
    "hubble": dict(
        path="data/reference/hubble/heic0515a.jpg", full_size=(3864, 3864),
        ref_value=(83.6355343, 22.0152411), ref_pixel=(1933.0, 1933.0),
        scale=(-2.76551527063e-05, 2.76381692778e-05), rotation=0.0),
    "jwst": dict(
        path="data/reference/jwst/stsci_2023-137a_3000.jpg", full_size=(10509, 9151),
        ref_value=(83.63514468279, 22.01126048902), ref_pixel=(5266.22198319237, 3954.14305809416),
        scale=(-8.67480e-06, 8.67480e-06), rotation=-2.16842767979),
}


def gauss(a, sigma):
    """Gaussian blur via FFT (sigma in cells)."""
    fy = np.fft.fftfreq(a.shape[0])[:, None]
    fx = np.fft.fftfreq(a.shape[1])[None, :]
    return np.fft.ifft2(np.fft.fft2(a) * np.exp(-2 * (math.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))).real


def highpass(a):
    return gauss(a, 1.5) - gauss(a, 8.0)


def model_grid():
    """Flux map of the cloud on the sky, east left / north up, and the per-cell (east, north) offsets in arcsec."""
    d = sc.read_fits(HERE / "data" / "3dmap_XYZflux.fits")
    east = -d[:, 0] * ARCSEC_PER_NATIVE_PC      # east = -col0, north = +col1 (verified against the paper's Figure 7)
    north = d[:, 1] * ARCSEC_PER_NATIVE_PC
    w = np.minimum(d[:, 3], np.percentile(d[:, 3], 95))
    half = GRID * CELL / 2
    edges = np.linspace(-half, half, GRID + 1)
    h = np.histogram2d(north, east, bins=[edges, edges], weights=w)[0][::-1]   # rows: north up; cols: east to the RIGHT
    h = h[:, ::-1]                                                              # east to the LEFT, as on the sky
    centers = (np.arange(GRID) + 0.5 - GRID / 2) * CELL
    e_grid = -centers[None, :].repeat(GRID, 0)          # column index grows toward west
    n_grid = -centers[:, None].repeat(GRID, 1)          # row index grows toward south
    return gauss(h, 1.5), e_grid, n_grid


def tangent_offsets(e_as, n_as, ra0, dec0):
    """(east, north) arcsec offsets from the expansion center -> gnomonic standard coords about (ra0, dec0)."""
    rac, decc = math.radians(sc.CENTER_RA), math.radians(sc.CENTER_DEC)
    xi, eta = e_as / ARCSEC_PER_RAD, n_as / ARCSEC_PER_RAD
    rho = np.hypot(xi, eta); c = np.arctan(rho)
    with np.errstate(invalid="ignore", divide="ignore"):
        dec = np.arcsin(np.cos(c) * math.sin(decc) + np.where(rho > 0, eta * np.sin(c) * math.cos(decc) / rho, 0))
    ra = rac + np.arctan2(xi * np.sin(c), rho * math.cos(decc) * np.cos(c) - eta * math.sin(decc) * np.sin(c))
    r0, d0 = math.radians(ra0), math.radians(dec0)
    cosc = math.sin(d0) * np.sin(dec) + math.cos(d0) * np.cos(dec) * np.cos(ra - r0)
    x = np.cos(dec) * np.sin(ra - r0) / cosc
    y = (math.cos(d0) * np.sin(dec) - math.sin(d0) * np.cos(dec) * np.cos(ra - r0)) / cosc
    return x * ARCSEC_PER_RAD, y * ARCSEC_PER_RAD


def sample(img, x, y):
    """Bilinear sample of a 2D or HxWx3 array at float pixel coordinates (x = column, y = row); 0 outside."""
    h, w = img.shape[:2]
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    fx = x - x0; fy = y - y0
    ok = (x0 >= 0) & (y0 >= 0) & (x0 < w - 1) & (y0 < h - 1)
    x0c = x0.clip(0, w - 2); y0c = y0.clip(0, h - 2)
    if img.ndim == 3:
        fx = fx[..., None]; fy = fy[..., None]; ok = ok[..., None]
    v = (img[y0c, x0c] * (1 - fx) * (1 - fy) + img[y0c, x0c + 1] * fx * (1 - fy)
         + img[y0c + 1, x0c] * (1 - fx) * fy + img[y0c + 1, x0c + 1] * fx * fy)
    return np.where(ok, v, 0.0)


class Transform:
    """Sky offsets from the expansion center (arcsec) -> pixel coordinates (column, row from the top) of an image."""

    def __init__(self, ref, img_size, k=1):
        self.ref, self.k = ref, k
        w, h = img_size
        fw, fh = ref["full_size"]
        self.h_full = h * (fh / h) if False else fh
        self.sx = ref["scale"][0] * 3600 * (fw / w) * k       # arcsec per (reduced) pixel, negative: x grows westward
        self.sy = ref["scale"][1] * 3600 * (fh / h) * k
        self.px0 = ref["ref_pixel"][0] * (w / fw) / k
        self.py0 = ref["ref_pixel"][1] * (h / fh) / k         # y from the bottom (AVM)
        self.hk = h / k

    def pixels(self, e_as, n_as, p, rotsign, ybottom):
        dx, dy, drot, s = p
        xi, eta = tangent_offsets(e_as, n_as, *self.ref["ref_value"])
        a, b = (xi + dx) * s, (eta + dy) * s
        rot = math.radians(rotsign * self.ref["rotation"] + drot)
        u = a * math.cos(rot) - b * math.sin(rot); v = a * math.sin(rot) + b * math.cos(rot)
        col = self.px0 + u / self.sx
        yb = self.py0 + v / self.sy
        row = (self.hk - yb) if ybottom else yb
        return col, row


def correlation(model_hp, warped, mask):
    wh = highpass(warped)
    a, b = model_hp[mask], wh[mask]
    a = a - a.mean(); b = b - b.mean()
    d = math.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else 0.0


def fit(name, ref, model, e_grid, n_grid, preview_dir):
    im = Image.open(HERE / ref["path"]).convert("RGB")
    reduced = np.asarray(im.reduce(REDUCE), dtype=float)
    lum = reduced @ np.array([0.299, 0.587, 0.114])
    lum = np.minimum(lum, np.percentile(lum, 98))           # tame the stars
    tr = Transform(ref, im.size, REDUCE)
    mhp = highpass(model)
    mask = gauss((model > 0.02 * model.max()).astype(float), 6) > 0.1
    best = None
    results = []
    for rotsign in (1, -1) if ref["rotation"] else (1,):
        for ybottom in (True, False):
            def score(p):
                col, row = tr.pixels(e_grid, n_grid, p, rotsign, ybottom)
                return correlation(mhp, sample(lum, col, row), mask)
            # coarse shift search at the published scale/rotation
            top = (-1, None)
            for dx in range(-30, 31, 4):
                for dy in range(-30, 31, 4):
                    c = score((dx, dy, 0.0, 1.0))
                    if c > top[0]:
                        top = (c, (float(dx), float(dy), 0.0, 1.0))
            results.append((top[0], rotsign, ybottom, top[1]))
    results.sort(key=lambda r: -r[0])
    print(f"[{name}] coarse results (corr, rotation sign, y from bottom, params):")
    for r in results:
        print("   %.3f  rotsign=%+d  ybottom=%s  p=%s" % r)
    c, rotsign, ybottom, p = results[0]
    # refine all four parameters by coordinate descent
    steps = [1.0, 1.0, 0.3, 0.004]
    p = list(p)
    def score(p):
        col, row = tr.pixels(e_grid, n_grid, p, rotsign, ybottom)
        return correlation(mhp, sample(lum, col, row), mask)
    cur = score(p)
    for _ in range(40):
        improved = False
        for i in range(4):
            for sgn in (1, -1):
                q = list(p); q[i] += sgn * steps[i]
                sc_ = score(q)
                if sc_ > cur + 1e-5:
                    p, cur, improved = q, sc_, True
        if not improved:
            steps = [s / 2 for s in steps]
            if steps[0] < 0.1:
                break
    print(f"[{name}] refined: corr {cur:.3f}, dx={p[0]:.1f}\" dy={p[1]:.1f}\" extra rotation={p[2]:.2f} deg, scale x{p[3]:.3f}")
    col, row = tr.pixels(e_grid, n_grid, p, rotsign, ybottom)
    if preview_dir:
        warped = sample(reduced, col, row)
        mm = np.clip(model / np.percentile(model, 99.5), 0, 1)
        left = (np.stack([mm] * 3, -1) * 255).astype(np.uint8)
        right = np.clip(warped, 0, 255).astype(np.uint8)
        strip = np.concatenate([left, right], axis=1)
        Image.fromarray(strip).reduce(2).save(Path(preview_dir) / f"registration_{name}.png")
    return dict(corr=cur, rotsign=rotsign, ybottom=ybottom, dx=p[0], dy=p[1], drot=p[2], scale=p[3])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=HERE / "data" / "reference" / "registration.json")
    ap.add_argument("--preview", type=Path, help="directory for side-by-side registration check images")
    args = ap.parse_args()
    if args.preview:
        args.preview.mkdir(parents=True, exist_ok=True)
    model, e_grid, n_grid = model_grid()
    out = {}
    for name, ref in REFS.items():
        out[name] = fit(name, ref, model, e_grid, n_grid, args.preview)
    args.out.write_text(json.dumps(out, indent=2))
    print("wrote", args.out)


if __name__ == "__main__":
    main()
