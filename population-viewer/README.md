# population-viewer

Every place on Earth with 1,000+ people (GeoNames `cities1000`) as a 2 km x 2 km glass
column at its location, as tall as its population, for OpenSpace. The look matches the
`glass` style of `../scale-objects` (translucent fill, brighter edges), in crimson rather
than cyan so it stands out against the blue ocean (`--color`, `--edge-color`).

## How it works

- **Height:** 10 m per 1,000 people by default (`--meters-per-1000`), so a city of 1
  million is 10 km tall and Shanghai (24.9M) is 249 km tall. Columns start at the
  GeoNames ground elevation (`dem`) and reach 200 m (`--sink`) below it so uneven terrain
  never shows a gap.
- **Merged per band, not one node per city.** 139,000 scene graph nodes would bring
  OpenSpace to a halt, so each population band is one merged model, with vertices
  baked in Earth's body-fixed frame (WGS84, origin at Earth's center). That is 8
  renderables in total. Float32 vertices this far from the origin are good to about
  0.5 m.
- **Glass look baked in.** Each model has two materials, translucent crimson faces
  (alpha 0.3) and brighter edge frames (alpha 0.6), so no override color is used and
  there are no style toggles. The edge frames float slightly off their faces
  (`--edge-lift`, 40 m at 1x); flush with the faces they z-fight and flicker as the
  camera moves. One model with edges built in measured 86 FPS against 81
  for separate fill and edge models (all bands, 10x, over Europe).
- **Bands:** 10M+, 1M to 10M, 500k to 1M, 100k to 500k, 50k to 100k, 10k to 50k,
  5k to 10k, 1k to 5k.

## Runtime (OpenSpace)

Actions under `/Population Viewer`:

- *Show cities with 10M+ / 1M+ / 500k+ / 100k+ / 50k+ / 10k+ / 5k+ / 1k+ people*: fade
  in every band at or above the threshold and fade out the rest
- *Hide all cities*
- `/Population Viewer/Settings`: *Scale 1x / 5x / 10x (Locks Rendering)* (1x: 2 km wide,
  5x: 5 km, 10x: 10 km, the default; rendering pauses while that scale loads)

**Scales** make the columns visible from further out. They stretch height most and
widen the footprint less, so columns stay slender: at 10x a city of 1M is 100 km tall
and 10 km wide. Pick the pairs with `--scales HEIGHT:WIDTH ...`. A node scale can't do
this for a merged model (it would scale about Earth's center), and one node per city
is far too slow, so each scale is its own pre-built set of models. Only the current
scale's models are in the scene; a scale action replaces the 8 nodes with the other
scale's models.

UserProperties: `PopulationViewerMinimum` (smallest population shown, 0 = none),
`PopulationViewerScale`.

On load, the asset checks Earth's radii (via `openspace.navigation.localPositionFromGeo`)
against the ones the models were built for and warns if they differ.

## Usage

    pip install -r requirements.txt
    python generate.py                       # scales 1:1 5:2.5 10:5 (~306 MB)
    python generate.py --no-edges            # faces only, no edge frames (~66 MB)
    python generate.py --scales 1 20:8       # 1x, and 20x height / 8x width (~102 MB per scale)
    python generate.py --meters-per-1000 20  # twice as tall

Output lands in `build/`: `population-viewer.asset`, `models/`, `LICENSE.md` and a user-facing
`README.md` (usage, data source and version, exclusions, caveats, counts per band). Copy
`build/` into `${USER_ASSETS}/population-viewer/` keeping the layout, or pass `--out`,
then add `${USER_ASSETS}/population-viewer/population-viewer` in OpenSpace.

Built and tested with OpenSpace 0.22.1: the asset requires
`scene/solarsystem/planets/earth/globe` and the models assume its WGS84 Earth (the asset
warns on load if Earth's radii differ; regenerate with `--radii`).
The runtime code is `lua/population-viewer.asset`, a template that `generate.py` fills
in with the band data.

## Data

GeoNames `cities1000` (https://download.geonames.org/export/dump/cities1000.zip),
CC BY 4.0, which requires attribution (in `build/LICENSE.md` and the asset metadata).
Downloads to `data/` on first run.

- Left out: sections of other places (`PPLX`: neighborhoods), historical, abandoned and
  destroyed places, and anything under 1,000 people.
- Places already counted in a larger one are dropped (`CONTAINERS` in `generate.py`):
  the five NYC boroughs (in New York City's 8.8M) and every place in the Shanghai
  municipality (in its 24.9M).
- Caveat: GeoNames populations mix city-proper and whole-municipality figures. Chongqing
  (22M) and Chengdu (20.9M) are municipality/prefecture totals; Tokyo (9.7M) is only
  the 23 wards. Neighboring cities in one metro area (Cairo / Giza, Mumbai / Thane) are
  separate columns.

## Layout

- `generate.py`: data loading, column meshes, GLB and asset writers
- `lua/population-viewer.asset`: runtime template (nodes, actions, UserProperties)
