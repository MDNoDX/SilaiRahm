"""The Silai Rahm mark, drawn from one description everywhere.

A tree whose trunk is two strands twisted together — "silai rahm", keeping
the ties of kinship — branching into the people of a family (the circles).
Coordinates are on a 32 × 32 grid, y downwards.

`svg()` gives the inline SVG (site, logo.svg); `polylines()` samples the
curves for raster drawing (app icons) and the PDF covers.
"""
# Strokes: each a start point and cubic Bézier segments ((c1, c2, end), …); lines are straight segments.
STRANDS = [
    # Two roots cross once and grow into the two main boughs: the ties that hold a family.
    ((10.8, 30.0), [((10.8, 24.8), (21.2, 23.0), (21.2, 16.6)), ((21.2, 13.8), (22.6, 12.0), (24.2, 10.6))]),
    ((21.2, 30.0), [((21.2, 24.8), (10.8, 23.0), (10.8, 16.6)), ((10.8, 13.8), (9.4, 12.0), (7.8, 10.6))]),
]
BRANCHES = [
    ((16.0, 22.4), (16.0, 8.6)),   # the stem between them
    ((11.0, 15.6), (6.2, 14.4)),
    ((21.0, 15.6), (25.8, 14.4)),
    ((16.0, 15.0), (12.6, 11.6)),
    ((16.0, 15.0), (19.4, 11.6)),
]
NODES = [  # (x, y, radius): the people of the family
    (16.0, 5.8, 2.9),
    (6.9, 9.4, 2.4),
    (25.1, 9.4, 2.4),
    (4.4, 14.0, 1.7),
    (27.6, 14.0, 1.7),
    (11.6, 10.6, 1.5),
    (20.4, 10.6, 1.5),
]


def svg(colour="currentColor"):
    parts = []
    for (x, y), segments in STRANDS:
        d = f"M{x:g} {y:g}" + "".join(
            f" C{a[0]:g} {a[1]:g} {b[0]:g} {b[1]:g} {c[0]:g} {c[1]:g}" for a, b, c in segments)
        parts.append(f'<path d="{d}"/>')
    parts.append('<path d="' + " ".join(f"M{a[0]:g} {a[1]:g}L{b[0]:g} {b[1]:g}" for a, b in BRANCHES) + '"/>')
    parts.append(f'<g fill="{colour}" stroke="none">' + "".join(
        f'<circle cx="{x:g}" cy="{y:g}" r="{r:g}"/>' for x, y, r in NODES) + "</g>")
    return "".join(parts)


def _bezier(p0, p1, p2, p3, steps=24):
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        yield (u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
               u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1])


def polylines():
    """Every stroke as a list of points (curves sampled), for raster drawing."""
    out = []
    for start, segments in STRANDS:
        points, current = [start], start
        for a, b, c in segments:
            points += list(_bezier(current, a, b, c))[1:]
            current = c
        out.append(points)
    out += [[a, b] for a, b in BRANCHES]
    return out
