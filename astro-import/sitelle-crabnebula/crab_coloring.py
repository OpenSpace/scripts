# SPDX-License-Identifier: GPL-3.0-only
#
# Part of the SITELLE Crab Nebula OpenSpace asset. It produces data derived from
# https://github.com/thomasorb/M1_paper (GNU General Public License v3.0) and is distributed under the same
# license: the GNU General Public License, version 3. The license text is in LICENSE (next to the generated
# data) and in LICENSE_M1_paper.txt. See NOTICE.txt and SOURCE.txt for what was changed and where it came from.
"""Formula-based "Hubble-like" and "JWST-like" colors for the SITELLE Crab Nebula cloud.

The SITELLE data only covers one red band (647-685 nm: H-alpha, [N II] and [S II]), so neither telescope's real
colors can be reproduced; these are look-alike palettes built by formula from the columns we do have. The
assumptions are written out below so they can be changed in one place.

Inputs, per voxel (arrays): flux, nii_ha, sii_ha, and the position (x, y, z in pc from the expansion center).

ASSUMPTIONS
  A1. `flux` is the sum of the five emission lines (H-alpha, [N II] 6548/6583, [S II] 6716/6731); the paper's
      Figure 7 calls it "integral of the emission in all five emission lines".
  A2. `nii_ha` = ([N II] 6548 + 6583) / H-alpha and `sii_ha` = ([S II] 6716 + 6731) / H-alpha. This is inferred from
      the file names and value ranges (medians 3.4 and 1.3); the paper does not describe these maps.
      With A1 and A2 each voxel's share of the five-line total is
          H-alpha: 1 / (1 + nii_ha + sii_ha),  [N II]: nii_ha / (...),  [S II]: sii_ha / (...).
  A3. Both published images are dominated by a radial color gradient as seen from Earth, so each look starts from a
      gradient over the sky-projected radius rho (0 at the center, 1 at the edge of the cloud), taken by eye from the
      image, and the line strengths then modulate it. Colors belong to the voxels, so they are designed for the
      view from Earth.
  A4. Hubble look. Published mapping: [O III] 502 nm -> red, [S II] 673 nm -> green, [O I] 631 nm -> blue (astropix.org
      entry for heic0515a). Gradient: pink-white -> cream -> green -> yellow-green -> orange, with no blue. Modulation:
      H-alpha stands in for [O III] (red), [S II] is itself (green), and [N II], at the red end of the band, adds
      warmth to the red channel. The blue channel comes from the gradient alone, scaled by the smaller of the red and
      green factors; since blue is the smallest channel at every gradient stop, no voxel can be blue-dominant.
  A5. JWST look. Published image: NIRCam + MIRI, a blue-white synchrotron haze in the middle and orange to yellow-white
      dust filaments (F162M blue ... F2100W red). We have neither, so: haze weight falls from the center out, and the
      filament color goes from orange to yellow-white with the low-ionization line strength ([N II] and [S II]).
  A6. Brightness follows `flux` (so bright filaments are bright and faint ones dim, never fully black).
Every line strength is stretched to 0..1 between the 5th and 95th percentile of the voxels.
"""
import numpy as np

FLUX_RANGE = (1.81, 18.17)  # the paper's Figure 7 colorbar
BRIGHTNESS_FLOOR = 0.30     # faintest voxels still show at this fraction


def _stretch(x, lo=5, hi=95):
    a, b = np.percentile(x, [lo, hi])
    return np.clip((x - a) / (b - a), 0.0, 1.0)


def line_strengths(nii_ha, sii_ha):
    """A2: stretched shares of H-alpha, [N II] and [S II] in the five-line total."""
    d = 1.0 + nii_ha + sii_ha
    return _stretch(1.0 / d), _stretch(nii_ha / d), _stretch(sii_ha / d)


def brightness(flux):
    """A5: 0.30 .. 1.0 from flux, square-root stretched so mid-flux filaments read clearly."""
    t = np.sqrt(np.clip((flux - FLUX_RANGE[0]) / (FLUX_RANGE[1] - FLUX_RANGE[0]), 0.0, 1.0))
    return BRIGHTNESS_FLOOR + (1.0 - BRIGHTNESS_FLOOR) * t


def sky_radius(xyz):
    """A3: sky-projected radius (x, y are the sky axes), 0 at the center, 1 at the 98th percentile."""
    r = np.hypot(xyz[:, 0], xyz[:, 1])
    return r / np.percentile(r, 98)


def _gradient(t, stops):
    """Piecewise-linear color gradient; stops = [(position, (r, g, b)), ...] with increasing positions."""
    pos = np.array([p for p, _ in stops]); col = np.array([c for _, c in stops])
    return np.stack([np.interp(t, pos, col[:, k]) for k in range(3)], axis=1)


# Blue is the smallest channel at every stop (so the look has no blue); the middle is warmed toward pink-white.
HUBBLE_GRADIENT = [(0.00, (0.98, 0.82, 0.74)),   # pink-white middle
                   (0.18, (0.90, 0.88, 0.66)),   # warm cream
                   (0.35, (0.70, 0.90, 0.52)),   # green
                   (0.55, (0.78, 0.88, 0.45)),   # yellow-green
                   (0.80, (0.92, 0.62, 0.22)),   # orange-yellow
                   (1.00, (0.88, 0.38, 0.12))]   # orange-red edge


def hubble_rgb(flux, nii_ha, sii_ha, xyz):
    """A3 + A4: Hubble's radial gradient, modulated red <- H-alpha and [N II], green <- [S II]; no blue."""
    c_ha, c_nii, c_sii = line_strengths(nii_ha, sii_ha)
    rgb = _gradient(np.clip(sky_radius(xyz), 0.0, 1.0), HUBBLE_GRADIENT)
    f_red = 0.75 + 0.35 * c_ha + 0.35 * c_nii
    f_green = 0.75 + 0.50 * c_sii
    rgb = rgb * np.stack([f_red, f_green, np.minimum(f_red, f_green)], axis=1)  # blue never boosted, see A4
    return np.clip(rgb * brightness(flux)[:, None], 0.0, 1.0)


def jwst_rgb(flux, nii_ha, sii_ha, xyz):
    """A3 + A5: blue-white haze over the middle, orange -> yellow-white filaments."""
    _c_ha, c_nii, c_sii = line_strengths(nii_ha, sii_ha)
    rho = np.clip(sky_radius(xyz), 0.0, 1.0)
    haze_w = np.clip(1.0 - rho / 0.85, 0.0, 1.0) ** 0.8
    low_ion = np.clip(0.5 * (c_nii + c_sii), 0.0, 1.0)
    orange, yellow_white, haze = np.array([1.0, 0.50, 0.18]), np.array([1.0, 0.92, 0.70]), np.array([0.70, 0.84, 1.0])
    filament = orange[None, :] * (1.0 - low_ion)[:, None] + yellow_white[None, :] * low_ion[:, None]
    rgb = (1.0 - haze_w)[:, None] * filament + haze_w[:, None] * haze[None, :]
    return np.clip(rgb * (1.0 - 0.3 * rho)[:, None] * brightness(flux)[:, None], 0.0, 1.0)


SIZE_RANGE = (0.4, 2.0)  # relative point size for the faintest and the brightest voxels


def flux_size(flux):
    """Point-size factor for the GUI's size mapping: SIZE_RANGE[0] .. SIZE_RANGE[1] times the base point size, from
    flux over the same range as the flux color map (FLUX_RANGE), square-root stretched like the brightness. It is a
    dimensionless multiplier because OpenSpace multiplies the mapped value into the point's base size. Raw flux is
    not used as the size because it is heavy-tailed (the maximum is 78,000) and would give a few giant points."""
    t = np.sqrt(np.clip((flux - FLUX_RANGE[0]) / (FLUX_RANGE[1] - FLUX_RANGE[0]), 0.0, 1.0))
    return SIZE_RANGE[0] + (SIZE_RANGE[1] - SIZE_RANGE[0]) * t


LOOKS = {"hubble": hubble_rgb, "jwst": jwst_rgb}
