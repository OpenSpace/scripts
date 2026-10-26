# qmd2pointcloud

Converts a Quarto (reveal.js) presentation into OpenSpace point clouds: every slide becomes
one `RenderablePointCloud` with one point per pixel of the 1920×1080 slide, and the
generated `.asset` has actions to step through the slides.

Each slide is split into three layers — background, media (images, videos, diagrams), and
text. The media and text layers sit in front of the background and are shrunk so that,
from the prime spot in front of the slide, the slide looks exactly like the original. From
the side, the layers have depth.

## Requirements

- **Python 3.10+** with `numpy`, `pillow`, and `playwright` (plus Playwright's Chromium).
- **[Quarto](https://quarto.org)** on the `PATH` (tested with 1.10).
- **OpenSpace** with the per-point RGB coloring and runtime `File` swap of
  `RenderablePointCloud` (see `PLAN.md`, Phase 1); currently the build in
  `A:/openspace/OpenSpace-dev-2`.
- Optional, for `verify_openspace.py`: `openspace-api`.

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m playwright install chromium
```

Run the converter from a regular Windows terminal (PowerShell or cmd). Shells without the
Windows environment variables (`PATHEXT`, `ComSpec`, `APPDATA`, ...) make Quarto fail with
"Failed to spawn 'CMD'" or "Required environment variable APPDATA not specified".

## Converting a deck

```sh
.venv/Scripts/python qmd2pointcloud.py "C:/Dropbox/University/presentations/2026-09-15 NASA SMD.qmd"
```

The deck folder is only read: the deck, `_quarto.yml`, the support folders, and the assets
the deck references are copied to a temporary folder and rendered there. The output goes
to `output/<deck>/`:

```
output/<deck>/
  <deck>.asset          the OpenSpace asset
  slides/slide_001.csv  one point cloud per slide (x, y, z, r, g, b, size)
  slides/slide_002.csv
  ...
```

The 47-slide pilot deck takes about 80 seconds and gives about 7.4 GB of CSVs. Identical
slides are stored once (hard links).

### Options

| Option | Default | Description |
| --- | --- | --- |
| `--out DIR` | `output/<deck>` | Output folder |
| `--width`, `--height` | `1920`, `1080` | Slide resolution in pixels (= points per row / column) |
| `--slide-width W` | `10` | Slide width in `--unit`s |
| `--unit` | `Km` | Unit of the CSV coordinates (`m` or `Km`) |
| `--depth MEDIA,TEXT` | `0.075,0.15` | How far the media and text layers move towards the camera, as fractions of the prime-spot distance; `0` gives a flat slide |
| `--point-size P` | `1.5` | Point size in pixel pitches; above 1 avoids gaps between the points when seen from the side, below 2 keeps the view from the prime spot exact |
| `--parent NODE` | `Root` | Scene graph parent of the slide node |
| `--position X,Y,Z` | 1 AU along −z | Position of the slide relative to the parent, in meters |
| `--project DIR` | deck folder | Quarto project root |
| `--browsers N` | `2` | Browsers that take the screenshots in parallel. Each slide gets a fixed second to settle, so more browsers competing for the CPU can capture unfinished transitions; `1` captures the slides one after the other |
| `--jobs N` | `8` (at most the CPU count) | Slides whose CSVs are written in parallel; above ~8 the disk is the limit |
| `--keep-png` | off | Keep the slide screenshots in `slides/` |
| `--from-png` | | Rebuild the CSVs and the asset from the screenshots of an earlier `--keep-png` run, without rendering |
| `--asset-only` | | Only regenerate the asset from the existing CSVs (e.g. for another `--point-size`, `--parent`, or `--position`). `--depth` is part of the CSVs and needs `--from-png` or a full run |

## Showing the slides in OpenSpace

Add the asset in OpenSpace, for example from the Lua console:

```lua
openspace.asset.add("A:/openspace/powerpointcloud/output/2026-09-15 NASA SMD/2026-09-15 NASA SMD.asset")
```

or `asset.require` it from a profile or another asset. The slides appear under
`/Presentations` in the GUI (scene graph node `Presentation_<deck>`), with these key
bindings:

| Key | Action |
| --- | --- |
| `Shift+Home` | Move the camera to the prime spot in front of the slide |
| `PageDown` / `PageUp` | Next / previous slide |
| `Home` / `End` | First / last slide |

The actions are also available in the GUI under `/Presentations/<deck>`. At the prime spot
one point covers one screen pixel when the window is 1920 pixels wide. Turn off FXAA
(`RenderEngine.FXAA`) for the sharpest text.
