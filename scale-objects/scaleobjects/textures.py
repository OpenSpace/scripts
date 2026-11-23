"""Procedural textures for region fills."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def grid100km(path: Path, size: int = 512) -> None:
    """One tile = one texture repeat. Lines on the tile edge make a continuous grid."""
    img = Image.new("RGB", (size, size), (235, 120, 25))
    d = ImageDraw.Draw(img)
    w = max(2, size // 64)
    d.rectangle([0, 0, size - 1, w - 1], fill=(255, 255, 255))
    d.rectangle([0, 0, w - 1, size - 1], fill=(255, 255, 255))
    # Fainter 50 km sub-grid.
    half = size // 2
    sub = max(1, w // 2)
    d.rectangle([0, half - sub // 2, size - 1, half + sub // 2], fill=(250, 190, 130))
    d.rectangle([half - sub // 2, 0, half + sub // 2, size - 1], fill=(250, 190, 130))
    img.save(path)


TEXTURES = {"grid100km": grid100km}


def write_texture(name: str, folder: Path) -> str:
    filename = f"{name}.png"
    TEXTURES[name](folder / filename)
    return filename
