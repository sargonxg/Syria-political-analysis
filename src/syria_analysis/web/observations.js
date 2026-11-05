/* Historical research atlas. No external services, generated records or idle loop. */
const PAGE_BASE = new URL("./", window.location.href);
const MANIFEST_URL = new URL("./data/manifest.json", PAGE_BASE);
const EXPORT_LIMIT = 200;
const EXPORT_BYTES = 1024 * 1024;
const PAGE_SIZE = 15;
const RAW_CACHE_LIMIT = 4;
const COMPACT_CACHE_BYTES = 12 * 1024 * 1024;
const number = new Intl.NumberFormat("en");
const decimal = new Intl.NumberFormat("en", { maximumFractionDigits: 2 });
const encoder = new TextEncoder();
const $ = (id) => document.getElementById(id);
const state = {
  manifest: null,
  datasets: new Map(),
  rawShards: new Map(),
  country: "SY",
  from: 2020,
  to: 2025,
  minYear: 2011,
  maxYear: 2025,
  events: [],
  filtered: [],
  indicators: [],
  indicatorCode: "",
  selected: null,
  selectedFull: null,
  selectedError: "",
  query: "",
  category: "",
  precision: "",
  order: "newest",
  page: 0,
  loading: true,
  indicatorLoading: true,
  view: "map",
  loadGeneration: 0,
  indicatorGeneration: 0,
  selectionGeneration: 0,
  exportGeneration: 0,
  loadController: null,
  indicatorController: null,
  selectionController: null,
  exportController: null,
  compactCache: new Map(),
  compactCacheBytes: 0,
  rawCache: new Map(),
  geography: [],
  geographyError: false,
  fitPending: true,
  camera: { x: 0, y: 0, scale: 100, fitScale: 100 },
  hitGrid: new Map(),
  mapped: 0,
  frame: 0,
  mapDirty: true,
  timelineDirty: true,
  indicatorDirty: true,
  networkDirty: true,
  brush: null,
};

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}

function sourceJSON(value, label) {
  const pre = element("pre", JSON.stringify(value, null, 2));
  pre.tabIndex = 0;
  pre.setAttribute("role", "region");
  pre.setAttribute("aria-label", label);
  return pre;
}

function localURL(path) {
  const url = new URL(path, PAGE_BASE);
  if (
    url.origin !== window.location.origin ||
    !["http:", "https:"].includes(url.protocol)
  ) {
    throw new Error(
      "Atlas data must use local, same-origin HTTP assets. Run a local web server to open downloaded files.",
    );
  }
  return url;
}

function publicLink(url, label) {
  label = label.replace(/\s*↗/g, "");
  try {
    const target = new URL(url);
    if (!["https:", "http:"].includes(target.protocol))
      return element("span", label);
    const link = element("a", label);
    link.href = target.href;
    link.target = "_blank";
    link.rel = "noreferrer";
    return link;
  } catch {
    return element("span", label);
  }
}

async function sha256(bytes) {
  if (!window.crypto?.subtle)
    throw new Error(
      "This browser needs HTTPS or localhost to verify source data integrity.",
    );
  const digest = await window.crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

function shardKey(shard) {
  return `${shard.path}#${shard.sha256}`;
}

async function decodeGzip(bytes, expected, signal) {
  const limit = 5 * 1024 * 1024;
  if (typeof DecompressionStream !== "function")
    throw new Error(
      "This browser cannot open the gzip-packaged original fields. Use a current browser with DecompressionStream support or download the source partition for local analysis.",
    );
  if (
    !Number.isSafeInteger(expected.decoded_bytes) ||
    expected.decoded_bytes < 1 ||
    expected.decoded_bytes > limit ||
    !/^[a-f0-9]{64}$/i.test(expected.decoded_sha256 || "")
  )
    throw new Error(
      "The gzip source partition has invalid decoded-size or decoded-hash metadata. Original fields cannot be verified.",
    );
  if (
    !Number.isSafeInteger(expected.bytes) ||
    expected.bytes !== bytes.byteLength
  )
    throw new Error(
      "The gzip asset length does not match its manifest. Original fields will not be displayed or exported.",
    );

  const reader = new Blob([bytes])
    .stream()
    .pipeThrough(new DecompressionStream("gzip"))
    .getReader();
  const chunks = [];
  let length = 0;
  const onAbort = () => {
    reader.cancel().catch(() => {});
  };
  signal?.addEventListener("abort", onAbort, { once: true });
  try {
    while (true) {
      if (signal?.aborted)
        throw new DOMException("Cancelled", "AbortError");
      const { value, done } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > limit) {
        await reader.cancel();
        throw new Error(
          "The decoded source partition exceeds the atlas’s 5 MiB per-file limit.",
        );
      }
      chunks.push(value);
    }
    if (signal?.aborted)
      throw new DOMException("Cancelled", "AbortError");
  } catch (error) {
    await reader.cancel().catch(() => {});
    if (error.name === "AbortError") throw error;
    throw new Error(
      `The gzip source partition could not be decoded. ${error.message}`,
    );
  } finally {
    signal?.removeEventListener("abort", onAbort);
    reader.releaseLock();
  }
  if (length !== expected.decoded_bytes)
    throw new Error(
      "Decoded source length does not match the manifest. Original fields will not be displayed or exported.",
    );
  const decoded = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    decoded.set(chunk, offset);
    offset += chunk.byteLength;
  }
  if ((await sha256(decoded)) !== expected.decoded_sha256.toLowerCase())
    throw new Error(
      "Decoded source integrity check failed. Its JSON bytes do not match the manifest SHA-256. Original fields will not be displayed or exported.",
    );
  return decoded;
}

async function fetchJSON(path, signal, cache = "force-cache", expected = null) {
  const url = localURL(path);
  if (expected) {
    if (!/^[a-f0-9]{64}$/i.test(expected.sha256 || ""))
      throw new Error(
        "A source shard has no valid manifest SHA-256. Source data cannot be verified.",
      );
    url.searchParams.set("sha256", expected.sha256);
  }
  const response = await fetch(url, {
    signal,
    cache,
    credentials: "same-origin",
  });
  if (!response.ok)
    throw new Error(
      `Could not load ${new URL(path, PAGE_BASE).pathname} (HTTP ${response.status}).`,
    );
  const bytes = await response.arrayBuffer();
  if (bytes.byteLength > 5 * 1024 * 1024)
    throw new Error("A data asset exceeds the atlas’s per-file safety limit.");
  if (expected && (await sha256(bytes)) !== expected.sha256.toLowerCase()) {
    throw new Error(
      `Source integrity check failed for ${url.pathname}. Its bytes do not match the manifest SHA-256. Retry after a complete dataset build.`,
    );
  }
  let jsonBytes = bytes;
  if (expected?.encoding === "gzip")
    jsonBytes = await decodeGzip(bytes, expected, signal);
  else if (expected?.encoding)
    throw new Error(`Unsupported source encoding: ${expected.encoding}.`);
  let value;
  try {
    value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(jsonBytes));
  } catch {
    throw new Error(
      "The requested asset is not valid JSON. An authentication page or incomplete build may have been returned.",
    );
  }
  if (
    expected &&
    (!Number.isInteger(expected.count) ||
      rowsOf(value).length !== expected.count)
  ) {
    throw new Error(
      `Source record count does not match the manifest for ${url.pathname}. No records from this file will be displayed.`,
    );
  }
  return { value, bytes: bytes.byteLength };
}

function rowsOf(value) {
  const rows = Array.isArray(value) ? value : value?.records;
  if (!Array.isArray(rows))
    throw new Error("A dataset shard has no records array.");
  return rows;
}

function finite(value) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function textOf(value) {
  return value === undefined || value === null ? "" : String(value);
}

function attributes(row) {
  return row.attributes && typeof row.attributes === "object"
    ? row.attributes
    : row;
}

function eventValue(row, key) {
  return attributes(row)[key] ?? row[key];
}

function labelOf(row) {
  return (
    row.label ||
    eventValue(row, "where_coordinates") ||
    eventValue(row, "adm_2") ||
    row.country ||
    "Recorded event"
  );
}

function dateLabel(row) {
  return row.date_start === row.date_end
    ? row.date_start
    : `${row.date_start} – ${row.date_end}`;
}

function sidesOf(row) {
  return [textOf(eventValue(row, "side_a")), textOf(eventValue(row, "side_b"))];
}

function normalizeEvent(row, shard) {
  if (!row || !row.id || !row.date_start || !row.date_end)
    throw new Error(
      "An event record is missing its identifier or date interval.",
    );
  const normalized = {
    ...row,
    id: String(row.id),
    dataset_id: row.dataset_id || shard.dataset_id,
    country_code: row.country_code || shard.country_code,
    latitude: finite(row.latitude),
    longitude: finite(row.longitude),
  };
  const a = attributes(normalized);
  normalized._search = [
    normalized.id,
    normalized.provider_id,
    normalized.label,
    normalized.country,
    a.where_coordinates,
    a.adm_1,
    a.adm_2,
    a.side_a,
    a.side_b,
  ]
    .filter(Boolean)
    .join(" ")
    .toLocaleLowerCase();
  normalized._yearStart = Number(normalized.date_start.slice(0, 4));
  normalized._yearEnd = Number(normalized.date_end.slice(0, 4));
  const point = project(normalized.longitude, normalized.latitude);
  normalized._point = point;
  return normalized;
}

function normalizeIndicator(row, shard) {
  if (
    !row ||
    !row.id ||
    !row.indicator_code ||
    !Number.isInteger(Number(row.year))
  ) {
    throw new Error(
      "A country indicator is missing its identifier, code or year.",
    );
  }
  return {
    ...row,
    dataset_id: row.dataset_id || shard.dataset_id,
    country_code: row.country_code || shard.country_code,
    year: Number(row.year),
    value: finite(row.value),
  };
}

async function inParallel(items, worker, signal, concurrency = 3) {
  const results = new Array(items.length);
  let cursor = 0;
  let stopped = false;
  async function runner() {
    while (cursor < items.length && !stopped) {
      if (signal?.aborted) throw new DOMException("Cancelled", "AbortError");
      const index = cursor++;
      try {
        results[index] = await worker(items[index], index);
      } catch (error) {
        stopped = true;
        throw error;
      }
    }
  }
  await Promise.all(
    Array.from({ length: Math.min(concurrency, items.length) }, runner),
  );
  return results;
}

function cacheCompact(path, result) {
  if (result.bytes > COMPACT_CACHE_BYTES) return;
  while (
    state.compactCacheBytes + result.bytes > COMPACT_CACHE_BYTES &&
    state.compactCache.size
  ) {
    const [oldPath, old] = state.compactCache.entries().next().value;
    state.compactCache.delete(oldPath);
    state.compactCacheBytes -= old.bytes;
  }
  state.compactCache.set(path, result);
  state.compactCacheBytes += result.bytes;
}

function abortExport() {
  if (state.exportController) {
    state.exportController.abort();
    state.exportController = null;
    state.exportGeneration += 1;
    $("export-status").textContent =
      "Download cancelled because the research selection changed. Start a new download when ready.";
    $("export-json").textContent = "Download selection JSON";
    $("export-markdown").textContent = "Download research brief";
  }
}

function clearSelected() {
  state.selectionController?.abort();
  state.selectionGeneration += 1;
  state.selected = null;
  state.selectedFull = null;
  state.selectedError = "";
  renderInspector();
}

function currentCountry() {
  return state.manifest?.countries.find(
    (country) => country.code === state.country,
  );
}

function eventShards(country = state.country) {
  return (state.manifest?.event_shards || []).filter(
    (shard) => shard.country_code === country,
  );
}

function countryYears() {
  const shards = eventShards();
  const starts = shards
    .map((shard) => Number(shard.year_start))
    .filter(Number.isFinite);
  const ends = shards
    .map((shard) => Number(shard.year_end))
    .filter(Number.isFinite);
  state.minYear = starts.length ? Math.min(...starts) : 2011;
  state.maxYear = ends.length ? Math.max(...ends) : 2025;
  for (const id of ["year-from", "year-to"]) {
    $(id).min = state.minYear;
    $(id).max = state.maxYear;
  }
}

function updateYears(from, to) {
  const parsedFrom = from === "" ? state.from : Number(from);
  const parsedTo = to === "" ? state.to : Number(to);
  const lo = Math.max(
    state.minYear,
    Math.min(
      state.maxYear,
      Number.isFinite(parsedFrom) ? Math.trunc(parsedFrom) : state.from,
    ),
  );
  const hi = Math.max(
    state.minYear,
    Math.min(
      state.maxYear,
      Number.isFinite(parsedTo) ? Math.trunc(parsedTo) : state.to,
    ),
  );
  state.from = Math.min(lo, hi);
  state.to = Math.max(lo, hi);
  $("year-from").value = state.from;
  $("year-to").value = state.to;
  $("period-label").textContent = `${state.from}–${state.to}`;
  state.timelineDirty = true;
  scheduleDraw();
}

async function loadEvents() {
  if (!state.manifest) return;
  abortExport();
  state.loadController?.abort();
  const controller = new AbortController();
  state.loadController = controller;
  const generation = ++state.loadGeneration;
  const country = state.country;
  const from = state.from;
  const to = state.to;
  const countryShards = eventShards();
  const shards = countryShards.filter(
    (shard) => Number(shard.year_start) <= to && Number(shard.year_end) >= from,
  );
  state.loading = true;
  state.events = [];
  state.filtered = [];
  state.page = 0;
  state.fitPending = true;
  clearSelected();
  $("map-card").setAttribute("aria-busy", "true");
  $("map-title").textContent = currentCountry()?.name || country;
  $("map-empty").hidden = false;
  $("map-empty").textContent = "Loading the selected historical period…";
  $("retry-load").hidden = true;
  $("load-status").textContent =
    `Loading ${country} · ${from}–${to} · ${number.format(shards.length)} compact data files.`;
  $("map-tooltip").hidden = true;
  renderTable();
  renderCategoryKey();
  updateExportPreview();
  state.mapDirty = true;
  state.networkDirty = true;
  scheduleDraw();
  let complete = 0;
  try {
    const batches = await inParallel(
      shards,
      async (shard) => {
        const key = shardKey(shard);
        let result = state.compactCache.get(key);
        if (!result) {
          result = await fetchJSON(
            shard.path,
            controller.signal,
            "force-cache",
            shard,
          );
          if (!controller.signal.aborted && generation === state.loadGeneration)
            cacheCompact(key, result);
        }
        const rows = rowsOf(result.value).map((row) =>
          normalizeEvent(row, shard),
        );
        complete += 1;
        if (
          generation === state.loadGeneration &&
          !controller.signal.aborted &&
          state.loading
        ) {
          $("load-status").textContent =
            `Loading ${country} · ${from}–${to}: ${complete} of ${shards.length} files.`;
        }
        return rows;
      },
      controller.signal,
    );
    if (controller.signal.aborted || generation !== state.loadGeneration)
      return;
    const unique = new Map();
    for (const rows of batches) for (const row of rows) unique.set(row.id, row);
    state.events = [...unique.values()].sort(
      (a, b) =>
        a.date_start.localeCompare(b.date_start) || a.id.localeCompare(b.id),
    );
    state.loading = false;
    populateEventCategories();
    $("map-card").setAttribute("aria-busy", "false");
    $("load-status").textContent =
      `${number.format(state.events.length)} historical records loaded for ${currentCountry()?.name || country}, ${from}–${to}. Original fields load on inspection or export.`;
    applyFilters(false);
    if (!countryShards.length) {
      $("load-status").textContent =
        `No separate historical event collection is included under ${currentCountry()?.name || country}. Annual context is loaded separately.`;
      $("map-empty").textContent =
        "No separate event series is included under this provider geography. Annual country context is available below. See source definitions for the provider’s geographic coding.";
    }
  } catch (error) {
    if (controller.signal.aborted || generation !== state.loadGeneration)
      return;
    controller.abort();
    state.loading = false;
    $("map-card").setAttribute("aria-busy", "false");
    $("load-status").textContent = `Data could not be loaded. ${error.message}`;
    $("retry-load").hidden = false;
    $("map-empty").hidden = false;
    $("map-empty").textContent =
      "Historical data could not be loaded. Use Retry loading above.";
    renderTable();
    updateExportPreview();
  }
}

async function loadIndicators() {
  state.indicatorController?.abort();
  const controller = new AbortController();
  state.indicatorController = controller;
  const generation = ++state.indicatorGeneration;
  state.indicators = [];
  state.indicatorLoading = true;
  $("indicator-status").textContent =
    "Loading this country’s separate annual series…";
  $("indicator-select").disabled = true;
  renderIndicators();
  const shards = (state.manifest?.indicator_shards || []).filter(
    (shard) => shard.country_code === state.country,
  );
  try {
    const batches = await inParallel(
      shards,
      async (shard) => {
        const result = await fetchJSON(
          shard.path,
          controller.signal,
          "force-cache",
          shard,
        );
        return rowsOf(result.value).map((row) =>
          normalizeIndicator(row, shard),
        );
      },
      controller.signal,
    );
    if (generation !== state.indicatorGeneration || controller.signal.aborted)
      return;
    state.indicators = batches
      .flat()
      .sort((a, b) => a.year - b.year || a.id.localeCompare(b.id));
    state.indicatorLoading = false;
    const codes = new Map();
    for (const row of state.indicators)
      codes.set(row.indicator_code, row.indicator_name || row.indicator_code);
    $("indicator-select").replaceChildren();
    for (const [code, name] of [...codes].sort((a, b) =>
      a[1].localeCompare(b[1]),
    )) {
      const option = element("option", name);
      option.value = code;
      $("indicator-select").append(option);
    }
    state.indicatorCode = codes.has(state.indicatorCode)
      ? state.indicatorCode
      : codes.has("SP.POP.TOTL")
        ? "SP.POP.TOTL"
        : [...codes.keys()][0] || "";
    $("indicator-select").value = state.indicatorCode;
    $("indicator-select").disabled = !codes.size;
    $("indicator-status").textContent = codes.size
      ? `${number.format(state.indicators.length)} source observations across ${codes.size} annual series. These are separate country-level records.`
      : "No annual country-indicator observations are included for this provider geography. Missing data are not zero.";
    renderIndicators();
    updateExportPreview();
  } catch (error) {
    if (generation !== state.indicatorGeneration || controller.signal.aborted)
      return;
    controller.abort();
    state.indicatorLoading = false;
    $("indicator-status").replaceChildren(
      element("span", `Country indicators could not load. ${error.message} `),
    );
    const retry = element("button", "Retry indicators", "text-button");
    retry.addEventListener("click", loadIndicators);
    $("indicator-status").append(retry);
    renderIndicators();
  }
}

function categoryLabel(code) {
  const dataset = [...state.datasets.values()].find(
    (item) => item.kind === "conflict_event",
  );
  return (
    dataset?.precision?.type_of_violence?.[code] ||
    dataset?.event_types?.[code] ||
    `Provider type ${code}`
  );
}

function populateEventCategories() {
  const values = [
    ...new Set(
      state.events
        .map((row) => textOf(eventValue(row, "type_of_violence")))
        .filter(Boolean),
    ),
  ].sort();
  const all = element("option", "All provider categories");
  all.value = "";
  $("event-type").replaceChildren(all);
  for (const code of values) {
    const option = element("option", categoryLabel(code));
    option.value = code;
    $("event-type").append(option);
  }
  $("event-type").value = state.category;
  if ($("event-type").value !== state.category) {
    state.category = "";
    $("event-type").value = "";
  }
}

function applyFilters(cancelExport = true) {
  if (cancelExport) abortExport();
  state.filtered = state.events.filter(
    (row) =>
      row._yearStart <= state.to &&
      row._yearEnd >= state.from &&
      (!state.category ||
        textOf(eventValue(row, "type_of_violence")) === state.category) &&
      (!state.precision ||
        textOf(eventValue(row, "where_prec")) === state.precision) &&
      (!state.query || row._search.includes(state.query)),
  );
  if (state.order === "newest") state.filtered.reverse();
  state.page = 0;
  if (
    state.selected &&
    !state.filtered.some((row) => row.id === state.selected.id)
  )
    clearSelected();
  $("map-empty").hidden = state.filtered.length > 0;
  if (!state.filtered.length)
    $("map-empty").textContent = state.loading
      ? "Loading historical records…"
      : "No recorded events match these filters. Try a wider period or a different search.";
  renderTable();
  renderCategoryKey();
  updateExportPreview();
  state.mapDirty = true;
  state.networkDirty = true;
  state.timelineDirty = true;
  scheduleDraw();
}

function renderCategoryKey() {
  const counts = new Map();
  for (const row of state.filtered) {
    const code = textOf(eventValue(row, "type_of_violence"));
    counts.set(code, (counts.get(code) || 0) + 1);
  }
  $("map-category-key").replaceChildren();
  for (const [code, count] of [...counts].sort()) {
    const item = element("span");
    const marker = element(
      "span",
      "",
      `category-dot${["1", "2", "3"].includes(code) ? ` category-${code}` : ""}`,
    );
    marker.setAttribute("aria-hidden", "true");
    item.append(
      marker,
      document.createTextNode(
        `${categoryLabel(code)} · ${number.format(count)}`,
      ),
    );
    $("map-category-key").append(item);
  }
}

function renderTable() {
  const rows = $("event-rows");
  rows.replaceChildren();
  const pages = Math.ceil(state.filtered.length / PAGE_SIZE);
  state.page = Math.max(0, Math.min(Math.max(0, pages - 1), state.page));
  const start = state.page * PAGE_SIZE;
  const current = state.filtered.slice(start, start + PAGE_SIZE);
  for (const row of current) {
    const tr = element(
      "tr",
      null,
      row.id === state.selected?.id ? "selected" : "",
    );
    const date = element("td", row.date_start);
    if (row.date_end !== row.date_start)
      date.append(element("span", `to ${row.date_end}`, "cell-secondary"));
    const place = element("td", labelOf(row));
    place.append(
      element(
        "span",
        row.provider_id ? `Provider ID ${row.provider_id}` : row.id,
        "cell-secondary",
      ),
    );
    const sides = sidesOf(row);
    const actors = element("td", sides[0] || "Not specified");
    if (sides[1])
      actors.append(element("span", ` / ${sides[1]}`, "cell-secondary"));
    const action = element("td");
    const button = element("button", "Inspect");
    button.setAttribute(
      "aria-label",
      `Inspect ${labelOf(row)}, ${row.date_start}, ${row.provider_id || row.id}`,
    );
    button.addEventListener("click", () => selectEvent(row, true));
    action.append(button);
    tr.append(date, place, actors, action);
    rows.append(tr);
  }
  if (!current.length) {
    const tr = element("tr");
    const td = element(
      "td",
      state.loading
        ? "Loading the selected country and period…"
        : "No matching event records.",
    );
    td.colSpan = 4;
    tr.append(td);
    rows.append(tr);
  }
  $("table-summary").textContent = state.loading
    ? "Loading compact records. Previous results are cleared while the selection changes."
    : `${number.format(state.filtered.length)} matching historical dataset records. ${current.length ? `Showing ${number.format(start + 1)}–${number.format(start + current.length)}.` : ""} Full original fields load when inspected.`;
  $("page-status").textContent =
    `Page ${pages ? state.page + 1 : 0} of ${number.format(pages)}`;
  $("previous-page").disabled = state.page === 0 || !pages;
  $("next-page").disabled = state.page + 1 >= pages;
}

async function fullEvent(row, signal) {
  if (!row.raw_shard) return row;
  const shard = state.rawShards.get(row.raw_shard);
  if (
    !shard ||
    shard.dataset_id !== row.dataset_id ||
    shard.country_code !== row.country_code
  ) {
    throw new Error(
      "The original-field shard is not registered for this event’s dataset and country in the manifest.",
    );
  }
  const key = shardKey(shard);
  let indexed = state.rawCache.get(key);
  if (indexed) {
    state.rawCache.delete(key);
    state.rawCache.set(key, indexed);
  } else {
    const result = await fetchJSON(row.raw_shard, signal, "force-cache", shard);
    indexed = new Map(
      rowsOf(result.value).map((original) => [String(original.id), original]),
    );
    if (signal?.aborted) throw new DOMException("Cancelled", "AbortError");
    while (state.rawCache.size >= RAW_CACHE_LIMIT)
      state.rawCache.delete(state.rawCache.keys().next().value);
    state.rawCache.set(key, indexed);
  }
  const original = indexed.get(row.id);
  if (
    !original ||
    original.dataset_id !== row.dataset_id ||
    original.raw_record_sha256 !== row.raw_record_sha256 ||
    !/^[a-f0-9]{64}$/i.test(row.raw_record_sha256 || "") ||
    !original.attributes
  ) {
    throw new Error(
      "The full source row does not match this event’s ID, dataset and original-row hash. No compact fallback will be exported.",
    );
  }
  const keys = Object.keys(original.attributes).sort();
  if (
    keys.length !== 49 ||
    !keys.every((name) => typeof original.attributes[name] === "string")
  ) {
    throw new Error(
      "The UCDP original row does not contain its 49 unchanged string-valued provider fields.",
    );
  }
  const canonical = JSON.stringify(
    Object.fromEntries(keys.map((name) => [name, original.attributes[name]])),
  );
  if (
    (await sha256(encoder.encode(canonical))) !==
    row.raw_record_sha256.toLowerCase()
  ) {
    throw new Error(
      "The canonical original provider-field digest does not match the compact event record. Inspection and export are blocked for this row.",
    );
  }
  return { ...row, ...original, _rawLoaded: true };
}

async function selectEvent(row, moveFocus = false) {
  if ($("export-kind").value === "selected") abortExport();
  state.selectionController?.abort();
  const controller = new AbortController();
  state.selectionController = controller;
  const generation = ++state.selectionGeneration;
  state.selected = row;
  state.selectedFull = row.raw_shard ? null : row;
  state.selectedError = "";
  renderInspector();
  renderTable();
  updateExportPreview();
  state.mapDirty = true;
  scheduleDraw();
  if (moveFocus) {
    $("inspector-title").tabIndex = -1;
    $("inspector-title").focus({ preventScroll: true });
    if (window.innerWidth < 800)
      $("inspector-title").scrollIntoView({ behavior: "auto", block: "start" });
  }
  if (!row.raw_shard) return;
  try {
    const original = await fullEvent(row, controller.signal);
    if (generation !== state.selectionGeneration || controller.signal.aborted)
      return;
    state.selectedFull = original;
    renderInspector();
  } catch (error) {
    if (generation !== state.selectionGeneration || controller.signal.aborted)
      return;
    state.selectedError = error.message;
    renderInspector();
  }
}

function precisionLabel(dataset, kind, value) {
  const code = textOf(value);
  if (!code) return "Not supplied";
  const key =
    kind === "geo" ? "where_prec" : kind === "date" ? "date_prec" : kind;
  const collection = dataset?.precision?.[kind] || dataset?.precision?.[key];
  const description = collection?.[code];
  return `Code ${code}${description ? ` · ${typeof description === "string" ? description : description.label || description.description || ""}` : " · see provider codebook"}`;
}

function addFact(list, title, value) {
  const group = element("div");
  group.append(element("dt", title), element("dd", value));
  list.append(group);
}

function renderInspector() {
  const container = $("event-inspector");
  container.replaceChildren();
  const row = state.selectedFull || state.selected;
  if (!row) {
    container.append(
      element(
        "p",
        "Select an event on the map or in the directory. Its provider ID, date and geographic precision, original fields and dataset provenance will appear here.",
      ),
      element(
        "p",
        "Dataset observations are attributed records, not independently corroborated findings.",
        "muted",
      ),
    );
    return;
  }
  const dataset = state.datasets.get(row.dataset_id);
  container.append(
    element("h3", labelOf(row)),
    element("p", row.id, "record-id"),
  );
  const list = element("dl", null, "fact-list");
  addFact(list, "Recorded date / interval", dateLabel(row));
  addFact(
    list,
    "Recorded opposing sides",
    sidesOf(row).filter(Boolean).join(" / ") || "Not supplied",
  );
  addFact(
    list,
    "Provider category",
    categoryLabel(textOf(eventValue(row, "type_of_violence"))),
  );
  addFact(
    list,
    "Geographic precision",
    precisionLabel(dataset, "geo", eventValue(row, "where_prec")),
  );
  addFact(
    list,
    "Date precision",
    precisionLabel(dataset, "date", eventValue(row, "date_prec")),
  );
  addFact(
    list,
    "Event clarity · provider code",
    precisionLabel(dataset, "event_clarity", eventValue(row, "event_clarity")),
  );
  addFact(
    list,
    "Published coordinates",
    row.latitude !== null && row.longitude !== null
      ? `${row.latitude}, ${row.longitude} · approximate as coded`
      : "Not supplied",
  );
  const bounds = ["low", "best", "high"].map((key) => eventValue(row, key));
  addFact(
    list,
    "Provider fatality estimates · low / best / high",
    bounds
      .map((value) =>
        value === undefined || value === null || value === ""
          ? "not supplied"
          : textOf(value),
      )
      .join(" / "),
  );
  addFact(
    list,
    "Source row locator",
    typeof row.source_locator === "string"
      ? row.source_locator
      : JSON.stringify(row.source_locator),
  );
  container.append(list);
  const nonOrdered =
    (row.quality_flags || []).some((flag) =>
      /bounds|order/i.test(textOf(flag)),
    ) ||
    (bounds.every((value) => finite(value) !== null) &&
      (Number(bounds[0]) > Number(bounds[1]) ||
        Number(bounds[1]) > Number(bounds[2])));
  if (nonOrdered)
    container.append(
      element(
        "p",
        "Provider values are not ordered low ≤ best ≤ high in this record. They remain unchanged and are not confidence intervals. Consult the provider codebook; this interface does not determine the cause for this record.",
        "quality-flag",
      ),
    );
  if (row.quality_flags?.length)
    container.append(
      element(
        "p",
        `Provider / pipeline flags: ${row.quality_flags.join(", ")}`,
        "record-id",
      ),
    );
  if (dataset) {
    container.append(
      publicLink(dataset.url, `${dataset.title} · ${dataset.version}`),
    );
    const rights = element(
      "p",
      `${dataset.publisher} · ${dataset.license}`,
      "record-id",
    );
    container.append(rights);
    if (dataset.codebook_url)
      container.append(
        publicLink(dataset.codebook_url, "Read the provider codebook ↗"),
      );
  }
  if (state.selectedFull) {
    const detail = element("details");
    detail.append(
      element(
        "summary",
        `Inspect ${Object.keys(attributes(state.selectedFull)).length} original provider fields`,
      ),
    );
    detail.append(
      sourceJSON(
        attributes(state.selectedFull),
        `Original provider fields for ${row.id}`,
      ),
    );
    container.append(detail);
    if (row.raw_record_sha256)
      container.append(
        element(
          "p",
          `Canonical original-row SHA-256: ${row.raw_record_sha256}`,
          "record-id",
        ),
      );
  } else if (state.selectedError) {
    container.append(
      element(
        "p",
        `Original fields could not load. ${state.selectedError}`,
        "quality-flag",
      ),
    );
    const retry = element("button", "Retry original fields");
    retry.addEventListener("click", () => selectEvent(state.selected));
    container.append(retry);
  } else {
    container.append(
      element(
        "p",
        "Loading original provider fields… Compact facts above remain attributed to the dataset.",
        "muted",
      ),
    );
  }
}

/* The map uses a Mercator projection and one Canvas path per event category. */
function project(longitude, latitude) {
  if (
    !Number.isFinite(longitude) ||
    !Number.isFinite(latitude) ||
    Math.abs(longitude) > 180 ||
    Math.abs(latitude) > 90
  )
    return null;
  const clamped = (Math.max(-84, Math.min(84, latitude)) * Math.PI) / 180;
  return [
    (longitude * Math.PI) / 180,
    -Math.log(Math.tan(Math.PI / 4 + clamped / 2)),
  ];
}

function unproject(x, y) {
  return [
    (x * 180) / Math.PI,
    ((2 * Math.atan(Math.exp(-y)) - Math.PI / 2) * 180) / Math.PI,
  ];
}

function prepareCanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  const width = Math.round(rect.width);
  const height = Math.round(rect.height);
  if (!width || !height) return null;
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const pixelWidth = Math.round(width * ratio);
  const pixelHeight = Math.round(height * ratio);
  if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
    canvas.width = pixelWidth;
    canvas.height = pixelHeight;
  }
  const context = canvas.getContext("2d");
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, width, height);
  return { context, width, height };
}

function mapScreen(point, width, height) {
  return [
    (point[0] - state.camera.x) * state.camera.scale + width / 2,
    (point[1] - state.camera.y) * state.camera.scale + height / 2,
  ];
}

function mapWorld(x, y, width, height) {
  return [
    (x - width / 2) / state.camera.scale + state.camera.x,
    (y - height / 2) / state.camera.scale + state.camera.y,
  ];
}

function fitMap() {
  const canvas = $("event-map");
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (!width || !height) return;
  const points = state.events.map((row) => row._point).filter(Boolean);
  const bbox = currentCountry()?.bbox;
  if (Array.isArray(bbox) && bbox.length === 4) {
    const first = project(Number(bbox[0]), Number(bbox[1]));
    const last = project(Number(bbox[2]), Number(bbox[3]));
    if (first && last) points.push(first, last);
  }
  if (!points.length) points.push(project(33, 12), project(59, 39));
  let x0 = Infinity;
  let x1 = -Infinity;
  let y0 = Infinity;
  let y1 = -Infinity;
  for (const [x, y] of points) {
    x0 = Math.min(x0, x);
    x1 = Math.max(x1, x);
    y0 = Math.min(y0, y);
    y1 = Math.max(y1, y);
  }
  const spanX = Math.max(0.035, x1 - x0);
  const spanY = Math.max(0.035, y1 - y0);
  const scale = Math.min(
    Math.max(100, width - 110) / spanX,
    Math.max(100, height - 75) / spanY,
  );
  state.camera = { x: (x0 + x1) / 2, y: (y0 + y1) / 2, scale, fitScale: scale };
  state.fitPending = false;
}

function drawGeography(context, width, height) {
  context.fillStyle = "#122a2c";
  context.fillRect(0, 0, width, height);
  context.strokeStyle = "#294542";
  context.lineWidth = 0.6;
  context.beginPath();
  for (let longitude = -180; longitude <= 180; longitude += 5) {
    const x = mapScreen(project(longitude, 0), width, height)[0];
    if (x >= 0 && x <= width) {
      context.moveTo(x, 0);
      context.lineTo(x, height);
    }
  }
  for (let latitude = -80; latitude <= 80; latitude += 5) {
    const y = mapScreen(project(0, latitude), width, height)[1];
    if (y >= 0 && y <= height) {
      context.moveTo(0, y);
      context.lineTo(width, y);
    }
  }
  context.stroke();
  context.fillStyle = "#213c36";
  context.strokeStyle = "#547064";
  context.lineWidth = 0.7;
  context.beginPath();
  for (const polygon of state.geography) {
    for (const ring of polygon) {
      let first = true;
      for (const point of ring) {
        const [x, y] = mapScreen(point, width, height);
        if (first) {
          context.moveTo(x, y);
          first = false;
        } else context.lineTo(x, y);
      }
      context.closePath();
    }
  }
  context.fill("evenodd");
  context.stroke();
}

function eventColor(row) {
  return (
    { 1: "#91d3b5", 2: "#e3b77b", 3: "#c5c0e4" }[
      textOf(eventValue(row, "type_of_violence"))
    ] || "#b2cbbd"
  );
}

function drawMap() {
  const prepared = prepareCanvas($("event-map"));
  if (!prepared) return;
  const { context, width, height } = prepared;
  if (state.fitPending) fitMap();
  drawGeography(context, width, height);
  state.hitGrid.clear();
  let mapped = 0;
  let inView = 0;
  const groups = new Map();
  const radius = Math.max(
    1.25,
    Math.min(
      3,
      1.5 +
        Math.log2(Math.max(1, state.camera.scale / state.camera.fitScale)) *
          0.25,
    ),
  );
  for (const row of state.filtered) {
    if (!row._point) continue;
    mapped += 1;
    const [x, y] = mapScreen(row._point, width, height);
    if (x < -5 || y < -5 || x > width + 5 || y > height + 5) continue;
    inView += 1;
    const color = eventColor(row);
    if (!groups.has(color)) groups.set(color, []);
    groups.get(color).push([x, y]);
    const key = `${Math.floor(x / 16)},${Math.floor(y / 16)}`;
    if (!state.hitGrid.has(key)) state.hitGrid.set(key, []);
    state.hitGrid.get(key).push({ row, x, y });
  }
  context.globalAlpha = 0.62;
  for (const [color, points] of groups) {
    context.fillStyle = color;
    context.beginPath();
    for (const [x, y] of points) {
      context.moveTo(x + radius, y);
      context.arc(x, y, radius, 0, Math.PI * 2);
    }
    context.fill();
  }
  context.globalAlpha = 1;
  if (state.selected?._point) {
    const [x, y] = mapScreen(state.selected._point, width, height);
    context.strokeStyle = "#fff2ca";
    context.lineWidth = 1.5;
    context.beginPath();
    context.arc(x, y, 7, 0, Math.PI * 2);
    context.stroke();
    context.fillStyle = "#fff2ca";
    context.beginPath();
    context.arc(x, y, 2, 0, Math.PI * 2);
    context.fill();
  }
  state.mapped = mapped;
  $("mapped-count").textContent = state.loading
    ? "Loading…"
    : `${number.format(mapped)} mapped / ${number.format(state.filtered.length)} matching${inView < mapped ? ` · ${number.format(inView)} in view` : ""}`;
  $("event-map").setAttribute(
    "aria-label",
    `${currentCountry()?.name || state.country}, ${state.from} to ${state.to}: ${number.format(mapped)} geolocated historical records, ${number.format(state.filtered.length)} matching records. Use the event table for individual records.`,
  );
  if (state.geographyError)
    $("map-coordinate").textContent =
      "Basemap unavailable · event coordinates retained";
}

function findPoint(x, y) {
  const cellX = Math.floor(x / 16);
  const cellY = Math.floor(y / 16);
  let closest = null;
  let distance = 100;
  for (let dx = -1; dx <= 1; dx += 1)
    for (let dy = -1; dy <= 1; dy += 1) {
      for (const point of state.hitGrid.get(`${cellX + dx},${cellY + dy}`) ||
        []) {
        const squared = (point.x - x) ** 2 + (point.y - y) ** 2;
        if (squared < distance) {
          distance = squared;
          closest = point;
        }
      }
    }
  return closest;
}

function zoomMap(
  factor,
  x = $("event-map").clientWidth / 2,
  y = $("event-map").clientHeight / 2,
) {
  const canvas = $("event-map");
  const before = mapWorld(x, y, canvas.clientWidth, canvas.clientHeight);
  state.camera.scale = Math.max(
    state.camera.fitScale * 0.3,
    Math.min(state.camera.fitScale * 40, state.camera.scale * factor),
  );
  const after = mapWorld(x, y, canvas.clientWidth, canvas.clientHeight);
  state.camera.x += before[0] - after[0];
  state.camera.y += before[1] - after[1];
  state.mapDirty = true;
  $("map-tooltip").hidden = true;
  scheduleDraw();
}

function yearlyCounts() {
  const counts = new Map();
  let complete = true;
  for (const shard of eventShards()) {
    if (Number(shard.year_start) === Number(shard.year_end)) {
      const year = Number(shard.year_start);
      counts.set(year, (counts.get(year) || 0) + Number(shard.count || 0));
    } else complete = false;
  }
  if (!complete) {
    counts.clear();
    for (const row of state.events) {
      const year = Number(eventValue(row, "year")) || row._yearStart;
      counts.set(year, (counts.get(year) || 0) + 1);
    }
  }
  return { counts, complete };
}

function drawTimeline() {
  const prepared = prepareCanvas($("timeline"));
  if (!prepared) return;
  const { context, width, height } = prepared;
  const { counts, complete } = yearlyCounts();
  const years = state.maxYear - state.minYear + 1;
  const step = (width - 4) / years;
  const max = Math.max(1, ...counts.values());
  const base = height - 22;
  const brushFrom = state.brush
    ? Math.min(state.brush.start, state.brush.end)
    : state.from;
  const brushTo = state.brush
    ? Math.max(state.brush.start, state.brush.end)
    : state.to;
  context.fillStyle = "#304b42";
  context.fillRect(
    (brushFrom - state.minYear) * step,
    0,
    (brushTo - brushFrom + 1) * step,
    base + 3,
  );
  for (let year = state.minYear; year <= state.maxYear; year += 1) {
    const value = counts.get(year) || 0;
    const bar = (value / max) * (base - 16);
    const active = year >= brushFrom && year <= brushTo;
    context.fillStyle = active ? "#b2d8b6" : "#65897a";
    context.fillRect(
      (year - state.minYear) * step + 2,
      base - bar,
      Math.max(1, step - 4),
      Math.max(value ? 1 : 0, bar),
    );
    if (
      (year - state.minYear) % Math.max(1, Math.ceil(years / 8)) === 0 ||
      year === state.maxYear
    ) {
      context.font = "9px Arial, sans-serif";
      context.fillStyle = active ? "#e5e8d2" : "#adc5b7";
      context.textAlign = "center";
      context.fillText(
        String(year),
        (year - state.minYear + 0.5) * step,
        height - 5,
      );
    }
  }
  context.font = "8px Arial, sans-serif";
  context.textAlign = "right";
  context.fillStyle = "#b8ccbc";
  context.fillText(`Annual maximum ${number.format(max)}`, width - 2, 10);
  $("timeline-note").textContent =
    `${complete ? "All included country records by provider year, before search/category filters." : "Loaded country records only; full annual shard counts are unavailable."} Drag a period, or enter years above. Recorded coverage is not a measure of all violence.`;
}

function drawNetwork() {
  const prepared = prepareCanvas($("sides-network"));
  if (!prepared) return;
  const { context, width, height } = prepared;
  const degrees = new Map();
  const pairs = new Map();
  for (const row of state.filtered) {
    const sides = sidesOf(row);
    if (!sides[0] || !sides[1] || sides[0] === sides[1]) continue;
    const names = [...sides].sort();
    const key = JSON.stringify(names);
    const pair = pairs.get(key) || { names, count: 0 };
    pair.count += 1;
    pairs.set(key, pair);
    for (const name of names) degrees.set(name, (degrees.get(name) || 0) + 1);
  }
  const nodes = [...degrees.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 18);
  const positions = new Map();
  const radius = Math.max(50, Math.min(width * 0.31, height * 0.34));
  nodes.forEach(([name], index) => {
    const angle = (index / nodes.length) * Math.PI * 2 - Math.PI / 2;
    positions.set(name, {
      x: width / 2 + Math.cos(angle) * radius,
      y: height / 2 + Math.sin(angle) * radius,
    });
  });
  const visiblePairs = [...pairs.values()]
    .filter((pair) => pair.names.every((name) => positions.has(name)))
    .sort((a, b) => b.count - a.count);
  const maxPair = Math.max(1, ...visiblePairs.map((pair) => pair.count));
  for (const pair of visiblePairs) {
    const [a, b] = pair.names.map((name) => positions.get(name));
    context.strokeStyle = `rgba(154, 199, 170, ${0.12 + 0.48 * Math.sqrt(pair.count / maxPair)})`;
    context.lineWidth = 0.5 + 3 * Math.sqrt(pair.count / maxPair);
    context.beginPath();
    context.moveTo(a.x, a.y);
    context.lineTo(b.x, b.y);
    context.stroke();
  }
  const maxDegree = Math.max(1, ...nodes.map((node) => node[1]));
  for (const [name, degree] of nodes) {
    const position = positions.get(name);
    context.fillStyle = "#d9c391";
    context.beginPath();
    context.arc(
      position.x,
      position.y,
      3 + 5 * Math.sqrt(degree / maxDegree),
      0,
      Math.PI * 2,
    );
    context.fill();
    context.font = "9px Arial, sans-serif";
    context.fillStyle = "#dce6d7";
    const left = position.x < width / 2;
    context.textAlign = left ? "right" : "left";
    const label = name.length > 30 ? `${name.slice(0, 27)}…` : name;
    const labelWidth = Math.min(150, width * 0.27);
    context.fillText(
      label,
      position.x + (left ? -12 : 12),
      position.y + 3,
      labelWidth,
    );
  }
  const list = element("ol");
  for (const pair of visiblePairs.slice(0, 8)) {
    const item = element("li", `${pair.names[0]} / ${pair.names[1]} `);
    item.append(element("span", `· ${number.format(pair.count)} records`));
    list.append(item);
  }
  $("network-pairs").replaceChildren(
    visiblePairs.length
      ? list
      : element(
          "p",
          "No paired side names are present in the current filtered records.",
        ),
  );
  $("sides-network").setAttribute(
    "aria-label",
    `Recorded opposing sides: ${nodes.length} displayed names from ${number.format(state.filtered.length)} matching event records. The largest recorded pairs are listed below.`,
  );
}

function selectedSeries() {
  return state.indicators.filter(
    (row) => row.indicator_code === state.indicatorCode,
  );
}

function renderIndicators() {
  const series = selectedSeries();
  const unit =
    series.find((row) => attributes(row).display_unit)?.attributes
      .display_unit ||
    series.find((row) => row.unit)?.unit ||
    "Provider unit not supplied";
  $("indicator-unit").textContent = unit;
  const valid = series.filter((row) => row.value !== null);
  $("indicator-coverage").textContent = series.length
    ? `${series[0].year}–${series.at(-1).year} · ${valid.length} numeric observations`
    : "No observations loaded";
  const source = $("indicator-source");
  source.replaceChildren();
  const dataset = series.length
    ? state.datasets.get(series[0].dataset_id)
    : null;
  if (dataset) {
    source.append(
      publicLink(dataset.url, `${dataset.publisher} · ${dataset.title}`),
    );
    const updated = attributes(series[0]).source_last_updated;
    source.append(
      document.createTextNode(
        ` · ${dataset.license}${updated ? ` · source updated ${updated}` : ""}. Missing years remain gaps; no event-series join is inferred.`,
      ),
    );
  }
  const firstAttributes = series.length ? attributes(series[0]) : {};
  $("indicator-reading").textContent = [
    firstAttributes.interpretation_note,
    firstAttributes.source_status_interpretation,
    firstAttributes.display_unit_basis
      ? `Unit basis: ${firstAttributes.display_unit_basis}.`
      : "",
  ]
    .filter(Boolean)
    .join(" ");
  const tbody = $("indicator-rows");
  tbody.replaceChildren();
  for (const row of series) {
    const tr = element("tr");
    const original = element("td");
    const details = element("details");
    details.append(
      element("summary", "Inspect"),
      sourceJSON(
        {
          id: row.id,
          source_locator: row.source_locator,
          attributes: attributes(row),
        },
        `Original annual indicator fields for ${row.year}`,
      ),
    );
    original.append(details);
    tr.append(
      element("td", row.year),
      element(
        "td",
        row.value === null ? "Missing / null" : numberForIndicator(row.value),
      ),
      element(
        "td",
        row.status || attributes(row).obs_status || "No status flag supplied",
      ),
      original,
    );
    tbody.append(tr);
  }
  if (!series.length) {
    const tr = element("tr");
    const td = element(
      "td",
      state.indicatorLoading
        ? "Loading country observations…"
        : "No indicator observations included.",
    );
    td.colSpan = 4;
    tr.append(td);
    tbody.append(tr);
  }
  state.indicatorDirty = true;
  scheduleDraw();
}

function numberForIndicator(value) {
  if (Math.abs(value) >= 0.01 || value === 0) return decimal.format(value);
  return value.toPrecision(4);
}

function drawIndicator() {
  const prepared = prepareCanvas($("indicator-chart"));
  if (!prepared) return;
  const { context, width, height } = prepared;
  const series = selectedSeries();
  const valid = series.filter((row) => row.value !== null);
  if (!valid.length) {
    context.fillStyle = "#596e62";
    context.font = "12px Arial, sans-serif";
    context.textAlign = "center";
    context.fillText(
      state.indicatorLoading
        ? "Loading annual observations…"
        : "No numeric observations in this series.",
      width / 2,
      height / 2,
    );
    return;
  }
  const left = 65;
  const right = width - 15;
  const top = 20;
  const bottom = height - 28;
  const firstYear = series[0].year;
  const lastYear = series.at(-1).year;
  let min = Math.min(...valid.map((row) => row.value));
  let max = Math.max(...valid.map((row) => row.value));
  if (min === max) {
    min -= Math.max(1, Math.abs(min) * 0.1);
    max += Math.max(1, Math.abs(max) * 0.1);
  }
  const x = (year) =>
    left +
    ((year - firstYear) / Math.max(1, lastYear - firstYear)) * (right - left);
  const y = (value) => bottom - ((value - min) / (max - min)) * (bottom - top);
  context.font = "9px Arial, sans-serif";
  context.textAlign = "right";
  for (let index = 0; index <= 3; index += 1) {
    const value = min + ((max - min) * index) / 3;
    const yy = y(value);
    context.strokeStyle = "#cfd6c9";
    context.lineWidth = 0.6;
    context.beginPath();
    context.moveTo(left, yy);
    context.lineTo(right, yy);
    context.stroke();
    context.fillStyle = "#5a6b63";
    context.fillText(
      Math.abs(value) >= 1e6
        ? new Intl.NumberFormat("en", {
            notation: "compact",
            maximumFractionDigits: 1,
          }).format(value)
        : numberForIndicator(value),
      left - 9,
      yy + 3,
    );
  }
  context.strokeStyle = "#1b7060";
  context.lineWidth = 1.7;
  context.beginPath();
  let previous = null;
  for (const row of series) {
    if (row.value === null) {
      previous = null;
      continue;
    }
    if (!previous || row.year - previous.year !== 1)
      context.moveTo(x(row.year), y(row.value));
    else context.lineTo(x(row.year), y(row.value));
    previous = row;
  }
  context.stroke();
  context.fillStyle = "#1b7060";
  for (const row of valid) {
    context.beginPath();
    context.arc(x(row.year), y(row.value), 2.5, 0, Math.PI * 2);
    context.fill();
  }
  context.font = "9px Arial, sans-serif";
  context.fillStyle = "#5a6b63";
  context.textAlign = "left";
  context.fillText(String(firstYear), left, height - 8);
  context.textAlign = "right";
  context.fillText(String(lastYear), right, height - 8);
  $("indicator-chart").setAttribute(
    "aria-label",
    `${series[0].indicator_name || state.indicatorCode}, ${currentCountry()?.name || state.country}, ${firstYear} to ${lastYear}, ${valid.length} numeric observations, unit ${series[0].unit || "not supplied"}. The annual-values table provides original numbers and status.`,
  );
}

function scheduleDraw() {
  if (state.frame || document.hidden) return;
  state.frame = requestAnimationFrame(() => {
    state.frame = 0;
    if (state.mapDirty && state.view === "map") {
      state.mapDirty = false;
      drawMap();
    }
    if (state.networkDirty && state.view === "network") {
      state.networkDirty = false;
      drawNetwork();
    }
    if (state.timelineDirty) {
      state.timelineDirty = false;
      drawTimeline();
    }
    if (state.indicatorDirty) {
      state.indicatorDirty = false;
      drawIndicator();
    }
  });
}

/* Selection JSON is its own contract. It is not a native knowledge context. */
function selectionCandidates() {
  const scope = $("export-kind").value;
  const events =
    scope === "selected"
      ? state.selected
        ? [state.selected]
        : []
      : state.filtered;
  const eventRecords = events.map((row) => ({ kind: "conflict_event", row }));
  const indicatorRecords = selectedSeries().map((row) => ({
    kind: "country_indicator",
    row,
  }));
  if (scope === "selected" || scope === "events") return eventRecords;
  if (scope === "indicators") return indicatorRecords;
  return [...indicatorRecords, ...eventRecords];
}

function selectionFilters() {
  const scope = $("export-kind").value;
  const result = {
    country_code: state.country,
    provider_country_label: currentCountry()?.name || state.country,
    export_scope: scope,
    record_order:
      scope === "both"
        ? "Selected indicator series in ascending year, followed by matching events in directory order"
        : "Current directory order for events; ascending year for indicators",
  };
  if (scope !== "indicators")
    result.events = {
      date_overlap: { from: `${state.from}-01-01`, to: `${state.to}-12-31` },
      search: state.query,
      type_of_violence: state.category || null,
      where_prec: state.precision || null,
      order: state.order,
      selected_event_id:
        scope === "selected" ? state.selected?.id || null : null,
    };
  if (scope === "indicators" || scope === "both") {
    const series = selectedSeries();
    result.country_indicators = {
      indicator_code: state.indicatorCode,
      years: series.map((row) => row.year),
      period:
        "All included annual observations; event search, violence type, location precision and event-period filters do not apply",
    };
  }
  return result;
}

function updateExportPreview() {
  const candidates = selectionCandidates();
  const scope = $("export-kind").value;
  const loading =
    ((scope === "events" || scope === "both" || scope === "selected") &&
      state.loading) ||
    ((scope === "indicators" || scope === "both") && state.indicatorLoading);
  const busy = Boolean(state.exportController);
  $("export-json").disabled = loading || busy || !candidates.length;
  $("export-markdown").disabled = loading || busy || !candidates.length;
  const prefix = loading
    ? "Selection is loading."
    : `${number.format(candidates.length)} matching ${scope === "both" ? "separately typed source" : scope === "indicators" ? "annual country-indicator" : "conflict-event"} records.`;
  $("export-preview").textContent =
    `${prefix} Download includes the first ${Math.min(EXPORT_LIMIT, candidates.length)} records, reduced further if needed to stay within 1 MiB.${scope === "both" ? " Selected series first, then events; the two types are not joined." : ""} Full original provider fields are loaded for exported events. Omitted counts are explicit.`;
}

function datasetForExport(id) {
  const dataset = state.datasets.get(id);
  if (!dataset)
    throw new Error(`No dataset provenance is registered for ${id}.`);
  const result = {};
  for (const key of [
    "id",
    "title",
    "version",
    "publisher",
    "url",
    "license",
    "sha256",
  ]) {
    if (typeof dataset[key] !== "string" || !dataset[key])
      throw new Error(
        `Dataset ${id} is missing ${key}; provenance must be complete before export.`,
      );
    result[key] = dataset[key];
  }
  return result;
}

function exportRecord(kind, row) {
  let original = attributes(row);
  if (kind === "country_indicator") {
    original = {
      ...original,
      normalized_indicator_code: row.indicator_code,
      normalized_indicator_name: row.indicator_name,
      normalized_year: row.year,
      normalized_value: row.value,
      normalized_unit: row.unit || "",
      normalized_status: row.status ?? null,
    };
  }
  const sourceAttributes = {};
  for (const [key, value] of Object.entries(original)) {
    if (
      value === null ||
      ["string", "number", "boolean"].includes(typeof value)
    )
      sourceAttributes[key] = value;
    else
      throw new Error(
        `Source attribute ${key} is not a flat value. The source row needs review before export.`,
      );
  }
  return {
    id: String(row.id),
    kind,
    dataset_id: row.dataset_id,
    label:
      kind === "conflict_event"
        ? labelOf(row)
        : `${row.indicator_name || row.indicator_code} · ${row.year}`,
    country_code: row.country_code,
    date_start:
      kind === "conflict_event" ? row.date_start : `${row.year}-01-01`,
    date_end: kind === "conflict_event" ? row.date_end : `${row.year}-12-31`,
    source_locator:
      typeof row.source_locator === "string"
        ? row.source_locator
        : JSON.stringify(row.source_locator),
    attributes: sourceAttributes,
  };
}

function downloadFile(content, name, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = element("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function markdownFor(pack) {
  const lines = [
    "# Historical research selection",
    "",
    pack.question || "Research question not yet supplied.",
    "",
    `Created: ${pack.created_at}`,
    `Country: ${pack.filters.provider_country_label} (${pack.filters.country_code})`,
    pack.filters.events
      ? `Event period: ${pack.filters.events.date_overlap.from} to ${pack.filters.events.date_overlap.to} (overlapping dates)`
      : "Annual country-indicator selection; event filters do not apply.",
    `Records: ${pack.counts.exported} exported / ${pack.counts.matched} matched; ${pack.counts.matched - pack.counts.exported} omitted.`,
    "",
    "## Dataset provenance",
    "",
  ];
  for (const dataset of pack.datasets)
    lines.push(
      `- ${dataset.title}, ${dataset.version}. ${dataset.publisher}. ${dataset.license}. ${dataset.url}`,
      `  Dataset SHA-256: ${dataset.sha256}`,
    );
  lines.push("", "## Attributed source records", "");
  for (const record of pack.records) {
    lines.push(
      `- **${record.label}** (${record.kind}); ${record.date_start} to ${record.date_end}.`,
      `  ID: ${record.id}. Dataset: ${record.dataset_id}. Source locator: ${record.source_locator}.`,
    );
    if (record.kind === "country_indicator")
      lines.push(
        `  Value: ${record.attributes.normalized_value ?? "missing"}; unit: ${record.attributes.normalized_unit || "not supplied"}.`,
      );
  }
  lines.push(
    "",
    "## Your assessment",
    "",
    pack.notes.assessment || "Not supplied.",
    "",
    "## Alternative explanations",
    "",
    pack.notes.alternatives || "Not supplied.",
    "",
    "## Evidence gaps",
    "",
    pack.notes.gaps || "Not supplied.",
    "",
    "## Limits",
    "",
    ...pack.limitations.map((limit) => `- ${limit}`),
    "",
    "This brief is not a native TACITUS knowledge context. Download the JSON selection to retain full original provider fields.",
    "",
  );
  return lines.join("\n");
}

async function exportSelection(kind) {
  abortExport();
  const candidates = selectionCandidates();
  if (!candidates.length) return;
  const controller = new AbortController();
  state.exportController = controller;
  const generation = ++state.exportGeneration;
  const snapshot = {
    created_at: new Date().toISOString(),
    question: $("brief-question").value,
    filters: selectionFilters(),
    notes: {
      assessment: $("note-assessment").value,
      alternatives: $("note-alternatives").value,
      gaps: $("note-gaps").value,
    },
    matched: candidates.length,
    candidates: candidates.slice(0, EXPORT_LIMIT),
    limitations: [
      ...new Set([
        "Historical dataset observations are attributed records, not independently corroborated findings or a live event feed.",
        "The export is a bounded first-record selection, not a representative sample or native TACITUS knowledge context.",
        "Event dates and coordinates retain provider precision; low/best/high values are provider estimates, not confidence intervals. Non-ordered values remain unchanged.",
        "Country indicators are separate annual records. No causal or event-level relationship is inferred. Missing observations are not zero.",
        "Annual indicator dates describe the calendar-year period, not an exact observation day. The event-period filter does not filter the separate annual series.",
        ...(state.manifest.limitations || []),
      ]),
    ],
  };
  $("export-json").textContent =
    kind === "json" ? "Loading original records…" : "Download selection JSON";
  $("export-markdown").textContent =
    kind === "markdown" ? "Preparing cited brief…" : "Download research brief";
  updateExportPreview();
  $("export-status").textContent =
    "Preparing the frozen selection and retrieving full original event fields. Changing filters cancels this download.";
  try {
    const groups = new Map();
    for (const item of snapshot.candidates) {
      const key =
        item.kind === "conflict_event"
          ? item.row.raw_shard || item.row.id
          : item.row.id;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(item);
    }
    const hydrated = new Map();
    let completed = 0;
    await inParallel(
      [...groups.values()],
      async (group) => {
        for (const item of group) {
          const row =
            item.kind === "conflict_event"
              ? await fullEvent(item.row, controller.signal)
              : item.row;
          hydrated.set(`${item.kind}:${row.id}`, exportRecord(item.kind, row));
        }
        completed += 1;
        if (generation === state.exportGeneration)
          $("export-status").textContent =
            `Original source groups loaded: ${completed} / ${groups.size}. Full fields are retained.`;
      },
      controller.signal,
    );
    if (controller.signal.aborted || generation !== state.exportGeneration)
      return;
    const records = snapshot.candidates.map((item) =>
      hydrated.get(`${item.kind}:${item.row.id}`),
    );
    const datasetIds = [...new Set(records.map((row) => row.dataset_id))];
    const pack = {
      format: "policy-research-selection/1",
      created_at: snapshot.created_at,
      question: snapshot.question,
      datasets: datasetIds.map(datasetForExport),
      filters: snapshot.filters,
      counts: {
        matched: snapshot.matched,
        exported: records.length,
        truncated: snapshot.matched > records.length,
        limit: EXPORT_LIMIT,
      },
      records,
      notes: snapshot.notes,
      limitations: snapshot.limitations,
    };
    for (const id of datasetIds) {
      const attribution = state.datasets.get(id)?.attribution;
      for (const credit of Array.isArray(attribution)
        ? attribution
        : attribution
          ? [attribution]
          : []) {
        pack.limitations.push(`Dataset attribution / modifications: ${credit}`);
      }
    }
    let content = "";
    while (pack.records.length) {
      pack.counts.exported = pack.records.length;
      pack.counts.truncated = pack.counts.matched > pack.counts.exported;
      const used = new Set(pack.records.map((row) => row.dataset_id));
      pack.datasets = pack.datasets.filter((dataset) => used.has(dataset.id));
      content = `${JSON.stringify(pack, null, 2)}\n`;
      if (encoder.encode(content).length <= EXPORT_BYTES) break;
      pack.records.pop();
    }
    if (!pack.records.length)
      throw new Error(
        "A complete source record and notes cannot fit within the 1 MiB selection limit. Shorten the notes or inspect the source shard directly.",
      );
    if (controller.signal.aborted || generation !== state.exportGeneration)
      return;
    const filename = `tacitus-research-${snapshot.filters.country_code}-${snapshot.created_at.slice(0, 10)}`;
    if (kind === "markdown")
      downloadFile(
        markdownFor(pack),
        `${filename}.md`,
        "text/markdown;charset=utf-8",
      );
    else
      downloadFile(
        content,
        `${filename}.json`,
        "application/json;charset=utf-8",
      );
    $("export-status").textContent =
      `Downloaded ${number.format(pack.counts.exported)} of ${number.format(pack.counts.matched)} matching records; ${number.format(pack.counts.matched - pack.counts.exported)} omitted. JSON selection size: ${number.format(encoder.encode(content).length)} bytes. Source fields and your notes are separate.`;
  } catch (error) {
    if (controller.signal.aborted || generation !== state.exportGeneration)
      return;
    controller.abort();
    $("export-status").textContent =
      `Download could not be completed. ${error.message} Retry the download; compact records will not replace missing original fields.`;
  } finally {
    if (generation === state.exportGeneration) {
      state.exportController = null;
      $("export-json").textContent = "Download selection JSON";
      $("export-markdown").textContent = "Download research brief";
      updateExportPreview();
    }
  }
}

function coverageLabel(dataset) {
  const coverage = dataset.coverage;
  if (typeof coverage === "string") return coverage;
  if (!coverage || typeof coverage !== "object") return "";
  if (coverage.date_start && coverage.date_end) {
    const count = (state.manifest.event_shards || [])
      .filter((shard) => shard.dataset_id === dataset.id)
      .reduce((sum, shard) => sum + Number(shard.count || 0), 0);
    return `${coverage.date_start.slice(0, 4)}–${coverage.date_end.slice(0, 4)} · ${number.format(count)} included historical records`;
  }
  if (Array.isArray(coverage.years)) {
    return `Annual values, ${coverage.years[0]}–${coverage.years.at(-1)}${coverage.indicator_count ? ` · ${coverage.indicator_count} indicators` : ""}${coverage.economy_count ? ` · ${coverage.economy_count} economies` : ""}. Each series has its own observed period.`;
  }
  return "See the dataset manifest for its release coverage.";
}

function renderProvenance() {
  const container = $("dataset-provenance");
  container.replaceChildren();
  for (const dataset of state.datasets.values()) {
    const card = element("section", null, "dataset-card");
    card.append(
      element("h3", dataset.title),
      element(
        "p",
        `${dataset.publisher} · ${dataset.version} · ${dataset.license}`,
      ),
    );
    if (dataset.coverage) card.append(element("p", coverageLabel(dataset)));
    const links = element("p", null, "dataset-links");
    links.append(publicLink(dataset.url, "Original dataset ↗"));
    if (dataset.codebook_url)
      links.append(publicLink(dataset.codebook_url, "Codebook ↗"));
    if (dataset.license_url)
      links.append(publicLink(dataset.license_url, "Source licence ↗"));
    card.append(links);
    if (dataset.sha256) {
      const identity = element("details");
      identity.append(
        element("summary", "Dataset build identity"),
        element("p", "Dataset / release SHA-256:"),
        element("code", dataset.sha256),
      );
      card.append(identity);
    }
    if (dataset.attribution) {
      const detail = element("details");
      detail.append(element("summary", "Attribution and modifications"));
      const credits = element("ul");
      for (const credit of Array.isArray(dataset.attribution)
        ? dataset.attribution
        : [dataset.attribution])
        credits.append(element("li", credit));
      detail.append(credits);
      card.append(detail);
    }
    const raw = (state.manifest.raw_shards || []).filter(
      (shard) =>
        shard.country_code === state.country && shard.dataset_id === dataset.id,
    );
    if (raw.length) {
      const details = element("details");
      details.append(
        element(
          "summary",
          `Original-field shards · ${currentCountry()?.name || state.country} · ${raw.length} files`,
        ),
      );
      details.addEventListener("toggle", () => {
        if (!details.open || details.querySelector("ul")) return;
        const list = element("ul");
        for (const shard of raw) {
          const item = element("li");
          const link = element(
            "a",
            `${shard.year_start}${shard.year_end !== shard.year_start ? `–${shard.year_end}` : ""}, part ${shard.part || "1"} · ${number.format(shard.count)} records${shard.encoding === "gzip" ? " · gzip JSON" : ""}`,
          );
          try {
            link.href = localURL(shard.path);
            link.download = "";
            item.append(link);
            list.append(item);
          } catch {
            /* A malformed optional download must not break the atlas. */
          }
        }
        details.append(list);
      });
      card.append(details);
    }
    container.append(card);
  }
  const limits = $("dataset-limitations");
  limits.replaceChildren();
  const all = new Set([
    "This is a historical research snapshot, not a live intelligence feed.",
    ...(state.manifest.limitations || []),
    ...[...state.datasets.values()].flatMap((dataset) =>
      Array.isArray(dataset.limitations)
        ? dataset.limitations
        : dataset.limitations
          ? [dataset.limitations]
          : [],
    ),
  ]);
  for (const limitation of all) limits.append(element("li", limitation));
}

function connectMap() {
  const canvas = $("event-map");
  let drag = null;
  canvas.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    canvas.setPointerCapture(event.pointerId);
    drag = {
      id: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      x: event.clientX,
      y: event.clientY,
      moved: false,
    };
    canvas.classList.add("dragging");
    $("map-tooltip").hidden = true;
  });
  canvas.addEventListener("pointermove", (event) => {
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    if (drag && drag.id === event.pointerId) {
      if (
        Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) > 4
      )
        drag.moved = true;
      state.camera.x -= (event.clientX - drag.x) / state.camera.scale;
      state.camera.y -= (event.clientY - drag.y) / state.camera.scale;
      drag.x = event.clientX;
      drag.y = event.clientY;
      state.mapDirty = true;
      scheduleDraw();
      return;
    }
    const point = findPoint(x, y);
    const tooltip = $("map-tooltip");
    if (point) {
      tooltip.textContent = `${labelOf(point.row)}\n${dateLabel(point.row)}\n${point.row.id}\nSelect to inspect source and precision.`;
      tooltip.style.left = `${Math.min(Math.max(8, x + 14), Math.max(8, rect.width - 270))}px`;
      tooltip.style.top = `${Math.min(Math.max(8, y + 14), Math.max(8, rect.height - 120))}px`;
      tooltip.hidden = false;
      canvas.style.cursor = "pointer";
    } else {
      tooltip.hidden = true;
      canvas.style.cursor = "grab";
    }
    if (!state.geographyError) {
      const lonLat = unproject(...mapWorld(x, y, rect.width, rect.height));
      $("map-coordinate").textContent =
        `${Math.abs(lonLat[1]).toFixed(2)}° ${lonLat[1] >= 0 ? "N" : "S"} / ${Math.abs(lonLat[0]).toFixed(2)}° ${lonLat[0] >= 0 ? "E" : "W"}`;
    }
  });
  function stopDrag(event, cancelled = false) {
    if (!drag || drag.id !== event.pointerId) return;
    const click = !drag.moved && !cancelled;
    drag = null;
    canvas.classList.remove("dragging");
    if (canvas.hasPointerCapture(event.pointerId))
      canvas.releasePointerCapture(event.pointerId);
    if (click) {
      const rect = canvas.getBoundingClientRect();
      const point = findPoint(
        event.clientX - rect.left,
        event.clientY - rect.top,
      );
      if (point) selectEvent(point.row);
    }
  }
  canvas.addEventListener("pointerup", (event) => stopDrag(event));
  canvas.addEventListener("pointercancel", (event) => stopDrag(event, true));
  canvas.addEventListener("pointerleave", () => {
    $("map-tooltip").hidden = true;
  });
  canvas.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      const rect = canvas.getBoundingClientRect();
      zoomMap(
        Math.exp(-Math.max(-100, Math.min(100, event.deltaY)) * 0.002),
        event.clientX - rect.left,
        event.clientY - rect.top,
      );
    },
    { passive: false },
  );
  canvas.addEventListener("keydown", (event) => {
    const moves = {
      ArrowLeft: [-50, 0],
      ArrowRight: [50, 0],
      ArrowUp: [0, -50],
      ArrowDown: [0, 50],
    };
    if (moves[event.key]) {
      event.preventDefault();
      state.camera.x += moves[event.key][0] / state.camera.scale;
      state.camera.y += moves[event.key][1] / state.camera.scale;
      state.mapDirty = true;
      scheduleDraw();
    } else if (["+", "=", "-", "_"].includes(event.key)) {
      event.preventDefault();
      zoomMap(event.key === "+" || event.key === "=" ? 1.4 : 1 / 1.4);
    } else if (event.key === "Home") {
      event.preventDefault();
      state.fitPending = true;
      state.mapDirty = true;
      scheduleDraw();
    }
  });
  $("zoom-in").addEventListener("click", () => zoomMap(1.5));
  $("zoom-out").addEventListener("click", () => zoomMap(1 / 1.5));
  $("fit-map").addEventListener("click", () => {
    state.fitPending = true;
    state.mapDirty = true;
    scheduleDraw();
  });
}

function connectTimeline() {
  const canvas = $("timeline");
  const atYear = (event) => {
    const rect = canvas.getBoundingClientRect();
    return Math.max(
      state.minYear,
      Math.min(
        state.maxYear,
        state.minYear +
          Math.floor(
            ((event.clientX - rect.left) / rect.width) *
              (state.maxYear - state.minYear + 1),
          ),
      ),
    );
  };
  canvas.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || !state.manifest) return;
    canvas.setPointerCapture(event.pointerId);
    state.brush = {
      start: atYear(event),
      end: atYear(event),
      pointer: event.pointerId,
    };
    state.timelineDirty = true;
    scheduleDraw();
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!state.brush || state.brush.pointer !== event.pointerId) return;
    state.brush.end = atYear(event);
    state.timelineDirty = true;
    scheduleDraw();
  });
  canvas.addEventListener("pointerup", (event) => {
    if (!state.brush || state.brush.pointer !== event.pointerId) return;
    const brush = state.brush;
    state.brush = null;
    if (canvas.hasPointerCapture(event.pointerId))
      canvas.releasePointerCapture(event.pointerId);
    updateYears(brush.start, brush.end);
    loadEvents();
  });
  canvas.addEventListener("pointercancel", () => {
    state.brush = null;
    state.timelineDirty = true;
    scheduleDraw();
  });
}

function connectControls() {
  $("country").addEventListener("change", () => {
    abortExport();
    state.country = $("country").value;
    state.compactCache.clear();
    state.compactCacheBytes = 0;
    state.rawCache.clear();
    countryYears();
    updateYears(state.from, state.to);
    renderProvenance();
    loadEvents();
    loadIndicators();
  });
  for (const id of ["year-from", "year-to"])
    $(id).addEventListener("change", () => {
      updateYears($("year-from").value, $("year-to").value);
      loadEvents();
    });
  $("retry-load").addEventListener("click", () =>
    state.manifest ? loadEvents() : initialize(),
  );
  $("event-type").addEventListener("change", () => {
    state.category = $("event-type").value;
    applyFilters();
  });
  $("event-search").addEventListener("input", () => {
    state.query = $("event-search").value.trim().toLocaleLowerCase();
    applyFilters();
  });
  $("location-precision").addEventListener("change", () => {
    state.precision = $("location-precision").value;
    applyFilters();
  });
  $("event-order").addEventListener("change", () => {
    state.order = $("event-order").value;
    applyFilters();
  });
  $("previous-page").addEventListener("click", () => {
    state.page -= 1;
    renderTable();
  });
  $("next-page").addEventListener("click", () => {
    state.page += 1;
    renderTable();
  });
  for (const [id, view] of [
    ["map-view", "map"],
    ["network-view", "network"],
  ])
    $(id).addEventListener("click", () => {
      state.view = view;
      $("map-view").setAttribute("aria-pressed", String(view === "map"));
      $("network-view").setAttribute(
        "aria-pressed",
        String(view === "network"),
      );
      $("geography-view").hidden = view !== "map";
      $("sides-view").hidden = view !== "network";
      state.mapDirty = true;
      state.networkDirty = true;
      scheduleDraw();
    });
  $("indicator-select").addEventListener("change", () => {
    abortExport();
    state.indicatorCode = $("indicator-select").value;
    renderIndicators();
    updateExportPreview();
  });
  $("export-kind").addEventListener("change", () => {
    abortExport();
    updateExportPreview();
  });
  $("export-json").addEventListener("click", () => exportSelection("json"));
  $("export-markdown").addEventListener("click", () =>
    exportSelection("markdown"),
  );
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && state.frame) {
      cancelAnimationFrame(state.frame);
      state.frame = 0;
    } else scheduleDraw();
  });
  const resize = new ResizeObserver(() => {
    state.mapDirty = true;
    state.timelineDirty = true;
    state.indicatorDirty = true;
    state.networkDirty = true;
    scheduleDraw();
  });
  for (const id of [
    "event-map",
    "timeline",
    "indicator-chart",
    "sides-network",
  ])
    resize.observe($(id));
  connectMap();
  connectTimeline();
}

function projectGeometry(geometry) {
  if (!geometry) return [];
  const polygons =
    geometry.type === "Polygon"
      ? [geometry.coordinates]
      : geometry.type === "MultiPolygon"
        ? geometry.coordinates
        : [];
  return polygons.map((polygon) =>
    polygon.map((ring) =>
      ring.map(([lon, lat]) => project(lon, lat)).filter(Boolean),
    ),
  );
}

async function loadGeography() {
  if (!state.manifest.geography) return;
  try {
    const result = await fetchJSON(state.manifest.geography);
    const data = result.value;
    const features =
      data.type === "FeatureCollection"
        ? data.features
        : data.type === "Feature"
          ? [data]
          : [{ geometry: data }];
    state.geography = features.flatMap((feature) =>
      projectGeometry(feature.geometry),
    );
    state.geographyError = false;
  } catch {
    state.geographyError = true;
  }
  state.mapDirty = true;
  scheduleDraw();
}

async function initialize() {
  $("retry-load").hidden = true;
  $("load-status").textContent = "Loading the dataset manifest…";
  try {
    const result = await fetchJSON(MANIFEST_URL, undefined, "no-store");
    const manifest = result.value;
    if (
      !Array.isArray(manifest.datasets) ||
      !Array.isArray(manifest.countries) ||
      !Array.isArray(manifest.event_shards)
    ) {
      throw new Error(
        "The manifest does not have the atlas datasets, countries and shard lists.",
      );
    }
    state.manifest = manifest;
    state.datasets = new Map(
      manifest.datasets.map((dataset) => [dataset.id, dataset]),
    );
    state.rawShards = new Map(
      (manifest.raw_shards || []).map((shard) => [shard.path, shard]),
    );
    const params = new URLSearchParams(window.location.search);
    const requestedCountry = params.get("country") || "SY";
    state.country = manifest.countries.some(
      (country) => country.code === requestedCountry,
    )
      ? requestedCountry
      : manifest.countries[0]?.code || "SY";
    $("country").replaceChildren();
    for (const country of manifest.countries) {
      const option = element("option", country.name);
      option.value = country.code;
      $("country").append(option);
    }
    $("country").value = state.country;
    for (const id of [
      "country",
      "year-from",
      "year-to",
      "event-type",
      "event-search",
      "location-precision",
    ])
      $(id).disabled = false;
    const precision =
      [...state.datasets.values()].find(
        (dataset) => dataset.kind === "conflict_event",
      )?.precision?.where_prec || {};
    const allCodes = element("option", "All provider codes");
    allCodes.value = "";
    $("location-precision").replaceChildren(allCodes);
    for (const [code, label] of Object.entries(precision)) {
      const option = element("option", `${code} · ${label}`);
      option.value = code;
      $("location-precision").append(option);
    }
    countryYears();
    updateYears(
      params.get("from") || 2020,
      params.get("to") || Math.min(2025, state.maxYear),
    );
    const count = manifest.event_shards.reduce(
      (sum, shard) => sum + Number(shard.count || 0),
      0,
    );
    const providerCountries = new Set(
      manifest.event_shards.map((shard) => shard.country_code),
    ).size;
    const years = manifest.event_shards
      .flatMap((shard) => [Number(shard.year_start), Number(shard.year_end)])
      .filter(Number.isFinite);
    $("edition-coverage").textContent =
      `${number.format(count)} recorded events · ${providerCountries} provider geographies${years.length ? ` · ${Math.min(...years)}–${Math.max(...years)}` : ""}`;
    $("build-date").textContent = manifest.built_at
      ? `Snapshot built ${manifest.built_at.slice(0, 10)}`
      : "Dated dataset releases";
    renderProvenance();
    loadGeography();
    loadEvents();
    loadIndicators();
  } catch (error) {
    state.loading = false;
    state.indicatorLoading = false;
    $("load-status").textContent =
      `The atlas could not start. ${error.message}`;
    $("edition-coverage").textContent = "Dataset manifest unavailable.";
    $("map-empty").textContent =
      "The dataset manifest could not be loaded. Use Retry loading above.";
    $("retry-load").hidden = false;
    $("map-card").setAttribute("aria-busy", "false");
    $("indicator-status").textContent =
      "Indicators are unavailable until the manifest loads.";
    renderTable();
    renderIndicators();
    updateExportPreview();
  }
}

connectControls();
initialize();
