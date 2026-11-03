(() => {
  "use strict";
  const pack = JSON.parse(document.getElementById("context-data").textContent);
  const $ = (id) => document.getElementById(id);
  const colours = [
    "#b0cbdc",
    "#e3be94",
    "#9bcbbb",
    "#d9c477",
    "#bbb9dd",
    "#d2dcca",
    "#d7b1c4",
  ];
  const index = new Map(pack.records.map((r) => [r.id, r]));
  const documents = new Map(
    pack.records
      .filter((r) => r.kind === "document")
      .map((r) => [r.data.id, r.data]),
  );
  let selected =
    pack.records.find((r) => r.kind === "normative_expression")?.id ||
    pack.records[0]?.id;
  let activeLayer = index.get(selected)?.layer || "sources";
  let visible = new Set(pack.layers.map((l) => l.id));
  const chosen = new Set();
  const notes = { interpretation: "", alternative: "", option: "", gaps: "" };
  let question = pack.question;
  function el(tag, text, parent, cls) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    if (parent) parent.append(node);
    return node;
  }
  function button(text, parent, click) {
    const b = el("button", text, parent);
    b.type = "button";
    b.addEventListener("click", click);
    return b;
  }
  function link(text, url, parent) {
    try {
      const u = new URL(url);
      if (!["https:", "http:"].includes(u.protocol) || u.username || u.password)
        return;
    } catch {
      return;
    }
    const a = el("a", text, parent);
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
  }
  function short(text, n = 65) {
    return text.length > n ? text.slice(0, n - 1) + "…" : text;
  }
  function select(id) {
    selected = id;
    activeLayer = index.get(id).layer;
    visible.add(activeLayer);
    render();
  }
  function neighbourhood() {
    const ids = new Set(selected ? [selected] : []);
    // Two explicit record hops expose publisher/document/claim and ontology paths.
    for (let hop = 0; hop < 2; hop++) {
      const previous = new Set(ids);
      pack.edges.forEach((e) => {
        if (previous.has(e.source) || previous.has(e.target)) {
          ids.add(e.source);
          ids.add(e.target);
        }
      });
    }
    return ids;
  }
  function renderLayers() {
    $("layers").replaceChildren();
    pack.layers.forEach((layer, i) => {
      const row = el("div", undefined, $("layers"), "layer-choice");
      row.style.setProperty("--layer", colours[i]);
      const check = el("input", undefined, row);
      check.type = "checkbox";
      check.checked = visible.has(layer.id);
      check.setAttribute("aria-label", "Show " + layer.title + " layer");
      check.addEventListener("change", () => {
        check.checked ? visible.add(layer.id) : visible.delete(layer.id);
        renderGraph();
      });
      const b = button("", row, () => {
        activeLayer = layer.id;
        const first = pack.records.find((r) => r.layer === layer.id);
        if (first) selected = first.id;
        visible.add(layer.id);
        render();
      });
      b.setAttribute("aria-pressed", String(activeLayer === layer.id));
      const name = el("span", undefined, b);
      el("small", undefined, name);
      name.append(document.createTextNode(layer.title));
      el("span", String(layer.record_count), b);
    });
  }
  function svg(tag, attrs, parent, text) {
    const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v));
    if (text !== undefined) n.textContent = text;
    parent.append(n);
    return n;
  }
  function renderGraph() {
    const root = $("graph");
    root.replaceChildren();
    const query = $("search").value.trim().toLocaleLowerCase();
    const matches = pack.records.filter(
      (r) =>
        !query ||
        (r.title + " " + JSON.stringify(r.data))
          .toLocaleLowerCase()
          .includes(query),
    );
    const matchIds = new Set(matches.map((r) => r.id));
    const near = neighbourhood();
    const positions = new Map();
    pack.layers.forEach((layer, i) => {
      const y = 52 + i * 78;
      svg(
        "text",
        { x: 22, y: y - 21, class: "graph-row-label" },
        root,
        layer.title + " · " + layer.record_count,
      );
      svg(
        "path",
        { d: `M20 ${y}H900`, stroke: "#537169", "stroke-opacity": ".18" },
        root,
      );
      if (!visible.has(layer.id)) return;
      const rows = matches.filter((r) => r.layer === layer.id);
      rows.forEach((r, j) =>
        positions.set(r.id, {
          x: 35 + ((j + 0.5) * 840) / rows.length,
          y,
          colour: colours[i],
        }),
      );
    });
    const surroundings = $("surroundings").checked;
    pack.edges.forEach((e) => {
      const a = positions.get(e.source),
        b = positions.get(e.target);
      if (!a || !b) return;
      const lit = near.has(e.source) && near.has(e.target);
      if (!lit && !surroundings) return;
      const path = svg(
        "path",
        {
          d: `M${a.x},${a.y} C${a.x},${(a.y + b.y) / 2} ${b.x},${(a.y + b.y) / 2} ${b.x},${b.y}`,
          fill: "none",
          stroke: lit ? "#d9c49f" : "#77958a",
          "stroke-width": lit ? 1.3 : 0.6,
          opacity: lit ? 0.7 : 0.1,
        },
        root,
      );
      svg("title", {}, path, e.relation.replaceAll("_", " "));
    });
    positions.forEach((p, id) => {
      const record = index.get(id),
        lit = near.has(id);
      const g = svg(
        "g",
        {
          transform: `translate(${p.x},${p.y})`,
          class: "graph-node",
          role: "button",
          tabindex: "0",
          "aria-label": record.title,
          "aria-pressed": String(selected === id),
        },
        root,
      );
      g.addEventListener("click", () => select(id));
      g.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          select(id);
        }
      });
      svg("title", {}, g, record.title);
      svg("circle", { r: 10, fill: "transparent" }, g);
      svg(
        "circle",
        {
          r: selected === id ? 7 : lit ? 4.5 : 2.5,
          fill: p.colour,
          opacity: lit || surroundings ? 1 : 0.22,
        },
        g,
      );
      if (selected === id)
        svg(
          "text",
          { x: 0, y: 24, "text-anchor": "middle", class: "graph-label" },
          g,
          short(record.title, 45),
        );
    });
    $("graph-status").textContent =
      matches.length +
      " of " +
      pack.records.length +
      " records · " +
      positions.size +
      " visible";
    const list = $("record-list");
    list.replaceChildren();
    const rows = matches.filter((r) => r.layer === activeLayer);
    rows.forEach((row) => {
      const b = button("", list, () => select(row.id));
      b.setAttribute("aria-pressed", String(selected === row.id));
      el("small", row.kind.replaceAll("_", " "), b);
      el("span", row.title, b).dir = "auto";
    });
    if (!rows.length)
      el(
        "p",
        activeLayer === "assessment"
          ? "Your interpretation belongs in Build a brief. No assessment is supplied by the source collection."
          : "No matching records in this layer.",
        list,
      );
    if (query && !matchIds.has(selected))
      $("graph-status").textContent +=
        " · Selected record is outside the search results";
  }
  function renderInspector() {
    const target = $("inspector");
    target.replaceChildren();
    const row = index.get(selected);
    if (!row) {
      el("h3", "No records in this collection.", target);
      return;
    }
    el(
      "p",
      pack.layers.find((l) => l.id === row.layer).title +
        " / " +
        row.kind.replaceAll("_", " "),
      target,
      "record-kind",
    );
    el(
      "h3",
      row.kind === "normative_expression"
        ? "A dated normative expression"
        : short(row.title, 95),
      target,
    ).dir = "auto";
    if (row.kind === "normative_expression" || row.title.length > 95)
      el("p", row.title, target, "record-copy").dir = "auto";
    const data = row.data,
      dl = el("dl", undefined, target);
    const info = (key, value) => {
      if (value === null || value === undefined || value === "") return;
      const div = el("div", undefined, dl);
      el("dt", key, div);
      el(
        "dd",
        typeof value === "object" ? JSON.stringify(value) : String(value),
        div,
      );
    };
    info("Review state", row.review_state);
    info("Source statement date", data.temporal_scope?.source_statement_on);
    info("Source verb", data.modality?.source_verb);
    info("Implementation asserted", data.modality?.implementation_asserted);
    info("Human review recorded", data.human_review_recorded);
    info("Publication", data.published_on || data.published_at);
    info("Retrieved", data.retrieved_at);
    info("Definition", data.definition || data.scope_note || data.purpose);
    if (data.qualifications)
      data.qualifications.forEach((v) => el("p", v, target));
    if (data.qualification) el("p", data.qualification, target);
    if (data.questions) data.questions.forEach((v) => el("p", v, target));
    const b = button(
      chosen.has(row.id) ? "Remove from cited brief" : "Add to cited brief",
      target,
      () => {
        chosen.has(row.id) ? chosen.delete(row.id) : chosen.add(row.id);
        renderInspector();
        renderSelection();
      },
    );
    b.className = "primary";
    const refs =
      data.evidence ||
      (row.kind === "document"
        ? [{ document_id: data.id, locator: "Document receipt" }]
        : []);
    refs.forEach((ref) => {
      const doc = documents.get(ref.document_id);
      if (!doc) return;
      const div = el("div", undefined, target, "evidence-item");
      link(doc.title, doc.url, div);
      el("small", ref.locator || "Suggested document-level reading", div);
      el(
        "small",
        "Published: " + (doc.published_on || doc.published_at || "Unknown"),
        div,
      );
      if (ref.original_passage === null)
        el(
          "small",
          "Attributed paraphrase; the original passage is not bundled.",
          div,
        );
    });
    const related = pack.edges.filter(
      (e) => e.source === row.id || e.target === row.id,
    );
    if (related.length) {
      const section = el("div", undefined, target, "related");
      el("h3", "Connected records", section);
      related.forEach((e) => {
        const other = index.get(e.source === row.id ? e.target : e.source);
        button(
          e.relation.replaceAll("_", " ") + " · " + short(other.title, 55),
          section,
          () => select(other.id),
        );
      });
    }
    const detail = el("details", undefined, target);
    el("summary", "Inspect exact record", detail);
    el("pre", JSON.stringify(row, null, 2), detail);
  }
  function renderSelection() {
    const box = $("selection");
    box.replaceChildren();
    if (!chosen.size)
      el(
        "p",
        "Select records in Explore layers, then add them to your brief.",
        box,
      );
    chosen.forEach((id) => {
      const row = index.get(id),
        div = el("div", short(row.title, 140), box, "selected-material");
      button("Remove", div, () => {
        chosen.delete(id);
        renderSelection();
        renderInspector();
      });
    });
  }
  function render() {
    renderLayers();
    renderGraph();
    renderInspector();
    renderSelection();
  }
  function download(name, value, type) {
    const url = URL.createObjectURL(new Blob([value], { type }));
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function exported() {
    return {
      ...pack,
      question,
      assessment: {
        ...notes,
        selected_record_ids: [...chosen],
        authorship:
          "Visitor-entered analysis; source review states are unchanged.",
      },
      exported_at: new Date().toISOString(),
    };
  }
  $("question").value = question;
  $("question").addEventListener("input", (e) => {
    question = e.target.value;
  });
  Object.keys(notes).forEach((key) =>
    $(key).addEventListener("input", (e) => {
      notes[key] = e.target.value;
    }),
  );
  $("download-context").addEventListener("click", () => {
    if (!question.trim()) {
      $("export-status").textContent = "Add a research question first.";
      return;
    }
    download(
      "policy-context.json",
      JSON.stringify(exported(), null, 2) + "\n",
      "application/json",
    );
    $("export-status").textContent =
      "Full context exported, including all layers, qualifications and your notes.";
  });
  $("download-brief").addEventListener("click", () => {
    if (!question.trim() || !chosen.size) {
      $("export-status").textContent =
        "Add a research question and at least one source-linked record.";
      return;
    }
    const out = ["# " + question, "", "## Selected source material", ""];
    chosen.forEach((id) => {
      const row = index.get(id);
      out.push(
        "### " + row.title,
        "",
        "Record: " +
          id +
          " · " +
          row.kind +
          " · Review: " +
          (row.review_state || "Not a review decision"),
        "",
      );
      (row.data.evidence || []).forEach((ref) => {
        const doc = documents.get(ref.document_id);
        if (doc)
          out.push(
            "- " +
              doc.title +
              " | " +
              doc.url +
              " | " +
              (ref.locator || "Document-level reference"),
          );
      });
      if (row.kind === "document") out.push("- Source: " + row.data.url);
      if (row.data.qualification)
        out.push("- Qualification: " + row.data.qualification);
      (row.data.qualifications || []).forEach((q) =>
        out.push("- Qualification: " + q),
      );
      if (row.data.temporal_scope)
        out.push(
          "- Temporal scope: " + JSON.stringify(row.data.temporal_scope),
        );
      out.push("");
    });
    [
      ["interpretation", "Analyst interpretation"],
      ["alternative", "Alternative explanation"],
      ["option", "Policy option to examine"],
      ["gaps", "Missing evidence"],
    ].forEach(([key, title]) =>
      out.push("## " + title, "", notes[key] || "[Not supplied]", ""),
    );
    out.push("## Use rules", "", ...pack.use_rules.map((rule) => "- " + rule));
    download("source-linked-brief.md", out.join("\n") + "\n", "text/markdown");
    $("export-status").textContent =
      "Cited source material and your separate assessment exported.";
  });
  document.querySelectorAll("[data-view]").forEach((b) =>
    b.addEventListener("click", () => {
      document
        .querySelectorAll("[data-view]")
        .forEach((n) => n.setAttribute("aria-pressed", String(n === b)));
      ["layers", "brief", "method"].forEach(
        (v) => ($("view-" + v).hidden = b.dataset.view !== v),
      );
      $("workspace").focus({ preventScroll: true });
    }),
  );
  $("search").addEventListener("input", renderGraph);
  $("surroundings").addEventListener("change", renderGraph);
  $("reset-view").addEventListener("click", () => {
    $("search").value = "";
    visible = new Set(pack.layers.map((l) => l.id));
    $("surroundings").checked = false;
    render();
  });
  $("collection").textContent = pack.country.name + " collection";
  $("edition").textContent = "Seven-layer research workspace";
  $("scope").textContent =
    pack.country.status === "empty_framework"
      ? "Empty country framework. No researched political records are supplied."
      : "A source-qualified research snapshot. Normative objectives retain their original source dates and review status.";
  const checked = pack.records
    .filter((r) => r.kind === "document")
    .map((r) => r.data.checked_on)
    .filter(Boolean)
    .sort()
    .at(-1);
  $("snapshot").textContent =
    "Source checks: " +
    (checked || "No checked documents") +
    " · " +
    pack.records.length +
    " records";
  pack.layers.forEach((l) => {
    const div = el("div", undefined, $("method-layers"), "method-layer");
    el("h3", l.title, div);
    el("p", l.description, div);
  });
  pack.use_rules.forEach((rule) => el("li", rule, $("rules")));
  render();
})();
