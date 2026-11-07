/* Plain DOM rendering of validated build-time data. Source material is text only. */
"use strict";

const get = (id) => document.getElementById(id);
function el(tag, text, parent, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (className) node.className = className;
  if (parent) parent.append(node);
  return node;
}
function link(url, text, parent) {
  const node = el("a", text, parent);
  node.href = url;
  node.target = "_blank";
  node.rel = "noopener noreferrer";
  return node;
}
function dateLabel(day) {
  return day ? new Intl.DateTimeFormat("en", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(day + "T12:00:00Z")) : "Not separately stated";
}
function download(value, filename) {
  const blob = new Blob([JSON.stringify(value, null, 2) + "\n"], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function status(message = "Source-checked drafts · Human review pending.") {
  get("study-status").textContent = message;
}

try {
  const bundle = JSON.parse(get("political-study-data").textContent);
  const study = bundle.study;
  const records = study.political.developments;
  const labels = { adoption: "Adoption", meeting: "Reported briefing", announced_programme: "Programme announcement" };
  let active = records[0].id;

  function showAct(id) {
    const record = records.find((item) => item.id === id);
    const ref = record.evidence[0];
    const source = study.political.sources.find((item) => item.id === ref.source_id);
    const quote = source.excerpts.find((item) => item.id === ref.excerpt_id);
    active = id;
    for (const button of get("act-choices").querySelectorAll("button")) button.setAttribute("aria-pressed", String(button.dataset.recordId === id));
    const target = get("act-detail");
    target.replaceChildren();
    const detail = el("div", null, target);
    el("h3", record.title, detail);
    el("p", record.statement, detail, "statement");
    const fields = el("dl", null, detail, "act-fields");
    for (const [label, value] of [
      ["Actor", record.structured_act.actor], ["Act", record.structured_act.act],
      ["Event date", dateLabel(record.event_time.start)], ["Source published", dateLabel(source.published_on)],
      ["Retrieved", dateLabel(source.retrieved_on)], ["Policy objectives implemented", "Not established by this record"],
    ]) {
      const row = el("div", null, fields); el("dt", label, row); el("dd", value, row);
    }
    const notes = el("details", null, detail, "date-basis");
    el("summary", "Date basis & qualifications", notes);
    el("p", record.event_time.basis, notes);
    const list = el("ul", null, notes);
    for (const item of record.qualifications) el("li", item, list);
    const excerpt = el("div", null, target, "source-excerpt");
    el("span", source.publisher + " · " + source.source_kind.replaceAll("_", " "), excerpt);
    el("blockquote", quote.text, excerpt);
    el("p", quote.locator, excerpt, "locator");
    link(source.url, "Read the source ↗", excerpt);
    get("download-act").disabled = false;
    status();
  }
  for (const record of records) {
    const button = el("button", null, get("act-choices"));
    button.type = "button";
    button.dataset.recordId = record.id;
    button.setAttribute("aria-pressed", String(record.id === active));
    el("span", labels[record.development_kind] || record.development_kind, button);
    el("span", record.title, button);
    button.addEventListener("click", () => showAct(record.id));
  }

  get("comparison-question").textContent = study.media.question;
  for (const source of study.media.sources) {
    const article = el("article", null, get("media-pair"));
    const meta = el("div", null, article, "media-meta");
    el("span", source.publisher, meta);
    el("span", (source.source_kind === "analysis" ? "Analysis" : "News report") + " · " + dateLabel(source.published_on), meta);
    el("h3", source.title, article);
    el("p", source.byline, article, "byline");
    for (const quote of source.excerpts.filter((item) => !item.id.endsWith("-headline"))) {
      const figure = el("figure", null, article);
      el("blockquote", quote.text, figure);
      el("figcaption", quote.locator, figure);
    }
    link(source.url, "Read the original ↗", article);
  }
  for (const item of study.media.annotations) {
    const note = el("div", null, get("comparison-annotations"), "annotation");
    el("span", item.kind === "analyst_interpretation" ? "Analyst interpretation" : "Observable textual feature", note);
    el("p", item.statement, note);
  }
  el("p", study.media.lineage.note, get("comparison-annotations"), "lineage-note");
  const primary = study.political.sources.find((source) => source.id === study.media.lineage.primary_document_source_id);
  const paragraph = primary.excerpts.find((quote) => quote.id === "2254-paragraph-4");
  el("blockquote", paragraph.text, get("primary-wording"));
  link(primary.url, "Resolution 2254 · Printed page 2/4 ↗", get("primary-wording"));

  function view(comparison) {
    get("acts-panel").hidden = comparison;
    get("comparison-panel").hidden = !comparison;
    get("show-acts").setAttribute("aria-pressed", String(!comparison));
    get("show-comparison").setAttribute("aria-pressed", String(comparison));
    status();
  }
  get("show-acts").addEventListener("click", () => view(false));
  get("show-comparison").addEventListener("click", () => view(true));
  get("download-act").addEventListener("click", () => {
    download(bundle.selections[active], active + ".json");
    status("Political record downloaded with its cited excerpt, date basis, omissions and pending review state.");
  });
  get("download-study").addEventListener("click", () => {
    download(study, "political-evidence-study.json");
    status("Cited study downloaded, including primary evidence, political records and comparison annotations.");
  });
  showAct(active);
} catch {
  status("This static study could not be opened. Rebuild it from the validated source collection.");
  get("download-act").disabled = true;
  get("download-study").disabled = true;
}
