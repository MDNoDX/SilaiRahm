/* The assistant page: a conversation kept in this tab only (sessionStorage),
   answers from /yordamchi/xabar/, and proposals that are saved only when the
   person presses "Add". */
(function () {
  "use strict";
  var box = document.querySelector("[data-ai]");
  if (!box) return;
  var log = box.querySelector("[data-ai-log]");
  var form = box.querySelector("[data-ai-form]");
  var input = form.querySelector("textarea");
  var send = form.querySelector("button[type=submit]");
  var key = "ai-history:" + box.getAttribute("data-archive");
  var csrf = window.SilaiRahm ? window.SilaiRahm.csrf : function () { return ""; };
  var history = [];
  try { history = JSON.parse(sessionStorage.getItem(key) || "[]"); } catch (e) { history = []; }

  function save() {
    try { sessionStorage.setItem(key, JSON.stringify(history.slice(-40))); } catch (e) { /* private mode */ }
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // A small, safe subset of Markdown: **bold**, *italic*, lists, paragraphs.
  function render(text) {
    var html = [], list = null;
    esc(text).split(/\n/).forEach(function (line) {
      var item = line.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);
      if (item) {
        if (!list) { list = []; }
        list.push(item[1]);
        return;
      }
      if (list) { html.push("<ul><li>" + list.join("</li><li>") + "</li></ul>"); list = null; }
      if (line.trim()) html.push("<p>" + line + "</p>");
    });
    if (list) html.push("<ul><li>" + list.join("</li><li>") + "</li></ul>");
    return html.join("")
      // Links only to pages of this site ([Name](/qarindoshlar/12/)).
      .replace(/\[([^\]]+)\]\((\/(?!\/)[^)\s"'<>]*)\)/g, '<a href="$2">$1</a>')
      .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
      .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>");
  }

  function bubble(role, text) {
    var el = document.createElement("div");
    el.className = "ai-msg ai-" + role;
    el.innerHTML = role === "user" ? "<p>" + esc(text).replace(/\n/g, "<br>") + "</p>" : render(text);
    log.appendChild(el);
    el.scrollIntoView({ block: "end", behavior: "smooth" });
    return el;
  }

  function proposal(p) {
    var card = document.createElement("div");
    card.className = "ai-proposal";
    card.innerHTML = '<p class="ai-proposal-title"></p>' + (p.story ? '<div class="ai-proposal-story"></div>' : "") +
      '<div class="row"><button type="button" class="btn btn-primary btn-sm" data-yes></button>' +
      '<button type="button" class="btn btn-sm" data-no></button></div>';
    card.querySelector(".ai-proposal-title").textContent = p.summary;
    if (p.story) card.querySelector(".ai-proposal-story").innerHTML = render(p.story);
    var yes = card.querySelector("[data-yes]"), no = card.querySelector("[data-no]");
    yes.textContent = p.button || gettext("Add");
    if (p.danger) { card.classList.add("is-danger"); yes.classList.remove("btn-primary"); yes.classList.add("btn-danger"); }
    no.textContent = gettext("No, thanks");
    yes.addEventListener("click", function () {
      yes.disabled = no.disabled = true;
      yes.textContent = gettext("Saving…");
      post(box.getAttribute("data-apply-url"), { token: p.token }).then(function (data) {
        var row = card.querySelector(".row");
        if (data.ok) {
          row.innerHTML = '<a class="ai-done" href="' + esc(data.url) + '"></a>';
          row.firstChild.textContent = "✓ " + data.message + " " + gettext("Open");
          history.push({ role: "user", text: "(" + gettext("Saved") + ": " + p.summary + ")" });
        } else {
          row.innerHTML = '<span class="ai-error"></span>';
          row.firstChild.textContent = data.error;
        }
        save();
      });
    });
    no.addEventListener("click", function () {
      card.remove();
      history.push({ role: "user", text: "(" + gettext("Not saved") + ": " + p.summary + ")" });
      save();
    });
    log.appendChild(card);
    card.scrollIntoView({ block: "end", behavior: "smooth" });
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST", credentials: "same-origin", body: JSON.stringify(body),
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() }
    }).then(function (r) {
      return r.json().catch(function () { return { error: gettext("Something went wrong. Please try again.") }; });
    }, function () {
      return { error: gettext("No connection. Check the internet and try again.") };
    });
  }

  function ask(text) {
    text = text.trim();
    if (!text || send.disabled) return;
    var hello = log.querySelector(".ai-hello");
    if (hello) hello.remove();
    bubble("user", text);
    input.value = "";
    grow();
    send.disabled = true;
    var wait = bubble("model", "");
    wait.classList.add("ai-wait");
    wait.innerHTML = "<span></span><span></span><span></span>";
    var reply = "", proposals = [], failed = "", el = null;
    function show() {
      if (!el) { wait.remove(); el = bubble("model", ""); }
      el.innerHTML = render(reply);
      el.scrollIntoView({ block: "end" });
    }
    function handle(line) {
      if (!line.trim()) return;
      var item;
      try { item = JSON.parse(line); } catch (e) { return; }
      if (item.t) { reply += item.t; show(); }
      if (item.error) failed = item.error;
      if (item.done) proposals = item.proposals || [];
    }
    function finish() {
      send.disabled = false;
      if (!el) wait.remove();
      if (failed && !reply) {
        bubble("model", failed).classList.add("ai-error");
        return;
      }
      if (failed) bubble("model", failed).classList.add("ai-error");
      history.push({ role: "user", text: text });
      var noted = proposals.map(function (p) { return "[" + gettext("Proposed") + ": " + p.summary + "]"; });
      history.push({ role: "model", text: [reply].concat(noted).join("\n").trim() });
      save();
      proposals.forEach(proposal);
      input.focus();
    }
    // The answer arrives line by line (JSON per line) and is shown as it is written.
    fetch(box.getAttribute("data-message-url"), {
      method: "POST", credentials: "same-origin", body: JSON.stringify({ message: text, history: history }),
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() }
    }).then(function (r) {
      var type = r.headers.get("Content-Type") || "";
      if (type.indexOf("ndjson") === -1 || !r.body || !window.TextDecoder) {
        return r.text().then(function (body) { body.split("\n").forEach(handle); if (!reply && !failed) {
          try { failed = JSON.parse(body).error || ""; } catch (e) { failed = gettext("Something went wrong. Please try again."); }
        } });
      }
      var reader = r.body.getReader(), decoder = new TextDecoder(), buffer = "";
      return (function pump() {
        return reader.read().then(function (step) {
          buffer += decoder.decode(step.value || new Uint8Array(), { stream: !step.done });
          var parts = buffer.split("\n");
          buffer = parts.pop();
          parts.forEach(handle);
          if (step.done) { handle(buffer); return; }
          return pump();
        });
      })();
    }).catch(function () {
      failed = failed || gettext("No connection. Check the internet and try again.");
    }).then(finish);
  }

  function grow() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 220) + "px";
  }

  // Bring back this tab's conversation.
  if (history.length) {
    var hello = log.querySelector(".ai-hello");
    if (hello) hello.remove();
    history.forEach(function (turn) {
      if (turn.text.charAt(0) !== "(") bubble(turn.role, turn.text.replace(/\n?\[[^\]]+\]/g, ""));
    });
  }

  form.addEventListener("submit", function (e) { e.preventDefault(); ask(input.value); });
  input.addEventListener("input", grow);
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); ask(input.value); }
  });
  Array.prototype.forEach.call(box.querySelectorAll("[data-ai-ask]"), function (b) {
    b.addEventListener("click", function () { ask(b.textContent); });
  });
  // A voice or video message: keep it as a family event under a title (as text too, if wished),
  // or turn it into words for the assistant.
  var MAX = 4194304;
  function offer(file) {
    if (file.size > MAX) {
      bubble("model", gettext("The recording is too long: up to 4 MB (about 25 minutes of voice or 1 minute of video).")).classList.add("ai-error");
      return;
    }
    var hello = log.querySelector(".ai-hello");
    if (hello) hello.remove();
    var card = document.createElement("div");
    card.className = "ai-proposal ai-recording";
    var video = /^video\//.test(file.type);
    var url = URL.createObjectURL(file);
    var canEdit = box.hasAttribute("data-can-edit");
    card.innerHTML = (video ? '<video controls playsinline></video>' : '<audio controls></audio>') +
      (canEdit ? '<label class="ai-field"><span></span><input type="text" maxlength="200" data-title></label>' +
        '<label class="checkbox"><input type="checkbox" data-as-text checked> <span></span></label>' : "") +
      '<div class="row">' + (canEdit ? '<button type="button" class="btn btn-primary btn-sm" data-save></button>' : "") +
      '<button type="button" class="btn btn-sm" data-words></button>' +
      '<button type="button" class="btn btn-sm btn-ghost" data-drop></button></div><p class="ai-error" hidden></p>';
    card.querySelector(video ? "video" : "audio").src = url;
    var errorBox = card.querySelector(".ai-error"), row = card.querySelector(".row");
    var words = card.querySelector("[data-words]"), drop = card.querySelector("[data-drop]");
    words.textContent = gettext("Turn into text and send");
    drop.textContent = gettext("Remove");
    if (canEdit) {
      card.querySelector(".ai-field span").textContent = gettext("Title");
      card.querySelector("[data-title]").placeholder = gettext("For example: Grandfather tells about his childhood");
      card.querySelector("[data-as-text] + span").textContent = gettext("Also write it down as text");
      card.querySelector("[data-save]").textContent = gettext("Save as an event");
    }
    function busy(on) {
      Array.prototype.forEach.call(card.querySelectorAll("button"), function (b) { b.disabled = on; });
      if (on) errorBox.hidden = true;
    }
    function upload(target, extra) {
      var data = new FormData();
      data.append("file", file, file.name || "recording");
      Object.keys(extra || {}).forEach(function (k) { data.append(k, extra[k]); });
      return fetch(box.getAttribute(target), { method: "POST", credentials: "same-origin", body: data,
        headers: { "X-CSRFToken": csrf() } })
        .then(function (r) { return r.json(); })
        .catch(function () { return { error: gettext("No connection. Check the internet and try again.") }; });
    }
    var saveBtn = card.querySelector("[data-save]");
    if (saveBtn) saveBtn.addEventListener("click", function () {
      var title = card.querySelector("[data-title]").value.trim();
      if (!title) {
        errorBox.textContent = gettext("Write a title for the recording.");
        errorBox.hidden = false;
        card.querySelector("[data-title]").focus();
        return;
      }
      busy(true);
      saveBtn.textContent = gettext("Saving…");
      upload("data-save-url", { title: title, as_text: card.querySelector("[data-as-text]").checked ? "1" : "" }).then(function (d) {
        if (d.error) {
          busy(false);
          saveBtn.textContent = gettext("Save as an event");
          errorBox.textContent = d.error;
          errorBox.hidden = false;
          return;
        }
        row.innerHTML = '<a class="ai-done"></a> <a class="btn btn-sm btn-ghost"></a>';
        row.children[0].href = d.url;
        row.children[0].textContent = "✓ " + d.message + " " + gettext("Open");
        row.children[1].href = d.edit_url;
        row.children[1].textContent = gettext("Edit");
        card.querySelectorAll("label").forEach(function (l) { l.remove(); });
        var head = document.createElement("p");
        head.className = "ai-proposal-title";
        head.textContent = title;
        card.insertBefore(head, card.firstChild);
        if (d.text) {
          var story = document.createElement("div");
          story.className = "ai-proposal-story";
          story.innerHTML = render(d.text);
          card.insertBefore(story, row);
        }
        history.push({ role: "user", text: "(" + gettext("Saved") + ": " + title + ")" });
        save();
      });
    });
    words.addEventListener("click", function () {
      busy(true);
      words.textContent = gettext("Writing it down…");
      upload("data-transcribe-url").then(function (d) {
        if (d.error) {
          busy(false);
          words.textContent = gettext("Turn into text and send");
          errorBox.textContent = d.error;
          errorBox.hidden = false;
          return;
        }
        card.remove();
        ask(d.text);
      });
    });
    drop.addEventListener("click", function () { URL.revokeObjectURL(url); card.remove(); });
    log.appendChild(card);
    card.scrollIntoView({ block: "end", behavior: "smooth" });
    var t = card.querySelector("[data-title]");
    if (t) t.focus();
  }

  var mic = form.querySelector("[data-ai-mic]");
  if (mic && window.MediaRecorder && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    mic.hidden = false;
    var rec = null, stopTimer = null;
    mic.addEventListener("click", function () {
      if (rec && rec.state === "recording") { rec.stop(); return; }
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
        var type = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus"].filter(function (t) {
          return MediaRecorder.isTypeSupported(t);
        })[0];
        var parts = [], size = 0;
        rec = new MediaRecorder(stream, type ? { mimeType: type, audioBitsPerSecond: 24000 } : { audioBitsPerSecond: 24000 });
        rec.ondataavailable = function (e) {
          if (!e.data || !e.data.size) return;
          parts.push(e.data);
          size += e.data.size;
          if (size > MAX * 0.94 && rec.state === "recording") rec.stop();
        };
        rec.onstop = function () {
          clearTimeout(stopTimer);
          stream.getTracks().forEach(function (t) { t.stop(); });
          mic.classList.remove("is-recording");
          var mime = (rec.mimeType || type || "audio/webm").split(";")[0].replace("video/", "audio/");
          var ext = { "audio/webm": "weba", "audio/mp4": "m4a", "audio/ogg": "ogg" }[mime] || "weba";
          offer(new File(parts, "voice." + ext, { type: mime }));
        };
        rec.start(1000);
        mic.classList.add("is-recording");
        stopTimer = setTimeout(function () { if (rec.state === "recording") rec.stop(); }, 25 * 60 * 1000);
      }).catch(function () {
        bubble("model", gettext("The microphone could not be turned on. Allow access to the microphone in the browser.")).classList.add("ai-error");
      });
    });
  }
  var picker = form.querySelector("[data-ai-file]");
  if (picker) picker.addEventListener("change", function () {
    if (picker.files[0]) offer(picker.files[0]);
    picker.value = "";
  });

  var clear = document.querySelector("[data-ai-clear]");
  if (clear) clear.addEventListener("click", function () {
    history = [];
    save();
    window.location.reload();
  });
})();
