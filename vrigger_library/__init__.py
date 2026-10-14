"""vRigger object library: rope-rigging equipment as SVG / EPS vector graphics."""

from __future__ import annotations

import os
from pathlib import Path

from .catalog import CATEGORIES, PALETTES, LibraryObject, all_objects, get
from .export import FORMATS, render, save

__version__ = "0.1.0"

__all__ = ["CATEGORIES", "FORMATS", "PALETTES", "LibraryObject", "all_objects",
           "get", "render", "save", "export_objects"]


def export_objects(ids: list[str], out_dir: str | os.PathLike,
                   formats: list[str] | tuple[str, ...] = ("svg",),
                   palette: str = "color", scale: float = 1.0,
                   overwrite: bool = True) -> list[Path]:
    """Save each object in each format into ``out_dir``; return written paths.

    Files are named ``<object id>.<format>``. With ``overwrite=False`` an
    existing file gets a numeric suffix instead of being replaced.
    """
    if not ids:
        raise ValueError("no objects selected")
    if not formats:
        raise ValueError("no output format selected")
    for fmt in formats:
        if fmt not in FORMATS:
            raise ValueError(f"unknown format {fmt!r}; choose from {FORMATS}")
    if palette not in PALETTES:
        raise ValueError(f"unknown palette {palette!r}; choose from {tuple(PALETTES)}")
    if scale <= 0:
        raise ValueError("scale must be positive")
    objects = [get(i) for i in ids]          # validate all ids before writing
    out = Path(out_dir).expanduser()
    written = []
    for obj in objects:
        drawing = obj.draw(palette)
        for fmt in formats:
            target = out / f"{obj.id}.{fmt}"
            n = 1
            while not overwrite and target.exists():
                target = out / f"{obj.id}-{n}.{fmt}"
                n += 1
            written.append(save(drawing, target, title=obj.name, scale=scale))
    return written
