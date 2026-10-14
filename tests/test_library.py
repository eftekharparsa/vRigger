import math
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vrigger_library import (CATEGORIES, FORMATS, PALETTES, all_objects,  # noqa: E402
                             export_objects, get, render)
from vrigger_library.geometry import bounds, circle, rounded_polygon  # noqa: E402

OBJECTS = all_objects()


def test_library_has_pulleys_and_carabiners():
    cats = {o.category for o in OBJECTS}
    assert {"Pulleys", "Carabiners"} <= cats
    assert cats <= set(CATEGORIES)
    assert len({o.id for o in OBJECTS}) == len(OBJECTS)


@pytest.mark.parametrize("obj", OBJECTS, ids=lambda o: o.id)
@pytest.mark.parametrize("palette", list(PALETTES))
def test_drawing_fits_its_canvas(obj, palette):
    d = obj.draw(palette)
    assert d.shapes
    x0, y0, x1, y1 = bounds(d)
    assert x0 >= -0.01 and y0 >= -0.01, (x0, y0)
    assert x1 <= d.width + 0.01 and y1 <= d.height + 0.01, (x1, y1, d.width, d.height)


@pytest.mark.parametrize("obj", OBJECTS, ids=lambda o: o.id)
def test_svg_is_valid_xml(obj):
    root = ET.fromstring(render(obj.draw(), "svg", obj.name))
    assert root.tag.endswith("svg")
    assert len(root.findall("{http://www.w3.org/2000/svg}path")) == len(obj.draw().shapes)


@pytest.mark.parametrize("obj", OBJECTS, ids=lambda o: o.id)
def test_eps_structure(obj):
    eps = render(obj.draw(), "eps", obj.name, scale=2.0)
    assert eps.startswith("%!PS-Adobe-3.0 EPSF-3.0")
    assert "%%BoundingBox: 0 0 " in eps and eps.rstrip().endswith("%%EOF")
    bbox = [int(v) for v in eps.split("%%BoundingBox: ")[1].split("\n")[0].split()]
    d = obj.draw()
    assert bbox[2] == round(d.width * 2 * 72 / 25.4)
    assert eps.count("gsave") == eps.count("grestore")


def test_circle_is_round():
    from vrigger_library.geometry import flatten
    pts = flatten(circle(10, 20, 5).commands, 0.05)[0][0]
    for x, y in pts:
        assert math.isclose(math.hypot(x - 10, y - 20), 5, abs_tol=0.01)


def test_rounded_polygon_stays_inside_square():
    from vrigger_library.geometry import Drawing, Style
    d = Drawing(10, 10)
    d.add(rounded_polygon([(0, 0), (10, 0), (10, 10), (0, 10)], 3), Style(fill="#000"))
    x0, y0, x1, y1 = bounds(d)
    assert (x0, y0) >= (-1e-9, -1e-9) and x1 <= 10 + 1e-9 and y1 <= 10 + 1e-9


def test_export_objects(tmp_path):
    paths = export_objects(["pulley_single", "carabiner_oval"], tmp_path, FORMATS)
    assert sorted(p.name for p in paths) == sorted(
        f"{i}.{f}" for i in ("pulley_single", "carabiner_oval") for f in FORMATS)
    again = export_objects(["pulley_single"], tmp_path, ["svg"], overwrite=False)
    assert again[0].name == "pulley_single-1.svg"


def test_export_rejects_bad_input(tmp_path):
    with pytest.raises(KeyError):
        export_objects(["nope"], tmp_path)
    with pytest.raises(ValueError):
        export_objects(["maillon"], tmp_path, ["pdf"])
    with pytest.raises(ValueError):
        export_objects(["maillon"], tmp_path, scale=0)
    assert not list(tmp_path.iterdir())


def test_cli(tmp_path):
    out = subprocess.run([sys.executable, "-m", "vrigger_library", "export", "--all",
                          "-f", "eps", "-o", str(tmp_path), "-p", "mono"],
                         cwd=ROOT, capture_output=True, text=True, check=True)
    assert len(out.stdout.split()) == len(OBJECTS)
    assert get("maillon").name in subprocess.run(
        [sys.executable, "-m", "vrigger_library", "list"], cwd=ROOT,
        capture_output=True, text=True, check=True).stdout
