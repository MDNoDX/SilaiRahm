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
    yes.textContent = gettext("Add");
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
    post(box.getAttribute("data-message-url"), { message: text, history: history }).then(function (data) {
      wait.remove();
      send.disabled = false;
      if (data.error) {
        bubble("model", data.error).classList.add("ai-error");
        return;
      }
      history.push({ role: "user", text: text });
      var noted = (data.proposals || []).map(function (p) { return "[" + gettext("Proposed") + ": " + p.summary + "]"; });
      history.push({ role: "model", text: [data.reply].concat(noted).join("\n").trim() });
      save();
      if (data.reply) bubble("model", data.reply);
      (data.proposals || []).forEach(proposal);
      input.focus();
    });
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
  // Speak instead of typing: the words are written into the box to check and send.
  var mic = form.querySelector("[data-ai-mic]");
  if (mic && window.MediaRecorder && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    mic.hidden = false;
    var rec = null, hint = input.placeholder;
    mic.addEventListener("click", function () {
      if (rec && rec.state === "recording") { rec.stop(); return; }
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
        var type = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus"].filter(function (t) {
          return MediaRecorder.isTypeSupported(t);
        })[0];
        var parts = [];
        rec = new MediaRecorder(stream, type ? { mimeType: type, audioBitsPerSecond: 24000 } : {});
        rec.ondataavailable = function (e) { if (e.data && e.data.size) parts.push(e.data); };
        rec.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
          mic.classList.remove("is-recording");
          var mime = (rec.mimeType || type || "audio/webm").split(";")[0].replace("video/", "audio/");
          var data = new FormData();
          var blob = new Blob(parts, { type: mime });
          data.append("file", blob, "voice.rec");
          mic.disabled = true;
          input.placeholder = gettext("Writing it down…");
          fetch(mic.getAttribute("data-transcribe-url"), { method: "POST", credentials: "same-origin", body: data,
            headers: { "X-CSRFToken": csrf() } })
            .then(function (r) { return r.json(); })
            .then(function (d) {
              if (d.error) { bubble("model", d.error).classList.add("ai-error"); return; }
              input.value = (input.value.trim() ? input.value.trim() + " " : "") + d.text;
              grow();
              input.focus();
            })
            .catch(function () { bubble("model", gettext("Something went wrong. Please try again.")).classList.add("ai-error"); })
            .then(function () { mic.disabled = false; input.placeholder = hint; });
        };
        rec.start(1000);
        mic.classList.add("is-recording");
        setTimeout(function () { if (rec.state === "recording") rec.stop(); }, 10 * 60 * 1000);
      }).catch(function () {
        bubble("model", gettext("The microphone could not be turned on. Allow access to the microphone in the browser.")).classList.add("ai-error");
      });
    });
  }

  var clear = document.querySelector("[data-ai-clear]");
  if (clear) clear.addEventListener("click", function () {
    history = [];
    save();
    window.location.reload();
  });
})();
