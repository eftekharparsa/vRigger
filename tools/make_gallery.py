"""Regenerate docs/gallery.svg showing every object in the library.

    python tools/make_gallery.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vrigger_library import all_objects, save  # noqa: E402
from vrigger_library.geometry import Drawing, Shape  # noqa: E402

GAP = 12.0


def _shift(cmd, dx, dy):
    if cmd[0] == "Z":
        return cmd
    return (cmd[0],) + tuple((x + dx, y + dy) for x, y in cmd[1:])


def main() -> None:
    drawings = [o.draw("color") for o in all_objects()]
    height = max(d.height for d in drawings)
    width = sum(d.width for d in drawings) + GAP * (len(drawings) - 1)
    sheet = Drawing(width, height)
    x = 0.0
    for d in drawings:
        dy = height - d.height          # align objects on a common baseline
        for s in d.shapes:
            sheet.shapes.append(Shape([_shift(c, x, dy) for c in s.commands], s.style))
        x += d.width + GAP
    out = save(sheet, ROOT / "docs" / "gallery.svg", title="vRigger object library",
               scale=0.5)
    print(out)


if __name__ == "__main__":
    main()
