# NISAR GCOV to GeoTIFF

Convert a NISAR Level-2 GCOV HDF5 product into an EPSG:4326 GeoTIFF, a
whole-globe VRT, and an OpenSpace `.info` layer file. The script reads HDF5
datasets in 512-by-512 windows, so it does not load the full product into
memory.

## Setup

Use Python 3.10 or newer. From this directory, install the Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

No GDAL command-line installation is required; Rasterio provides the GDAL
library used for reprojection.

## Examples

Create the false-color composite used by the original
[NISAR into Planetarium guide](https://github.com/hedbergj/nisar-into-planetarium):

```powershell
python .\nisar_to_geotiff.py .\NISAR_L2_PR_GCOV_....h5 .\nisar-rgb.tif
```

The output maps HH backscatter to red, HV backscatter to green, and the HH/HV
backscatter ratio to blue. Backscatter channels use a -30 to 0 dB stretch and
the ratio uses a 0 to 20 dB stretch. Adjust those ranges to change the display:

```powershell
python .\nisar_to_geotiff.py input.h5 nisar-rgb.tif --db-range -35 5 --ratio-range 0 25
```

For faster color experiments, reduce the linear output resolution:

```powershell
python .\nisar_to_geotiff.py input.h5 nisar-preview.tif --resolution-percent 5
```

The percentage controls width and height: `10` samples approximately every
10th source pixel along each axis, producing about 1% as many pixels as full
resolution; `5` produces about 0.25%. This uses nearest-pixel sampling rather
than averaging, which keeps previews quick but makes them less suitable for
final scientific analysis. Valid values are greater than 0 and up to 100.

Create a single-band GeoTIFF instead. Its values remain linear GCOV power values;
the selected polarization defaults to HHHH:

```powershell
python .\nisar_to_geotiff.py input.h5 nisar-hh.tif --mode single --polarization HHHH
python .\nisar_to_geotiff.py input.h5 nisar-hv.tif --mode single --polarization HVHV
```

Use `--frequency B` for the frequency-B grid. By default, the script writes
the GeoTIFF, a same-named `.vrt` spanning the full globe, and a `.info` file
that points to the VRT and defines an OpenSpace color layer. The VRT and `.info`
file should stay alongside the GeoTIFF; use the `.info` file with
`openspace.globebrowsing.parseInfoFile()` or
`openspace.globebrowsing.addBlendingLayersFromDirectory()`. The layer uses
normal alpha blending, and its display name includes the acquisition date and
output resolution percentage. Use `--no-vrt` to omit both the VRT and `.info`
file.
Existing outputs are not overwritten unless `--overwrite` is supplied.

The script applies the product's projection EPSG code, coordinate vectors, and
sample mask from the HDF5 file. The RGB GeoTIFF contains RGBA channels; the
single-polarization GeoTIFF retains its float values and NaN no-data pixels.

## Compare two RGB scenes

Create absolute and signed RGB changes between two full-resolution scene
GeoTIFFs, crop both outputs to the scenes' overlapping geographic bounds, and
write matching whole-globe VRT and OpenSpace `.info` files:

```powershell
python .\create_rgb_difference.py `
  .\100pers\nisar_025_069_D_067_4005_DHDH_A_20260712T235152_20260712T235226_P05023_N_F_J_001_frequencyA_rgb.tif `
  .\100pers\nisar_031_170_D_067_4005_DHDH_A_20260930T000009_20260930T000044_P05023_N_F_J_001_frequencyA_rgb.tif `
  --output-prefix .\differences\nisar_rgb_difference_20260712_to_20260930_overlap
```

The absolute output uses zero for no channel change and brighter RGB values for
larger per-channel changes. The signed output encodes no change as neutral gray
(128); values below 128 indicate decreases and values above 128 indicate
increases in the later scene. Both outputs are transparent where either scene
has invalid data. By default, a pixel is also made transparent unless at least
one RGB channel changes by 40 or more byte levels (`--threshold 40`). Set
`--threshold` to a value from 0 to 255; 0 disables thresholding. The chosen
threshold is included in the output filenames and OpenSpace layer names.

## Create color-mapping experiments

Create ten September 30 5% display variants without reopening the large HDF5:

```powershell
python .\create_color_variants.py `
  .\5pers\nisar_031_170_D_067_4005_DHDH_A_20260930T000009_20260930T000044_P05023_N_F_J_001_frequencyA_rgb_5pct.tif `
  .\color_experiments
```

The variants include all six assignments of HH, HV, and HH/HV ratio to red,
green, and blue; individual-component grayscale views; and a grayscale mean of
all three displayed components. These previews reuse the source GeoTIFF's
existing stretch, changing channel mapping rather than recalculating backscatter
display ranges. Each variant has a VRT and `.info` file.

To approximate the NASA portal's pale, high-key rendering while keeping HH red,
HV green, and the HH/HV ratio blue, create a second set using independent
per-channel percentile stretches followed by gamma adjustments:

```powershell
python .\create_palette_variants.py `
  .\5pers\nisar_031_170_D_067_4005_DHDH_A_20260930T000009_20260930T000044_P05023_N_F_J_001_frequencyA_rgb_5pct.tif `
  .\color_experiments\portal_palette
```

This creates ten portal-inspired candidates from the existing 5% RGB raster
without reprocessing the HDF5. Each channel is stretched independently using
the selected valid-pixel percentiles, then adjusted with per-channel gamma
(below 1 brightens; above 1 darkens). The composite is then hue-rotated by 60
degrees and desaturated to 30% to approximate the portal's pale mint/magenta
look. This is an approximation; exact matching requires the portal's original
display settings. Each candidate includes a GeoTIFF with internal overviews,
VRT, and `.info` file.

To create only the `portal-detail` version from a full-resolution RGB GeoTIFF,
use `--preset portal-detail`. For example:

```powershell
python .\create_palette_variants.py `
  .\100pers\nisar_025_133_A_023_4005_DHDH_A_20260717T095915_20260717T095948_P05023_N_F_J_001_frequencyA_rgb.tif `
  .\color_experiments\portal_detail_100pct\2026-07-17 `
  --preset portal-detail
```

The output filename and OpenSpace layer metadata reflect the input resolution.

By default, each scene is stretched using its own percentiles, so the same
color can mean different backscatter in different scenes. To compare scenes,
pass the same `--stretch-from` list for every scene. Percentiles then come from
the combined histogram of those GeoTIFFs, and every scene gets identical bounds:

```powershell
$jun = ".\100pers\nisar_023_134_A_022_4005_DHDH_A_20260623T113834_20260623T113909_P05023_N_F_J_001_frequencyA_rgb.tif"
$oct = ".\100pers\nisar_033_134_A_022_4005_DHDH_A_20261021T113830_20261021T113905_P05023_N_F_J_001_frequencyA_rgb.tif"
python .\create_palette_variants.py $jun .\100persFixedStretch\2026-06-23 --preset portal-detail --stretch-from $jun --stretch-from $oct
python .\create_palette_variants.py $oct .\100persFixedStretch\2026-10-21 --preset portal-detail --stretch-from $jun --stretch-from $oct
```

The stretch sources are recorded in the GeoTIFF tags and the `.info`
description.

## Time series from a volcano (NASA SVS 5675)

`nisar_download.py` and `nisar_timelapse.py` recreate the HH time-lapse of the
Krasheninnikov eruption in [NASA SVS 5675](https://svs.gsfc.nasa.gov/5675/).

Download the granules over a point (searching needs no login; downloading
needs an Earthdata Login bearer token in the `EARTHDATA_TOKEN` environment
variable, or on the first line of `~/.earthdata_token`). Add `--list` to only
print the matches. Partial downloads resume.

```powershell
python .\nisar_download.py .\data\krasheninnikov --track 060 --direction D --start 2025-12-01 --end 2026-08-31
```

Build co-registered frames from the downloaded files (files and/or folders):

```powershell
python .\nisar_timelapse.py .\data\krasheninnikov .\data\krasheninnikov_hh
```

Every scene is cropped to the same box (`--center LON LAT`, `--half-size-km`,
default a 24 km square around the crater at `--pixel-m 10`), warped onto one
shared EPSG:4326 grid, and stretched with one shared dB range (`--db-range LOW
HIGH`, or by default the pooled 2nd to 99.5th percentile of all frames), so
frames can be flipped through without shifting or flickering. Each frame gets a
GeoTIFF, VRT, and `.info` file, and `manifest.json` records the series. Use
`--track`/`--direction` to keep one radar geometry; mixed geometries trigger a
warning because shadow and layover differ.

Data availability: the SVS page lists 17 dates (2025-12-25 to 2026-08-17, HH
only) but no granule IDs. As of 2026-11-24 the public catalog only had track
060 descending GCOV from 2026-06-18 onward over the volcano (the page's
Jun 18, Jun 30, Jul 12, Jul 24 and Aug 17 frames); the earlier dates were not
found in any public NISAR GCOV, GSLC or RSLC collection.

## Performance

`nisar_to_geotiff.py` decodes HDF5 strips in parallel worker processes, one per
CPU core. All scripts enable GDAL multithreading for compression, warping, and
overviews. `create_palette_variants.py` precomputes each palette as a lookup
table over all 2^24 RGB values. A full-resolution scene (about 5 GB of HDF5)
converts in about 30 seconds, and `portal-detail` takes about 1 minute on a
24-core machine.
