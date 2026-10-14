"""Command line interface.

    python -m vrigger_library                 # open the graphical chooser
    python -m vrigger_library list
    python -m vrigger_library export pulley_single carabiner_hms -f svg eps -o ./out
    python -m vrigger_library export --all -f eps -o ./out --palette mono
"""

from __future__ import annotations

import argparse
import sys

from . import CATEGORIES, FORMATS, PALETTES, all_objects, export_objects


def _cmd_list(_args: argparse.Namespace) -> int:
    for cat in CATEGORIES:
        print(cat)
        for obj in all_objects():
            if obj.category == cat:
                print(f"  {obj.id:<18} {obj.name}")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    ids = [o.id for o in all_objects()] if args.all else args.ids
    if not ids:
        print("error: name at least one object id or use --all", file=sys.stderr)
        return 2
    try:
        paths = export_objects(ids, args.output, args.formats, args.palette,
                               args.scale, overwrite=not args.keep)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc.args[0]}", file=sys.stderr)
        return 2
    for p in paths:
        print(p)
    return 0


def _cmd_gui(_args: argparse.Namespace) -> int:
    from .gui import main
    main()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vrigger_library",
                                     description="vRigger object library exporter")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("gui", help="open the graphical chooser (default)").set_defaults(func=_cmd_gui)
    sub.add_parser("list", help="list available objects").set_defaults(func=_cmd_list)
    ex = sub.add_parser("export", help="save objects as SVG/EPS")
    ex.add_argument("ids", nargs="*", help="object ids (see 'list')")
    ex.add_argument("--all", action="store_true", help="export every object")
    ex.add_argument("-f", "--formats", nargs="+", choices=FORMATS, default=["svg"])
    ex.add_argument("-o", "--output", default=".", help="destination folder")
    ex.add_argument("-p", "--palette", choices=tuple(PALETTES), default="color")
    ex.add_argument("-s", "--scale", type=float, default=1.0,
                    help="size multiplier (1 = real size in mm)")
    ex.add_argument("-k", "--keep", action="store_true",
                    help="never overwrite; add a number to the file name instead")
    ex.set_defaults(func=_cmd_export)
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        return _cmd_gui(args)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
