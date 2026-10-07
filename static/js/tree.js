/* Family tree viewer.
   The server computes the layout and every card's text (names, years, the
   relationship name) in the active language; this file draws it and handles:
   pan / zoom with semantic zoom (less detail, larger type when zoomed out),
   the generation rail, the mini-map, branch colours, opening and closing
   branches, the side sheet (details and adding a relative in place) and PNG
   export. */
(function () {
  "use strict";

  var root = document.getElementById("tree");
  if (!root) return;

  var SVGNS = "http://www.w3.org/2000/svg";
  var view = document.getElementById("tree-view");
  var statusEl = document.getElementById("tree-status");
  var rail = document.getElementById("tree-rail");
  var minimap = document.getElementById("tree-minimap");
  var tip = document.getElementById("tree-tip");
  var sheet = document.getElementById("tree-sheet");
  var sheetInner = document.getElementById("tree-sheet-inner");
  var picker = document.getElementById("tree-person");
  var dataUrl = root.getAttribute("data-url");
  var pdfUrl = root.getAttribute("data-pdf-url");
  var canEdit = !!root.getAttribute("data-can-edit");

  var FONT = "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif";
  // Card geometry (the same numbers are used in apps/genealogy/pdf.py).
  var AV = { cx: 34, cy: 34, r: 20 }, TX = 64, PADR = 10;
  var NEAR = 0.56, MID = 0.27;  // screen pixels per chart unit

  var params = new URLSearchParams(window.location.search);
  function idSet(name) {
    return new Set((params.get(name) || "").split(",").filter(Boolean).map(Number));
  }
  var state = {
    data: null, vb: null, svg: null, selected: null,
    focus: parseInt(root.getAttribute("data-focus"), 10),
    view: "tree",
    all: params.get("all") === "1",
    opened: idSet("open"), closed: idSet("closed"), folded: idSet("folded"), unfolded: idSet("kids"),
  };
  var measureCtx = document.createElement("canvas").getContext("2d");

  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function setStatus(text) {
    statusEl.hidden = !text;
    if (text) statusEl.textContent = text;
  }
  function query(extra) {
    var q = new URLSearchParams();
    q.set("person", state.focus);
    if (state.all) q.set("all", "1");
    [["open", state.opened], ["closed", state.closed], ["folded", state.folded], ["kids", state.unfolded]].forEach(function (p) {
      if (p[1].size) q.set(p[0], Array.from(p[1]).join(","));
    });
    Object.keys(extra || {}).forEach(function (k) { q.set(k, extra[k]); });
    return q.toString();
  }

  // ---- text helpers ------------------------------------------------------------
  function fitText(text, font, maxW) {
    measureCtx.font = font;
    text = String(text || "");
    if (measureCtx.measureText(text).width <= maxW) return text;
    while (text.length > 1 && measureCtx.measureText(text + "…").width > maxW) text = text.slice(0, -1);
    return text + "…";
  }
  function wrap(text, font, maxW, maxLines) {
    measureCtx.font = font;
    var words = String(text || "").split(/\s+/).filter(Boolean);
    var lines = [], cur = "";
    words.forEach(function (w) {
      var trial = cur ? cur + " " + w : w;
      if (!cur || measureCtx.measureText(trial).width <= maxW) cur = trial;
      else { lines.push(cur); cur = w; }
    });
    if (cur) lines.push(cur);
    if (lines.length > maxLines) { lines = lines.slice(0, maxLines); lines[maxLines - 1] += "…"; }
    return lines.map(function (line) { return fitText(line, font, maxW); });
  }
  // Everything written on a card, with positions; shared by SVG and PNG.
  function cardText(n, card) {
    var inner = card.w - TX - PADR;
    var nameFont = "700 13.5px " + FONT, smallFont = "500 12px " + FONT, labelFont = "600 11.5px " + FONT;
    var out = [], y = 25;
    wrap(n.name, nameFont, inner, 2).forEach(function (line) {
      out.push({ t: line, x: TX, y: y, cls: "t-name", font: nameFont }); y += 16;
    });
    if (n.years) out.push({ t: n.years, x: TX, y: y + 1, cls: "t-years", font: smallFont });
    var label = null;
    if (n.label) {
      var t = fitText(n.label, labelFont, inner - 12);
      measureCtx.font = labelFont;
      label = { t: t, x: TX + 6, y: card.h - 13, w: measureCtx.measureText(t).width + 12, font: labelFont };
    }
    return { lines: out, label: label };
  }
  function el(name, attrs, parent) {
    var node = document.createElementNS(SVGNS, name);
    Object.keys(attrs || {}).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(node);
    return node;
  }
  // Polyline with softly rounded corners.
  function pathD(points) {
    var R = 12, d = "M" + points[0][0] + "," + points[0][1];
    for (var i = 1; i < points.length - 1; i++) {
      var p = points[i - 1], c = points[i], n = points[i + 1];
      var l1 = Math.hypot(c[0] - p[0], c[1] - p[1]), l2 = Math.hypot(n[0] - c[0], n[1] - c[1]);
      var r = Math.min(R, l1 / 2, l2 / 2);
      if (r < 1) { d += " L" + c[0] + "," + c[1]; continue; }
      var a = [c[0] + (p[0] - c[0]) * r / l1, c[1] + (p[1] - c[1]) * r / l1];
      var b = [c[0] + (n[0] - c[0]) * r / l2, c[1] + (n[1] - c[1]) * r / l2];
      d += " L" + a[0] + "," + a[1] + " Q" + c[0] + "," + c[1] + " " + b[0] + "," + b[1];
    }
    var last = points[points.length - 1];
    return d + " L" + last[0] + "," + last[1];
  }
  // Small rounded button on a card: open/close brothers and sisters or children.
  function toggle(parent, x, y, text, title, action, id, isOpen) {
    var g = el("g", { "class": "t-toggle" + (isOpen ? " open" : ""), transform: "translate(" + x + "," + y + ")",
      tabindex: "0", role: "button", "aria-label": title, "aria-expanded": String(isOpen) }, parent);
    g.dataset.action = action;
    g.dataset.id = id;
    g.dataset.open = isOpen ? "1" : "";
    el("title", {}, g).textContent = title;
    var w = Math.max(24, text.length * 7.5 + 14);
    el("rect", { x: -w / 2, y: -11, width: w, height: 22, rx: 11 }, g);
    el("text", { x: 0, y: 4, "text-anchor": "middle" }, g).textContent = text;
  }

  // ---- the tree ----------------------------------------------------------------
  var positions = {};
  function key(n) { return n.id + (n.dup ? "d" : ""); }

  function render(data, anchor, flashId) {
    var card = data.card;
    var old = positions;
    positions = {};
    var svg = el("svg", { role: "group", "aria-label": gettext("Family tree") });
    var defs = el("defs", {}, svg);
    var g = el("g", {}, svg);
    var lines = el("g", { "class": "t-lines" }, g);
    // Direct-line connectors are drawn last so that they lie on top.
    data.lines.slice().sort(function (a, b) { return (a.direct ? 1 : 0) - (b.direct ? 1 : 0); }).forEach(function (line) {
      el("path", { d: pathD(line.points), "class": "t-line " + line.kind + (line.direct ? " direct" : "") }, lines);
    });
    var cards = [];
    data.nodes.forEach(function (n) {
      positions[key(n)] = { x: n.x, y: n.y };
      var cls = ["t-card", "b-" + n.branch, n.direct ? "direct" : "", n.focus ? "focus" : "", n.dup ? "dup" : "",
        n.deceased ? "deceased" : "", n.id === state.selected ? "selected" : "", n.id === flashId ? "flash" : ""].join(" ");
      var cg = el("g", { "class": cls, transform: "translate(" + n.x + "," + n.y + ")" }, g);
      cards.push([cg, n]);
      var body = el("g", { "class": "t-body", tabindex: "0", role: "button",
        "aria-label": [n.name, n.years, n.label].filter(Boolean).join(", ") }, cg);
      body.dataset.id = n.id;
      el("rect", { "class": "box", width: card.w, height: card.h, rx: 14 }, body);
      el("rect", { "class": "stripe", x: 0, y: 12, width: 4, height: card.h - 24, rx: 2 }, body);
      var av = el("g", { "class": "t-avatar" }, body);
      el("circle", { "class": "avatar-bg", cx: AV.cx, cy: AV.cy, r: AV.r }, av);
      if (n.photo) {
        var clipId = "clip-" + key(n);
        el("circle", { cx: AV.cx, cy: AV.cy, r: AV.r - 1 }, el("clipPath", { id: clipId }, defs));
        el("image", { href: n.photo, x: AV.cx - AV.r, y: AV.cy - AV.r, width: AV.r * 2, height: AV.r * 2,
          preserveAspectRatio: "xMidYMid slice", "clip-path": "url(#" + clipId + ")" }, av);
      } else {
        el("text", { "class": "t-initials", x: AV.cx, y: AV.cy + 4.5, "text-anchor": "middle" }, av).textContent = n.initials;
      }
      var text = cardText(n, card);
      text.lines.forEach(function (t) { el("text", { x: t.x, y: t.y, "class": t.cls }, body).textContent = t.t; });
      if (text.label) {
        el("rect", { "class": "t-pill", x: text.label.x - 6, y: text.label.y - 12, width: text.label.w, height: 17, rx: 8.5 }, body);
        el("text", { x: text.label.x, y: text.label.y, "class": "t-label" }, body).textContent = text.label.t;
      }
      // Shown instead of the details when the chart is small on screen.
      el("text", { "class": "t-big", x: TX, y: card.h / 2 + 9 }, body).textContent =
        fitText(n.first || n.name, "700 25px " + FONT, card.w - TX - 8);
      el("text", { "class": "t-huge", x: card.w / 2, y: card.h / 2 + 16, "text-anchor": "middle" }, body).textContent = n.initials;
      if (n.sibs) {
        toggle(cg, n.sibs.side === "left" ? 18 : card.w - 18, 0, n.sibs.open ? "−" : "+" + n.sibs.count,
          (n.sibs.open ? gettext("Hide brothers and sisters") : gettext("Show brothers and sisters")) + " (" + n.sibs_label + ")",
          "sibs", n.id, n.sibs.open);
      }
      if (n.kids) {
        toggle(cg, card.w - 24, card.h, n.kids.open ? "−" : "+" + n.kids.count,
          (n.kids.open ? gettext("Hide children") : gettext("Show children")) + " (" + n.kids_label + ")",
          "kids", n.id, n.kids.open);
      }
    });

    // Keep the clicked card where it was on screen and let the other cards
    // glide from their old places to the new ones.
    var shift = { x: 0, y: 0 };
    var animate = anchor && state.vb && old[anchor] && positions[anchor];
    if (animate) {
      shift.x = positions[anchor].x - old[anchor].x;
      shift.y = positions[anchor].y - old[anchor].y;
    }
    view.querySelectorAll("svg").forEach(function (s) { s.remove(); });
    view.insertBefore(svg, view.firstChild);
    state.svg = svg;
    state.data = data;
    if (!animate) { fit(true); return; }
    state.vb.x += shift.x;
    state.vb.y += shift.y;
    applyViewBox();
    lines.classList.add("t-appear");
    var moving = [];
    cards.forEach(function (c) {
      var from = old[key(c[1])];
      if (!from) { c[0].classList.add("t-appear"); return; }
      var fx = from.x + shift.x, fy = from.y + shift.y;
      if (Math.abs(fx - c[1].x) < 0.5 && Math.abs(fy - c[1].y) < 0.5) return;
      c[0].style.transform = "translate(" + fx + "px," + fy + "px)";
      moving.push(c);
    });
    if (!moving.length) return;
    svg.getBoundingClientRect(); // commit the starting positions
    moving.forEach(function (c) {
      c[0].classList.add("t-move");
      c[0].style.transform = "translate(" + c[1].x + "px," + c[1].y + "px)";
    });
    window.setTimeout(function () {
      moving.forEach(function (c) { c[0].classList.remove("t-move"); c[0].style.transform = ""; });
    }, 600);
  }

  // ---- pan & zoom via the viewBox ---------------------------------------------
  function bounds() {
    return { x: 0, y: 0, w: state.data.width, h: state.data.height };
  }
  function scaleNow() { return state.vb ? view.clientWidth / state.vb.w : 1; }

  function applyViewBox() {
    var vb = state.vb;
    state.svg.setAttribute("viewBox", [vb.x, vb.y, vb.w, vb.h].join(" "));
    var s = scaleNow();
    state.svg.classList.toggle("z-mid", state.view === "tree" && s < NEAR && s >= MID);
    state.svg.classList.toggle("z-far", state.view === "tree" && s < MID);
    state.k = s;
    drawRail();
    drawMinimap();
  }

  // The whole chart; with `nearFocus`, large charts open around the centre person.
  function fit(nearFocus) {
    if (!state.svg) return;
    var rect = view.getBoundingClientRect(), b = bounds();
    var scale = Math.max(b.w / rect.width, b.h / rect.height, 1 / 1.3);
    var vw = rect.width * scale, vh = rect.height * scale;
    state.vb = { x: b.x + (b.w - vw) / 2, y: b.y + (b.h - vh) / 2, w: vw, h: vh };
    if (state.view === "tree") {
      var f = state.data.nodes.filter(function (n) { return n.focus && !n.dup; })[0];
      if (nearFocus && f && scale > 1.4) {
        scale = 1.05;
        vw = rect.width * scale; vh = rect.height * scale;
        state.vb = { x: f.x + state.data.card.w / 2 - vw / 2, y: f.y + state.data.card.h / 2 - vh * 0.62, w: vw, h: vh };
      }
    }
    applyViewBox();
  }
  function zoom(factor, cx, cy) {
    var vb = state.vb;
    if (!vb) return;
    var nw = Math.min(Math.max(vb.w * factor, 240), 60000);
    var k = nw / vb.w;
    var px = cx === undefined ? vb.x + vb.w / 2 : cx;
    var py = cy === undefined ? vb.y + vb.h / 2 : cy;
    state.vb = { x: px - (px - vb.x) * k, y: py - (py - vb.y) * k, w: nw, h: vb.h * k };
    applyViewBox();
  }
  function toChart(clientX, clientY) {
    var rect = view.getBoundingClientRect(), vb = state.vb;
    return { x: vb.x + (clientX - rect.left) / rect.width * vb.w, y: vb.y + (clientY - rect.top) / rect.height * vb.h };
  }

  // Generation names at the left edge, level with each row of cards. Zoomed
  // out, the rows come closer than a wrapped name is tall: names then take
  // one line each, and one that would still touch its neighbour is left out
  // (the viewer's own generation is placed first, then outwards from it).
  var RAIL_LINE = 16, RAIL_WRAPPED = 56;   // px: one line; the tallest wrapped name
  function drawRail() {
    rail.innerHTML = "";
    if (state.view !== "tree" || !state.data || !state.vb) return;
    var h = view.clientHeight, vb = state.vb, card = state.data.card;
    var rows = state.data.rows.map(function (row) {
      return { label: row.label, gen: row.gen, y: (row.y + card.h / 2 - vb.y) / vb.h * h };
    }).sort(function (a, b) { return a.y - b.y; });
    var pitch = Infinity;
    for (var i = 1; i < rows.length; i++) pitch = Math.min(pitch, rows[i].y - rows[i - 1].y);
    var tight = pitch < RAIL_WRAPPED, gap = tight ? RAIL_LINE : 0, placed = [];
    rail.classList.toggle("tight", tight);
    rows.slice().sort(function (a, b) { return Math.abs(a.gen) - Math.abs(b.gen); }).forEach(function (row) {
      if (row.y < 14 || row.y > h - 14) return;
      if (placed.some(function (y) { return Math.abs(y - row.y) < gap; })) return;
      placed.push(row.y);
      var s = document.createElement("span");
      s.textContent = row.label;
      s.title = row.label;
      s.style.top = row.y + "px";
      rail.appendChild(s);
    });
  }

  // The mini-map: every card as a dot in its branch colour, and the part on screen.
  var MM = { w: 380, h: 236, pad: 10 };
  function minimapScale() {
    var b = bounds();
    return Math.min((MM.w - 2 * MM.pad) / b.w, (MM.h - 2 * MM.pad) / b.h);
  }
  function drawMinimap() {
    if (state.view !== "tree" || !state.data || !state.vb) { minimap.hidden = true; return; }
    var b = bounds(), vb = state.vb;
    var covers = vb.w >= b.w * 0.98 && vb.h >= b.h * 0.98;
    minimap.hidden = covers || state.data.nodes.length < 12;
    if (minimap.hidden) return;
    var ctx = minimap.getContext("2d"), k = minimapScale(), card = state.data.card;
    var ox = (MM.w - b.w * k) / 2, oy = (MM.h - b.h * k) / 2;
    ctx.clearRect(0, 0, MM.w, MM.h);
    var colours = { own: css("--own"), paternal: css("--paternal"), maternal: css("--maternal"), other: css("--other") };
    state.data.nodes.forEach(function (n) {
      ctx.fillStyle = n.focus ? css("--accent") : colours[n.branch] || colours.other;
      ctx.globalAlpha = n.focus ? 1 : 0.75;
      ctx.fillRect(ox + n.x * k, oy + n.y * k, Math.max(3, card.w * k), Math.max(3, card.h * k));
    });
    ctx.globalAlpha = 1;
    ctx.strokeStyle = css("--accent");
    ctx.lineWidth = 3;
    var x = ox + (vb.x - b.x) * k, y = oy + (vb.y - b.y) * k;
    ctx.strokeRect(Math.max(1.5, x), Math.max(1.5, y),
      Math.min(MM.w - 3 - Math.max(0, x), vb.w * k), Math.min(MM.h - 3 - Math.max(0, y), vb.h * k));
  }
  function minimapGo(e) {
    var r = minimap.getBoundingClientRect(), b = bounds(), k = minimapScale();
    var px = (e.clientX - r.left) / r.width * MM.w, py = (e.clientY - r.top) / r.height * MM.h;
    var ox = (MM.w - b.w * k) / 2, oy = (MM.h - b.h * k) / 2;
    state.vb.x = b.x + (px - ox) / k - state.vb.w / 2;
    state.vb.y = b.y + (py - oy) / k - state.vb.h / 2;
    applyViewBox();
  }
  var mmDrag = false;
  minimap.addEventListener("pointerdown", function (e) { mmDrag = true; minimap.setPointerCapture(e.pointerId); minimapGo(e); e.stopPropagation(); });
  minimap.addEventListener("pointermove", function (e) { if (mmDrag) minimapGo(e); });
  minimap.addEventListener("pointerup", function (e) { mmDrag = false; e.stopPropagation(); });

  // Mouse wheel and trackpad pinch zoom; two-finger trackpad scrolling pans.
  view.addEventListener("wheel", function (e) {
    if (!state.vb) return;
    e.preventDefault();
    var mouseWheel = e.deltaMode === 1 || (e.deltaX === 0 && Math.abs(e.deltaY) >= 50 && Number.isInteger(e.deltaY));
    if (e.ctrlKey || e.metaKey || mouseWheel) {
      var p = toChart(e.clientX, e.clientY);
      var step = e.ctrlKey && !mouseWheel ? Math.exp(e.deltaY / 100) : (e.deltaY > 0 ? 1.15 : 1 / 1.15);
      zoom(step, p.x, p.y);
      return;
    }
    var rect = view.getBoundingClientRect();
    state.vb.x += e.deltaX / rect.width * state.vb.w;
    state.vb.y += e.deltaY / rect.height * state.vb.h;
    applyViewBox();
  }, { passive: false });

  // Drag to pan (mouse or one finger), pinch with two fingers.
  var pointers = new Map(), drag = null, pinch = null, lastTap = { id: null, at: 0 };
  view.addEventListener("pointerdown", function (e) {
    if (!state.vb || e.target === minimap) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 1) {
      drag = { x: e.clientX, y: e.clientY, vb: Object.assign({}, state.vb), moved: false, target: e.target };
    } else if (pointers.size === 2) {
      var pts = Array.from(pointers.values());
      pinch = { d: Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y), vb: Object.assign({}, state.vb) };
      drag = null;
    }
  });
  window.addEventListener("pointermove", function (e) {
    if (!pointers.has(e.pointerId)) { hover(e); return; }
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pinch && pointers.size === 2) {
      var pts = Array.from(pointers.values());
      var d = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
      state.vb = Object.assign({}, pinch.vb);
      var p = toChart((pts[0].x + pts[1].x) / 2, (pts[0].y + pts[1].y) / 2);
      zoom(pinch.d / Math.max(d, 1), p.x, p.y);
      return;
    }
    if (!drag) return;
    var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!drag.moved && Math.abs(dx) + Math.abs(dy) < 5) return;
    if (!drag.moved) { drag.moved = true; view.classList.add("dragging"); tip.hidden = true; }
    var rect = view.getBoundingClientRect();
    state.vb.x = drag.vb.x - dx / rect.width * drag.vb.w;
    state.vb.y = drag.vb.y - dy / rect.height * drag.vb.h;
    applyViewBox();
  });
  function endPointer(e) {
    if (!pointers.has(e.pointerId)) return;
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = null;
    if (pointers.size) return;
    var d = drag;
    drag = null;
    view.classList.remove("dragging");
    if (d && !d.moved) activate(d.target);
  }
  window.addEventListener("pointerup", endPointer);
  window.addEventListener("pointercancel", endPointer);

  // When the cards are too small to read, a tooltip tells who it is.
  function hover(e) {
    var body = e.target.closest && e.target.closest(".t-body");
    if (!body || !state.data || scaleNow() >= NEAR || !view.contains(body)) { tip.hidden = true; return; }
    var id = parseInt(body.dataset.id, 10);
    var n = state.data.nodes.filter(function (x) { return x.id === id; })[0];
    if (!n) { tip.hidden = true; return; }
    tip.innerHTML = "";
    var b = document.createElement("b");
    b.textContent = n.name;
    tip.appendChild(b);
    tip.appendChild(document.createTextNode([n.label, n.years].filter(Boolean).join(" · ")));
    var r = view.getBoundingClientRect();
    tip.hidden = false;
    tip.style.left = Math.min(r.width - tip.offsetWidth - 8, e.clientX - r.left + 14) + "px";
    tip.style.top = Math.max(8, e.clientY - r.top - tip.offsetHeight - 10) + "px";
  }
  view.addEventListener("pointerleave", function () { tip.hidden = true; });

  view.addEventListener("keydown", function (e) {
    var target = e.target.closest && e.target.closest(".t-toggle, .t-body");
    if ((e.key === "Enter" || e.key === " ") && target) {
      e.preventDefault();
      activate(target);
    } else if (e.key === "+" || e.key === "=") zoom(1 / 1.2);
    else if (e.key === "-") zoom(1.2);
    else if (e.key === "Escape") closeSheet();
  });

  root.querySelectorAll("[data-zoom]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var what = btn.getAttribute("data-zoom");
      if (what === "in") zoom(1 / 1.25);
      else if (what === "out") zoom(1.25);
      else fit(false);
    });
  });

  // A toggle opens or closes a branch. A card opens the side sheet; a second
  // tap on the same card puts that person in the centre.
  function activate(target) {
    var t = target.closest && target.closest(".t-toggle");
    if (t) {
      var id = parseInt(t.dataset.id, 10);
      if (t.dataset.action === "sibs") {
        if (t.dataset.open) { state.closed.add(id); state.opened.delete(id); }
        else { state.opened.add(id); state.closed.delete(id); }
      } else if (t.dataset.open) { state.folded.add(id); state.unfolded.delete(id); }
      else { state.unfolded.add(id); state.folded.delete(id); }
      load(String(id));
      return;
    }
    var body = target.closest && target.closest(".t-body");
    if (!body) return;
    var pid = parseInt(body.dataset.id, 10), now = Date.now();
    if (lastTap.id === pid && now - lastTap.at < 450) { centre(pid); return; }
    lastTap = { id: pid, at: now };
    openSheet(pid);
  }
  function centre(pid) {
    state.focus = pid;
    load(String(pid));
  }

  // ---- the side sheet: who this is, and adding a relative in place --------------
  function markSelected() {
    if (!state.svg) return;
    state.svg.querySelectorAll(".t-card.selected").forEach(function (c) { c.classList.remove("selected"); });
    state.svg.querySelectorAll(".t-body").forEach(function (b) {
      if (parseInt(b.dataset.id, 10) === state.selected) b.parentNode.classList.add("selected");
    });
  }
  function closeSheet() {
    sheet.classList.remove("open");
    state.selected = null;
    markSelected();
  }
  function openSheet(pid, relation) {
    state.selected = pid;
    markSelected();
    fetch("/qarindoshlar/" + pid + "/karta.json", { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (p) { fillSheet(p, relation); })
      .catch(function () {});
  }
  function fillSheet(p, relation) {
    var frag = document.getElementById("sheet-tpl").content.cloneNode(true);
    function f(name) { return frag.querySelector('[data-f="' + name + '"]'); }
    function row(name, value) {
      var r = frag.querySelector('[data-row="' + name + '"]');
      if (!value) { r.remove(); return; }
      f(name).textContent = value;
    }
    var node = (state.data ? state.data.nodes : []).filter(function (n) { return n.id === p.id; })[0];
    var av = f("avatar");
    av.className = "avatar b-" + (node ? node.branch : "other") + (p.deceased ? " deceased" : "");
    if (p.photo) { var img = document.createElement("img"); img.src = p.photo; img.alt = ""; av.appendChild(img); }
    else av.textContent = p.initials;
    f("name").textContent = p.name;
    if (p.label || p.is_me) f("label").textContent = p.label || gettext("You"); else f("label").remove();
    f("years").textContent = p.years;
    row("born", p.born);
    row("place", p.birth_place);
    row("died", p.died);
    row("work", p.occupation);
    if (p.account) {  // a relative with an account: "@name", linking to their own family tree
      f("account").textContent = p.account.name;
      if (p.account.url) f("account").href = p.account.url;
    } else frag.querySelector('[data-row="account"]').remove();
    f("url").href = p.url;
    if (p.edit_url) f("edit").href = p.edit_url; else f("edit").remove();
    var centreBtn = frag.querySelector('[data-act="centre"]');
    if (p.id === state.focus) centreBtn.remove();
    else centreBtn.addEventListener("click", function () { centre(p.id); });
    frag.querySelector("[data-sheet-close]").addEventListener("click", closeSheet);

    var addBlock = f("add-block");
    if (!p.add_url) addBlock.remove();
    else {
      var form = addBlock.querySelector("form"), chips = Array.from(addBlock.querySelectorAll("[data-rel]"));
      var errorEl = f("error"), dupBox = addBlock.querySelector(".dups"), dupList = f("dups");
      var genderField = f("gender-field"), more = f("more");
      var current = null, confirmDup = false;
      var choose = function (rel) {
        current = rel;
        confirmDup = false;
        chips.forEach(function (c) { c.setAttribute("aria-pressed", String(c.dataset.rel === rel)); });
        form.hidden = false;
        dupBox.hidden = true;
        errorEl.hidden = true;
        genderField.hidden = rel === "father" || rel === "mother";
        var gender = form.elements.gender;
        if (rel === "spouse") gender.value = p.gender === "male" ? "female" : "male";
        var surname = function () {
          if (rel === "sibling") return p.last_name;
          if (rel === "child") return gender.value === "male" ? p.child_surname.son : p.child_surname.daughter;
          return "";
        };
        form.elements.last_name.value = surname();
        gender.onchange = function () { if (rel === "child") form.elements.last_name.value = surname(); };
        more.href = p.more_url + "?relation=" + rel;
        form.elements.first_name.focus();
      };
      chips.forEach(function (c) {
        c.disabled = !p.can_add[c.dataset.rel];
        c.addEventListener("click", function () { choose(c.dataset.rel); });
      });
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var body = new FormData(form);
        body.set("relation", current);
        if (confirmDup) body.set("confirm_duplicate", "on");
        var btn = form.querySelector("button[type=submit]");
        btn.disabled = true;
        fetch(p.add_url, { method: "POST", body: body, credentials: "same-origin",
          headers: { "X-CSRFToken": window.SilaiRahm.csrf(), Accept: "application/json" } })
          .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
          .then(function (res) {
            btn.disabled = false;
            if (res.ok && res.d.ok) {
              form.reset();
              form.hidden = true;
              chips.forEach(function (c) { c.setAttribute("aria-pressed", "false"); });
              load(String(p.id), res.d.id);
              openSheet(p.id);
              return;
            }
            var dups = res.d.duplicates || [];
            dupBox.hidden = !dups.length;
            dupList.innerHTML = "";
            dups.forEach(function (d) {
              var a = document.createElement("a");
              a.href = d.url; a.target = "_blank"; a.rel = "noopener";
              a.textContent = d.name + (d.years ? " · " + d.years : "");
              dupList.appendChild(a);
            });
            confirmDup = dups.length > 0;
            var messages = [];
            Object.keys(res.d.errors || {}).forEach(function (k) {
              if (!(dups.length && k === "__all__")) messages = messages.concat(res.d.errors[k]);
            });
            errorEl.hidden = !messages.length;
            errorEl.textContent = messages.join(" ");
          })
          .catch(function () { btn.disabled = false; errorEl.hidden = false; errorEl.textContent = gettext("An error occurred."); });
      });
      if (relation && p.can_add[relation]) window.setTimeout(function () { choose(relation); }, 0);
    }
    sheetInner.innerHTML = "";
    sheetInner.appendChild(frag);
    sheet.classList.add("open");
  }

  // ---- loading -------------------------------------------------------------------
  function syncUi() {
    root.querySelectorAll("[data-expand]").forEach(function (b) {
      b.setAttribute("aria-pressed", String((b.getAttribute("data-expand") === "all") === state.all));
    });
    var q = query();
    document.getElementById("tree-pdf").href = pdfUrl + "?" + q;
    document.getElementById("tree-poster-a2").href = pdfUrl + "?" + query({ size: "A2", all: "1" });
    document.getElementById("tree-poster-a1").href = pdfUrl + "?" + query({ size: "A1", all: "1" });
    window.history.replaceState(null, "", window.location.pathname + "?" + q);
  }
  function fail() {
    view.classList.remove("loading");
    setStatus(gettext("Could not load the family tree. Please try again."));
  }
  function load(anchor, flashId) {
    view.classList.add("loading");
    fetch(dataUrl + "?" + query(), { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) {
        view.classList.remove("loading");
        state.focus = data.focus;
        if (!data.nodes.length) { setStatus(gettext("The family tree is empty.")); return; }
        setStatus("");
        render(data, anchor, flashId);
        var f = data.nodes.filter(function (n) { return n.focus && !n.dup; })[0];
        if (f && document.activeElement !== picker) picker.value = f.name;
        syncUi();
      })
      .catch(fail);
  }
  function reload() { load(null); }

  // The name picker (live search) puts the chosen person in the centre.
  picker.addEventListener("livesearch:pick", function (e) { state.focus = e.detail.id; reload(); });
  root.querySelectorAll("[data-expand]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      state.all = btn.getAttribute("data-expand") === "all";
      state.opened.clear(); state.closed.clear(); state.folded.clear(); state.unfolded.clear();
      load(String(state.focus));
    });
  });

  // ---- PNG export: drawn on a canvas so the web font is used -----------------
  document.getElementById("tree-png").addEventListener("click", function () {
    var data = state.data;
    if (!data) return;
    var scale = Math.min(2, 16000 / Math.max(data.width, data.height));
    var canvas = document.createElement("canvas");
    canvas.width = Math.round(data.width * scale);
    canvas.height = Math.round(data.height * scale);
    var ctx = canvas.getContext("2d");
    ctx.scale(scale, scale);
    ctx.fillStyle = css("--tree-bg");
    ctx.fillRect(0, 0, data.width, data.height);
    ctx.lineJoin = "round";
    data.lines.forEach(function (line) {
      ctx.beginPath();
      ctx.setLineDash(line.kind === "partners" ? [6, 4] : []);
      ctx.strokeStyle = line.direct ? css("--gold-bright") : (line.kind === "child" ? css("--tree-line") : css("--accent"));
      ctx.lineWidth = line.direct ? 2.6 : (line.kind === "child" ? 1.6 : 2.2);
      line.points.forEach(function (p, i) { if (i) ctx.lineTo(p[0], p[1]); else ctx.moveTo(p[0], p[1]); });
      ctx.stroke();
    });
    ctx.setLineDash([]);
    var card = data.card;
    data.nodes.forEach(function (n) {
      var tint = css("--" + n.branch) || css("--other"), soft = css("--" + n.branch + "-soft") || css("--other-soft");
      ctx.save();
      ctx.translate(n.x, n.y);
      ctx.shadowColor = "rgba(0,0,0,.08)"; ctx.shadowBlur = 8; ctx.shadowOffsetY = 2;
      ctx.beginPath(); ctx.roundRect(0, 0, card.w, card.h, 14);
      ctx.fillStyle = n.focus ? css("--accent-soft") : css("--surface"); ctx.fill();
      ctx.shadowColor = "transparent";
      ctx.setLineDash(n.dup ? [5, 4] : []);
      ctx.strokeStyle = n.focus ? css("--accent") : (n.direct ? css("--gold-bright") : css("--line-strong"));
      ctx.lineWidth = n.focus ? 2.4 : (n.direct ? 1.6 : 1); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = tint;
      ctx.beginPath(); ctx.roundRect(0, 12, 4, card.h - 24, 2); ctx.fill();
      ctx.beginPath(); ctx.arc(AV.cx, AV.cy, AV.r, 0, Math.PI * 2);
      ctx.fillStyle = soft; ctx.fill();
      ctx.fillStyle = tint; ctx.font = "700 13px " + FONT; ctx.textAlign = "center";
      ctx.fillText(n.initials || "", AV.cx, AV.cy + 4.5);
      ctx.textAlign = "left";
      var text = cardText(n, card);
      text.lines.forEach(function (t) {
        ctx.font = t.font;
        ctx.fillStyle = t.cls === "t-years" ? css("--muted") : css("--ink");
        ctx.fillText(t.t, t.x, t.y);
      });
      if (text.label) {
        ctx.fillStyle = css("--accent-soft");
        ctx.beginPath(); ctx.roundRect(text.label.x - 6, text.label.y - 12, text.label.w, 17, 8.5); ctx.fill();
        ctx.font = text.label.font; ctx.fillStyle = css("--accent");
        ctx.fillText(text.label.t, text.label.x, text.label.y);
      }
      ctx.restore();
    });
    canvas.toBlob(function (blob) {
      if (!blob) { window.alert(gettext("An error occurred.")); return; }
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = pgettext("file name", "family-tree") + ".png";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
    }, "image/png");
  });

  // When the view changes size (window, sidebar, side sheet) keep the same
  // place in the middle at the same zoom.
  function reflow() {
    if (!state.svg || !state.vb || !state.k) return;
    var rect = view.getBoundingClientRect(), vb = state.vb;
    if (!rect.width || !rect.height) return;
    var cx = vb.x + vb.w / 2, cy = vb.y + vb.h / 2;
    vb.w = rect.width / state.k;
    vb.h = rect.height / state.k;
    vb.x = cx - vb.w / 2;
    vb.y = cy - vb.h / 2;
    applyViewBox();
  }
  if (window.ResizeObserver) new ResizeObserver(reflow).observe(view);
  else window.addEventListener("resize", reflow);
  syncUi();
  (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(reload);
})();
