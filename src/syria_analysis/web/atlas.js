/* The atlas deliberately uses DOM text nodes, not HTML interpolation of source records. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const labels = {
    official_reporting: "Official reporting",
    international_wire: "International wires",
    syrian_local_media: "Syrian & regional media",
    state_media: "State media",
    advocacy_monitoring: "Monitoring & advocacy",
    think_tank: "Research institutes",
    analyst: "Named analysts",
    regional_media: "Regional media",
  };
  const shortNames = {
    "unhcr-syria": "UNHCR Syria",
    "ose-syria": "UN Special Envoy",
    "coi-syria": "UN Syria Commission",
    "iom-dtm-syria": "IOM DTM Syria",
    "associated-press": "Associated Press",
    "carnegie-middle-east": "Carnegie Middle East",
    "crisis-group": "Crisis Group",
    "un-security-council": "UN Security Council",
    "un-syria": "United Nations in Syria",
    mei: "Middle East Institute",
    sana: "SANA",
    afp: "AFP",
  };
  let data;
  try {
    data = JSON.parse($("atlas-data").textContent);
  } catch {
    const p = document.createElement("p");
    p.className = "fatal";
    p.setAttribute("role", "alert");
    p.textContent =
      "The embedded research data could not be read. Rebuild the atlas with syria-analysis build-atlas.";
    $("workspace").replaceChildren(p);
    return;
  }
  const sources = new Map(data.sources.map((s) => [s.id, s]));
  const documents = new Map(data.documents.map((d) => [d.id, d]));
  const topics = new Map(data.context.map((t) => [t.id, t]));
  const network = data.relationships || { entities: [], relationships: [] };
  const relations = new Map(network.relationships.map((r) => [r.id, r]));
  const entities = new Map(
    [...data.sources, ...network.entities].map((s) => [s.id, s]),
  );
  const state = {
    selected:
      data.sources.find((s) => s.id === "syria-direct")?.id ||
      data.sources[0]?.id,
    kind: "source",
    list: false,
    compare: new Set(),
  };
  const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const append = (parent, ...children) => {
    parent.append(...children.filter(Boolean));
    return parent;
  };
  const link = (label, url) => {
    const a = el("a", label);
    try {
      const u = new URL(url);
      if (!["https:", "http:"].includes(u.protocol)) return el("span", label);
      a.href = u.href;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    } catch {
      return el("span", label);
    }
    return a;
  };
  const list = (rows) => {
    const ul = el("ul");
    for (const row of rows || []) ul.append(el("li", row));
    return ul;
  };
  const date = (value) => (value ? String(value).slice(0, 10) : "Not supplied");
  const title = (value) => String(value || "").replaceAll("_", " ");
  const download = (name, text, type) => {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const a = el("a");
    a.href = url;
    a.download = name;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  function option(select, value, label) {
    const o = el("option", label);
    o.value = value;
    select.append(o);
  }
  function selectRecord(id, kind = "source") {
    state.selected = id;
    state.kind = kind;
    renderGraph();
    renderDirectory();
    renderInspector();
  }
  function matches() {
    const query = $("search").value.trim().toLocaleLowerCase();
    const category = $("category").value;
    const language = $("language").value;
    const topic = topics.get($("topic").value);
    return data.sources.filter(
      (s) =>
        (!category || s.type === category) &&
        (!language || s.languages.includes(language)) &&
        (!topic || topic.source_ids.includes(s.id)) &&
        (!query ||
          JSON.stringify([
            s.name,
            s.description,
            s.scope,
            s.languages,
            s.ownership_or_perspective,
            s.strengths,
            s.limits,
            s.catalogue_review,
          ])
            .toLocaleLowerCase()
            .includes(query)),
    );
  }
  function render() {
    const rows = matches();
    if (state.kind === "source" && !rows.some((s) => s.id === state.selected)) {
      state.selected = rows[0]?.id;
      state.kind = "source";
    }
    $("result-count").textContent =
      `${rows.length} of ${data.sources.length} source entities shown`;
    $("empty").hidden = rows.length > 0;
    $("network-panel").hidden = state.list || rows.length === 0;
    $("directory").hidden = !state.list || rows.length === 0;
    renderGraph();
    renderDirectory();
    renderInspector();
    renderCoverage(rows);
  }
  const svgNS = "http://www.w3.org/2000/svg";
  function svg(tag, attrs = {}, text) {
    const node = document.createElementNS(svgNS, tag);
    for (const [key, value] of Object.entries(attrs))
      node.setAttribute(key, value);
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function wrap(text, max = 24) {
    const words = text.split(" ");
    const lines = [""];
    for (const word of words) {
      const i = lines.length - 1;
      if ((lines[i] + " " + word).trim().length > max && lines[i])
        lines.push(word);
      else lines[i] = (lines[i] + " " + word).trim();
    }
    return lines;
  }
  function renderGraph() {
    if ($("graph-mode").value === "relationships") {
      renderRelations();
      return;
    }
    $("graph-heading").textContent = "Sources & research themes";
    $("graph-legend").textContent =
      "□ Source entity   ○ Research theme   Line: editorial suggested reading";
    $("graph-note").textContent =
      "Positions are layout only. Node size is constant; lines are not reliability, influence or funding scores. Sources without a theme link remain visible.";
    const root = $("network");
    root.setAttribute("aria-label", "Source to research theme network");
    const rows = matches();
    const visible = new Set(rows.map((s) => s.id));
    const midpoint = Math.ceil(rows.length / 2);
    const points = new Map();
    const rowHeight = rows.length > 20 ? 57 : 65;
    const sourceHeight =
      Math.max(midpoint, rows.length - midpoint) * rowHeight + 80;
    const height = Math.max(740, sourceHeight);
    root.setAttribute("viewBox", `0 0 1000 ${height}`);
    root.replaceChildren();
    root.append(
      svg("text", { x: 35, y: 22, class: "graph-column" }, "SOURCE ENTITIES"),
      svg("text", { x: 445, y: 22, class: "graph-column" }, "RESEARCH THEMES"),
      svg("text", { x: 765, y: 22, class: "graph-column" }, "SOURCE ENTITIES"),
    );
    rows.forEach((s, i) =>
      points.set(s.id, {
        x: i < midpoint ? 145 : 855,
        y: 62 + (i % midpoint) * rowHeight,
      }),
    );
    data.context.forEach((t, i) =>
      points.set(t.id, {
        x: 500,
        y: 70 + i * ((height - 145) / Math.max(1, data.context.length - 1)),
      }),
    );
    const activeTopic =
      state.kind === "context" ? topics.get(state.selected) : null;
    const activeSource = state.kind === "source" ? state.selected : null;
    for (const t of data.context) {
      for (const sid of t.source_ids) {
        if (!visible.has(sid)) continue;
        const a = points.get(sid),
          b = points.get(t.id);
        const highlighted = activeTopic?.id === t.id || activeSource === sid;
        const direction = a.x < 500 ? 1 : -1;
        const line = svg("path", {
          d: `M ${a.x + direction * 105} ${a.y} C ${a.x + direction * 220} ${a.y}, ${b.x - direction * 160} ${b.y}, ${b.x - direction * 126} ${b.y}`,
          class: `graph-edge${highlighted ? " highlight" : ""}`,
        });
        line.append(
          svg(
            "title",
            {},
            `${t.title} → ${sources.get(sid).name}: suggested reading source; editorial research grouping, not affiliation`,
          ),
        );
        root.append(line);
      }
    }
    function node(id, kind, caption, sub) {
      const p = points.get(id);
      const selected = state.selected === id;
      const related = kind === "source" && activeTopic?.source_ids.includes(id);
      const g = svg("g", {
        class: `graph-node${selected ? " selected" : ""}${related ? " related" : ""}`,
        transform: `translate(${p.x},${p.y})`,
        tabindex: "0",
        role: "button",
        "aria-label": `${kind === "context" ? "Research theme" : "Source"}: ${caption}`,
        "aria-pressed": String(selected),
      });
      g.append(
        svg("rect", {
          x: kind === "context" ? -126 : -105,
          y: -24,
          width: kind === "context" ? 252 : 210,
          height: 48,
          rx: kind === "context" ? 24 : 3,
        }),
      );
      const lines = wrap(caption, kind === "context" ? 34 : 26);
      g.append(
        svg(
          "text",
          { "text-anchor": "middle", y: lines.length > 1 ? -4 : -2 },
          lines[0],
        ),
      );
      if (lines.length > 1)
        g.append(
          svg(
            "text",
            { "text-anchor": "middle", y: 11 },
            lines.slice(1).join(" "),
          ),
        );
      else
        g.append(
          svg("text", { "text-anchor": "middle", y: 13, class: "kind" }, sub),
        );
      g.append(svg("title", {}, caption));
      g.addEventListener("click", () => selectRecord(id, kind));
      g.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          selectRecord(id, kind);
          const replacement = [...root.querySelectorAll("[role=button]")].find(
            (n) =>
              n.getAttribute("aria-label") === g.getAttribute("aria-label"),
          );
          replacement?.focus();
        }
      });
      root.append(g);
    }
    for (const s of rows)
      node(
        s.id,
        "source",
        shortNames[s.id] || s.name,
        labels[s.type] || title(s.type),
      );
    for (const t of data.context)
      node(t.id, "context", t.title, "Suggested reading connections");
  }
  function renderRelations() {
    const root = $("network");
    root.setAttribute(
      "aria-label",
      "Documented institutional relationships network",
    );
    root.replaceChildren();
    const visible = new Set(matches().map((s) => s.id));
    const rows = network.relationships.filter((r) => visible.has(r.source));
    const height = Math.max(400, rows.length * 115 + 70);
    root.setAttribute("viewBox", `0 0 1000 ${height}`);
    $("graph-heading").textContent = "Documented institutional relationships";
    $("graph-legend").textContent =
      "□ Source / institution   Solid: organizational relation   Dashed: operating location   Select a label for evidence";
    $("graph-note").textContent =
      "No edge means no relationship documented here, not proof of independence. Profile checks establish what was described on that date. Unknown start and end dates remain unknown. Layout is not geography or influence.";
    if (!rows.length) {
      root.append(
        svg(
          "text",
          { x: 50, y: 90, class: "graph-column" },
          "No documented relationships for the current source filters.",
        ),
      );
      return;
    }
    function choose(id, kind) {
      state.selected = id;
      state.kind = kind;
      renderRelations();
      renderInspector();
    }
    function activate(g, fn) {
      g.addEventListener("click", fn);
      g.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          fn();
          const label = g.getAttribute("aria-label");
          [...root.querySelectorAll("[role=button]")]
            .find((n) => n.getAttribute("aria-label") === label)
            ?.focus();
        }
      });
    }
    rows.forEach((r, i) => {
      const y = 65 + i * 115;
      const selected = state.selected === r.id;
      root.append(
        svg("path", {
          d: `M 255 ${y} L 745 ${y}`,
          class: `graph-edge${selected ? " highlight" : ""}${r.type === "operates_in" ? " location-edge" : ""}`,
        }),
      );
      for (const [id, x] of [
        [r.source, 140],
        [r.target, 860],
      ]) {
        const e = entities.get(id);
        const g = svg("g", {
          transform: `translate(${x},${y})`,
          class: `graph-node${state.selected === id ? " selected" : ""}`,
          tabindex: "0",
          role: "button",
          "aria-label": `Entity: ${e.name}`,
        });
        g.append(
          svg("rect", { x: -115, y: -27, width: 230, height: 54, rx: 3 }),
        );
        const lines = wrap(shortNames[id] || e.name, 30);
        if (e.type === "location" && lines.length === 1)
          lines.push("Location / not political control");
        lines.slice(0, 2).forEach((t, j) =>
          g.append(
            svg(
              "text",
              {
                "text-anchor": "middle",
                y: lines.length > 1 ? -4 + j * 16 : 4,
              },
              t,
            ),
          ),
        );
        activate(g, () => choose(id, sources.has(id) ? "source" : "entity"));
        root.append(g);
      }
      const label = svg("g", {
        transform: `translate(500,${y})`,
        class: `graph-node${selected ? " selected" : ""}`,
        tabindex: "0",
        role: "button",
        "aria-label": `Relationship evidence: ${r.label}`,
      });
      label.append(
        svg("rect", { x: -168, y: -24, width: 336, height: 48, rx: 3 }),
        svg("text", { "text-anchor": "middle", y: -2 }, r.label),
        svg(
          "text",
          { "text-anchor": "middle", y: 14, class: "kind" },
          `Profile checked ${r.checked_on}`,
        ),
      );
      activate(label, () => choose(r.id, "relationship"));
      root.append(label);
    });
  }
  function renderDirectory() {
    const root = $("directory");
    root.replaceChildren();
    for (const s of matches()) {
      const row = el(
        "article",
        undefined,
        `directory-row${state.selected === s.id ? " selected" : ""}`,
      );
      const head = el("div");
      const b = el("button", s.name);
      b.setAttribute("aria-pressed", String(state.selected === s.id));
      b.addEventListener("click", () => selectRecord(s.id));
      append(head, b, el("p", `${labels[s.type]} · ${s.languages.join(", ")}`));
      append(row, head, el("p", s.description));
      root.append(row);
    }
  }
  function heading(root, label) {
    root.append(el("h4", label));
  }
  function renderInspector() {
    const root = $("inspector");
    root.replaceChildren();
    if (!state.selected) {
      root.append(
        el(
          "p",
          "No source selected. Clear the filters to restore the register.",
        ),
      );
      return;
    }
    if (state.kind === "relationship") {
      const r = relations.get(state.selected);
      append(
        root,
        el("p", "Documented relationship", "record-type"),
        el("h3", r.label),
        el(
          "p",
          `${entities.get(r.source).name} → ${entities.get(r.target).name}`,
          "profile-description",
        ),
        el("p", r.statement),
      );
      heading(root, "Evidence basis");
      root.append(el("p", title(r.basis)), el("p", r.caveat, "qualifier"));
      heading(root, "Supporting record");
      for (const e of r.evidence)
        root.append(
          link("Open supporting profile", e.url),
          el("p", `${e.locator} · Checked ${e.checked_on}`, "record-meta"),
        );
      heading(root, "Dates & scope");
      root.append(
        el(
          "p",
          `Profile checked: ${r.checked_on}. Start: ${r.valid_from || "unknown"}. End: ${r.valid_to || "unknown"}.`,
        ),
        el(
          "p",
          "No independent corporate audit or article-level factual verification is implied. A check date is not a publication date or a guarantee of continuing status.",
          "record-meta",
        ),
      );
      return;
    }
    if (state.kind === "entity") {
      const entity = entities.get(state.selected);
      append(
        root,
        el("p", title(entity.type), "record-type"),
        el("h3", entity.name),
        el(
          "p",
          "This entity appears because an explicitly cited profile describes a relationship. No broader political, funding or control ties are inferred.",
        ),
      );
      heading(root, "Documented links");
      for (const r of network.relationships.filter(
        (r) => r.source === entity.id || r.target === entity.id,
      )) {
        const b = el("button", r.label);
        b.addEventListener("click", () => selectRecord(r.id, "relationship"));
        root.append(b, el("p", r.statement));
      }
      return;
    }
    if (state.kind === "context") {
      const t = topics.get(state.selected);
      append(
        root,
        el("p", "Research theme / editorial grouping", "record-type"),
        el("h3", t.title),
        el("p", title(t.record_type), "record-meta"),
        el("p", t.summary, "profile-description"),
      );
      heading(root, "Research questions");
      root.append(list(t.questions));
      heading(root, "Limits");
      root.append(list(t.limits));
      heading(root, "Suggested reading connections");
      for (const sid of t.source_ids) {
        const s = sources.get(sid);
        if (!s) continue;
        const b = el("button", s.name);
        b.addEventListener("click", () => selectRecord(sid));
        root.append(
          b,
          el(
            "p",
            "Relation: suggested_reading_source. This is an editorial choice, not a documented affiliation.",
            "record-meta",
          ),
        );
      }
      heading(root, "Document evidence");
      for (const ref of t.evidence || []) {
        const d = documents.get(ref.document_id);
        if (d)
          root.append(
            link(d.title, d.url),
            el(
              "p",
              `${ref.locator || "Document reference"} · Published ${date(d.published_at || d.published_on)}`,
              "record-meta",
            ),
          );
      }
      root.append(
        el("p", `Record last checked: ${date(t.checked_on)}`, "record-meta"),
      );
      return;
    }
    const s = sources.get(state.selected);
    if (!s) return;
    append(
      root,
      el("p", labels[s.type] || title(s.type), "record-type"),
      el("h3", s.name),
      el(
        "p",
        `${s.languages.join(" / ")} · Checked ${date(s.checked_on)}`,
        "record-meta",
      ),
      el("p", s.description, "profile-description"),
    );
    const a = link("Visit source", s.reading_url || s.url);
    a.className = "source-link";
    root.append(a);
    heading(root, "Remit & subject coverage");
    root.append(
      el("p", s.scope.join(" · ")),
      el(
        "p",
        "Remit is not a claim of continuous on-the-ground access.",
        "record-meta",
      ),
    );
    heading(root, "Ownership, funding & stated perspective");
    root.append(
      el("p", s.ownership_or_perspective.summary),
      el("p", s.ownership_or_perspective.attribution, "record-meta"),
    );
    if (s.ownership_update_note)
      root.append(el("p", s.ownership_update_note, "qualifier"));
    if (s.catalogue_review) {
      const review = s.catalogue_review;
      const reviewRoot = el("details", undefined, "review-details");
      reviewRoot.append(
        el("summary", "Funding, corrections, access & review evidence"),
      );
      root.append(reviewRoot);
      reviewRoot.append(
        el("p", review.ownership_funding.summary),
        el("p", review.ownership_funding.caveat, "qualifier"),
      );
      const fields = [
        ["Transparency", review.qualifications.transparency],
        ["Corrections policy", review.qualifications.corrections],
        ["Access", review.qualifications.access],
        ["Evidence status", title(review.evidence_status)],
        ["Language scope", review.language_scope],
        ["Coverage basis", review.geography_basis],
      ];
      for (const [label, value] of fields)
        reviewRoot.append(el("h4", label), el("p", value));
      reviewRoot.append(
        list(review.qualifications.caveats),
        el("p", review.qualification_basis, "record-meta"),
      );
      heading(reviewRoot, "Evidence for the additional review");
      for (const e of review.evidence)
        reviewRoot.append(
          link(e.title, e.url),
          el(
            "p",
            `${title(e.basis)} · Reviewed ${date(e.reviewedAt)}${e.publishedAt ? " · Published " + date(e.publishedAt) : " · Page publication date not supplied"}`,
            "record-meta",
          ),
        );
      reviewRoot.append(
        el(
          "p",
          `Catalogue ${s.catalogue_provenance.library_file_id}, version ${s.catalogue_provenance.library_version}. Read through the text interface; organizational review, not accuracy certification.`,
          "record-meta",
        ),
        el(
          "p",
          "Field evidence is a relevant-source navigation index, not certified field-level corroboration.",
          "record-meta",
        ),
      );
    }
    heading(root, "Useful for");
    root.append(list(s.strengths));
    heading(root, "Read with these limits");
    root.append(list(s.limits));
    if (s.access_note) root.append(el("p", s.access_note, "qualifier"));
    heading(root, "Profile evidence");
    for (const e of s.evidence) {
      const item = el("div", undefined, "evidence-item");
      append(
        item,
        link(e.title || "Original profile evidence", e.url),
        el("p", e.basis),
        el(
          "p",
          `${title(e.kind)} · ${title(e.access)} · Checked ${date(e.checked_on)}`,
          "record-meta",
        ),
      );
      root.append(item);
    }
    heading(root, "Collection status");
    root.append(
      el(
        "p",
        s.feeds.length
          ? `${s.feeds.length} verified endpoint(s). No automatic refresh.`
          : s.feed_status || "No verified endpoint registered.",
      ),
    );
    const count = data.documents.filter((d) => d.source_id === s.id).length;
    root.append(
      el(
        "p",
        `${count} document reference(s) in this corpus. Profile verification is not article verification.`,
        "record-meta",
      ),
    );
    const b = el(
      "button",
      state.compare.has(s.id)
        ? "Remove from comparison"
        : "Add to comparison (up to 3)",
      "compare-toggle",
    );
    b.addEventListener("click", () => toggleCompare(s.id));
    b.disabled = !state.compare.has(s.id) && state.compare.size >= 3;
    root.append(b);
  }
  function renderCoverage(rows) {
    const root = $("coverage-bars");
    root.replaceChildren();
    for (const [id, label] of Object.entries(labels)) {
      const n = rows.filter((s) => s.type === id).length;
      const row = el("div", undefined, "bar-row");
      const track = el("div", undefined, "bar-track");
      const fill = el("div", undefined, "bar-fill");
      fill.style.width = `${rows.length ? (n / rows.length) * 100 : 0}%`;
      track.append(fill);
      append(row, el("span", label), track, el("strong", String(n)));
      root.append(row);
    }
  }
  function renderEvidence() {
    for (const claim of data.claims) {
      const article = el("article", undefined, "claim");
      const meta = el("div", undefined, "record-meta");
      append(meta, el("p", title(claim.review_state)), el("small", claim.id));
      const body = el("div");
      append(
        body,
        el("h3", claim.statement),
        el("p", claim.qualification, "qualifier"),
        el("p", `Geographic scope: ${claim.geographic_scope}`, "record-meta"),
      );
      const refs = el("ul", undefined, "refs");
      for (const ref of claim.evidence) {
        const d = documents.get(ref.document_id);
        if (!d) continue;
        const li = el("li");
        append(
          li,
          link(d.title, d.url),
          el(
            "p",
            `Publisher: ${d.publisher} · Published: ${date(d.published_at || d.published_on)} · Retrieved: ${date(d.retrieved_at)}`,
            "record-meta",
          ),
          el(
            "p",
            `Reporting period: ${d.reporting_period ? JSON.stringify(d.reporting_period) : "not supplied"} · Locator: ${ref.locator || "document level"}`,
            "record-meta",
          ),
          el("small", d.id),
        );
        refs.append(li);
      }
      body.append(refs);
      append(article, meta, body);
      $("claims").append(article);
    }
  }
  function renderQueue() {
    const rows = data.documents
      .filter((d) => d.review_state === "unreviewed_reference")
      .sort((a, b) =>
        (b.published_at || "").localeCompare(a.published_at || ""),
      );
    if (!rows.length) {
      $("queue").append(el("p", "No unreviewed references in this snapshot."));
      return;
    }
    for (const d of rows) {
      const row = el("article", undefined, "queue-item");
      const meta = el("div");
      append(
        meta,
        el("p", d.publisher),
        el(
          "p",
          `Published ${date(d.published_at || d.published_on)}`,
          "record-meta",
        ),
      );
      const body = el("div");
      const h = el("h3");
      h.append(link(d.title, d.url));
      append(
        body,
        h,
        el(
          "p",
          `Retrieved ${date(d.retrieved_at)} · ${title(d.retrieval_method)} · Unreviewed reference`,
        ),
        el("p", "No article text collected; no event location inferred."),
      );
      append(row, meta, body);
      $("queue").append(row);
    }
  }
  function toggleCompare(id) {
    if (state.compare.has(id)) state.compare.delete(id);
    else if (state.compare.size < 3) state.compare.add(id);
    renderInspector();
    renderComparison();
  }
  function renderComparison() {
    const root = $("comparison");
    root.replaceChildren();
    if (!state.compare.size) {
      root.append(
        el(
          "p",
          "No sources selected for comparison. Open a source in the atlas and choose “Add to comparison”.",
          "qualifier",
        ),
      );
      return;
    }
    const grid = el("div", undefined, "comparison");
    for (const id of state.compare) {
      const s = sources.get(id);
      const card = el("article", undefined, "compare-card");
      append(
        card,
        el("h3", s.name),
        el("p", labels[s.type], "record-meta"),
        el("p", s.ownership_or_perspective.summary),
        el("h4", "Useful for"),
        list(s.strengths),
        el("h4", "Limits"),
        list(s.limits),
        el("p", `Checked ${date(s.checked_on)}`, "record-meta"),
      );
      const b = el("button", `Remove ${s.name}`);
      if (s.catalogue_review) {
        card.append(
          el("h4", "Funding & corrections review"),
          el("p", s.catalogue_review.ownership_funding.summary),
          el("p", s.catalogue_review.ownership_funding.caveat),
          el("p", s.catalogue_review.qualifications.corrections),
        );
      }
      b.addEventListener("click", () => toggleCompare(id));
      card.append(b);
      grid.append(card);
    }
    root.append(grid);
  }
  const checked = [...new Set(data.sources.map((s) => s.checked_on))].sort();
  $("checked").textContent =
    `Profile reference dates ${checked.length === 1 ? checked[0] : checked[0] + " to " + checked.at(-1)}`;
  $("build-date").textContent =
    `Built ${date(data.built_at)} · Offline snapshot`;
  for (const [n, label] of [
    [data.sources.length, "source entities"],
    [data.documents.length, "document references"],
    [data.claims.length, "attributed paraphrases"],
    [data.context.length, "research themes"],
  ]) {
    const box = el("div", undefined, "metric");
    append(box, el("strong", String(n)), el("span", label));
    $("metrics").append(box);
  }
  for (const [id, label] of Object.entries(labels))
    option($("category"), id, label);
  for (const language of [
    ...new Set(data.sources.flatMap((s) => s.languages)),
  ].sort())
    option($("language"), language, language);
  for (const topic of data.context) option($("topic"), topic.id, topic.title);
  $("filters").addEventListener("submit", (e) => e.preventDefault());
  $("search").addEventListener("input", render);
  for (const id of ["category", "language", "topic"])
    $(id).addEventListener("change", render);
  $("filters").addEventListener("reset", () => setTimeout(render, 0));
  $("network-view").addEventListener("click", () => {
    state.list = false;
    $("network-view").setAttribute("aria-pressed", "true");
    $("list-view").setAttribute("aria-pressed", "false");
    render();
  });
  $("list-view").addEventListener("click", () => {
    state.list = true;
    $("list-view").setAttribute("aria-pressed", "true");
    $("network-view").setAttribute("aria-pressed", "false");
    render();
  });
  $("graph-mode").addEventListener("change", () => {
    state.kind = "source";
    state.selected = matches()[0]?.id;
    render();
  });
  document.querySelectorAll("[data-view]").forEach((b) =>
    b.addEventListener("click", () => {
      document
        .querySelectorAll("[data-view]")
        .forEach((n) => n.removeAttribute("aria-current"));
      b.setAttribute("aria-current", "page");
      document
        .querySelectorAll(".view")
        .forEach((n) => (n.hidden = n.id !== `view-${b.dataset.view}`));
    }),
  );
  $("theme").addEventListener("click", () => {
    const dark = document.body.classList.toggle("dark");
    $("theme").textContent = dark ? "Light theme" : "Dark theme";
    $("theme").setAttribute(
      "aria-label",
      dark ? "Switch to light theme" : "Switch to dark theme",
    );
  });
  $("download-data").addEventListener("click", () => {
    const selected = matches();
    const ids = new Set(selected.map((s) => s.id));
    const edges = network.relationships.filter((r) => ids.has(r.source));
    const targets = new Set(edges.map((r) => r.target));
    download(
      "syria-source-register.json",
      JSON.stringify(
        {
          built_at: data.built_at,
          scope: "Curated research snapshot; not comprehensive or live",
          filters: {
            query: $("search").value,
            role: $("category").value,
            language: $("language").value,
            theme: $("topic").value,
          },
          sources: selected,
          related_sources: data.sources.filter(
            (s) => targets.has(s.id) && !ids.has(s.id),
          ),
          relationships: {
            ...network,
            entities: network.entities.filter((e) => targets.has(e.id)),
            relationships: edges,
          },
          export_note:
            "The sources array matches the current filters. Related institutional source profiles are included separately to preserve relationship endpoints. For full context and document data use the repository exports.",
        },
        null,
        2,
      ),
      "application/json",
    );
  });
  $("worksheet").addEventListener("submit", (e) => {
    e.preventDefault();
    if (!$("question").value.trim()) {
      $("worksheet-status").textContent =
        "Add a research question before downloading.";
      $("question").focus();
      return;
    }
    const selected = [...state.compare].map((id) => sources.get(id));
    const lines = [
      `# Research brief: ${$("question").value.trim()}`,
      "",
      `Prepared ${new Date().toISOString()}`,
      "",
      "## Scope",
      "Curated public-source snapshot. Analyst text below is user-entered and has not been independently verified.",
      "",
      "## Source-supported record",
      $("record").value || "[Not supplied]",
      "",
      "## Analyst assessment",
      $("assessment").value || "[Not supplied]",
      "",
      "## Alternative explanations and information gaps",
      $("gaps").value || "[Not supplied]",
      "",
      "## Selected source profiles (not independent corroboration)",
    ];
    for (const s of selected) {
      lines.push(
        "",
        `### ${s.name}`,
        `Role: ${labels[s.type]}`,
        `Profile checked: ${s.checked_on}`,
        s.url,
        s.ownership_or_perspective.summary,
        ...s.limits.map((t) => `- Limit: ${t}`),
        ...s.evidence.map(
          (e) => `- Profile evidence: ${e.url} (${e.checked_on})`,
        ),
      );
      if (s.catalogue_review)
        lines.push(
          `Additional funding review: ${s.catalogue_review.ownership_funding.summary}`,
          `Qualification: ${s.catalogue_review.ownership_funding.caveat}`,
          `Corrections: ${s.catalogue_review.qualifications.corrections}`,
          `Review input: ${s.catalogue_provenance.library_file_id}, version ${s.catalogue_provenance.library_version}`,
        );
    }
    if (!selected.length) lines.push("[No source profiles selected]");
    download(
      "syria-research-brief.md",
      lines.join("\n") + "\n",
      "text/markdown",
    );
    $("worksheet-status").textContent =
      "Brief downloaded. Draft text remains here until the page is reloaded.";
  });
  renderEvidence();
  renderQueue();
  renderComparison();
  render();
})();
