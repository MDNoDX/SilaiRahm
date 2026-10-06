"""Family-tree layout shared by the web view (SVG/PNG) and the PDF export.

One connected chart around a focus person, with no one drawn twice:

* the focus person among their brothers and sisters, with spouse(s) and all
  descendants below;
* above them the parents as one couple, the father's family on the left and
  the mother's family on the right; the same again for every generation of
  ancestors (in each couple the husband's kin go left, the wife's kin right);
* the brothers and sisters of every ancestor (amaki, amma, togʻa, xola, …)
  with their spouses and descendants. They can be opened and closed; by
  default those of the parents are open and older generations are closed.
  Their children (cousins) are folded behind a "+N" button in the compact
  view, so the chart stays readable; "open everything" shows them all.

Branches are packed with per-row contours (a tidy-tree technique): they sit
as close as possible without overlapping, and a couple stays side by side
unless relatives between them make that impossible.

Coordinates are abstract units; the browser and the PDF scale them.
"""
from django.utils.translation import ngettext

from .kinship import Archive
from .terminology import generation_label

CARD_W, CARD_H = 220, 92
SIB_GAP, COUPLE_GAP, GROUP_GAP, ROW_GAP = 26, 34, 46, 78
ROW_H = CARD_H + ROW_GAP
PAD = 48
NEG_INF = float("-inf")
POS_INF = float("inf")


class Block:
    """Placed cards and lines plus, per row, the horizontal extent in use.

    Contour keys are row numbers for cards and row + 0.5 for the band of
    connecting lines under that row.
    """

    def __init__(self):
        self.nodes = []
        self.lines = []
        self.cont = {}

    def extend(self, key, lo, hi):
        c = self.cont.get(key)
        self.cont[key] = [min(c[0], lo), max(c[1], hi)] if c else [lo, hi]

    def add_node(self, node):
        self.nodes.append(node)
        self.extend(node["row"], node["x"], node["x"] + CARD_W)
        if node.get("kids"):  # the open/close button under the card
            self.extend(node["row"] + 0.5, node["x"], node["x"] + CARD_W)
        return node

    def add_line(self, points, kind, band=None, **who):
        """`who`: the people a line joins (to=child, a/b=couple), for highlighting."""
        self.lines.append({"points": [list(p) for p in points], "kind": kind, **who})
        if band is not None:
            xs = [p[0] for p in points]
            self.extend(band, min(xs), max(xs))

    def shift(self, dx):
        if not dx:
            return
        for n in self.nodes:
            n["x"] += dx
        for line in self.lines:
            for p in line["points"]:
                p[0] += dx
        for c in self.cont.values():
            c[0] += dx
            c[1] += dx

    def merge(self, other):
        self.nodes += other.nodes
        self.lines += other.lines
        for key, (lo, hi) in other.cont.items():
            self.extend(key, lo, hi)
        return self

    def lower(self, min_key):
        """The contour from row/band `min_key` downwards."""
        view = Block()
        view.cont = {k: list(v) for k, v in self.cont.items() if k >= min_key}
        return view


def gap_needed(left, right, gap):
    """How far `right` must move right to clear `left` on every shared row."""
    need = NEG_INF
    for key, (lo, _hi) in right.cont.items():
        if key in left.cont:
            need = max(need, left.cont[key][1] + gap - lo)
    return need


def room_before(left, right, gap):
    """How far `left` may move right before it touches `right`."""
    room = POS_INF
    for key, (_lo, hi) in left.cont.items():
        if key in right.cont:
            room = min(room, right.cont[key][0] - gap - hi)
    return room


def row_y(row):
    return row * ROW_H


def pack(parts, gap_for):
    """Place blocks left to right as tightly as their contours allow.

    parts: [(block, anchor_x)]; returns (merged block, shifted anchor xs).
    """
    merged, anchors = Block(), []
    for i, (block, ax) in enumerate(parts):
        dx = gap_needed(merged, block, gap_for(i)) if i else 0.0
        dx = 0.0 if dx == NEG_INF else dx
        block.shift(dx)
        merged.merge(block)
        anchors.append(ax + dx)
    return merged, anchors


class TreeLayout:
    def __init__(self, archive: Archive, focus_id, open_all=False, opened=(), closed=(), folded=(), unfolded=(),
                 side=None):
        self.a = archive
        self.focus = focus_id
        self.side = side  # "paternal" / "maternal": only that half of the ancestry
        self.open_all = open_all
        self.opened = set(opened)
        self.closed = set(closed)
        self.folded = set(folded)
        self.unfolded = set(unfolded)
        self.placed = set()

    # ---- helpers --------------------------------------------------------------
    def _born(self, pk):
        return (self.a.people[pk].birth_key or (9999,), pk)

    def _full_siblings(self, pk):
        """Children of exactly the same parents (or of the same single parent)."""
        me = self.a.people[pk]
        if not me.father_id and not me.mother_id:
            return []
        return sorted(
            (o for o, p in self.a.people.items()
             if o != pk and p.father_id == me.father_id and p.mother_id == me.mother_id),
            key=self._born,
        )

    def _siblings_open(self, pk, level):
        if pk in self.closed:
            return False
        return self.open_all or pk in self.opened or level <= 1

    def _kind(self, marriage):
        if marriage is None:
            return "partners"
        return "divorced" if marriage.is_divorced else "couple"

    def _connect(self, block, drop, centers, child_row, level=0, ids=()):
        """Lines from a couple's drop point down to their children."""
        # One elbow per child (down, across, down) so the browser can round
        # the corners; the shared trunk is simply drawn over itself.
        bar = row_y(child_row) - ROW_GAP / 2 + 8 * level
        dx, dy = drop
        band = child_row - 0.5
        for i, cx in enumerate(centers):
            who = {"to": ids[i]} if i < len(ids) else {}
            if abs(cx - dx) < 0.5:
                block.add_line([(dx, dy), (dx, row_y(child_row))], "child", band=band, **who)
            else:
                block.add_line([(dx, dy), (dx, bar), (cx, bar), (cx, row_y(child_row))], "child", band=band, **who)

    # ---- descendants ----------------------------------------------------------
    def desc(self, pk, row, collateral=False):
        """pk with spouse(s) and, unless folded, all descendants. Returns (block, x of pk).

        collateral: pk is a brother or sister of an ancestor; their children
        start folded unless everything is open or the user unfolded them.
        """
        block = Block()
        if pk in self.placed:
            block.add_node({"id": pk, "x": 0.0, "row": row, "dup": True})
            return block, 0.0
        self.placed.add(pk)

        groups = {}
        for partner, marriage in self.a.unions.get(pk, []):
            groups[partner] = {"partner": partner, "marriage": marriage, "kids": []}
        for kid in self.a.children.get(pk, []):
            child = self.a.people[kid]
            other = child.mother_id if child.father_id == pk else child.father_id
            other = other if other in self.a.people else None
            groups.setdefault(other, {"partner": other, "marriage": None, "kids": []})["kids"].append(kid)
        ordered = [g for key, g in groups.items() if key is not None]
        if None in groups:
            ordered.append(groups[None])

        kid_total = sum(len(g["kids"]) for g in ordered)
        folded = pk in self.folded or (
            collateral and not self.open_all and pk not in self.unfolded)
        block.add_node({"id": pk, "x": 0.0, "row": row, "dup": False,
                        "kids": {"count": kid_total, "open": not folded} if kid_total else None})

        spouses = [g for g in ordered if g["partner"] is not None]
        mid = row_y(row) + CARD_H / 2
        for i, g in enumerate(spouses, start=1):
            g["x"] = i * (CARD_W + COUPLE_GAP)
            dup = g["partner"] in self.placed
            self.placed.add(g["partner"])
            block.add_node({"id": g["partner"], "x": g["x"], "row": row, "dup": dup})
            kind = self._kind(g["marriage"])
            if i == 1:  # the first spouse stands next to pk
                block.add_line([(CARD_W, mid), (g["x"], mid)], kind, a=pk, b=g["partner"])
                g["drop"] = ((CARD_W + g["x"]) / 2, mid)
            else:       # later spouses: a line over the cards
                top = row_y(row) - 10 - 7 * i
                block.add_line([(CARD_W / 2, row_y(row)), (CARD_W / 2, top),
                                (g["x"] + CARD_W / 2, top), (g["x"] + CARD_W / 2, row_y(row))],
                               kind, band=row - 0.5, a=pk, b=g["partner"])
                g["drop"] = (g["x"] + CARD_W / 2, row_y(row) + CARD_H)
        for g in ordered:
            g.setdefault("drop", (CARD_W / 2, row_y(row) + CARD_H))

        if folded or not kid_total:
            return block, 0.0

        parts, owners, kid_ids = [], [], []
        for gi, g in enumerate(ordered):
            for ki, kid in enumerate(g["kids"]):
                kb, kx = self.desc(kid, row + 1)
                parts.append((kb, kx))
                owners.append((gi, ki))
                kid_ids.append(kid)
        kids_block, xs = pack(parts, lambda i: GROUP_GAP if owners[i][1] == 0 else SIB_GAP)
        centers = [x + CARD_W / 2 for x in xs]
        unit_w = (len(spouses) + 1) * CARD_W + len(spouses) * COUPLE_GAP
        shift = unit_w / 2 - (min(centers) + max(centers)) / 2
        kids_block.shift(shift)
        block.merge(kids_block)
        for gi, g in enumerate(ordered):
            mine = [i for i, (ogi, _k) in enumerate(owners) if ogi == gi]
            cs = [centers[i] + shift for i in mine]
            if cs:
                self._connect(block, g["drop"], cs, row + 1, level=gi if len(ordered) > 1 else 0,
                              ids=[kid_ids[i] for i in mine])
        return block, 0.0

    def _alone(self, pk, row):
        """Just this person's card (no brothers, sisters or ancestors)."""
        block = Block()
        self.placed.add(pk)
        block.add_node({"id": pk, "x": 0.0, "row": row, "dup": False, "sibs": None})
        return block, 0.0

    # ---- ancestors and their families ----------------------------------------
    def up(self, pk, row, side, level):
        """pk among their brothers and sisters, with all their ancestry above.

        side "left": pk stands at the right end of the sibling row (the
        husband's family in the couple below); "right": at the left end.
        Returns (block, x of pk).
        """
        is_focus = level == 0
        sibs = self._full_siblings(pk)
        sib_open = is_focus or self._siblings_open(pk, level)
        if is_focus:
            members = sorted([pk] + sibs, key=self._born)
        elif not sib_open:
            members = [pk]
        else:
            members = sibs + [pk] if side == "left" else [pk] + sibs

        parts = []
        for member in members:
            if member == pk and not is_focus:
                mb = Block()
                self.placed.add(pk)
                info = {"count": len(sibs), "open": sib_open, "side": side} if sibs else None
                mb.add_node({"id": pk, "x": 0.0, "row": row, "dup": False, "sibs": info})
                parts.append((mb, 0.0))
            else:
                parts.append(self.desc(member, row, collateral=not is_focus))
        row_block, xs = pack(parts, lambda i: SIB_GAP)
        pk_x = xs[members.index(pk)]
        centers = [x + CARD_W / 2 for x in xs]

        me = self.a.people[pk]
        father = me.father_id if me.father_id in self.a.people else None
        mother = me.mother_id if me.mother_id in self.a.people else None
        if not father and not mother:
            return row_block, pk_x
        # "Father's side only": the mother is still shown next to the father,
        # but without her own family (and the other way round).
        alone = {"paternal": mother, "maternal": father}.get(self.side) if is_focus else None

        left = right = None
        fx = mx = 0.0
        if father:
            left, fx = self._alone(father, row - 1) if father == alone else self.up(father, row - 1, "left", level + 1)
        if mother:
            right, mx = self._alone(mother, row - 1) if mother == alone else self.up(mother, row - 1, "right", level + 1)
        if left and right:
            dx = max(gap_needed(left, right, COUPLE_GAP), fx + CARD_W + COUPLE_GAP - mx)
            right.shift(dx)
            mx += dx

        def drop_x():
            if left and right:
                return (fx + CARD_W + mx) / 2
            return (fx if left else mx) + CARD_W / 2

        # Place the sibling row under the parents but clear of the relatives
        # the parents' families bring into the same rows.
        low = row - 0.5
        span_mid = (min(centers) + max(centers)) / 2
        target = drop_x() - span_mid
        view = Block()
        view.cont = {k: list(v) for k, v in row_block.cont.items()}
        view.extend(low, min(centers + [span_mid]), max(centers + [span_mid]))
        lo = gap_needed(left.lower(low), view, SIB_GAP) if left else NEG_INF
        hi = room_before(view, right.lower(low), SIB_GAP) if right else POS_INF
        if lo > hi and right:
            # Not enough room between the two families: move the wife's side.
            right.shift(lo - hi)
            mx += lo - hi
            hi = lo
            target = drop_x() - span_mid
        shift = min(max(target, lo), hi)
        row_block.shift(shift)
        pk_x += shift
        centers = [c + shift for c in centers]

        block = Block()
        for part in (left, right, row_block):
            if part:
                block.merge(part)

        prow = row - 1
        if left and right:
            kind = self._kind(self.a.marriage_between(father, mother))
            between = any(
                row_y(n["row"]) == row_y(prow) and fx < n["x"] < mx for n in block.nodes
            )
            if not between:
                mid = row_y(prow) + CARD_H / 2
                block.add_line([(fx + CARD_W, mid), (mx, mid)], kind, a=father, b=mother)
                drop = ((fx + CARD_W + mx) / 2, mid)
            else:
                low_y = row_y(prow) + CARD_H + ROW_GAP / 4
                block.add_line([(fx + CARD_W / 2, row_y(prow) + CARD_H), (fx + CARD_W / 2, low_y),
                                (mx + CARD_W / 2, low_y), (mx + CARD_W / 2, row_y(prow) + CARD_H)], kind,
                               a=father, b=mother)
                drop = ((fx + mx + CARD_W) / 2, low_y)
        else:
            drop = (drop_x(), row_y(prow) + CARD_H)
        self._connect(block, drop, centers, row, ids=members)
        return block, pk_x

    def build(self):
        block, _x = self.up(self.focus, 0, "left", 0)
        return self._finish(block)

    def _finish(self, block):
        nodes = block.nodes
        min_x = min(n["x"] for n in nodes)
        min_y = min(row_y(n["row"]) for n in nodes)
        dx, dy = PAD - min_x, PAD - min_y
        rows = sorted({n["row"] for n in nodes})
        for n in nodes:
            n["x"] = round(n["x"] + dx, 1)
            n["gen"] = n["row"]
            n["y"] = round(row_y(n.pop("row")) + dy, 1)
        lines = [{**line, "points": [[round(x + dx, 1), round(y + dy, 1)] for x, y in line["points"]]}
                 for line in block.lines]
        width = max(n["x"] for n in nodes) + CARD_W + PAD
        height = max(n["y"] for n in nodes) + CARD_H + PAD + 24
        return {"nodes": nodes, "lines": lines, "width": round(width), "height": round(height),
                "rows": [{"gen": row, "y": round(row_y(row) + dy, 1)} for row in rows]}


def build_tree(archive: Archive, focus_id, photo_urls=True, viewer_person=None,
               open_all=False, opened=(), closed=(), folded=(), unfolded=(), side=None):
    """Layout plus the text of every card, in the active language.

    viewer_person: the viewer's own record; the centre card is labelled
    "You" only when it is that record.
    """
    layout = TreeLayout(archive, focus_id, open_all=open_all, opened=opened, closed=closed, folded=folded,
                        unfolded=unfolded, side=side).build()
    branches = archive.branches(focus_id)
    ancestors = set(archive.ancestors(focus_id))
    for node in layout["nodes"]:
        person = archive.people[node["id"]]
        is_centre_not_viewer = person.pk == focus_id and focus_id != viewer_person
        kids, sibs = node.get("kids"), node.get("sibs")
        node.update(
            name=person.short_name,
            first=person.first_name,
            initials=person.initials,
            years=person.lifespan,
            label="" if is_centre_not_viewer else archive.label(focus_id, person.pk),
            gender=person.gender,
            deceased=person.is_deceased,
            focus=person.pk == focus_id,
            branch=branches.get(person.pk, "other"),
            direct=person.pk in ancestors,
            url=person.get_absolute_url(),
            photo=f"{person.photo.url}?s=t" if photo_urls and person.photo else "",
            kids_label=(ngettext("%(count)d child", "%(count)d children", kids["count"])
                        % {"count": kids["count"]}) if kids else "",
            sibs_label=(ngettext("%(count)d brother or sister", "%(count)d brothers and sisters", sibs["count"])
                        % {"count": sibs["count"]}) if sibs else "",
        )
    for line in layout["lines"]:
        to, a, b = line.pop("to", None), line.pop("a", None), line.pop("b", None)
        if (to in ancestors) or (a in ancestors and b in ancestors and a != focus_id and b != focus_id):
            line["direct"] = True
    for row in layout["rows"]:
        row["label"] = generation_label(row["gen"])
    layout["card"] = {"w": CARD_W, "h": CARD_H}
    layout["focus"] = focus_id
    layout["side"] = side or ""
    return layout
