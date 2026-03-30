# Generate Moon Assets

Python scripts that generate [OpenSpace](https://www.openspaceproject.com/) `.asset` files for Saturn's minor moons, using SPICE kernel data from JPL.

## Scripts

### `generatemoonassets.py`

Generates OpenSpace asset files for recently discovered Saturn moons. For each moon it creates:

- A **RenderableGlobe** scene graph node (body)
- A **RenderableTrailOrbit** (orbital trail)
- A **RenderableLabel** (text label, disabled by default)

All objects are parented to `SaturnBarycenter` and placed under `/Solar System/Planets/Saturn/Minor Moons/<Group> Group/` in the GUI.

The script contains two ID blocks mapping provisional moon designations to SPICE kernel IDs:

| Block | IDs | SPICE Kernel | Description |
|-------|-----|--------------|-------------|
| `id_block2` | 65094 -- 65157 | `kernels454` (SAT453) | May 2023 discoveries |
| `id_block` | 65158 -- 65285 | `kernels455` | March 2025 discoveries |

The active block (`id_block`, parsed on line 225) is split into two output files to keep asset sizes manageable (e.g. `march_2025_discoveries-1.asset` and `march_2025_discoveries-2.asset`). To switch batches, change line 225 to parse `id_block2` instead.

### `lookuptable.py`

A data module exporting a `saturn_moons` dictionary with physical and orbital properties for ~288 Saturn moons. Each entry contains:

- **group** -- dynamical family (e.g. Norse (Mundilfari), Inuit (Kiviuq), Gallic, inner ring)
- **orbital_period_days** -- orbital period in days (negative values indicate retrograde orbits)
- **diameter_km** -- approximate diameter in km

Groups covered: inner/regular moons, co-orbital, ring-embedded, trojans, Inuit, Gallic, and Norse (with sub-groups Mundilfari, Phoebe, Kari, low-inclination).

When run standalone it prints a summary table of all moons sorted by orbital period.

## Usage

```bash
python generatemoonassets.py
```

This writes two `.asset` files in the current directory. Place them in the appropriate OpenSpace data folder alongside the referenced SPICE kernel and transforms assets.

## Dependencies

- Python 3.6+ (f-strings)
- No external packages
