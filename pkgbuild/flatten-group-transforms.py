#!/usr/bin/env python3
"""Move every <g transform> in the symbolic icons onto the shapes inside it.

GTK 4 draws a "-symbolic" icon with its own SVG renderer, and that renderer
ignores a transform written on a group. Papirus writes many icons that way —
network-transmit-receive draws its arrows inside translate(-201 -503.36) — so
under GTK they came out empty, or shifted off their frame. A transform on the
shape itself is honoured, and moving it there draws the same picture.

Usage: flatten-group-transforms.py THEME_DIR...

Only symbolic icons are rewritten: files named "*-symbolic.svg", and the files
those names link to (Papirus links many of them into panel/). A group that
also clips, masks or filters is left alone, because its clip is drawn in the
group's own coordinates and would move if the transform left it.
"""

import os
import sys
from xml.dom import minidom
from xml.parsers.expat import ExpatError

# Elements a transform can move. Anything else inside a group — <title>,
# <defs>, <style> — has no geometry of its own and is left untouched.
DRAWN = {
    "path",
    "rect",
    "circle",
    "ellipse",
    "line",
    "polyline",
    "polygon",
    "text",
    "use",
    "image",
    "g",
}
KEEPS_ITS_FRAME = ("clip-path", "mask", "filter")


def local_name(node):
    return node.tagName.split(":")[-1]


def push_down(group):
    """Give the group's transform to its children, then do the same below."""
    moved = False
    transform = group.getAttribute("transform").strip()
    if transform and not any(group.hasAttribute(name) for name in KEEPS_ITS_FRAME):
        for child in group.childNodes:
            if child.nodeType != child.ELEMENT_NODE or local_name(child) not in DRAWN:
                continue
            # The group's transform applies first, so it comes first in the list.
            own = child.getAttribute("transform").strip()
            child.setAttribute("transform", f"{transform} {own}".strip())
        group.removeAttribute("transform")
        moved = True
    for child in group.childNodes:
        if child.nodeType == child.ELEMENT_NODE:
            if local_name(child) == "g":
                moved |= push_down(child)
            else:
                moved |= push_down_below(child)
    return moved


def push_down_below(node):
    moved = False
    for child in node.childNodes:
        if child.nodeType == child.ELEMENT_NODE and local_name(child) == "g":
            moved |= push_down(child)
    return moved


def flatten(path):
    with open(path, "rb") as source:
        document = minidom.parse(source)
    if not push_down_below(document.documentElement):
        return False
    # Written without an XML declaration, as the originals are.
    with open(path, "w", encoding="utf-8") as target:
        target.write(document.documentElement.toxml())
        target.write("\n")
    return True


def symbolic_files(themes):
    """Every real file a symbolic icon name resolves to, once each."""
    seen = set()
    for theme in themes:
        for root, _dirs, files in os.walk(theme, followlinks=True):
            for name in files:
                if not name.endswith("-symbolic.svg"):
                    continue
                real = os.path.realpath(os.path.join(root, name))
                if real not in seen and os.path.isfile(real):
                    seen.add(real)
                    yield real


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    changed = 0
    for path in symbolic_files(sys.argv[1:]):
        # A broken icon stays as it was, and says so.
        try:
            changed += flatten(path)
        except (OSError, ExpatError) as error:
            print(f"flatten-group-transforms: {path}: {error}", file=sys.stderr)
    print(f"flatten-group-transforms: {changed} icons rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
