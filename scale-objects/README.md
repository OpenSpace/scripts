# scale-objects

Generates true-scale region models (US states, countries, cities) as OpenSpace assets,
for size comparisons on any globe.

How these differ from the landmark scale models (Eiffel Tower etc.):

- **Curved to the globe.** Regions are hundreds of km across, so a flat model would
  float off the surface at its edges. Each region is projected with an equal-area
  (Lambert azimuthal) projection and wrapped onto a sphere of Earth's radius, keeping
  its true area. When placed on another globe, its anchor node gets a vertical scale of
  Earth radius / globe radius (from `openspace.interactionSphere`), which gives that
  globe's curvature. One set of models works on Earth, Mars, Titan, Mimas, ...
- **Three parts per region:** Fill, Grid (lines every 100 km from the center) and
  Outline (a band just inside the border), each its own model, so they can be
  switched at runtime.
- **Hidden until used.** Everything starts disabled; actions fade regions in and out.
- **Few asset files.** Each set is split into a handful of group assets (US states:
  Northeast, Southeast, Midwest, Southwest, West; countries: the 23 UN M49
  subregions, Northern Europe ... Antarctica), plus one set asset that requires
  them all. Groups never overlap, so any combination can be loaded together. They are
  packaging only: there are no group actions, users work with the per-region actions.
  Group assets are just data; the node and action code lives in the shared asset.

## Runtime (OpenSpace)

`scale_locations.asset` (required by every set) adds UserProperties and actions under
`/Scale Objects/Settings`:

| UserProperty | Actions |
|---|---|
| `ScaleLocationFills`, `ScaleLocationGrids`, `ScaleLocationOutlines` | Enable / Disable scale location fills, grids, outlines |
| `ScaleLocationAltitude` (m above terrain at the region center) | Raise / Lower scale locations (2 km steps), Reset scale location height |
| `ScaleLocationFitCurvature` | Fit scale locations to globe curvature (default) / Keep scale locations at Earth curvature (vertical scale 1) |
| `ScaleLocationsShown` (managed by the actions) | Hide all scale locations (in `/Scale Objects`) |

Each region has: *Show <name> under camera* and *Show <name> where the camera is
looking* (on whatever globe the camera is anchored to, turned so the region's north is
at the top of the screen), *Show <name> at its real location* (true north), and
*Hide <name>*. "Where the camera is looking" intersects the center of the view with the
globe, using only the navigation state (position, up, yaw, pitch), and does nothing
when the view is on the sky.

Depth testing stays on, so high terrain (e.g. Tharsis on Mars) can hide parts of a
region: raise the regions rather than drawing through the planet.

## Usage

    pip install -r requirements.txt
    python generate.py us-states                       # all 50 states (150 .glb, ~3.4 MB)
    python generate.py us-states --only NY TX
    python generate.py countries                       # 241 countries/territories (718 .glb, ~40 MB)
    python generate.py country-capitals                # 183 capitals, 8 UN SDG region groups
    python generate.py most-populated-cities           # top 100, one group per continent
    python generate.py top-openspace-cities            # top 50 by OpenSpace launches
    python generate.py us-state-capitals               # 50 capitals (city limits)
    python generate.py style-test --only "New York"    # every style, side by side
    python preview.py "New York"                       # offline style preview PNG

Output lands in `build/`: `scale_locations.asset` plus one folder per set, e.g.
`build/us_states/` with `models/`, `northeast.asset` ... `west.asset` and
`us_states.asset` (all groups). Copy `build/` into `${USER_ASSETS}/<folder>/` keeping
the layout, or pass `--out`.
Boundary data downloads to `data/` on first run. `build/LICENSE.md` lists every
source and its terms; all boundary data must come from public domain sources.

## Data

- **US states:** US Census Bureau Cartographic Boundary Files 2024, 1:5M (public
  domain). The 50 states; DC and territories are left out.
- **Countries:** Natural Earth Admin 0 Countries, 1:10m (public domain), de facto
  boundaries as Natural Earth maps them. Sovereign states plus dependencies and
  territories; specks, leases, bases and buffer zones are left out (`COUNTRY_EXCLUDE`).
  Parts more than 1000 km from the rest of a country are dropped (France without
  French Guiana, the US without Hawaii), except for island nations whose largest piece
  is under half their land.
- **Country capitals / 100 most populated cities:** GHS Urban Centre Database 2025
  (EU JRC, CC BY 4.0). One definition worldwide: contiguous 1 km cells with at least
  1,500 people/km², 50,000 people in total, so small capitals are missing and some
  centres span several cities (Guangzhou, 43 million). Names as in GHS-UCDB; the 2025
  population is in each description. Capitals are its `GC_UCM_CAP` flag; continents for
  the top 100 come from the Natural Earth country containing each centre.
- **Top OpenSpace cities:** launch counts per location from the usage statistics at
  status.openspaceproject.com (`data/openspace_usage.json`, downloaded once; delete it to
  refresh). Each location goes to the GHS-UCDB urban centre containing it, else the nearest
  within 25 km; the top 50 centres by all-time launches are kept (~75% of all launches;
  the rest are in smaller towns or farther out).
- **US state capitals:** US Census Bureau 2024 Places (public domain): official city
  limits, so e.g. Juneau is ~7,000 km².
- Cities use 10 km grid lines, a 250 m-1 km border band and 50 m simplification
  (`CITY_STYLE` in sources.py).
- Borders are simplified by 250 m (below the accuracy of either source) and meshed
  with ~20 km cells (8 m of chord sag on Earth).

## Layout

- `scaleobjects/sources.py`: data sources, their groups and licenses
- `scaleobjects/geometry.py`: projection, meshing, draping
- `scaleobjects/parts.py`: builds Fill / Grid / Outline meshes for a style
- `scaleobjects/styles.py`: style presets (`glass` is the default)
- `scaleobjects/writers.py`: GLB/OBJ and asset writers
- `lua/scale_locations.asset`: shared runtime settings and actions
