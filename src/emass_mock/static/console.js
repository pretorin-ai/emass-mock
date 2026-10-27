// emass-mock console: compose and send any eMASS spec operation to this mock.
// Plain DOM, no framework. Every value from the server is set with
// textContent, never innerHTML.
(function () {
  "use strict";

  const config = window.EMASS_MOCK || {};
  const state = { ops: [], systems: [], current: null };
  const WRITE = new Set(["POST", "PUT", "DELETE", "PATCH"]);

  const $ = (sel, root) => (root || document).querySelector(sel);

  function el(tag, attrs, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value === undefined || value === null || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else if (value === true) node.setAttribute(key, "");
      else node.setAttribute(key, value);
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function pill(text, kind) {
    return el("span", { class: "pill " + (kind || ""), text });
  }

  function statusKind(status) {
    if (status >= 200 && status < 300) return "ok";
    if (status >= 400 && status < 500) return "warn";
    return "bad";
  }

  async function getJSON(url, options) {
    const resp = await fetch(url, options);
    if (!resp.ok) throw new Error(url + " returned " + resp.status);
    return resp.json();
  }

  // ---------------------------------------------------------------- list

  function renderList() {
    const filter = $("#op-filter").value.trim().toLowerCase();
    const statefulOnly = $("#op-stateful").checked;
    const groups = new Map();
    for (const op of state.ops) {
      if (statefulOnly && !op.stateful) continue;
      const hay = (op.method + " " + op.path + " " + op.operationId + " " + op.tag + " " + op.summary).toLowerCase();
      if (filter && !filter.split(/\s+/).every((word) => hay.includes(word))) continue;
      if (!groups.has(op.tag)) groups.set(op.tag, []);
      groups.get(op.tag).push(op);
    }
    const container = $("#op-groups");
    container.replaceChildren();
    if (!groups.size) {
      container.append(el("p", { class: "empty", text: "No operations match." }));
      return;
    }
    for (const [tag, ops] of groups) {
      const group = el("div", { class: "op-group" }, el("h4", { text: tag }));
      for (const op of ops) {
        group.append(
          el(
            "button",
            {
              type: "button",
              class: "op-item" + (state.current && state.current.operationId === op.operationId ? " selected" : ""),
              title: op.operationId + (op.summary ? " — " + op.summary : ""),
              onclick: () => selectOp(op.operationId, true),
            },
            el("span", { class: "method " + op.method, text: op.method }),
            el("span", { class: "path", text: op.path.replace(/^\/api/, "") || "/" }),
            el("span", { class: "dot" + (op.stateful ? " on" : ""), title: op.stateful ? "Answered by the mock" : "Proxied to Prism" })
          )
        );
      }
      container.append(group);
    }
  }

  // ------------------------------------------------------------- builder

  function inputFor(param, prefix, initial) {
    const id = prefix + param.name;
    let input;
    const enumValues = param.enum || (param.type === "boolean" ? [true, false] : null);
    if (enumValues) {
      input = el("select", { id, "data-name": param.name });
      input.append(el("option", { value: "", text: param.required ? "Choose…" : "(not sent)" }));
      for (const value of enumValues) input.append(el("option", { value: String(value), text: String(value) }));
      if (initial !== undefined && initial !== null) input.value = String(initial);
    } else {
      input = el("input", {
        id,
        type: "text",
        "data-name": param.name,
        placeholder: param.default !== null && param.default !== undefined ? "default " + param.default : param.example !== null && param.example !== undefined ? "e.g. " + param.example : "",
      });
      if (initial !== undefined && initial !== null) input.value = String(initial);
    }
    input.addEventListener("input", updateUrl);
    input.addEventListener("change", updateUrl);
    return el(
      "div",
      { class: "field" },
      el("label", { for: id }, param.name, param.required ? " *" : "", param.description ? el("span", { class: "muted", text: " · " + param.description }) : null),
      input
    );
  }

  function initialPathValue(name) {
    const params = new URLSearchParams(location.search);
    if (name === "systemId") return params.get("systemId") || (state.systems[0] !== undefined ? state.systems[0] : 1);
    return params.get(name) || "";
  }

  function buildUrl() {
    const op = state.current;
    if (!op) return "";
    let path = op.path;
    for (const param of op.parameters.filter((p) => p.in === "path")) {
      const value = ($("#path-" + param.name) || {}).value || "";
      path = path.replace("{" + param.name + "}", encodeURIComponent(value || "{" + param.name + "}"));
    }
    const query = new URLSearchParams();
    for (const param of op.parameters.filter((p) => p.in === "query")) {
      const value = ($("#query-" + param.name) || {}).value;
      if (value !== undefined && value !== "") query.set(param.name, value);
    }
    const qs = query.toString();
    return path + (qs ? "?" + qs : "");
  }

  function updateUrl() {
    const target = $("#url-path");
    if (target) target.textContent = buildUrl();
  }

  async function loadExample(mode) {
    const op = state.current;
    const textarea = $("#body-json");
    if (!op || !textarea) return;
    try {
      const data = await getJSON("/_admin/operations/" + encodeURIComponent(op.operationId) + "/example?mode=" + mode);
      textarea.value = JSON.stringify(data.body, null, 2);
      showValidation(null);
    } catch (err) {
      showValidation({ valid: false, errors: [String(err)] });
    }
  }

  function parseBody() {
    const text = $("#body-json").value.trim();
    if (!text) return { ok: true, value: undefined };
    try {
      return { ok: true, value: JSON.parse(text) };
    } catch (err) {
      return { ok: false, error: "Body is not valid JSON: " + err.message };
    }
  }

  function showValidation(result) {
    const box = $("#validation");
    if (!box) return;
    box.replaceChildren();
    if (!result) return;
    if (result.valid) {
      box.append(el("div", { class: "callout ok", text: "Body matches " + state.current.operationId + " in eMASS API " + config.specVersion + "." }));
      return;
    }
    box.append(
      el(
        "div",
        { class: "callout bad" },
        el("strong", { text: "The spec would reject this body." }),
        el("ul", {}, (result.errors || []).map((message) => el("li", { class: "mono", text: message })))
      )
    );
  }

  async function validate() {
    const parsed = parseBody();
    if (!parsed.ok) return showValidation({ valid: false, errors: [parsed.error] });
    try {
      const result = await getJSON("/_admin/validate", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ operationId: state.current.operationId, body: parsed.value === undefined ? null : parsed.value }),
      });
      showValidation(result);
    } catch (err) {
      showValidation({ valid: false, errors: [String(err)] });
    }
  }

  function formatBody() {
    const parsed = parseBody();
    if (!parsed.ok) return showValidation({ valid: false, errors: [parsed.error] });
    if (parsed.value !== undefined) $("#body-json").value = JSON.stringify(parsed.value, null, 2);
  }

  function multipartSection(op) {
    const wrap = el("div", {}, el("h3", { text: "Multipart body" }));
    for (const field of op.multipart) {
      if (field.binary) {
        const partSelect = el(
          "select",
          { id: "part-name", "aria-label": "Part name" },
          el("option", { value: field.name, text: field.name + " (spec)" }),
          el("option", { value: "file", text: "file (what emu sends)" })
        );
        wrap.append(
          el(
            "div",
            { class: "field" },
            el("label", { for: "part-file" }, "File *", field.description ? el("span", { class: "muted", text: " · " + field.description }) : null),
            el("div", { class: "row" }, el("input", { id: "part-file", type: "file", class: "grow" }), el("div", { style: "width: 14rem" }, partSelect))
          )
        );
      } else {
        wrap.append(inputFor({ name: field.name, required: field.required, enum: field.enum, type: field.type, default: field.default, description: field.description }, "form-", undefined));
      }
    }
    return wrap;
  }

  function selectOp(operationId, pushHistory) {
    const op = state.ops.find((o) => o.operationId === operationId);
    if (!op) return;
    state.current = op;
    if (pushHistory) {
      const params = new URLSearchParams(location.search);
      params.set("op", operationId);
      history.replaceState(null, "", "?" + params.toString());
    }
    renderList();

    const pathParams = op.parameters.filter((p) => p.in === "path");
    const queryParams = op.parameters.filter((p) => p.in === "query");
    const isWrite = WRITE.has(op.method);
    const builder = $("#builder");
    builder.replaceChildren();

    builder.append(
      el(
        "div",
        { class: "row", style: "justify-content: space-between; margin-bottom: 0.5rem" },
        el("div", {}, el("h2", { style: "margin:0", text: op.operationId }), op.summary ? el("p", { class: "muted", style: "margin:0", text: op.summary }) : null),
        el("div", { class: "row" }, pill(op.tag, "info"), op.stateful ? pill("answered by the mock", "ok") : pill(config.prism ? "proxied to Prism" : "not handled: 501 without PRISM_URL", "warn"))
      ),
      el("div", { class: "url-bar" }, el("span", { class: "method " + op.method, text: op.method }), el("span", { id: "url-path" }))
    );

    if (pathParams.length || queryParams.length) {
      const params = el("div", { class: "grid cols-2", style: "margin-top: 1rem" });
      for (const param of pathParams) params.append(inputFor(param, "path-", initialPathValue(param.name)));
      for (const param of queryParams) params.append(inputFor(param, "query-", param.required ? param.default : undefined));
      builder.append(el("h3", { text: "Parameters" }), params);
    }

    const sendUid = isWrite || config.userUidOnAll;
    builder.append(
      el("h3", { text: "Headers" }),
      el(
        "div",
        { class: "grid cols-2" },
        el("div", { class: "field" }, el("label", { for: "h-api-key" }, "api-key", el("span", { class: "muted", text: config.requireApiKey ? " · required on every call" : " · not checked" })), el("input", { id: "h-api-key", type: "text", value: config.apiKey || "" })),
        el(
          "div",
          { class: "field" },
          el("label", { for: "h-user-uid" }, "user-uid", el("span", { class: "muted", text: config.userUidOnAll ? " · required on every call" : " · required on PUT, POST, DELETE" })),
          el("div", { class: "row" }, el("input", { id: "h-user-uid", type: "text", class: "grow", value: "1234567890" }), el("label", { class: "check", style: "margin:0" }, el("input", { id: "h-send-uid", type: "checkbox", checked: sendUid }), "send"))
        )
      )
    );

    if (op.body === "json") {
      builder.append(
        el("div", { class: "row", style: "justify-content: space-between; margin-top: 1rem" }, el("h3", { style: "margin:0", text: "JSON body" }), el("div", { class: "row" },
          el("button", { type: "button", class: "small", onclick: () => loadExample("required") }, "Required fields"),
          el("button", { type: "button", class: "small", onclick: () => loadExample("full") }, "Full example"),
          el("button", { type: "button", class: "small", onclick: formatBody }, "Format"),
          el("button", { type: "button", class: "small", onclick: validate }, "Validate"))),
        el("div", { class: "field", style: "margin-top: 0.5rem" }, el("textarea", { id: "body-json", spellcheck: "false", "aria-label": "JSON body" })),
        el("div", { id: "validation" })
      );
    } else if (op.body === "multipart") {
      builder.append(multipartSection(op));
    }

    builder.append(
      el("div", { class: "row end", style: "margin-top: 0.5rem" },
        el("button", { type: "button", onclick: copyCurl, id: "copy-curl" }, "Copy as curl"),
        el("button", { type: "button", class: "primary", onclick: send, id: "send" }, "Send request"))
    );

    updateUrl();
    if (op.body === "json") loadExample("required");
    $("#response").hidden = true;
  }

  // ---------------------------------------------------------------- send

  function collectHeaders() {
    const headers = {};
    const key = $("#h-api-key").value;
    if (key) headers["api-key"] = key;
    if ($("#h-send-uid").checked && $("#h-user-uid").value) headers["user-uid"] = $("#h-user-uid").value;
    return headers;
  }

  function buildRequest() {
    const op = state.current;
    const headers = collectHeaders();
    let body;
    if (op.body === "json") {
      const parsed = parseBody();
      if (!parsed.ok) return { error: parsed.error };
      if (parsed.value !== undefined) {
        headers["content-type"] = "application/json";
        body = JSON.stringify(parsed.value);
      }
    } else if (op.body === "multipart") {
      const form = new FormData();
      const file = $("#part-file").files[0];
      if (file) form.append($("#part-name").value, file, file.name);
      for (const field of op.multipart.filter((f) => !f.binary)) {
        const value = $("#form-" + field.name).value;
        if (value !== "") form.append(field.name, value);
      }
      body = form;
    }
    return { method: op.method, url: buildUrl(), headers, body };
  }

  function shellQuote(value) {
    return "'" + String(value).replace(/'/g, "'\\''") + "'";
  }

  async function copyCurl() {
    const req = buildRequest();
    if (req.error) return showValidation({ valid: false, errors: [req.error] });
    const parts = ["curl", "-sS", "-X", req.method, shellQuote(location.origin + req.url)];
    for (const [name, value] of Object.entries(req.headers)) parts.push("-H", shellQuote(name + ": " + value));
    if (typeof req.body === "string") parts.push("--data", shellQuote(req.body));
    if (req.body instanceof FormData) {
      for (const [name, value] of req.body.entries()) {
        parts.push("-F", shellQuote(value instanceof File ? name + "=@" + value.name : name + "=" + value));
      }
    }
    const text = parts.join(" ");
    const button = $("#copy-curl");
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = "Copied";
    } catch (err) {
      window.prompt("Copy the command:", text);
    }
    setTimeout(() => (button.textContent = "Copy as curl"), 1500);
  }

  function rowSummary(body) {
    const rows = body && Array.isArray(body.data) ? body.data : null;
    if (!rows || !rows.length || typeof rows[0] !== "object" || !("success" in rows[0])) return null;
    const failed = rows.filter((row) => row && row.success === false);
    if (!failed.length) return el("div", { class: "callout ok", text: "All " + rows.length + " row" + (rows.length === 1 ? "" : "s") + " succeeded." });
    return el(
      "div",
      { class: "callout warn" },
      el("strong", { text: failed.length + " of " + rows.length + " rows failed." }),
      el("ul", {}, failed.map((row) => {
        const id = row.acronym || row.poamId || row.milestoneId || row.hardwareId || row.softwareId || row.filename || row.cci || "row";
        return el("li", {}, el("code", { text: String(id) }), " ", (row.errors || []).join("; "));
      }))
    );
  }

  async function send() {
    const req = buildRequest();
    if (req.error) return showValidation({ valid: false, errors: [req.error] });
    const button = $("#send");
    button.disabled = true;
    button.textContent = "Sending…";
    const started = performance.now();
    const out = $("#response-body");
    out.replaceChildren();
    $("#response").hidden = false;
    try {
      const resp = await fetch(req.url, { method: req.method, headers: req.headers, body: req.body });
      const elapsed = Math.round(performance.now() - started);
      const text = await resp.text();
      let parsed = null;
      try { parsed = JSON.parse(text); } catch (err) { parsed = null; }
      const requestId = resp.headers.get("x-emass-mock-request-id");
      const errorMessage = parsed && parsed.meta && parsed.meta.errorMessage;
      out.append(
        el("div", { class: "response-head" },
          pill(String(resp.status), statusKind(resp.status)),
          el("span", { class: "muted", text: elapsed + " ms" }),
          requestId ? el("a", { href: "/ui/traffic#" + requestId, text: "Open in traffic log #" + requestId }) : null)
      );
      if (errorMessage) out.append(el("div", { class: "callout bad" }, el("strong", { text: "meta.errorMessage: " }), errorMessage));
      const summary = rowSummary(parsed);
      if (summary) out.append(summary);
      out.append(el("pre", { text: parsed ? JSON.stringify(parsed, null, 2) : text || "(empty body)" }));
      const headerLines = [];
      resp.headers.forEach((value, name) => headerLines.push(name + ": " + value));
      out.append(el("details", { style: "margin-top: 0.75rem" }, el("summary", { text: "Response headers" }), el("pre", { text: headerLines.join("\n") })));
    } catch (err) {
      out.append(el("div", { class: "callout bad", text: "Request failed: " + err }));
    } finally {
      button.disabled = false;
      button.textContent = "Send request";
      $("#response").scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  // ----------------------------------------------------------------- init

  async function init() {
    try {
      const [ops, settings] = await Promise.all([getJSON("/_admin/operations"), getJSON("/_admin/settings")]);
      state.ops = ops;
      state.systems = settings.systems || [];
    } catch (err) {
      $("#op-groups").replaceChildren(el("p", { class: "callout bad", text: "Could not load operations: " + err }));
      return;
    }
    $("#op-filter").addEventListener("input", renderList);
    $("#op-stateful").addEventListener("change", renderList);
    const wanted = new URLSearchParams(location.search).get("op");
    if (wanted && state.ops.some((o) => o.operationId === wanted)) {
      if (!state.ops.find((o) => o.operationId === wanted).stateful) $("#op-stateful").checked = false;
      selectOp(wanted, false);
    } else {
      renderList();
    }
  }

  init();
})();
