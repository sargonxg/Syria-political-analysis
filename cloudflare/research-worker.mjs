/** Read-only D1 research API. Whole-host Cloudflare Access is configured externally. */
const API_VERSION = 'policy-research-db/1';
const PREFIX = '/api/research';
const MAX_LIMIT = 200;
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
function json(value, status = 200) {
    return Response.json(value, { status, headers: {
            'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'same-origin', 'Vary': 'Origin',
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
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000'))
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
function filters(params, state, pagination = true) {
    checkParameters(params, pagination ? [...FILTER_KEYS, 'limit', 'cursor'] : FILTER_KEYS);
    const country = params.get('country') || null;
    if (country && (!/^[A-Z]{2}$/.test(country) || !state.countries.some((item) => item.code === country)))
        fail(400, 'INVALID_COUNTRY', 'country must be one of the supplied uppercase ISO2 country codes.');
    const from = day(params.get('from') || state.snapshot.date_start, 'from');
    const to = day(params.get('to') || state.snapshot.date_end, 'to');
    if (from > to)
        fail(400, 'REVERSED_DATES', 'from must not be later than to.');
    return { country, from, to, actor: boundedText(params.get('actor') || '', 200, 'actor'),
        type: params.has('type') ? integer(params.get('type'), 1, 3, 'type') : null,
        precision: params.has('precision') ? integer(params.get('precision'), 1, 7, 'precision') : null,
        date_precision: params.has('date_precision') ? integer(params.get('date_precision'), 1, 5, 'date_precision') : null };
}
function whereEvents(filter) {
    const clauses = ['date_end >= ?', 'date_start <= ?'], bindings = [filter.from, filter.to];
    for (const [key, column] of [['country', 'country_code'], ['type', 'violence_type'], ['precision', 'geography_precision'], ['date_precision', 'date_precision']]) {
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
    return { sql: clauses.join(' AND '), bindings };
}
async function digest(text) {
    const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
    return [...new Uint8Array(bytes)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}
function encodeCursor(value) { return btoa(JSON.stringify(value)).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, ''); }
function decodeCursor(value, fingerprint, state) {
    if (value.length > 2048 || !/^[A-Za-z0-9_-]+$/.test(value))
        fail(400, 'INVALID_CURSOR', 'The page cursor is invalid.');
    let parsed;
    try {
        parsed = JSON.parse(atob(value.replaceAll('-', '+').replaceAll('_', '/')));
    }
    catch {
        fail(400, 'INVALID_CURSOR', 'The page cursor is invalid.');
    }
    if (!parsed || Object.keys(parsed).sort().join(',') !== 'date,fingerprint,id,kind,snapshot,v'
        || parsed.v !== 1 || parsed.kind !== 'events' || parsed.snapshot !== state.snapshot.id || parsed.fingerprint !== fingerprint
        || typeof parsed.id !== 'string' || !/^[A-Za-z0-9:._-]{1,200}$/.test(parsed.id))
        fail(400, 'CURSOR_MISMATCH', 'The cursor belongs to a different query or snapshot; restart the query.');
    day(parsed.date, 'cursor date');
    return parsed;
}
async function stateOf(db) {
    const rows = await db.batch([
        db.prepare('SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1'),
        db.prepare('SELECT key,value FROM research_meta'),
    ]);
    const state = Object.fromEntries(rows[1].results.map((row) => [row.key, JSON.parse(row.value)]));
    if (rows[0].results[0]?.version !== 1 || state.schema_version !== 1 || state.format !== API_VERSION || state.state !== 'ready'
        || !/^[a-f0-9]{64}$/.test(state.snapshot?.id || '') || !Array.isArray(state.countries))
        fail(503, 'DB_SCHEMA_NOT_READY', 'The research database has not completed a compatible snapshot import.');
    return state;
}
function envelope(state) {
    return { api_version: API_VERSION, status: 'ready', backend: state.backend || 'd1', runtime: state.runtime || 'cloudflare-d1', read_only: true,
        snapshot: state.snapshot, provenance: { basis: 'validated_committed_snapshot', transport: 'cloudflare_d1' } };
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
async function datasets(db) {
    const result = await db.prepare('SELECT metadata_json FROM datasets ORDER BY id').all();
    return result.results.map((row) => JSON.parse(row.metadata_json));
}
async function events(url, db, state) {
    const filter = filters(url.searchParams, state), predicate = whereEvents(filter);
    const limit = url.searchParams.has('limit') ? integer(url.searchParams.get('limit'), 1, MAX_LIMIT, 'limit') : 100;
    const fingerprint = await digest(JSON.stringify(filter));
    let pageSQL = predicate.sql, pageBindings = [...predicate.bindings];
    if (url.searchParams.has('cursor')) {
        const cursor = decodeCursor(url.searchParams.get('cursor'), fingerprint, state);
        pageSQL += ' AND (date_start < ? OR (date_start = ? AND id < ?))';
        pageBindings.push(cursor.date, cursor.date, cursor.id);
    }
    const result = await db.batch([
        db.prepare('SELECT count(*) AS matched FROM events WHERE ' + predicate.sql).bind(...predicate.bindings),
        db.prepare('SELECT record_json,id,date_start FROM events WHERE ' + pageSQL + ' ORDER BY date_start DESC,id DESC LIMIT ?').bind(...pageBindings, limit + 1),
    ]);
    const matched = result[0].results[0].matched, available = result[1].results;
    const hasMore = available.length > limit, page = available.slice(0, limit), last = page.at(-1);
    const next = hasMore ? encodeCursor({ v: 1, kind: 'events', snapshot: state.snapshot.id, fingerprint, date: last.date_start, id: last.id }) : null;
    return json({ ...envelope(state), datasets: (await datasets(db)).filter((item) => item.kind === 'conflict_event'),
        filters: filter, order: 'date_start_desc,id_desc', records: page.map((row) => parsedRecord(row, true)), matched,
        returned: page.length, limit, next_cursor: next, has_more: hasMore, page_scope: 'current_page', bounded: true, truncated: matched > page.length });
}
async function eventDetail(id, db, state) {
    const row = await db.prepare('SELECT record_json,dataset_id FROM events WHERE id=? LIMIT 1').bind(id).first();
    if (!row)
        fail(404, 'NOT_FOUND', 'This event is not present in the imported snapshot.');
    const original = JSON.parse(row.record_json), record = parsedRecord(row);
    const dataset = await db.prepare('SELECT metadata_json FROM datasets WHERE id=? LIMIT 1').bind(row.dataset_id).first();
    return json({ ...envelope(state), record, dataset: JSON.parse(dataset.metadata_json), provenance: {
            basis: 'validated_committed_snapshot', transport: 'cloudflare_d1', source_partition: original.raw_shard || null,
            manifest_sha256: state.snapshot.manifests['ucdp-ged-snapshot'], canonical_original_record_sha256: record.raw_record_sha256,
            digest_basis: 'Server-supplied digest of the retained provider fields; not an independent browser manifest attestation.',
        } });
}
async function aggregates(url, db, state) {
    const filter = filters(url.searchParams, state, false), predicate = whereEvents(filter);
    const spatial = predicate.sql + ' AND latitude IS NOT NULL AND longitude IS NOT NULL AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180';
    const result = await db.batch([
        db.prepare('SELECT count(*) AS records FROM events WHERE ' + predicate.sql).bind(...predicate.bindings),
        db.prepare('SELECT event_year AS year,count(*) AS records FROM events WHERE ' + predicate.sql + ' GROUP BY event_year ORDER BY event_year').bind(...predicate.bindings),
        db.prepare('SELECT violence_type AS type,count(*) AS records FROM events WHERE ' + predicate.sql + ' GROUP BY violence_type ORDER BY violence_type').bind(...predicate.bindings),
        db.prepare('SELECT count(*) AS records FROM events WHERE ' + spatial).bind(...predicate.bindings),
        db.prepare('SELECT CAST((longitude+180)/2 AS INTEGER) AS x,CAST((latitude+90)/2 AS INTEGER) AS y,count(*) AS records FROM events WHERE ' + spatial + ' GROUP BY x,y ORDER BY records DESC,x,y LIMIT 501').bind(...predicate.bindings),
    ]);
    return json({ ...envelope(state), filters: filter, matched: result[0].results[0].records,
        timeline: result[1].results, categories: result[2].results,
        geography: { degrees: 2, bounded: true, limit: 500, truncated: result[4].results.length > 500,
            geocoded_records: result[3].results[0].records,
            omitted_missing_or_invalid_coordinates: result[0].results[0].records - result[3].results[0].records,
            cells: result[4].results.slice(0, 500).map((row) => ({ longitude: row.x * 2 - 179, latitude: row.y * 2 - 89, records: row.records })),
            interpretation: 'Two-degree bins of provider coordinates, with their original uncertainty. Missing or invalid coordinates are omitted and counted. Counts do not establish territorial control.' } });
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
async function api(request, env) {
    validateHost(request, env);
    const url = new URL(request.url);
    if (request.url.length > 4096)
        fail(414, 'URL_TOO_LONG', 'The query URL exceeds its bound.');
    if (request.method !== 'GET')
        fail(405, 'READ_ONLY', 'The research API accepts GET requests only.');
    if (!env.RESEARCH_DB)
        return json({ api_version: API_VERSION, status: 'unconfigured', backend: 'none', read_only: true,
            error: { code: 'DB_UNCONFIGURED', message: 'No research database is bound. The static snapshot remains a separate mode.' } }, 503);
    const db = env.RESEARCH_DB, state = await stateOf(db), path = url.pathname;
    state.backend = env.RESEARCH_BACKEND === 'sqlite' ? 'sqlite' : 'd1';
    state.runtime = state.backend === 'sqlite' ? 'sqlite-local-adapter' : 'cloudflare-d1';
    if (path === PREFIX + '/status' || path === PREFIX + '/health') {
        checkParameters(url.searchParams, []);
        return json({ ...envelope(state), schema_version: 1, counts: state.counts, countries: state.countries,
            capabilities: { events: true, indicators: state.counts.indicators > 0, sources: state.counts.sources > 0,
                aggregates: true, lenses: state.counts.lenses > 0 },
            limits: { page_records: 200, actor_characters: 200, url_bytes: 4096 }, limitations: state.limitations });
    }
    if (path === PREFIX + '/events')
        return events(url, db, state);
    if (path.startsWith(PREFIX + '/events/')) {
        checkParameters(url.searchParams, []);
        return eventDetail(routeID(path, PREFIX + '/events/'), db, state);
    }
    if (path === PREFIX + '/aggregates')
        return aggregates(url, db, state);
    if (path === PREFIX + '/sources')
        return sourceProfiles(url, db, state);
    if (path === PREFIX + '/indicators')
        return indicators(url, db, state);
    if (path === PREFIX + '/datasets') {
        checkParameters(url.searchParams, []);
        return json({ ...envelope(state), datasets: await datasets(db) });
    }
    if (path === PREFIX + '/lenses') {
        checkParameters(url.searchParams, []);
        const result = await db.prepare('SELECT lens_json FROM semantic_lenses ORDER BY id').all();
        return json({ ...envelope(state), lenses: result.results.map((row) => JSON.parse(row.lens_json)) });
    }
    if (path === PREFIX + '/provenance') {
        checkParameters(url.searchParams, []);
        const result = await db.prepare('SELECT id,path,sha256,bytes,chunks FROM manifests ORDER BY id').all();
        return json({ ...envelope(state), manifests: result.results, datasets: await datasets(db) });
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
            const known = error instanceof APIError;
            const code = known ? error.code : 'DB_UNAVAILABLE';
            if (!known)
                console.error(JSON.stringify({ event: 'research_api_failure', code, request_id: crypto.randomUUID() }));
            return json({ api_version: API_VERSION, status: 'unavailable', backend: env.RESEARCH_DB ? (env.RESEARCH_BACKEND === 'sqlite' ? 'sqlite' : 'd1') : 'none', read_only: true,
                error: { code, message: known ? error.message : 'The research database could not answer this request. Retry or explicitly choose the static snapshot.' } }, known ? error.status : 503);
        }
    },
};
