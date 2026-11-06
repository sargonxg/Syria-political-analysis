import { test } from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import worker from './research-worker.mjs';
import { sqliteBinding } from './local-api.mjs';
function fixture() {
    const db = new DatabaseSync(':memory:');
    db.exec(readFileSync(new URL('./schema.sql', import.meta.url), 'utf8'));
    const dataset = { id: 'ucdp-ged-26.1', kind: 'conflict_event', title: 'Fixture', version: '26.1', publisher: 'Fixture', url: 'https://example.org/', license: 'Fixture', sha256: 'a'.repeat(64) };
    db.prepare('INSERT INTO datasets VALUES (?,?,?,?,?,?,?,?)').run(dataset.id, dataset.title, dataset.version, dataset.publisher, dataset.url, dataset.license, dataset.sha256, JSON.stringify(dataset));
    const original = JSON.parse(readFileSync(new URL('../tests/fixtures/ucdp-ged-26.1-sample.json', import.meta.url), 'utf8')).records[0];
    for (let index = 0; index < 4; index++) {
        const attrs = { ...original, id: String(index + 1), year: '2024', side_a: index === 0 ? "O'Brien Government" : 'Government', side_b: 'Civilians', type_of_violence: String(index % 3 + 1), where_prec: '1', date_prec: '1' };
        const id = `ucdp-ged:26.1:${index + 1}`, date = `2024-01-0${index + 1}`;
        const digest = createHash('sha256').update(JSON.stringify(Object.fromEntries(Object.keys(attrs).sort().map((key) => [key, attrs[key]])))).digest('hex');
        const record = { id, dataset_id: dataset.id, kind: 'conflict_event', country_code: 'SY', label: 'Fixture', date_start: date, date_end: date,
            latitude: index === 0 ? null : 35, longitude: index === 0 ? null : 38, attributes: attrs, raw_record_sha256: digest,
            raw_shard: './data/events-raw/SY/2024-001.json', source_locator: `fixture; id=${index + 1}` };
        db.prepare('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)').run(id, dataset.id, 'SY', 2024, date, date, index % 3 + 1, 1, 1, attrs.side_a, attrs.side_b, (attrs.side_a + '\n' + attrs.side_b).toLowerCase(), record.latitude, record.longitude, 1, 1, 1, digest, JSON.stringify(record));
    }
    const metadata = { format: 'policy-research-db/1', state: 'ready', schema_version: 1, snapshot: { id: 'b'.repeat(64), built_at: '2026-11-06T00:00:00Z', date_start: '2024-01-01', date_end: '2024-01-04', from_year: 2024, to_year: 2024, manifests: { 'ucdp-ged-snapshot': 'c'.repeat(64) } },
        countries: [{ code: 'SY', name: 'Syria', events: 4, indicators: 0 }], counts: { events: 4, indicators: 0, sources: 0, lenses: 0 }, limitations: ['Synthetic test data.'] };
    for (const [key, value] of Object.entries(metadata))
        db.prepare('INSERT INTO research_meta VALUES (?,?)').run(key, JSON.stringify(value));
    return { db, env: { RESEARCH_DB: sqliteBinding(db), PRIVATE_HOSTNAME: 'private.example.org', ASSETS: { fetch: async () => new Response('asset') } } };
}
async function request(path, env, options = {}) { return worker.fetch(new Request('https://private.example.org/api/research' + path, options), env); }
test('explicit unconfigured/ready health and same-host asset fallback', async () => {
    const { db, env } = fixture();
    const unavailable = await request('/status', { PRIVATE_HOSTNAME: 'private.example.org' });
    assert.equal(unavailable.status, 503);
    assert.equal((await unavailable.json()).status, 'unconfigured');
    const response = await request('/status', env), status = await response.json();
    assert.equal(status.backend, 'd1');
    assert.equal(status.schema_version, 1);
    assert.equal(status.counts.events, 4);
    assert.equal(response.headers.get('cache-control'), 'private, no-store');
    assert.equal(response.headers.get('access-control-allow-origin'), null);
    assert.equal(await (await worker.fetch(new Request('https://private.example.org/'), env)).text(), 'asset');
    db.close();
});
test('keyset pages cover all matches exactly once and cursors bind query/snapshot', async () => {
    const { db, env } = fixture();
    const first = await (await request('/events?country=SY&limit=2', env)).json();
    const second = await (await request('/events?country=SY&limit=2&cursor=' + first.next_cursor, env)).json();
    assert.deepEqual([...first.records, ...second.records].map((row) => row.id), ['ucdp-ged:26.1:4', 'ucdp-ged:26.1:3', 'ucdp-ged:26.1:2', 'ucdp-ged:26.1:1']);
    assert.equal(first.matched, 4);
    assert.equal(first.has_more, true);
    assert.equal(second.has_more, false);
    assert.equal(second.next_cursor, null);
    assert.equal(first.records[0].raw_shard, undefined);
    assert.equal(Object.keys(first.records[0].attributes).length, 15);
    assert.equal((await request('/events?country=SY&type=2&cursor=' + first.next_cursor, env)).status, 400);
    const detail = await (await request(first.records[0].detail_url.slice('/api/research'.length), env)).json();
    assert.equal(Object.keys(detail.record.attributes).length, 49);
    assert.equal(detail.record.raw_shard, undefined);
    assert.equal(detail.provenance.transport, 'cloudflare_d1');
    assert.equal(detail.provenance.manifest_sha256, 'c'.repeat(64));
    db.close();
});
test('typed filters remain bound literal values, with truthful overlaps and read-only errors', async () => {
    const { db, env } = fixture();
    const actor = await (await request('/events?actor=' + encodeURIComponent("O'Brien"), env)).json();
    assert.equal(actor.matched, 1);
    const injection = await (await request('/events?actor=' + encodeURIComponent("' OR 1=1 --"), env)).json();
    assert.equal(injection.matched, 0);
    assert.equal((await (await request('/events?from=2024-01-02&to=2024-01-03', env)).json()).matched, 2);
    for (const query of ['?limit=201', '?type=4', '?country=ZZ', '?precision=0', '?date_precision=6', '?from=2024-02-30', '?from=2025-01-01&to=2024-01-01', '?sql=DELETE', '?country=SY&country=IQ', '?cursor=bad'])
        assert.equal((await request('/events' + query, env)).status, 400, query);
    assert.equal((await request('/events', env, { method: 'POST' })).status, 405);
    assert.equal(db.prepare('SELECT count(*) AS total FROM events').get().total, 4);
    db.close();
});
test('geography excludes null coordinates and reports missing coverage without invented positions', async () => {
    const { db, env } = fixture();
    const result = await (await request('/aggregates?country=SY', env)).json();
    assert.equal(result.matched, 4);
    assert.equal(result.geography.geocoded_records, 3);
    assert.equal(result.geography.omitted_missing_or_invalid_coordinates, 1);
    assert.equal(result.geography.cells.reduce((sum, row) => sum + row.records, 0), 3);
    assert(!result.geography.cells.some((row) => row.longitude === -179 || row.latitude === -89));
    assert.equal(result.timeline[0].records, 4);
    assert.equal((await request('/aggregates?actor=Government&limit=2', env)).status, 400);
    db.close();
});
test('production host configuration and cross-origin requests fail closed without permissive CORS', async () => {
    const { db, env } = fixture();
    assert.equal((await request('/status', { RESEARCH_DB: env.RESEARCH_DB })).status, 503);
    assert.equal((await worker.fetch(new Request('https://preview.example.org/api/research/status'), env)).status, 403);
    const forbidden = await request('/status', env, { headers: { Origin: 'https://other.example.org' } });
    assert.equal(forbidden.status, 403);
    assert.equal(forbidden.headers.get('access-control-allow-origin'), null);
    assert.equal((await request('/status', env, { headers: { 'Sec-Fetch-Site': 'cross-site' } })).status, 403);
    assert.equal((await worker.fetch(new Request('http://127.0.0.1/api/research/status'), { RESEARCH_DB: env.RESEARCH_DB })).status, 200);
    db.close();
});
test('incomplete schema never claims ready and SQL errors do not leak database details', async () => {
    const { db, env } = fixture();
    db.prepare("DELETE FROM research_meta WHERE key='state'").run();
    assert.equal((await request('/status', env)).status, 503);
    const empty = new DatabaseSync(':memory:');
    const result = await request('/status', { ...env, RESEARCH_DB: sqliteBinding(empty) });
    assert.equal(result.status, 503);
    const body = await result.text();
    assert(body.includes('DB_UNAVAILABLE'));
    assert(!body.includes('no such table'));
    db.close();
    empty.close();
});
test('only a bound private-host manifest gets the explicit API gate, preserving every data hash', async () => {
    const { db, env } = fixture();
    const original = { format: 'policy-observation-atlas/1', event_shards: [{ path: './data/a.json', sha256: 'd'.repeat(64) }], raw_shards: [{ path: './data/a.json.gz', sha256: 'e'.repeat(64), decoded_sha256: 'f'.repeat(64) }] };
    const body = JSON.stringify(original);
    const assets = { async fetch(request) {
            if (request.headers.get('If-None-Match'))
                return new Response(null, { status: 304 });
            return new Response(body, { headers: { 'Content-Type': 'application/json', 'Content-Length': String(body.length), ETag: 'original', 'Last-Modified': 'date' } });
        } };
    for (const path of ['/tools/middle-east/observations/data/manifest.json', '/observations/data/manifest.json']) {
        const request = new Request('https://private.example.org' + path, { headers: { 'If-None-Match': 'original' } });
        const result = await worker.fetch(request, { ...env, ASSETS: assets });
        assert.equal(result.status, 200);
        const manifest = await result.json();
        assert.deepEqual(manifest.query_api, { enabled: true, base_url: '/api/research' });
        delete manifest.query_api;
        assert.deepEqual(manifest, original);
        assert.equal(result.headers.get('cache-control'), 'private, no-store');
        for (const header of ['etag', 'content-length', 'last-modified', 'content-encoding'])
            assert.equal(result.headers.get(header), null);
        const unbound = await worker.fetch(new Request('https://private.example.org' + path), { ASSETS: assets });
        assert.equal(await unbound.text(), body);
        assert.equal(unbound.headers.get('etag'), 'original');
    }
    const blocked = await worker.fetch(new Request('https://wrong.example.org/observations/data/manifest.json'), { ...env, ASSETS: assets });
    assert.equal(blocked.status, 403);
    const tooLarge = await worker.fetch(new Request('https://private.example.org/observations/data/manifest.json'), { ...env, ASSETS: { fetch: async () => new Response(' '.repeat(2 * 1024 * 1024 + 1)) } });
    assert.equal(tooLarge.status, 503);
    assert.equal((await tooLarge.json()).error.code, 'MANIFEST_TOO_LARGE');
    db.close();
});

test('Workbench manifest paths have their own strict format and unchanged hashes without a binding', async () => {
    const { db, env } = fixture();
    const original = { format: 'tacitus-semantic-explorer/1', graph: { path: './graph.json', sha256: 'd'.repeat(64) },
        catalog: { path: './catalog.json', sha256: 'e'.repeat(64) }, source_snapshot: { sha256: 'f'.repeat(64) } };
    const body = JSON.stringify(original);
    const assets = { fetch: async () => new Response(body, { headers: { 'Content-Type': 'application/json', ETag: 'semantic-original' } }) };
    for (const path of ['/tools/tacitus-context/semantic/manifest.json', '/semantic/manifest.json']) {
        const result = await worker.fetch(new Request('https://private.example.org' + path), { ...env, ASSETS: assets });
        assert.equal(result.status, 200);
        const manifest = await result.json();
        assert.deepEqual(manifest.query_api, { enabled: true, base_url: '/api/research' });
        delete manifest.query_api;
        assert.deepEqual(manifest, original);
        assert.equal(result.headers.get('cache-control'), 'private, no-store');
        assert.equal(result.headers.get('etag'), null);
        const unbound = await worker.fetch(new Request('https://private.example.org' + path), { ASSETS: assets });
        assert.equal(await unbound.text(), body);
        assert.equal(unbound.headers.get('etag'), 'semantic-original');
        const wrong = await worker.fetch(new Request('https://private.example.org' + path), { ...env,
            ASSETS: { fetch: async () => new Response(JSON.stringify({ format: 'policy-observation-atlas/1' })) } });
        assert.equal(wrong.status, 503);
        assert.equal((await wrong.json()).error.code, 'MANIFEST_UNAVAILABLE');
    }
    const wrongFamily = await worker.fetch(new Request('https://private.example.org/observations/data/manifest.json'), { ...env, ASSETS: assets });
    assert.equal(wrongFamily.status, 503);
    const unrelated = await worker.fetch(new Request('https://private.example.org/semantic/other-manifest.json'), { ...env, ASSETS: assets });
    assert.equal(await unrelated.text(), body);
    const blocked = await worker.fetch(new Request('https://wrong.example.org/semantic/manifest.json'), { ...env, ASSETS: assets });
    assert.equal(blocked.status, 403);
    db.close();
});
