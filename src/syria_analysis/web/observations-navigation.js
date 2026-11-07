/* Pure helpers for bounded, source-qualified atlas navigation. No I/O. */
export const NAVIGATION_VERSION = "1";
export const GRAPH_LIMITS = [60, 250, 1000, 2048];
const VIEWS = ["map", "network", "lenses"];
const LENSES = ["prov-o", "skos", "owl-time", "geosparql", "sosa-ssn"];
const SCOPES = ["events", "selected", "indicators", "both"];
const defaults = () => ({
  country: "SY", from: 2020, to: 2025, actor: "", query: "", category: "",
  precision: "", order: "newest", view: "map", indicatorCode: "SP.POP.TOTL",
  selectedId: "", networkFocus: "", networkLimit: 6, lens: "prov-o", collection: "query", scope: "events", graphLimit: 60,
});

export function decodeNavigation(search, countries = ["SY"]) {
  const value = defaults(), ignored = [];
  const knownCountries = new Set(countries);
  if (!knownCountries.has(value.country)) value.country = countries[0] || "SY";
  if (typeof search !== "string" || search.length > 4096)
    return { value, ignored: ["oversized or invalid query"] };
  const params = new URLSearchParams(search);
  const one = (key) => {
    const values = params.getAll(key);
    if (values.length > 1) { ignored.push(key); return null; }
    return values[0] ?? null;
  };
  const set = (key, property, valid, convert = (item) => item) => {
    const candidate = one(key);
    if (candidate === null) return;
    if (valid(candidate)) value[property] = convert(candidate);
    else ignored.push(key);
  };
  const text = (item) => item.length <= 200 && !/[\u0000-\u001f\u007f]/u.test(item);
  const year = (item) => /^\d{4}$/.test(item) && Number(item) >= 1900 && Number(item) <= 2100;
  set("country", "country", (item) => knownCountries.has(item));
  set("from", "from", year, Number);
  set("to", "to", year, Number);
  if (value.from > value.to) { value.from = 2020; value.to = 2025; ignored.push("reversed interval"); }
  set("actor", "actor", text, (item) => item.trim().toLocaleLowerCase());
  set("search", "query", text, (item) => item.trim().toLocaleLowerCase());
  set("type", "category", (item) => item === "" || /^[1-3]$/.test(item));
  set("precision", "precision", (item) => item === "" || /^[1-7]$/.test(item));
  set("order", "order", (item) => ["newest", "oldest"].includes(item));
  set("view", "view", (item) => VIEWS.includes(item));
  set("side", "networkFocus", text);
  set("connections", "networkLimit", (item) => [6, 12, 18].includes(Number(item)), Number);
  set("indicator", "indicatorCode", (item) => /^[A-Za-z0-9_.-]{1,60}$/.test(item));
  set("event", "selectedId", (item) => /^ucdp-ged:[A-Za-z0-9._-]{1,20}:\d{1,20}$/.test(item));
  set("lens", "lens", (item) => LENSES.includes(item));
  set("collection", "collection", (item) => ["query", "index"].includes(item));
  set("scope", "scope", (item) => SCOPES.includes(item));
  set("nodes", "graphLimit", (item) => GRAPH_LIMITS.includes(Number(item)), Number);
  if (value.scope === "selected" && !value.selectedId) { ignored.push("selected scope without a record"); }
  return { value, ignored };
}

export function encodeNavigation(value) {
  const params = new URLSearchParams();
  params.set("country", value.country);
  params.set("from", String(value.from));
  params.set("to", String(value.to));
  const add = (key, item, omit = "") => { if (item && item !== omit) params.set(key, String(item)); };
  add("actor", value.actor); add("search", value.query);
  add("type", value.category); add("precision", value.precision);
  add("order", value.order, "newest"); add("view", value.view, "map");
  add("indicator", value.indicatorCode, "SP.POP.TOTL"); add("event", value.selectedId);
  add("scope", value.scope, "events");
  if (value.view === "network") {
    add("side", value.networkFocus); add("connections", value.networkLimit, 6);
  }
  if (value.view === "lenses") {
    add("lens", value.lens, "prov-o"); add("collection", value.collection, "query");
    add("nodes", value.graphLimit, 60);
  }
  return params.toString();
}

/** A one-hop provider-pair view. Never synthesize affiliation or additional edges. */
export function networkNeighborhood(pairs, requestedFocus = "", limit = 6) {
  const boundedLimit = [6, 12, 18].includes(limit) ? limit : 6;
  const degrees = new Map();
  for (const pair of pairs) for (const name of pair.names) degrees.set(name, (degrees.get(name) || 0) + pair.count);
  const ranked = [...degrees].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const focus = degrees.has(requestedFocus) ? requestedFocus : ranked[0]?.[0] || "";
  const neighbours = pairs.filter((pair) => pair.names.includes(focus))
    .sort((a, b) => b.count - a.count || a.names.join("\0").localeCompare(b.names.join("\0")));
  const retained = neighbours.slice(0, boundedLimit - 1);
  const names = focus ? [focus, ...retained.map((pair) => pair.names.find((name) => name !== focus))] : [];
  return { focus, ranked, pairs: retained, names, totalNames: degrees.size, connectedNames: neighbours.length + (focus ? 1 : 0) };
}

/** Deterministic nearby records for navigation, with no relevance or sampling claim. */
export function lensNeighborhood(rows, selected, limit = 60, facet = () => "") {
  const boundedLimit = GRAPH_LIMITS.includes(limit) ? limit : 60;
  if (rows.length <= boundedLimit) return rows;
  const date = (row) => row.indicator_code ? `${row.year}-01-01` : row.date_start;
  if (!selected || !rows.some((row) => row.id === selected.id)) return rows.slice(0, boundedLimit);
  const center = Date.parse(date(selected));
  const group = facet(selected);
  return [...rows].sort((a, b) => {
    if (a.id === selected.id) return -1;
    if (b.id === selected.id) return 1;
    return Number(facet(b) === group) - Number(facet(a) === group)
      || Math.abs(Date.parse(date(a)) - center) - Math.abs(Date.parse(date(b)) - center)
      || a.id.localeCompare(b.id);
  }).slice(0, boundedLimit);
}

const quote = (value) => `'${String(value).replaceAll("'", "'\\''")}'`;
export function reproductionRecipe(value, datasets, url, database = null) {
  const annual = value.scope === "indicators";
  const command = ["policy-analysis", "--country", quote(value.country), "research-query", "--atlas", "dist/observations"];
  if (annual) command.push("--indicator", quote(value.indicatorCode), "--from-year", "1900", "--to-year", "2100");
  else {
    command.push("--from-year", String(value.from), "--to-year", String(value.to));
    if (value.actor) command.push("--actor", quote(value.actor));
    if (value.category) command.push("--violence-type", value.category);
    if (value.precision) command.push("--geography-precision", value.precision);
  }
  command.push("--limit", "200", "--output", "output/reproduced-selection.json");
  const qualifications = ["The link pins filters, not source bytes. Verify the source identities below: refreshed hosting may serve a newer snapshot. Typed questions and analyst notes are deliberately excluded.", "The CLI command reproduces this country/filter scope in ascending date and ID order. Export timestamps, analyst notes, and the byte-limit cutoff may differ."];
  if (value.query || value.scope === "selected" || value.scope === "both") qualifications.push("Browser record search, selected-record and combined-series scopes require the shared view or original exported JSON; the CLI command below does not reproduce those extra selections.");
  if (database) qualifications.push("This view currently uses a bounded database page. A shared link opens the static snapshot and does not replay a paid query or its pagination cursor.");
  return ["# Reopen the research view", url, "", "# Local setup (Python 3.11+; from the repository root)", "python -m pip install -e .", "python scripts/build_showcase.py", "", "# Reproduce the supported query scope", command.join(" "), "policy-analysis validate-selection output/reproduced-selection.json", "", "# Source identities", ...datasets.map((dataset) => `${dataset.id}: ${dataset.sha256}`), ...(database ? [`Database snapshot: ${database.id || "not declared"}`] : []), "", ...qualifications].join("\n");
}
