(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const node = (tag, text, cls) => {
    const e = document.createElement(tag);
    if (text !== undefined) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  };
  const state = {
    caseId: null,
    record: null,
    references: [],
    offset: 0,
    total: 0,
    queryVersion: 0,
    dirty: false,
  };
  const fields = [
    "title",
    "body",
    "url",
    "excerpt",
    "locator",
    "published_on",
    "reviewed_on",
    "event_on",
    "confidence",
    "confidence_reason",
  ];
  const fieldId = (k) =>
    ["title", "body", "url"].includes(k)
      ? "record-" + k
      : k.replaceAll("_", "-");
  function message(text) {
    $("status").textContent = text;
  }
  async function api(path, options = {}) {
    let response;
    try {
      response = await fetch(path, {
        ...options,
        headers: { "Content-Type": "application/json", "X-Desk-Request": "1" },
        credentials: "same-origin",
      });
    } catch {
      throw new Error(
        "The desk could not be reached. Your draft remains here. Check the connection before retrying a create operation.",
      );
    }
    const body = await response.json();
    if (!response.ok) {
      if (response.status === 401) {
        $("workspace").hidden = true;
        $("login-panel").hidden = false;
        $("logout").hidden = true;
      }
      throw new Error(
        body.error?.message || "Request failed. Your draft remains here.",
      );
    }
    return body;
  }
  const mutation = (method, value) => ({ method, body: JSON.stringify(value) });
  function discard() {
    return !state.dirty || window.confirm("Discard the unsaved draft?");
  }
  function typeFields() {
    const kind = $("record-kind").value;
    $("document-fields").hidden = kind !== "document";
    $("claim-fields").hidden = kind !== "claim";
    $("source-id").required = kind === "document";
    for (const id of ["document-id", "excerpt", "locator"])
      $(id).required = kind === "claim";
    $("record-url").required = kind === "source";
  }
  function option(select, value, label) {
    const e = node("option", label);
    e.value = value;
    select.append(e);
  }
  function referenceOptions() {
    for (const id of ["source-id", "document-id", "links"]) {
      $(id).replaceChildren();
      if (id !== "links") option($(id), "", "Choose a record in this case");
    }
    for (const r of state.references) {
      if (r.id === state.record?.id) continue;
      option($("links"), r.id, `${r.kind} / ${r.title}`);
      if (r.kind === "source") option($("source-id"), r.id, r.title);
      if (r.kind === "document") option($("document-id"), r.id, r.title);
    }
  }
  function editor(record = null) {
    state.record = record;
    state.dirty = false;
    $("record-form").reset();
    referenceOptions();
    $("record-kind").disabled = !!record;
    $("record-kind").value = record?.kind || "note";
    for (const k of fields)
      $(fieldId(k)).value =
        record?.[k] || (k === "confidence" ? "unassessed" : "");
    $("source-id").value = record?.source_id || "";
    $("document-id").value = record?.document_id || "";
    $("citation-version").textContent = record?.citation_provenance
      ? `Evidence snapshot: document revision ${record.citation_provenance.document_revision}; published ${record.citation_provenance.published_on || "unknown"}; reviewed ${record.citation_provenance.reviewed_on || "unknown"}.`
      : "The evidence document revision is recorded when a claim is saved.";
    $("tags").value = (record?.tags || []).join(", ");
    for (const o of $("links").options)
      o.selected = (record?.links || []).includes(o.value);
    $("record-heading").textContent =
      record?.title || "What are you working on?";
    $("record-meta").textContent = record
      ? `${record.kind} / revision ${record.revision} / saved ${record.updated_at.slice(0, 19)} UTC`
      : "New record";
    $("record-error").textContent = "";
    $("save-state").textContent = "";
    $("reload-record").hidden = !record;
    $("connections").hidden = !record;
    $("history-panel").hidden = !record;
    $("history").replaceChildren();
    $("history-panel").open = false;
    $("provenance-panel").hidden = !record?.provenance;
    $("provenance").textContent = record?.provenance
      ? JSON.stringify(record.provenance, null, 2)
      : "";
    typeFields();
    renderGraph();
    document.querySelectorAll(".record-link").forEach((b) => {
      if (b.dataset.id === record?.id) b.setAttribute("aria-current", "true");
      else b.removeAttribute("aria-current");
    });
  }
  async function loadList() {
    const version = ++state.queryVersion;
    const caseId = state.caseId;
    if (!caseId) return;
    const params = new URLSearchParams({
      q: $("search").value,
      kind: $("kind-filter").value,
      offset: state.offset,
      limit: 50,
    });
    const result = await api(`/api/cases/${caseId}/records?${params}`);
    if (version !== state.queryVersion || caseId !== state.caseId) return;
    state.total = result.total;
    $("result-count").textContent =
      `${result.total} matching records / ${Math.min(state.offset + 1, result.total)}–${Math.min(state.offset + result.items.length, result.total)} shown`;
    $("record-list").replaceChildren();
    if (!result.items.length)
      $("record-list").append(
        node(
          "p",
          "No records match. Clear the search/type filter, or create a record.",
          "help",
        ),
      );
    for (const r of result.items) {
      const b = node("button", r.title, "record-link");
      b.dataset.id = r.id;
      b.append(
        node("span", `${r.kind} / ${r.confidence} / revision ${r.revision}`),
      );
      b.addEventListener("click", () => openRecord(r.id));
      if (state.record?.id === r.id) b.setAttribute("aria-current", "true");
      $("record-list").append(b);
    }
    $("previous").disabled = state.offset === 0;
    $("next").disabled = state.offset + 50 >= result.total;
  }
  async function loadReferences() {
    const caseId = state.caseId;
    const all = [];
    let offset = 0;
    while (offset < 1000) {
      const result = await api(
        `/api/cases/${caseId}/records?offset=${offset}&limit=100`,
      );
      all.push(...result.items);
      offset += 100;
      if (offset >= result.total) break;
    }
    if (state.caseId === caseId) state.references = all;
    if (all.length === 1000)
      message(
        "Reference choices show the first 1,000 records. The API and case exports preserve the full case.",
      );
  }
  async function loadCase() {
    const caseId = $("case").value;
    state.caseId = caseId || null;
    state.offset = 0;
    state.queryVersion++;
    state.references = [];
    $("no-case").hidden = !!caseId;
    $("case-desk").hidden = true;
    $("export").disabled = !caseId;
    if (!caseId) return;
    message("Loading this private case…");
    $("search").value = "";
    $("kind-filter").value = "";
    await loadReferences();
    if (state.caseId !== caseId) return;
    editor();
    await loadList();
    if (state.caseId !== caseId) return;
    $("case-desk").hidden = false;
    message(
      "Private case loaded. Drafts are saved only when you choose Save record.",
    );
  }
  async function cases() {
    const result = await api("/api/cases");
    $("case").replaceChildren();
    for (const c of result.items) option($("case"), c.id, c.title);
    $("workspace").hidden = false;
    $("login-panel").hidden = true;
    $("logout").hidden = false;
    if (result.items.some((c) => c.id === state.caseId))
      $("case").value = state.caseId;
    await loadCase();
  }
  async function openRecord(id) {
    if (!discard()) return;
    try {
      const r = await api("/api/records/" + encodeURIComponent(id));
      if (r.case_id !== state.caseId) return;
      editor(r);
      $("record-heading").scrollIntoView({ block: "start" });
    } catch (e) {
      message(e.message);
    }
  }
  async function history() {
    if (!state.record) return;
    try {
      const result = await api(`/api/records/${state.record.id}/history`);
      $("history").replaceChildren();
      for (const r of result.items) {
        const a = node("article");
        a.append(
          node("strong", `Revision ${r.revision} / ${r.updated_at}`),
          node("p", r.title),
          node("p", r.body),
        );
        if (r.excerpt) a.append(node("p", "Cited excerpt: " + r.excerpt));
        $("history").append(a);
      }
    } catch (e) {
      message(e.message);
    }
  }
  function renderGraph() {
    const svg = $("record-graph");
    svg.replaceChildren();
    $("backlinks").replaceChildren();
    const r = state.record;
    if (!r) return;
    const refs = new Map(state.references.map((x) => [x.id, x]));
    const outgoing = [
      ...new Set(
        [...(r.links || []), r.source_id, r.document_id].filter(Boolean),
      ),
    ]
      .map((id) => refs.get(id))
      .filter(Boolean);
    const incoming = r.backlinks || [];
    const count = Math.max(outgoing.length, incoming.length, 1);
    const height = Math.max(220, count * 85 + 70);
    svg.setAttribute("viewBox", `0 0 800 ${height}`);
    const ns = "http://www.w3.org/2000/svg";
    const s = (tag, attrs, text) => {
      const e = document.createElementNS(ns, tag);
      for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
      if (text) e.textContent = text;
      return e;
    };
    function label(item, x, y, active) {
      const g = s("g", {
        class: "graph-node" + (active ? " active" : ""),
        transform: `translate(${x},${y})`,
        role: "button",
        tabindex: "0",
        "aria-label": `Open ${item.kind}: ${item.title}`,
      });
      g.append(
        s("rect", { x: -115, y: -25, width: 230, height: 50, rx: 3 }),
        s(
          "text",
          { "text-anchor": "middle", y: -3 },
          item.title.length > 30 ? item.title.slice(0, 29) + "…" : item.title,
        ),
        s("text", { "text-anchor": "middle", y: 15 }, item.kind),
      );
      g.append(s("title", {}, item.title));
      g.addEventListener("click", () => openRecord(item.id));
      g.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openRecord(item.id).then(() => $("record-title").focus());
        }
      });
      svg.append(g);
    }
    label(r, 400, height / 2, true);
    for (const [items, x, relation] of [
      [outgoing, 140, "references / citation"],
      [incoming, 660, "backlink"],
    ])
      items.forEach((item, i) => {
        const y = 50 + i * 85;
        svg.prepend(
          s("path", {
            class: "edge",
            d: `M ${x < 400 ? 255 : 545} ${y} L ${x < 400 ? 285 : 515} ${height / 2}`,
          }),
        );
        label(item, x, y, false);
      });
    if (!outgoing.length && !incoming.length)
      $("backlinks").append(
        node(
          "p",
          "No links yet. Add a reference or create a claim linked to a stored document.",
          "help",
        ),
      );
    for (const item of incoming) {
      const b = node(
        "button",
        `${item.kind}: ${item.title} (${item.relation})`,
      );
      b.addEventListener("click", () => openRecord(item.id));
      $("backlinks").append(b);
    }
  }
  $("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const button = e.submitter;
    button.disabled = true;
    try {
      await api(
        "/api/session",
        mutation("POST", { access_key: $("access-key").value }),
      );
      $("access-key").value = "";
      $("login-error").textContent = "";
      if (state.dirty && state.caseId) {
        $("workspace").hidden = false;
        $("login-panel").hidden = true;
        $("logout").hidden = false;
        message("Signed in again. Your unsaved draft is still open.");
      } else await cases();
    } catch (error) {
      $("login-error").textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
  $("case-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!discard()) return;
    const b = e.submitter;
    b.disabled = true;
    try {
      const c = await api(
        "/api/cases",
        mutation("POST", { title: $("case-title").value }),
      );
      state.caseId = c.id;
      state.dirty = false;
      $("case-title").value = "";
      e.target.closest("details").open = false;
      await cases();
    } catch (error) {
      message(error.message);
    } finally {
      b.disabled = false;
    }
  });
  $("case").addEventListener("change", () => {
    if (!discard()) {
      $("case").value = state.caseId;
      return;
    }
    loadCase().catch((e) => message(e.message));
  });
  $("new-record").addEventListener("click", () => {
    if (discard()) {
      editor();
      $("record-title").focus();
    }
  });
  $("record-kind").addEventListener("change", typeFields);
  $("record-form").addEventListener("input", () => {
    state.dirty = true;
    $("save-state").textContent = "Unsaved draft";
  });
  $("record-form").addEventListener("change", () => {
    state.dirty = true;
  });
  $("record-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const button = $("save-record");
    button.disabled = true;
    $("record-error").textContent = "";
    const value = { kind: $("record-kind").value };
    for (const k of fields)
      value[k] =
        $(fieldId(k)).value ||
        (["published_on", "reviewed_on", "event_on"].includes(k) ? null : "");
    value.tags = $("tags")
      .value.split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    value.links = [...$("links").selectedOptions].map((o) => o.value);
    value.source_id =
      value.kind === "document" ? $("source-id").value || null : null;
    value.document_id =
      value.kind === "claim" ? $("document-id").value || null : null;
    if (value.kind !== "claim") {
      value.excerpt = "";
      value.locator = "";
    }
    try {
      const previous = state.record;
      const result = await api(
        previous
          ? `/api/records/${previous.id}`
          : `/api/cases/${state.caseId}/records`,
        mutation(
          previous ? "PUT" : "POST",
          previous ? { ...value, revision: previous.revision } : value,
        ),
      );
      state.dirty = false;
      await loadReferences();
      editor(result);
      await loadList();
      $("save-state").textContent = `Saved revision ${result.revision}`;
    } catch (error) {
      $("record-error").textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
  $("reload-record").addEventListener("click", () => {
    if (state.record) openRecord(state.record.id);
  });
  $("history-panel").addEventListener("toggle", () => {
    if ($("history-panel").open) history();
  });
  let timer;
  for (const id of ["search", "kind-filter"])
    $(id).addEventListener(id === "search" ? "input" : "change", () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        state.offset = 0;
        loadList().catch((e) => message(e.message));
      }, 150);
    });
  $("previous").addEventListener("click", () => {
    state.offset = Math.max(0, state.offset - 50);
    loadList().catch((e) => message(e.message));
  });
  $("next").addEventListener("click", () => {
    state.offset += 50;
    loadList().catch((e) => message(e.message));
  });
  $("export").addEventListener("click", async () => {
    try {
      const data = await api(`/api/cases/${state.caseId}/export`);
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      const a = node("a");
      a.href = url;
      a.download = "analysis-case.json";
      document.body.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      message(
        "Case exported, including notes and revision history. Keep this file private.",
      );
    } catch (e) {
      message(e.message);
    }
  });
  $("logout").addEventListener("click", async () => {
    if (!discard()) return;
    try {
      await api("/api/session", { method: "DELETE" });
      location.reload();
    } catch (e) {
      message(e.message);
    }
  });
  $("theme").addEventListener("click", () => {
    const dark = document.body.classList.toggle("dark");
    $("theme").textContent = dark ? "Light theme" : "Dark theme";
  });
  window.addEventListener("beforeunload", (e) => {
    if (state.dirty) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
  api("/api/session")
    .then((s) => (s.authenticated ? cases() : null))
    .catch((e) => {
      $("login-error").textContent = e.message;
    });
})();
