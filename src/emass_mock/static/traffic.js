// emass-mock traffic log: poll /_admin/requests and show what clients sent.
// Values from requests are untrusted; everything is set with textContent.
(function () {
  "use strict";

  const state = { entries: [], lastId: 0, selected: null, timer: null };
  const $ = (sel) => document.querySelector(sel);
  const HANDLED = { stateful: "mock", prism: "Prism", unhandled: "unhandled", injected: "injected" };

  function el(tag, attrs, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value === undefined || value === null || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? "" : value);
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function pill(text, kind, title) {
    return el("span", { class: "pill " + (kind || ""), text, title });
  }

  function statusKind(status) {
    if (status >= 200 && status < 300) return "ok";
    if (status >= 400 && status < 500) return "warn";
    return "bad";
  }

  function time(iso) {
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleTimeString([], { hour12: false }) + "." + String(d.getMilliseconds()).padStart(3, "0");
  }

  function matches(entry) {
    const text = $("#f-text").value.trim().toLowerCase();
    const status = $("#f-status").value;
    const handled = $("#f-handled").value;
    if (text && !(entry.path + " " + (entry.operation_id || "")).toLowerCase().includes(text)) return false;
    if (status && String(entry.status)[0] !== status) return false;
    if (handled && entry.handled_by !== handled) return false;
    if ($("#f-spec").checked && !entry.spec_errors) return false;
    return true;
  }

  function authPill(entry) {
    if (entry.api_key === "missing") return pill("no api-key", "bad");
    if (entry.api_key === "wrong") return pill("bad api-key", "bad");
    return entry.user_uid ? pill("uid", "ok", "user-uid: " + entry.user_uid) : pill("key only", "", "api-key, no user-uid");
  }

  function render() {
    const tbody = $("#rows");
    tbody.replaceChildren();
    const visible = state.entries.filter(matches);
    for (const entry of visible) {
      const request = el("td", { class: "path" },
        el("span", { class: "method " + entry.method, text: entry.method }), " ",
        entry.path + (entry.query ? "?" + entry.query : ""),
        el("div", { class: "small" }, entry.operation_id ? el("code", { text: entry.operation_id }) : pill("not in spec", "bad")));
      const status = el("td", {}, pill(String(entry.status || "—"), statusKind(entry.status)), " ",
        entry.spec_errors ? pill(entry.spec_errors + " spec", "bad", "Request body problems against the spec") : null,
        el("div", { class: "muted small", text: HANDLED[entry.handled_by] || entry.handled_by }));
      tbody.append(el("tr", {
        class: "traffic-row" + (state.selected === entry.id ? " selected" : ""),
        onclick: () => select(entry.id, true),
      },
        el("td", { class: "mono", text: String(entry.id) }),
        el("td", { class: "mono small", text: time(entry.timestamp) }),
        request, status,
        el("td", {}, authPill(entry)),
        el("td", { class: "num", text: String(entry.duration_ms) })));
    }
    $("#no-rows").hidden = visible.length > 0;
    $("#no-rows").textContent = state.entries.length ? "No requests match the filters." : "No requests yet.";
  }

  function section(title, content) {
    return [el("h3", { text: title }), content];
  }

  function jsonBlock(value) {
    if (value === null || value === undefined || value === "") return el("p", { class: "muted", text: "(none)" });
    return el("pre", { text: typeof value === "string" ? value : JSON.stringify(value, null, 2) });
  }

  async function select(id, setHash) {
    state.selected = id;
    if (setHash) history.replaceState(null, "", "#" + id);
    render();
    const detail = $("#detail");
    let entry;
    try {
      const resp = await fetch("/_admin/requests/" + id);
      if (!resp.ok) throw new Error("request " + id + " is no longer in the log");
      entry = await resp.json();
    } catch (err) {
      detail.replaceChildren(el("p", { class: "callout warn", text: String(err.message || err) }));
      return;
    }
    const meta = el("dl", { class: "kv" },
      el("dt", { text: "Operation" }), el("dd", {}, entry.operation_id ? el("code", { text: entry.operation_id }) : pill("not an eMASS spec operation", "bad")),
      el("dt", { text: "Handled by" }), el("dd", { text: HANDLED[entry.handled_by] || entry.handled_by }),
      el("dt", { text: "api-key" }), el("dd", { text: entry.auth.api_key }),
      el("dt", { text: "user-uid" }), el("dd", { text: entry.auth.user_uid || "(not sent)" }),
      el("dt", { text: "Content-Type" }), el("dd", { class: "mono small", text: entry.request_content_type || "(none)" }),
      el("dt", { text: "Request size" }), el("dd", { text: entry.request_size + " bytes" + (entry.truncated ? " (capture truncated)" : "") }),
      el("dt", { text: "Duration" }), el("dd", { text: entry.duration_ms + " ms" }),
      el("dt", { text: "Time" }), el("dd", { class: "mono small", text: entry.timestamp }));

    const parts = [];
    parts.push(el("div", { class: "row", style: "justify-content: space-between" },
      el("h2", { style: "margin:0" }, el("span", { class: "method " + entry.method, text: entry.method }), " #" + entry.id),
      pill(String(entry.status), statusKind(entry.status))));
    parts.push(el("div", { class: "url-bar", style: "margin: 0.5rem 0 0.75rem" }, entry.path + (entry.query ? "?" + entry.query : "")));
    if (entry.spec_errors && entry.spec_errors.length) {
      parts.push(el("div", { class: "callout bad" }, el("strong", { text: "The spec would reject this request." }),
        el("ul", {}, entry.spec_errors.map((m) => el("li", { class: "mono", text: m })))));
    }
    parts.push(meta);
    if (entry.operation_id) {
      parts.push(el("p", {}, el("a", { href: "/ui/console?op=" + encodeURIComponent(entry.operation_id) }, "Open this operation in the console")));
    }
    if (entry.request_parts && entry.request_parts.length) {
      parts.push(...section("Multipart parts", el("div", { class: "table-wrap" }, el("table", {},
        el("thead", {}, el("tr", {}, el("th", { text: "Name" }), el("th", { text: "File / value" }), el("th", { text: "Type" }))),
        el("tbody", {}, entry.request_parts.map((p) => el("tr", {},
          el("td", {}, el("code", { text: p.name }), p.binary && p.name !== "filename" ? [" ", pill("spec says filename", "warn")] : null),
          el("td", { class: "mono small", text: p.filename !== undefined ? p.filename : p.value !== undefined ? p.value : "" }),
          el("td", { class: "small", text: p.content_type || "" }))))))));
    } else {
      parts.push(...section("Request body", jsonBlock(entry.request_body)));
    }
    parts.push(...section("Response body", jsonBlock(entry.response_body)));
    const headerText = Object.entries(entry.request_headers || {}).map(([k, v]) => k + ": " + v).join("\n");
    parts.push(el("details", { style: "margin-top: 0.75rem" }, el("summary", { text: "Request headers" }), el("pre", { text: headerText })));
    detail.replaceChildren(...parts);
  }

  async function poll() {
    try {
      const resp = await fetch("/_admin/requests?after=" + state.lastId + "&limit=500");
      if (resp.ok) {
        const data = await resp.json();
        if (data.entries.length) {
          for (const entry of data.entries) state.entries.unshift(entry);
          state.lastId = data.entries[data.entries.length - 1].id;
          if (state.entries.length > data.limit) state.entries.length = data.limit;
          render();
        }
      }
    } catch (err) {
      // Server restarting; try again on the next tick.
    }
  }

  function schedule() {
    clearInterval(state.timer);
    if ($("#live").checked) state.timer = setInterval(poll, 1500);
  }

  async function clearLog() {
    if (!confirm("Clear the request log?")) return;
    await fetch("/_admin/requests", { method: "DELETE" });
    state.entries = [];
    state.selected = null;
    $("#detail").replaceChildren(el("p", { class: "empty", text: "Select a request to see what was sent and what came back." }));
    history.replaceState(null, "", location.pathname);
    render();
  }

  for (const id of ["#f-text", "#f-status", "#f-handled", "#f-spec"]) {
    $(id).addEventListener("input", render);
    $(id).addEventListener("change", render);
  }
  $("#live").addEventListener("change", schedule);
  $("#clear").addEventListener("click", clearLog);

  poll().then(() => {
    const wanted = parseInt(location.hash.slice(1), 10);
    if (wanted) select(wanted, false);
  });
  schedule();
})();
