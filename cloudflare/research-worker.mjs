/** Read-only D1 research API. Whole-host Cloudflare Access is configured externally. */
const API_VERSION = 'policy-research-db/1';
const PREFIX = '/api/research';
const MAX_LIMIT = 200;
const MAX_QUERY_YEARS = 6;
const MAX_CANDIDATES = 20000;
const MAX_AGGREGATE_GROUPS = 10000;
const CACHE_TTL_MS = 60000;
// Regional API policy, separate from the actual availability reported by status.
const COUNTRY_CODES = new Set(['EG', 'IL', 'IQ', 'IR', 'JO', 'LB', 'PS', 'SY', 'TR', 'YE']);
// Only snapshot metadata / aggregate values are cached. No Request, Response,
// user identity, annotations, I/O promise or per-request backend is retained.
// These bounded isolate-local caches are neither durable nor a global rate limit.
const stateCache = new WeakMap();
const aggregateCache = new WeakMap();
const quotaBackoff = new WeakMap();
const MANIFEST_FORMATS = Object.freeze({
    '/tools/middle-east/observations/data/manifest.json': 'policy-observation-atlas/1',
    '/observations/data/manifest.json': 'policy-observation-atlas/1',
    '/tools/tacitus-context/semantic/manifest.json': 'tacitus-semantic-explorer/1',
    '/semantic/manifest.json': 'tacitus-semantic-explorer/1',
});
const COMPACT_FIELDS = ['year', 'type_of_violence', 'side_a', 'side_b', 'side_a_new_id', 'side_b_new_id',
    'best', 'low', 'high', 'where_prec', 'date_prec', 'event_clarity', 'adm_1', 'adm_2', 'where_coordinates'];
const FILTER_KEYS = ['country', 'from', 'to', 'actor', 'type', 'precision', 'date_precision'];
class APIError extends Error {
    constructor(status, code, message) { super(message); this.status = status; this.code = code; }
}
function json(value, status = 200, headers = {}) {
    return Response.json(value, { status, headers: {
            'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'same-origin', 'Vary': 'Origin', ...headers,
        } });
}
function fail(status, code, message) { throw new APIError(status, code, message); }
function validateHost(request, env) {
    const url = new URL(request.url);
    const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
    if (!local) {
        if (!env.PRIVATE_HOSTNAME)
            fail(503, 'PRIVATE_HOST_UNCONFIGURED', 'The private API hostname has not been configured.');
        if (url.hostname !== env.PRIVATE_HOSTNAME)
            fail(403, 'HOST_NOT_ALLOWED', 'This hostname is not configured for the research API.');
    }
    const origin = request.headers.get('Origin');
    if ((origin && origin !== url.origin) || request.headers.get('Sec-Fetch-Site') === 'cross-site')
        fail(403, 'SAME_ORIGIN_REQUIRED', 'Use the research API from its own private site.');
}
function checkParameters(params, allowed) {
    for (const key of params.keys()) {
        if (!allowed.includes(key))
            fail(400, 'INVALID_PARAMETER', `Unsupported query parameter: ${key}.`);
        if (params.getAll(key).length !== 1)
            fail(400, 'DUPLICATE_PARAMETER', `Query parameter ${key} must appear once.`);
    }
}
function day(value, name) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000'))
        fail(400, 'INVALID_DATE', `${name} must be a real ISO calendar day.`);
    const parsed = new Date(value + 'T00:00:00Z');
    if (!Number.isFinite(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== value)
        fail(400, 'INVALID_DATE', `${name} must be a real ISO calendar day.`);
    return value;
}
function boundedText(value, maximum, name) {
    const text = value.trim();
    if ([...text].length > maximum || /[\u0000-\u001f\u007f]/.test(text))
        fail(400, 'INVALID_TEXT', `${name} exceeds its text bound or contains control characters.`);
    return text;
}
function integer(value, minimum, maximum, name) {
    if (!/^(0|[1-9]\d*)$/.test(value))
        fail(400, 'INVALID_INTEGER', `${name} must be an integer.`);
    const number = Number(value);
    if (!Number.isSafeInteger(number) || number < minimum || number > maximum)
        fail(400, 'INVALID_INTEGER', `${name} is outside its allowed range.`);
    return number;
}
function countryCode(value) {
    if (!COUNTRY_CODES.has(value))
        fail(400, 'INVALID_COUNTRY', 'An available uppercase regional country code is required.');
    return value;
}
function filters(params, pagination = true) {
    checkParameters(params, pagination ? [...FILTER_KEYS, 'limit', 'cursor', 'count'] : FILTER_KEYS);
    const country = countryCode(params.get('country'));
    const from = day(params.get('from') || '', 'from');
    const to = day(params.get('to') || '', 'to');
    if (from > to)
        fail(400, 'REVERSED_DATES', 'from must not be later than to.');
    if (Number(to.slice(0, 4)) - Number(from.slice(0, 4)) >= MAX_QUERY_YEARS)
        fail(422, 'QUERY_WINDOW_TOO_WIDE', 'Use at most six calendar years per query, or explore the full verified static snapshot.');
    return { country, from, to, actor: boundedText(params.get('actor') || '', 200, 'actor'),
        type: params.has('type') ? integer(params.get('type'), 1, 3, 'type') : null,
        precision: params.has('precision') ? integer(params.get('precision'), 1, 7, 'precision') : null,
        date_precision: params.has('date_precision') ? integer(params.get('date_precision'), 1, 5, 'date_precision') : null };
}
function queryBounds(state) {
    const bounds = state.query_bounds;
    if (bounds?.format !== 'policy-query-bounds/1' || bounds.snapshot_id !== state.snapshot.id
        || bounds.events !== state.counts.events || !Number.isSafeInteger(bounds.maximum_interval_days)
        || bounds.maximum_interval_days < 0 || bounds.maximum_interval_days > 36600
        || !bounds.country_start_year_counts || typeof bounds.country_start_year_counts !== 'object')
        return null;
    let total = 0;
    for (const [country, years] of Object.entries(bounds.country_start_year_counts)) {
        if (!COUNTRY_CODES.has(country) || !years || typeof years !== 'object' || Array.isArray(years)) return null;
        for (const [year, count] of Object.entries(years)) {
            if (!/^[1-9]\d{3}$/.test(year) || !Number.isSafeInteger(count) || count < 0) return null;
            total += count;
        }
    }
    return total === bounds.events ? bounds : null;
}
function whereEvents(filter, state) {
    const bounds = queryBounds(state);
    if (!bounds)
        fail(503, 'DB_QUERY_BOUNDS_REQUIRED', 'This snapshot needs offline-validated query bounds before event queries can run. Use the verified static snapshot.');
    if (!state.countries.some((item) => item.code === filter.country))
        fail(400, 'INVALID_COUNTRY', 'The country is not present in this snapshot.');
    const earliest = new Date(filter.from + 'T00:00:00Z');
    earliest.setUTCDate(earliest.getUTCDate() - bounds.maximum_interval_days);
    const lower = earliest.toISOString().slice(0, 10);
    const candidates = Object.entries(bounds.country_start_year_counts[filter.country] || {})
        .filter(([year]) => Number(year) >= earliest.getUTCFullYear() && Number(year) <= Number(filter.to.slice(0, 4)))
        .reduce((sum, [, count]) => sum + count, 0);
    if (candidates > MAX_CANDIDATES)
        fail(422, 'QUERY_READ_BUDGET', 'This interval exceeds the conservative 20,000 candidate-record budget. Narrow the dates or use the verified static snapshot.');
    // A validated maximum interval supplies a safe lower date_start bound.
    // Both ends seek the existing country/date index; the residual date_end
    // predicate preserves overlaps, including intervals crossing a year boundary.
    const clauses = ['country_code = ?', 'date_start >= ?', 'date_start <= ?', 'date_end >= ?'];
    const bindings = [filter.country, lower, filter.to, filter.from];
    for (const [key, column] of [['type', 'violence_type'], ['precision', 'geography_precision'], ['date_precision', 'date_precision']]) {
        if (filter[key] !== null) {
            clauses.push(column + ' = ?');
            bindings.push(filter[key]);
        }
    }
    // Literal substring rather than LIKE: no wildcards, and no D1 LIKE-pattern byte limit.
    if (filter.actor) {
        clauses.push('instr(actor_search, ?) > 0');
        bindings.push(filter.actor.toLowerCase());
    }
    return { sql: clauses.join(' AND '), bindings, candidates };
}
async function digest(text) {
    const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
    return [...new Uint8Array(bytes)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}
function encodeCursor(value) { return btoa(JSON.stringify(value)).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, ''); }
function decodeCursor(value, fingerprint) {
    if (value.length > 2048 || !/^[A-Za-z0-9_-]+$/.test(value))
        fail(400, 'INVALID_CURSOR', 'The page cursor is invalid.');
    let parsed;
    try {
        parsed = JSON.parse(atob(value.replaceAll('-', '+').replaceAll('_', '/')));
    }
    catch {
        fail(400, 'INVALID_CURSOR', 'The page cursor is invalid.');
    }
    if (!parsed || typeof parsed !== 'object' || Object.keys(parsed).sort().join(',') !== 'date,fingerprint,id,kind,snapshot,v'
        || parsed.v !== 1 || parsed.kind !== 'events' || !/^[a-f0-9]{64}$/.test(parsed.snapshot) || parsed.fingerprint !== fingerprint
        || typeof parsed.id !== 'string' || !/^[A-Za-z0-9:._-]{1,200}$/.test(parsed.id))
        fail(400, 'CURSOR_MISMATCH', 'The cursor belongs to a different query or snapshot; restart the query.');
    day(parsed.date, 'cursor date');
    return parsed;
}
async function stateOf(db) {
    const cached = stateCache.get(db);
    if (cached && cached.expires > Date.now()) return cached.state;
    const rows = await db.batch([
        db.prepare('SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1'),
        db.prepare('SELECT key,value FROM research_meta LIMIT 32'),
        db.prepare('SELECT metadata_json FROM datasets ORDER BY id LIMIT 100'),
    ]);
    const state = Object.fromEntries(rows[1].results.map((row) => [row.key, JSON.parse(row.value)]));
    if (rows[0].results[0]?.version !== 1 || state.schema_version !== 1 || state.format !== API_VERSION || state.state !== 'ready'
        || !/^[a-f0-9]{64}$/.test(state.snapshot?.id || '') || !Array.isArray(state.countries))
        fail(503, 'DB_SCHEMA_NOT_READY', 'The research database has not completed a compatible snapshot import.');
    state.datasets = rows[2].results.map((row) => JSON.parse(row.metadata_json));
    stateCache.set(db, { state, expires: Date.now() + CACHE_TTL_MS });
    return state;
}
function envelope(state) {
    return { api_version: API_VERSION, status: 'ready', backend: state.backend || 'd1', runtime: state.runtime || 'cloudflare-d1', read_only: true,
        snapshot: state.snapshot, provenance: { basis: 'validated_committed_snapshot', transport: state.backend === 'sqlite' ? 'sqlite_local_adapter' : 'cloudflare_d1' } };
}
function parsedRecord(row, compact = false) {
    const record = JSON.parse(row.record_json);
    delete record.raw_shard;
    if (compact) {
        record.attributes = Object.fromEntries(COMPACT_FIELDS.filter((key) => key in record.attributes).map((key) => [key, record.attributes[key]]));
        record.detail_url = PREFIX + '/events/' + encodeURIComponent(record.id);
    }
    return record;
}
async function events(plan, db, state) {
    const { filter, limit, fingerprint, cursor, count } = plan, predicate = whereEvents(filter, state);
    let pageSQL = predicate.sql, pageBindings = [...predicate.bindings];
    if (cursor) {
        if (cursor.snapshot !== state.snapshot.id)
            fail(400, 'CURSOR_MISMATCH', 'The cursor belongs to a different snapshot; restart the query.');
        pageSQL += ' AND (date_start < ? OR (date_start = ? AND id < ?))';
        pageBindings.push(cursor.date, cursor.date, cursor.id);
    }
    const statements = [
        db.prepare('SELECT record_json,id,date_start FROM events WHERE ' + pageSQL + ' ORDER BY date_start DESC,id DESC LIMIT ?').bind(...pageBindings, limit + 1),
    ];
    if (count === 'exact') statements.push(db.prepare('SELECT count(*) AS matched FROM events WHERE ' + predicate.sql).bind(...predicate.bindings));
    const result = await db.batch(statements);
    const matched = count === 'exact' ? result[1].results[0].matched : null, available = result[0].results;
    const hasMore = available.length > limit, page = available.slice(0, limit), last = page.at(-1);
    const next = hasMore ? encodeCursor({ v: 1, kind: 'events', snapshot: state.snapshot.id, fingerprint, date: last.date_start, id: last.id }) : null;
    return json({ ...envelope(state), datasets: state.datasets.filter((item) => item.kind === 'conflict_event'),
        filters: filter, order: 'date_start_desc,id_desc', records: page.map((row) => parsedRecord(row, true)), matched,
        returned: page.length, limit, next_cursor: next, has_more: hasMore, page_scope: 'current_page', bounded: true,
        count_scope: count === 'exact' ? 'exact_query' : 'not_requested', query_fingerprint: fingerprint,
        candidate_records_upper_bound: predicate.candidates,
        truncated: matched === null ? (hasMore || cursor ? true : false) : matched > page.length });
}
async function eventDetail(id, db, state) {
    const row = await db.prepare('SELECT record_json,dataset_id FROM events WHERE id=? LIMIT 1').bind(id).first();
    if (!row)
        fail(404, 'NOT_FOUND', 'This event is not present in the imported snapshot.');
    const original = JSON.parse(row.record_json), record = { ...original };
    delete record.raw_shard;
    const dataset = state.datasets.find((item) => item.id === row.dataset_id);
    if (!dataset) fail(503, 'DB_SCHEMA_NOT_READY', 'The event dataset is absent from this snapshot’s bounded metadata.');
    return json({ ...envelope(state), record, dataset, provenance: {
            basis: 'validated_committed_snapshot', transport: state.backend === 'sqlite' ? 'sqlite_local_adapter' : 'cloudflare_d1', source_partition: original.raw_shard || null,
            manifest_sha256: state.snapshot.manifests['ucdp-ged-snapshot'], canonical_original_record_sha256: record.raw_record_sha256,
            digest_basis: 'Server-supplied digest of the retained provider fields; not an independent browser manifest attestation.',
        } });
}
async function aggregates(filter, db, state) {
    const predicate = whereEvents(filter, state), key = state.snapshot.id + ':' + JSON.stringify(filter);
    let cache = aggregateCache.get(db);
    if (!cache) { cache = new Map(); aggregateCache.set(db, cache); }
    const cached = cache.get(key);
    if (cached && cached.expires > Date.now()) return json({ ...envelope(state), ...cached.value });
    // One indexed scan, grouped once. Derive all three views from those same
    // groups; never sample a result and label it an exact aggregate.
    const valid = 'latitude IS NOT NULL AND longitude IS NOT NULL AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180';
    const sql = 'SELECT event_year AS year,violence_type AS type,'
        + `CASE WHEN ${valid} THEN MIN(179,CAST((longitude+180)/2 AS INTEGER)) ELSE NULL END AS x,`
        + `CASE WHEN ${valid} THEN MIN(89,CAST((latitude+90)/2 AS INTEGER)) ELSE NULL END AS y,`
        + 'count(*) AS records FROM events WHERE ' + predicate.sql
        + ' GROUP BY event_year,violence_type,x,y ORDER BY event_year,violence_type,x,y LIMIT ?';
    const result = await db.prepare(sql).bind(...predicate.bindings, MAX_AGGREGATE_GROUPS + 1).all();
    if (result.results.length > MAX_AGGREGATE_GROUPS)
        fail(422, 'AGGREGATE_GROUP_BUDGET', 'This query exceeds the bounded aggregate group budget. Narrow its dates or filters. No partial totals are returned.');
    const years = new Map(), types = new Map(), cells = new Map();
    let matched = 0, geocoded = 0;
    for (const row of result.results) {
        matched += row.records;
        years.set(row.year, (years.get(row.year) || 0) + row.records);
        types.set(row.type, (types.get(row.type) || 0) + row.records);
        if (row.x === null || row.y === null) continue;
        geocoded += row.records;
        const cell = row.x + ',' + row.y, previous = cells.get(cell);
        cells.set(cell, { x: row.x, y: row.y, records: (previous?.records || 0) + row.records });
    }
    const spatial = [...cells.values()].sort((a, b) => b.records - a.records || a.x - b.x || a.y - b.y);
    const value = { filters: filter, matched, candidate_records_upper_bound: predicate.candidates,
        timeline: [...years].sort((a, b) => a[0] - b[0]).map(([year, records]) => ({ year, records })),
        categories: [...types].sort((a, b) => a[0] - b[0]).map(([type, records]) => ({ type, records })),
        geography: { degrees: 2, bounded: true, limit: 500, truncated: spatial.length > 500,
            geocoded_records: geocoded, omitted_missing_or_invalid_coordinates: matched - geocoded,
            cells: spatial.slice(0, 500).map((row) => ({ longitude: row.x * 2 - 179, latitude: row.y * 2 - 89, records: row.records })),
            interpretation: 'Two-degree bins of provider coordinates, with their original uncertainty. Missing or invalid coordinates are omitted and counted. Counts do not establish territorial control.' } };
    if (cache.size >= 16) cache.delete(cache.keys().next().value);
    cache.set(key, { expires: Date.now() + CACHE_TTL_MS, value });
    return json({ ...envelope(state), ...value });
}
async function sourceProfiles(url, db, state) {
    checkParameters(url.searchParams, ['q', 'type', 'limit', 'offset']);
    const q = boundedText(url.searchParams.get('q') || '', 200, 'q').toLowerCase();
    const type = boundedText(url.searchParams.get('type') || '', 80, 'type');
    const limit = url.searchParams.has('limit') ? integer(url.searchParams.get('limit'), 1, 200, 'limit') : 100;
    const offset = url.searchParams.has('offset') ? integer(url.searchParams.get('offset'), 0, 10000, 'offset') : 0;
    const clauses = ['1=1'], bindings = [];
    if (q) {
        clauses.push('instr(search_text,?)>0');
        bindings.push(q);
    }
    if (type) {
        clauses.push('type=?');
        bindings.push(type);
    }
    const predicate = clauses.join(' AND ');
    const result = await db.batch([
        db.prepare('SELECT count(*) AS matched FROM sources WHERE ' + predicate).bind(...bindings),
        db.prepare('SELECT profile_json FROM sources WHERE ' + predicate + ' ORDER BY name,id LIMIT ? OFFSET ?').bind(...bindings, limit, offset),
    ]);
    return json({ ...envelope(state), profiles: result[1].results.map((row) => JSON.parse(row.profile_json)),
        matched: result[0].results[0].matched, returned: result[1].results.length, limit, offset,
        has_more: offset + result[1].results.length < result[0].results[0].matched,
        interpretation: 'Attributed catalogue descriptions; retain first-party/evidence qualifications. No inferred political bias scores or ownership links.' });
}
async function indicators(url, db, state) {
    checkParameters(url.searchParams, ['country', 'indicator', 'from_year', 'to_year', 'limit', 'offset']);
    const country = url.searchParams.get('country');
    if (!country || !state.countries.some((item) => item.code === country))
        fail(400, 'INVALID_COUNTRY', 'An available uppercase country code is required.');
    const series = boundedText(url.searchParams.get('indicator') || '', 100, 'indicator');
    if (!/^[A-Z0-9._]+$/.test(series))
        fail(400, 'INVALID_INDICATOR', 'An explicit indicator code is required.');
    const from = integer(url.searchParams.get('from_year') || '1960', 1, 9999, 'from_year');
    const to = integer(url.searchParams.get('to_year') || '2025', 1, 9999, 'to_year');
    if (from > to)
        fail(400, 'REVERSED_DATES', 'from_year must not be later than to_year.');
    const limit = url.searchParams.has('limit') ? integer(url.searchParams.get('limit'), 1, 200, 'limit') : 100;
    const offset = url.searchParams.has('offset') ? integer(url.searchParams.get('offset'), 0, 10000, 'offset') : 0;
    const bindings = [country, series, from, to];
    const predicate = 'country_code=? AND indicator_id=? AND observation_year>=? AND observation_year<=?';
    const result = await db.batch([
        db.prepare('SELECT count(*) AS matched FROM indicators WHERE ' + predicate).bind(...bindings),
        db.prepare('SELECT record_json FROM indicators WHERE ' + predicate + ' ORDER BY observation_year DESC,id DESC LIMIT ? OFFSET ?').bind(...bindings, limit, offset),
    ]);
    return json({ ...envelope(state), records: result[1].results.map((row) => JSON.parse(row.record_json)), matched: result[0].results[0].matched,
        returned: result[1].results.length, limit, offset, has_more: offset + result[1].results.length < result[0].results[0].matched,
        interpretation: 'Separate annual country context. No event linkage, interpolation, causal attribution or regional aggregation.' });
}
async function preflight(url) {
    const path = url.pathname, params = url.searchParams;
    if ([PREFIX + '/status', PREFIX + '/health', PREFIX + '/datasets', PREFIX + '/lenses', PREFIX + '/provenance'].includes(path)) {
        checkParameters(params, []);
        return { path };
    }
    if (path === PREFIX + '/events' || path === PREFIX + '/aggregates') {
        const filter = filters(params, path.endsWith('/events'));
        if (path.endsWith('/aggregates')) return { path, filter };
        const limit = params.has('limit') ? integer(params.get('limit'), 1, MAX_LIMIT, 'limit') : 100;
        const count = params.has('count') ? params.get('count') : (params.has('cursor') ? 'none' : 'exact');
        if (!['exact', 'none'].includes(count)) fail(400, 'INVALID_COUNT', 'count must be exact or none.');
        const fingerprint = await digest(JSON.stringify(filter));
        const cursor = params.has('cursor') ? decodeCursor(params.get('cursor'), fingerprint) : null;
        return { path, filter, limit, count, fingerprint, cursor };
    }
    if (path.startsWith(PREFIX + '/events/')) {
        checkParameters(params, []);
        return { path, id: routeID(path, PREFIX + '/events/') };
    }
    if (path === PREFIX + '/sources') {
        checkParameters(params, ['q', 'type', 'limit', 'offset']);
        boundedText(params.get('q') || '', 200, 'q');
        boundedText(params.get('type') || '', 80, 'type');
    } else if (path === PREFIX + '/indicators') {
        checkParameters(params, ['country', 'indicator', 'from_year', 'to_year', 'limit', 'offset']);
        countryCode(params.get('country'));
        const series = boundedText(params.get('indicator') || '', 100, 'indicator');
        if (!/^[A-Z0-9._]+$/.test(series)) fail(400, 'INVALID_INDICATOR', 'An explicit indicator code is required.');
        const from = integer(params.get('from_year') || '1960', 1, 9999, 'from_year');
        const to = integer(params.get('to_year') || '2025', 1, 9999, 'to_year');
        if (from > to) fail(400, 'REVERSED_DATES', 'from_year must not be later than to_year.');
    } else fail(404, 'NOT_FOUND', 'This research endpoint does not exist.');
    if (params.has('limit')) integer(params.get('limit'), 1, MAX_LIMIT, 'limit');
    if (params.has('offset')) integer(params.get('offset'), 0, 10000, 'offset');
    return { path };
}
function routeID(path, prefix) {
    const encoded = path.slice(prefix.length);
    let id;
    try {
        id = decodeURIComponent(encoded);
    }
    catch {
        fail(400, 'INVALID_ID', 'The record identifier is malformed.');
    }
    if (!/^[A-Za-z0-9:._-]{1,200}$/.test(id))
        fail(400, 'INVALID_ID', 'The record identifier is malformed.');
    return id;
}
function quotaError(retryAt) {
    const error = new APIError(503, 'DB_QUOTA_EXHAUSTED', 'D1 reports its daily quota is exhausted. Explicitly choose the verified static snapshot; database requests are paused until the next UTC day.');
    error.retryAt = retryAt;
    return error;
}
function isDailyD1Quota(error) {
    // Never expose provider error text. Match only a named D1 daily/free-tier
    // error, including wrapped causes; generic faults are not labelled quotas.
    for (let depth = 0; error && depth < 4; depth++, error = error.cause) {
        const message = String(error.message || '').slice(0, 4096);
        if (/\bD1(?:_ERROR|_EXEC_ERROR|_QUOTA_ERROR)\b/i.test(message)
            && /daily|for the day|free tier/i.test(message) && /limit|exceed|quota/i.test(message)) return true;
    }
    return false;
}
function nextUTCDay() {
    const day = new Date();
    day.setUTCHours(24, 0, 0, 0);
    return day.valueOf();
}
async function api(request, env) {
    validateHost(request, env);
    const url = new URL(request.url);
    if (request.url.length > 4096)
        fail(414, 'URL_TOO_LONG', 'The query URL exceeds its bound.');
    if (request.method !== 'GET')
        fail(405, 'READ_ONLY', 'The research API accepts GET requests only.');
    const plan = await preflight(url); // Reject routes, parameters and malformed cursors before touching D1.
    if (!env.RESEARCH_DB)
        return json({ api_version: API_VERSION, status: 'unconfigured', backend: 'none', read_only: true,
            error: { code: 'DB_UNCONFIGURED', message: 'No research database is bound. The static snapshot remains a separate mode.' } }, 503);
    const db = env.RESEARCH_DB;
    if ((quotaBackoff.get(db) || 0) > Date.now()) throw quotaError(quotaBackoff.get(db));
    const backend = env.RESEARCH_BACKEND === 'sqlite' ? 'sqlite' : 'd1';
    const state = { ...await stateOf(db), backend, runtime: backend === 'sqlite' ? 'sqlite-local-adapter' : 'cloudflare-d1' }, path = plan.path;
    if (path === PREFIX + '/status' || path === PREFIX + '/health') {
        checkParameters(url.searchParams, []);
        return json({ ...envelope(state), schema_version: 1, counts: state.counts, countries: state.countries,
            capabilities: { events: !!queryBounds(state), indicators: state.counts.indicators > 0, sources: state.counts.sources > 0,
                aggregates: !!queryBounds(state), lenses: state.counts.lenses > 0 },
            limits: { page_records: MAX_LIMIT, actor_characters: 200, url_bytes: 4096,
                event_query_years: MAX_QUERY_YEARS, event_candidate_records: MAX_CANDIDATES, aggregate_groups: MAX_AGGREGATE_GROUPS,
                metadata_cache_seconds: CACHE_TTL_MS / 1000 }, limitations: state.limitations });
    }
    if (path === PREFIX + '/events')
        return events(plan, db, state);
    if (path.startsWith(PREFIX + '/events/')) {
        checkParameters(url.searchParams, []);
        return eventDetail(plan.id, db, state);
    }
    if (path === PREFIX + '/aggregates')
        return aggregates(plan.filter, db, state);
    if (path === PREFIX + '/sources')
        return sourceProfiles(url, db, state);
    if (path === PREFIX + '/indicators')
        return indicators(url, db, state);
    if (path === PREFIX + '/datasets') {
        checkParameters(url.searchParams, []);
        return json({ ...envelope(state), datasets: state.datasets });
    }
    if (path === PREFIX + '/lenses') {
        checkParameters(url.searchParams, []);
        const result = await db.prepare('SELECT lens_json FROM semantic_lenses ORDER BY id').all();
        return json({ ...envelope(state), lenses: result.results.map((row) => JSON.parse(row.lens_json)) });
    }
    if (path === PREFIX + '/provenance') {
        checkParameters(url.searchParams, []);
        const result = await db.prepare('SELECT id,path,sha256,bytes,chunks FROM manifests ORDER BY id').all();
        return json({ ...envelope(state), manifests: result.results, datasets: state.datasets });
    }
    fail(404, 'NOT_FOUND', 'This research endpoint does not exist.');
}
async function connectedManifest(request, env, expectedFormat) {
    validateHost(request, env);
    if (!env.ASSETS)
        fail(503, 'ASSETS_UNCONFIGURED', 'The static atlas is not configured.');
    const headers = new Headers(request.headers);
    for (const name of ['If-None-Match', 'If-Modified-Since', 'If-Range', 'Range'])
        headers.delete(name);
    headers.set('Accept-Encoding', 'identity');
    const response = await env.ASSETS.fetch(new Request(request, { headers }));
    if (!response.ok || request.method !== 'GET')
        return response;
    const reader = response.body?.getReader();
    if (!reader)
        fail(503, 'MANIFEST_UNAVAILABLE', 'The static atlas manifest could not be read.');
    const chunks = [];
    let length = 0;
    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done)
                break;
            length += value.byteLength;
            if (length > 2 * 1024 * 1024) {
                await reader.cancel();
                fail(503, 'MANIFEST_TOO_LARGE', 'The atlas manifest exceeds its bounded read size.');
            }
            chunks.push(value);
        }
    }
    finally {
        reader.releaseLock();
    }
    const bytes = new Uint8Array(length);
    let offset = 0;
    for (const chunk of chunks) {
        bytes.set(chunk, offset);
        offset += chunk.byteLength;
    }
    let manifest;
    try {
        manifest = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
    }
    catch {
        fail(503, 'MANIFEST_UNAVAILABLE', 'The static atlas manifest is not valid UTF-8 JSON.');
    }
    if (manifest.format !== expectedFormat)
        fail(503, 'MANIFEST_UNAVAILABLE', 'The static asset does not match the expected research-manifest format for this path.');
    manifest.query_api = { enabled: true, base_url: PREFIX };
    const outgoing = new Headers(response.headers);
    for (const name of ['Content-Length', 'ETag', 'Last-Modified', 'Content-Encoding'])
        outgoing.delete(name);
    outgoing.set('Content-Type', 'application/json; charset=utf-8');
    outgoing.set('Cache-Control', 'private, no-store');
    outgoing.set('X-Content-Type-Options', 'nosniff');
    return new Response(JSON.stringify(manifest), { status: response.status, headers: outgoing });
}
export default {
    async fetch(request, env) {
        const path = new URL(request.url).pathname;
        try {
            if (Object.hasOwn(MANIFEST_FORMATS, path) && env.RESEARCH_DB && env.RESEARCH_UI_ENABLED !== 'false')
                return await connectedManifest(request, env, MANIFEST_FORMATS[path]);
            if (path !== PREFIX && !path.startsWith(PREFIX + '/')) {
                if (env.ASSETS)
                    return env.ASSETS.fetch(request);
                return new Response('Static assets are not configured.', { status: 503 });
            }
            return await api(request, env);
        }
        catch (error) {
            if (env.RESEARCH_DB && isDailyD1Quota(error)) {
                const retryAt = nextUTCDay();
                quotaBackoff.set(env.RESEARCH_DB, retryAt);
                stateCache.delete(env.RESEARCH_DB);
                aggregateCache.delete(env.RESEARCH_DB);
                error = quotaError(retryAt);
            }
            const known = error instanceof APIError;
            const code = known ? error.code : 'DB_UNAVAILABLE';
            if (!known)
                console.error(JSON.stringify({ event: 'research_api_failure', code, request_id: crypto.randomUUID() }));
            return json({ api_version: API_VERSION, status: 'unavailable', backend: env.RESEARCH_DB ? (env.RESEARCH_BACKEND === 'sqlite' ? 'sqlite' : 'd1') : 'none', read_only: true,
                ...(error?.retryAt ? { retry_at: new Date(error.retryAt).toISOString(), fallback: { mode: 'static', automatic: false } } : {}),
                error: { code, message: known ? error.message : 'The research database could not answer this request. Retry or explicitly choose the static snapshot.' } }, known ? error.status : 503,
                error?.retryAt ? { 'Retry-After': String(Math.max(1, Math.ceil((error.retryAt - Date.now()) / 1000))) } : {});
        }
    },
};
