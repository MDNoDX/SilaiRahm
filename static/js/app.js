/* Progressive enhancements for every page. All messages go through Django's
   JavaScript catalogue (gettext / interpolate from /jsi18n/), so they appear
   in the user's language. */
(function () {
  "use strict";

  var root = document.documentElement;
  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $all(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }
  function csrf() { var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/); return m ? decodeURIComponent(m[1]) : ""; }
  function debounce(fn, ms) {
    var t;
    return function () { var args = arguments; clearTimeout(t); t = setTimeout(function () { fn.apply(null, args); }, ms); };
  }
  window.Shajara = { csrf: csrf };

  // ---- Confirm destructive actions -----------------------------------------
  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-confirm]");
    if (el && !window.confirm(el.getAttribute("data-confirm") || gettext("Are you sure you want to delete this?"))) e.preventDefault();
  });

  // ---- Sidebar: wide or a narrow rail, remembered in this browser -----------
  $all("[data-nav-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var rail = root.getAttribute("data-nav") !== "rail";
      if (rail) root.setAttribute("data-nav", "rail"); else root.removeAttribute("data-nav");
      try { localStorage.setItem("nav", rail ? "rail" : "wide"); } catch (e) {}
      window.dispatchEvent(new Event("resize"));
    });
  });

  // ---- Colour theme: light, dark, or the system's ---------------------------
  var dark = window.matchMedia("(prefers-color-scheme: dark)");
  function themeMode() { try { return localStorage.getItem("theme") || "light"; } catch (e) { return "light"; } }
  function applyTheme(mode) {
    root.setAttribute("data-theme", mode === "auto" ? (dark.matches ? "dark" : "light") : mode);
    var names = { auto: gettext("Automatic"), light: gettext("Light"), dark: gettext("Dark") };
    $all("[data-theme-toggle]").forEach(function (b) {
      b.setAttribute("data-mode", mode);
      b.title = gettext("Colour theme") + ": " + names[mode];
    });
    $all("[data-theme-value]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-theme-value") === mode));
    });
  }
  function setTheme(mode) {
    try { localStorage.setItem("theme", mode); } catch (e) {}
    applyTheme(mode);
  }
  applyTheme(themeMode());
  dark.addEventListener("change", function () { if (themeMode() === "auto") applyTheme("auto"); });
  document.addEventListener("click", function (e) {
    var toggle = e.target.closest("[data-theme-toggle]");
    if (toggle) setTheme({ light: "dark", dark: "auto", auto: "light" }[themeMode()] || "light");
    var choice = e.target.closest("[data-theme-value]");
    if (choice) setTheme(choice.getAttribute("data-theme-value"));
  });

  // ---- Menus close when clicking elsewhere or choosing an item --------------
  document.addEventListener("click", function (e) {
    $all("details.dropdown[open]").forEach(function (d) {
      var summary = d.querySelector("summary");
      var keep = e.target.closest("[data-theme-value]");
      if (!d.contains(e.target) || (!summary.contains(e.target) && !keep && e.target.closest(".menu a, .menu button"))) {
        d.removeAttribute("open");
      }
    });
  });

  // ---- Toasts ----------------------------------------------------------------
  $all(".toast").forEach(function (toast, i) {
    var close = function () { toast.classList.add("hide"); window.setTimeout(function () { toast.remove(); }, 350); };
    toast.querySelector(".toast-close").addEventListener("click", close);
    window.setTimeout(close, 6000 + i * 600);
  });

  // ---- Forms -----------------------------------------------------------------
  // Show the death fields only for deceased people, and similar switches.
  $all("[data-show-if]").forEach(function (block) {
    var box = document.getElementById(block.getAttribute("data-show-if"));
    if (!box) return;
    var sync = function () { block.hidden = !box.checked; };
    box.addEventListener("change", sync);
    sync();
  });

  // "Add relative": hide new-person fields when linking an existing person,
  // the gender choice for father/mother, and "other parent" unless adding a child.
  var relation = document.getElementById("id_relation");
  var existing = document.getElementById("id_existing");
  if (relation) {
    var newPerson = $("[data-new-person]");
    var forRelation = $all("[data-show-if-relation]");
    var anchorGender = relation.form && relation.form.getAttribute("data-anchor-gender");
    var genderField = document.getElementById("id_gender") && document.getElementById("id_gender").closest(".field");
    var syncRelation = function () {
      if (newPerson && existing) newPerson.hidden = !!existing.value;
      forRelation.forEach(function (el) { el.hidden = relation.value !== el.getAttribute("data-show-if-relation"); });
      if (genderField) genderField.hidden = relation.value === "father" || relation.value === "mother";
      // A husband's spouse is a wife and the other way round: chosen in advance, can be changed.
      if (relation.value === "spouse" && anchorGender && !$("input[name=gender]:checked")) {
        var other = $("input[name=gender][value=" + (anchorGender === "male" ? "female" : "male") + "]");
        if (other) other.checked = true;
      }
    };
    relation.addEventListener("change", syncRelation);
    if (existing) existing.addEventListener("change", syncRelation);
    syncRelation();
  }

  // Buttons disabled by the submit handler come back when the page is
  // restored from the back/forward cache.
  window.addEventListener("pageshow", function (e) {
    if (!e.persisted) return;
    $all("button[data-label]").forEach(function (b) {
      b.disabled = false; b.textContent = b.getAttribute("data-label"); b.removeAttribute("data-label");
    });
  });

  // Prevent double submission and show progress.
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (form.method.toLowerCase() !== "post" || form.classList.contains("langsw") || form.hasAttribute("data-no-busy")) return;
    var btn = e.submitter;
    if (!btn || btn.name === "delete" || btn.closest(".menu")) return;
    window.setTimeout(function () {
      btn.disabled = true;
      btn.setAttribute("data-label", btn.textContent);
      btn.textContent = gettext("Saving…");
    }, 0);
  });

  // Parts of a form shown for one choice of a radio group: data-show-when="name=value".
  $all("[data-show-when]").forEach(function (el) {
    var rule = el.getAttribute("data-show-when").split("="), form = el.closest("form");
    if (!form) return;
    var sync = function () {
      var checked = form.querySelector('input[name="' + rule[0] + '"]:checked');
      el.hidden = !checked || checked.value !== rule[1];
    };
    form.addEventListener("change", sync);
    sync();
  });

  // File fields: the browser's own button speaks the browser's language, so
  // it is replaced by ours (the album's drop zone has its own).
  $all("input[type=file]").forEach(function (input) {
    if (input.closest(".dropzone") || !input.id) return;
    var box = document.createElement("span"), pick = document.createElement("label"), name = document.createElement("span");
    box.className = "filepick";
    pick.className = "btn btn-sm";
    pick.htmlFor = input.id;
    pick.textContent = gettext("Choose a file");
    name.className = "filepick-name";
    var show = function () {
      var files = input.files || [];
      box.classList.toggle("chosen", files.length > 0);
      name.textContent = files.length ? Array.prototype.map.call(files, function (f) { return f.name; }).join(", ")
                                      : gettext("No file chosen");
    };
    input.parentNode.insertBefore(box, input);
    box.appendChild(pick); box.appendChild(name); box.appendChild(input);
    input.classList.add("visually-hidden");
    input.addEventListener("change", show);
    input.addEventListener("filepick", show);   // after the photo was made smaller, or refused
    show();
  });

  // A search box above long multiple-choice lists (people in an event).
  $all("select[data-filterable]").forEach(function (select) {
    var box = document.createElement("input");
    box.type = "search";
    box.className = "filter-box";
    box.placeholder = gettext("Type a name to filter…");
    select.parentNode.insertBefore(box, select);
    box.addEventListener("input", function () {
      var q = box.value.trim().toLowerCase();
      Array.prototype.forEach.call(select.options, function (o) {
        o.hidden = q && o.text.toLowerCase().indexOf(q) === -1 && !o.selected;
      });
    });
  });

  // New son: suggest the surname made from the paternal grandfather's name.
  var surnameHint = $("[data-son-surname]");
  if (surnameHint) {
    var lastName = document.getElementById("id_last_name");
    var suggested = surnameHint.getAttribute("data-son-surname");
    var fatherSurname = surnameHint.getAttribute("data-father-surname");
    $all("input[name=gender]").forEach(function (radio) {
      radio.addEventListener("change", function () {
        var rel = document.getElementById("id_relation");
        if (!lastName || !rel || rel.value !== "child" || !suggested) return;
        var untouched = !lastName.value || lastName.value === suggested || lastName.value === fatherSurname;
        if (radio.value === "male" && radio.checked && untouched) lastName.value = suggested;
        if (radio.value === "female" && radio.checked && lastName.value === suggested) lastName.value = "";
      });
    });
  }

  // Copy a code or a link to the clipboard.
  $all("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var src = document.getElementById(btn.getAttribute("data-copy"));
      var text = (src.getAttribute("data-copy-text") || src.textContent).trim();
      var done = function () {
        btn.classList.add("copied");
        btn.title = gettext("Copied");
        window.setTimeout(function () { btn.classList.remove("copied"); }, 1600);
      };
      if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () {});
    });
  });

  // ---- Photos: made smaller in the browser before they are sent -------------
  // Phone pictures are 5–12 MB; hosting limits one request to a few MB.
  var MAX_SIDE = 2000, SHRINK_OVER = 900 * 1024;
  function shrinkImage(file) {
    if (!/^image\/(jpeg|png|webp|heic|heif)$/i.test(file.type) || file.size < SHRINK_OVER || !window.createImageBitmap) {
      return Promise.resolve(file);
    }
    return createImageBitmap(file, { imageOrientation: "from-image" }).then(function (bitmap) {
      var k = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
      var canvas = document.createElement("canvas");
      canvas.width = Math.round(bitmap.width * k);
      canvas.height = Math.round(bitmap.height * k);
      canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      return new Promise(function (resolve) {
        canvas.toBlob(function (blob) {
          if (!blob || blob.size >= file.size) { resolve(file); return; }
          resolve(new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" }));
        }, "image/jpeg", 0.86);
      });
    }).catch(function () { return file; });
  }
  function shrinkInput(input) {
    var files = Array.prototype.slice.call(input.files || []);
    if (!files.length || !window.DataTransfer) return Promise.resolve();
    return Promise.all(files.map(shrinkImage)).then(function (out) {
      var dt = new DataTransfer();
      out.forEach(function (f) { dt.items.add(f); });
      input.files = dt.files;
    });
  }
  document.addEventListener("change", function (e) {
    var input = e.target;
    if (input.type !== "file" || !input.files || !input.files.length) return;
    var form = input.form;
    var buttons = form ? $all("button[type=submit]", form) : [];
    buttons.forEach(function (b) { b.disabled = true; });
    shrinkInput(input).then(function () {
      buttons.forEach(function (b) { b.disabled = false; });
      var limit = form && parseInt(form.getAttribute("data-photo-limit") || "0", 10);
      if (limit && input.files[0] && input.files[0].size > limit * 1024 * 1024) {
        window.alert(interpolate(gettext("The photo is too large. The maximum size is %(size)s MB."), { size: limit }, true));
        input.value = "";
        input.dispatchEvent(new Event("filepick"));
        return;
      }
      input.dispatchEvent(new Event("filepick"));
      if (input.hasAttribute("data-autosubmit")) form.submit();
    });
  });
  // Album drop zone.
  $all(".dropzone").forEach(function (zone) {
    var input = $("input[type=file]", zone);
    ["dragenter", "dragover"].forEach(function (n) {
      zone.addEventListener(n, function (e) { e.preventDefault(); zone.classList.add("over"); });
    });
    ["dragleave", "drop"].forEach(function (n) {
      zone.addEventListener(n, function (e) { e.preventDefault(); zone.classList.remove("over"); });
    });
    zone.addEventListener("drop", function (e) {
      if (!e.dataTransfer || !e.dataTransfer.files.length) return;
      input.files = e.dataTransfer.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
  });

  // ---- Album lightbox --------------------------------------------------------
  document.addEventListener("click", function (e) {
    var shot = e.target.closest("[data-lightbox]");
    if (!shot) return;
    var shots = $all("[data-lightbox]");
    var index = shots.indexOf(shot);
    var box = document.createElement("div");
    box.className = "lightbox";
    box.innerHTML = '<div class="lb-bar"></div><figure><img alt=""><figcaption></figcaption></figure>';
    var img = $("img", box), cap = $("figcaption", box), bar = $(".lb-bar", box);
    function show(i) {
      index = (i + shots.length) % shots.length;
      var s = shots[index];
      img.src = s.getAttribute("data-lightbox");
      cap.textContent = s.getAttribute("data-caption") || "";
      bar.innerHTML = "";
      var tools = document.getElementById(s.getAttribute("data-tools") || "");
      if (tools) bar.appendChild(tools.content.cloneNode(true));
      var close = document.createElement("button");
      close.type = "button"; close.className = "icon-btn"; close.setAttribute("aria-label", gettext("Close"));
      close.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>';
      close.addEventListener("click", shut);
      bar.appendChild(close);
    }
    function shut() { box.remove(); document.removeEventListener("keydown", keys); }
    function keys(ev) {
      if (ev.key === "Escape") shut();
      else if (ev.key === "ArrowRight") show(index + 1);
      else if (ev.key === "ArrowLeft") show(index - 1);
    }
    box.addEventListener("click", function (ev) { if (ev.target === box) shut(); });
    img.addEventListener("click", function () { show(index + 1); });
    document.addEventListener("keydown", keys);
    document.body.appendChild(box);
    show(index);
  });

  // ---- Live search pickers (choose a person by name) -------------------------
  function personRow(item, className) {
    var a = document.createElement("a");
    a.className = className;
    a.href = item.url;
    a.setAttribute("role", "option");
    var av = document.createElement("span");
    av.className = "avatar sm b-" + (item.branch || "other");
    if (item.photo) { var img = document.createElement("img"); img.src = item.photo; img.alt = ""; av.appendChild(img); }
    else av.textContent = item.initials;
    var who = document.createElement("span");
    who.className = className === "cmdk-item" ? "who" : "live-who";
    var name = document.createElement("b");
    name.textContent = item.name;
    who.appendChild(name);
    var meta = [item.years, item.label].filter(Boolean).join(" · ");
    if (meta) { var m = document.createElement("small"); m.textContent = meta; who.appendChild(m); }
    a.appendChild(av);
    a.appendChild(who);
    return a;
  }

  $all("input[data-live-search]").forEach(function (input) {
    var box = input.parentNode.querySelector(".live-results");
    var mode = input.getAttribute("data-mode") || "navigate";
    var url = input.getAttribute("data-live-search");
    var items = [], active = -1, lastQuery = null, request = 0;

    function hide() { box.hidden = true; input.setAttribute("aria-expanded", "false"); active = -1; }
    function mark() {
      $all(".live-item", box).forEach(function (el, i) {
        el.classList.toggle("active", i === active);
        el.setAttribute("aria-selected", String(i === active));
        if (i === active) el.scrollIntoView({ block: "nearest" });
      });
    }
    function choose(item) {
      hide();
      if (mode === "pick") {
        input.value = item.name;
        input.blur();
        input.dispatchEvent(new CustomEvent("livesearch:pick", { detail: item, bubbles: true }));
      } else {
        window.location.href = item.url;
      }
    }
    function render(data) {
      items = data.results;
      active = items.length ? 0 : -1;
      box.innerHTML = "";
      if (!items.length) {
        var none = document.createElement("div");
        none.className = "live-empty";
        none.textContent = gettext("No results found.");
        box.appendChild(none);
      }
      items.forEach(function (item, i) {
        var a = personRow(item, "live-item");
        a.addEventListener("mousedown", function (e) { e.preventDefault(); });
        a.addEventListener("click", function (e) { e.preventDefault(); choose(item); });
        a.addEventListener("mousemove", function () { if (active !== i) { active = i; mark(); } });
        box.appendChild(a);
      });
      box.hidden = false;
      input.setAttribute("aria-expanded", "true");
      mark();
    }
    var run = debounce(function () {
      var q = input.value.trim();
      if (!q) { hide(); lastQuery = null; return; }
      if (q === lastQuery && !box.hidden) return;
      lastQuery = q;
      var mine = ++request;
      fetch(url + (url.indexOf("?") === -1 ? "?" : "&") + "q=" + encodeURIComponent(q), {
        credentials: "same-origin", headers: { Accept: "application/json" },
      }).then(function (r) { return r.json(); }).then(function (data) {
        if (mine === request) render(data);
      }).catch(function () {});
    }, 150);

    input.addEventListener("input", run);
    input.addEventListener("focus", function () {
      if (mode === "pick") input.select();
      else if (input.value.trim()) run();
    });
    input.addEventListener("keydown", function (e) {
      if (mode === "pick" && e.key === "Enter") e.preventDefault();  // never submit the surrounding form
      if (box.hidden) { if (e.key === "ArrowDown") run(); return; }
      if (e.key === "ArrowDown") { e.preventDefault(); active = Math.min(active + 1, items.length - 1); mark(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); active = Math.max(active - 1, 0); mark(); }
      else if (e.key === "Enter" && active >= 0 && items[active]) { e.preventDefault(); choose(items[active]); }
      else if (e.key === "Escape") { hide(); }
    });
    input.addEventListener("blur", function () { setTimeout(hide, 150); });
  });

  // A picked person fills a hidden field; a form marked data-autosubmit is
  // sent as soon as every hidden field has a value ("Who is who?").
  document.addEventListener("livesearch:pick", function (e) {
    var target = e.target.getAttribute("data-pick-target");
    var field = target && document.getElementById(target);
    if (!field) return;
    field.value = e.detail.id;
    field.dispatchEvent(new Event("change", { bubbles: true }));
    var form = field.form;
    if (form && form.hasAttribute("data-autosubmit")) {
      var ready = $all("input[type=hidden]:not([name=csrfmiddlewaretoken])", form).every(function (h) { return h.value; });
      if (ready) HTMLFormElement.prototype.submit.call(form);
    }
  });
  // Emptying a picker marked data-pick-clear clears its hidden field too.
  $all("input[data-pick-clear]").forEach(function (input) {
    input.addEventListener("input", function () {
      var field = document.getElementById(input.getAttribute("data-pick-target"));
      if (field && field.value && !input.value.trim()) {
        field.value = "";
        field.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
  });
  $all("[data-swap]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var ids = btn.getAttribute("data-swap").split(" ");
      var a = document.getElementById(ids[0]), b = document.getElementById(ids[1]);
      var an = document.getElementById(ids[0] + "-name"), bn = document.getElementById(ids[1] + "-name");
      var v = a.value; a.value = b.value; b.value = v;
      v = an.value; an.value = bn.value; bn.value = v;
      if (a.value && b.value) HTMLFormElement.prototype.submit.call(a.form);
    });
  });

  // Search pages: the results below update while typing.
  $all("form[data-live-page]").forEach(function (form) {
    var input = $("input[type=search]", form);
    var target = document.getElementById(form.getAttribute("data-target"));
    var base = form.getAttribute("data-live-page");
    var request = 0;
    var update = debounce(function () {
      var q = input.value.trim();
      var mine = ++request;
      target.classList.add("updating");
      var sep = base.indexOf("?") === -1 ? "?" : "&";
      fetch(base + sep + "partial=1&q=" + encodeURIComponent(q), { credentials: "same-origin" })
        .then(function (r) { return r.text(); })
        .then(function (html) {
          if (mine !== request) return;
          target.innerHTML = html;
          target.classList.remove("updating");
          window.history.replaceState(null, "", base + (q ? sep + "q=" + encodeURIComponent(q) : ""));
        })
        .catch(function () { target.classList.remove("updating"); });
    }, 200);
    input.addEventListener("input", update);
    form.addEventListener("submit", function (e) { e.preventDefault(); update(); });
  });

  // ---- Command palette (⌘K, Ctrl+K or "/") ------------------------------------
  var cmdk = document.getElementById("cmdk");
  if (cmdk) {
    var cq = document.getElementById("cmdk-q"), clist = document.getElementById("cmdk-list");
    var actions = $all("#cmdk-actions a").map(function (a) {
      return { title: a.textContent.trim(), url: a.getAttribute("href"), icon: a.querySelector("svg").outerHTML };
    });
    var rows = [], cur = 0, creq = 0;
    var open = function () {
      cmdk.hidden = false;
      cq.value = "";
      draw([], "");
      cq.focus();
    };
    var close = function () { cmdk.hidden = true; };
    var select = function (i) {
      cur = Math.max(0, Math.min(i, rows.length - 1));
      rows.forEach(function (r, n) { r.classList.toggle("active", n === cur); });
      if (rows[cur]) rows[cur].scrollIntoView({ block: "nearest" });
    };
    var draw = function (people, q) {
      clist.innerHTML = "";
      rows = [];
      people.forEach(function (p) { rows.push(clist.appendChild(personRow(p, "cmdk-item"))); });
      var needle = q.toLowerCase();
      actions.filter(function (a) { return !needle || a.title.toLowerCase().indexOf(needle) !== -1; }).forEach(function (a) {
        var el = document.createElement("a");
        el.className = "cmdk-item";
        el.href = a.url;
        el.innerHTML = a.icon;
        var span = document.createElement("span");
        span.textContent = a.title;
        el.appendChild(span);
        rows.push(clist.appendChild(el));
      });
      if (!rows.length) {
        var none = document.createElement("div");
        none.className = "live-empty";
        none.textContent = gettext("No results found.");
        clist.appendChild(none);
      }
      rows.forEach(function (r, n) { r.addEventListener("mousemove", function () { if (cur !== n) select(n); }); });
      select(0);
    };
    var search = debounce(function () {
      var q = cq.value.trim();
      if (!q) { draw([], ""); return; }
      var mine = ++creq;
      fetch(cq.getAttribute("data-search-url") + "?q=" + encodeURIComponent(q), {
        credentials: "same-origin", headers: { Accept: "application/json" },
      }).then(function (r) { return r.json(); }).then(function (d) { if (mine === creq) draw(d.results, q); })
        .catch(function () { draw([], q); });
    }, 140);
    cq.addEventListener("input", search);
    cq.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); select(cur + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); select(cur - 1); }
      else if (e.key === "Enter" && rows[cur]) { e.preventDefault(); window.location.href = rows[cur].getAttribute("href"); }
    });
    cmdk.addEventListener("click", function (e) { if (e.target === cmdk) close(); });
    document.addEventListener("click", function (e) { if (e.target.closest("[data-cmdk-open]")) open(); });
    document.addEventListener("keydown", function (e) {
      var typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target.tagName || "")) || e.target.isContentEditable;
      if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) { e.preventDefault(); if (cmdk.hidden) open(); else close(); }
      else if (e.key === "/" && !typing && cmdk.hidden) { e.preventDefault(); open(); }
      else if (e.key === "Escape" && !cmdk.hidden) close();
    });
  }

  // ---- Connecting Telegram: the page notices by itself -----------------------
  var tgWait = $("[data-telegram-wait]");
  if (tgWait) {
    var started = Date.now();
    var poll = function () {
      if (Date.now() - started > 15 * 60 * 1000) return;
      if (document.hidden) { window.setTimeout(poll, 3000); return; }
      fetch(tgWait.getAttribute("data-telegram-wait"), { credentials: "same-origin", headers: { Accept: "application/json" } })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.connected) { window.location.hash = "telegram"; window.location.reload(); }
          else window.setTimeout(poll, 3000);
        })
        .catch(function () { window.setTimeout(poll, 6000); });
    };
    window.setTimeout(poll, 3000);
  }

  // ---- Service worker and push notifications on this device ------------------
  var canPush = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  if ("serviceWorker" in navigator && root.lang && document.body.classList.contains("has-tabbar")) {
    navigator.serviceWorker.register("/sw.js").catch(function () {});
  }
  var pushBox = $("[data-push]");
  if (pushBox) {
    var state = $("[data-push-state]", pushBox), onBtn = $("[data-push-on]", pushBox), offBtn = $("[data-push-off]", pushBox);
    var testBtn = $("[data-push-test]", pushBox);
    var key = pushBox.getAttribute("data-push");
    var post = function (url, body) {
      return fetch(url, { method: "POST", credentials: "same-origin", body: JSON.stringify(body || {}),
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() } });
    };
    var b64 = function (s) {
      var pad = "=".repeat((4 - s.length % 4) % 4);
      var raw = atob((s + pad).replace(/-/g, "+").replace(/_/g, "/"));
      return Uint8Array.from(raw, function (c) { return c.charCodeAt(0); });
    };
    var paint = function (sub) {
      var on = !!sub;
      state.textContent = on ? gettext("On for this device") : (Notification.permission === "denied"
        ? gettext("Blocked in the browser settings") : gettext("Off for this device"));
      onBtn.hidden = on || Notification.permission === "denied";
      offBtn.hidden = !on;
      if (testBtn) testBtn.hidden = !on;
      pushBox.querySelector(".setting-icon").classList.toggle("ok", on);
    };
    if (!key || /ShajaraMac/.test(navigator.userAgent)) {
      // Not set up on the server, or the Mac app (it has its own notifications).
      pushBox.closest("section").hidden = true;
    } else if (!canPush) {
      pushBox.hidden = true;
      var hint = document.getElementById(pushBox.getAttribute("data-push-hint") || "");
      if (hint) hint.hidden = false;
    } else {
      navigator.serviceWorker.ready.then(function (reg) {
        reg.pushManager.getSubscription().then(paint);
        onBtn.addEventListener("click", function () {
          Notification.requestPermission().then(function (perm) {
            if (perm !== "granted") { paint(null); return; }
            reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64(key) }).then(function (sub) {
              return post(onBtn.getAttribute("data-push-on"), sub.toJSON()).then(function () { paint(sub); });
            }).catch(function () { paint(null); });
          });
        });
        offBtn.addEventListener("click", function () {
          reg.pushManager.getSubscription().then(function (sub) {
            if (!sub) { paint(null); return; }
            post(offBtn.getAttribute("data-push-off"), { endpoint: sub.endpoint });
            sub.unsubscribe().then(function () { paint(null); });
          });
        });
        if (testBtn) testBtn.addEventListener("click", function () { post(testBtn.getAttribute("data-push-test")); });
      });
    }
  }
})();
