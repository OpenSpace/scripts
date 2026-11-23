"""Visual presets for region models.

Every region gets up to three models per body, each its own renderable:
  * Fill    - the region's surface, draped over the body
  * Grid    - lines every `grid_spacing` meters, centered on the region
  * Outline - the border, as a flat band just inside it (or a vertical wall)

Which of the three are shown is chosen at runtime through UserProperties (see
lua/scale_locations.asset). A style sets the geometry and the default look; color and
opacity remain live properties in OpenSpace.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Part:
    enabled: bool = True  # whether the model is generated at all
    color: tuple[float, float, float] = (1.0, 0.55, 0.1)
    opacity: float = 1.0  # baked into OverrideColor's alpha
    shading: bool = False  # lit by the Sun (True) or flat unlit color (False)
    wireframe: bool = False
    texture: str | None = None  # name of a generated texture in textures.py


@dataclass
class Style:
    name: str
    description: str
    fill: Part = field(default_factory=Part)
    grid: Part = field(default_factory=lambda: Part(enabled=False))
    outline: Part = field(default_factory=Part)

    fill_height: float = 0.0  # m above the anchor, baked into the model
    texture_tile: float = 100_000.0  # m covered by one repeat of a fill texture

    grid_spacing: float = 100_000.0  # m between lines
    grid_width: float = 1_500.0  # m, line width on the ground
    grid_lift: float = 150.0  # m above the fill, avoids z-fighting

    simplify: float = 250.0  # m, border simplification (below the data's accuracy)

    # "band": flat strip just inside the border, visible from above.
    # "wall": vertical wall from outline_bottom to outline_top, visible from the side.
    outline_mode: str = "band"
    outline_width: float | None = None  # m; None = ~1% of the region's size, clipped:
    outline_min: float = 1_500.0  # m
    outline_max: float = 6_000.0  # m
    outline_lift: float = 250.0  # m above the fill (band mode)
    outline_bottom: float = -2_000.0  # m (wall mode)
    outline_top: float = 2_000.0  # m (wall mode)


ORANGE = (1.0, 0.55, 0.1)
CYAN = (0.2, 0.85, 1.0)
LIGHT_CYAN = (0.45, 0.92, 1.0)

STYLES: dict[str, Style] = {
    s.name: s
    for s in [
        Style(
            "glass",
            "Translucent cyan fill, 100 km grid lines and border band, all see-through.",
            fill=Part(color=CYAN, opacity=0.3),
            grid=Part(color=LIGHT_CYAN, opacity=0.3),
            outline=Part(color=LIGHT_CYAN, opacity=0.6),
        ),
        Style(
            "solid",
            "Opaque, unlit orange fill and a darker border band.",
            fill=Part(color=ORANGE),
            grid=Part(color=(1.0, 0.8, 0.55)),
            outline=Part(color=(0.65, 0.3, 0.0)),
        ),
        Style(
            "fence",
            "Tall translucent wall along the border, for low oblique views.",
            fill=Part(color=ORANGE, opacity=0.25),
            outline=Part(color=ORANGE, opacity=0.85),
            outline_mode="wall",
            outline_bottom=-1_000.0,
            outline_top=15_000.0,
        ),
        Style(
            "slab",
            "Thick, Sun-lit block. Most 'physical' looking.",
            fill=Part(color=(0.95, 0.85, 0.6), shading=True),
            outline=Part(color=(0.95, 0.85, 0.6), shading=True),
            fill_height=10_000.0,
            outline_mode="wall",
            outline_bottom=-2_000.0,
            outline_top=10_000.0,
        ),
    ]
}
