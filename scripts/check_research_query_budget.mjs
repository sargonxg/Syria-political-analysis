#!/usr/bin/env node
/** Offline, full-snapshot query-plan proof. No remote calls; database opened read-only. */
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { writeFile } from 'node:fs/promises';
import worker from '../cloudflare/research-worker.mjs';
import { sqliteBinding } from '../cloudflare/local-api.mjs';

const [database, output] = process.argv.slice(2);
if (!database || !output) throw new Error('Usage: node scripts/check_research_query_budget.mjs path/research.sqlite3 path/report.json');
const db = new DatabaseSync(database, { readOnly: true });
const binding = sqliteBinding(db), queries = [];
const env = { RESEARCH_BACKEND: 'sqlite', RESEARCH_DB: {
  prepare(sql) {
    const build = (values = []) => ({
      bind(...parameters) { return build(parameters); },
      async all() {
        queries.push({ sql, values, plan: db.prepare('EXPLAIN QUERY PLAN ' + sql).all(...values).map((row) => row.detail) });
        return binding.prepare(sql).bind(...values).all();
      },
      async first() { return (await this.all()).results[0] || null; },
    });
    return build();
  },
  batch(statements) { return Promise.all(statements.map((statement) => statement.all())); },
} };
const get = async (path) => {
  const response = await worker.fetch(new Request('http://127.0.0.1/api/research' + path), env);
  return { status: response.status, body: await response.json() };
};
try {
  const scope = 'country=SY&from=2020-01-01&to=2025-12-31&actor=SDF&limit=200';
  const first = await get('/events?' + scope);
  assert.equal(first.status, 200);
  const legacySQL = 'SELECT count(*) AS matched FROM events WHERE date_end >= ? AND date_start <= ? AND country_code=? AND instr(actor_search,?)>0';
  const legacyValues = ['2020-01-01', '2025-12-31', 'SY', 'sdf'];
  const expected = db.prepare(legacySQL).get(...legacyValues).matched;
  assert.equal(first.body.matched, expected);
  const firstQueries = queries.splice(0), eventQueries = firstQueries.filter((row) => row.sql.includes('FROM events'));
  assert.equal(eventQueries.length, 2);
  for (const query of eventQueries)
    assert(query.plan.some((line) => /SEARCH events USING INDEX .*country.*date_start>\? AND date_start<\?/.test(line)), 'Both ends of the country/date index must bound event reads');
  const second = await get('/events?' + scope + '&cursor=' + first.body.next_cursor);
  assert.equal(second.status, 200);
  assert.equal(second.body.matched, null);
  assert.equal(second.body.count_scope, 'not_requested');
  assert.equal(queries.length, 1);
  assert(!queries[0].sql.includes('count(*)'));
  const continuationQueries = queries.splice(0);
  const allIDs = [...first.body.records, ...second.body.records].map((row) => row.id);
  let cursor = second.body.next_cursor, pages = 2;
  while (cursor && pages < 20) {
    const next = await get('/events?' + scope + '&cursor=' + cursor);
    assert.equal(next.status, 200);
    assert.equal(next.body.matched, null);
    assert.equal(queries.length, 1);
    continuationQueries.push(...queries.splice(0));
    allIDs.push(...next.body.records.map((row) => row.id));
    cursor = next.body.next_cursor;
    pages++;
  }
  assert.equal(cursor, null, 'The proof query must finish within twenty bounded pages');
  assert.equal(allIDs.length, expected);
  assert.equal(new Set(allIDs).size, expected);
  const aggregate = await get('/aggregates?country=SY&from=2020-01-01&to=2025-12-31&actor=SDF');
  assert.equal(aggregate.status, 200);
  assert.equal(aggregate.body.matched, expected);
  assert.equal(aggregate.body.timeline.reduce((sum, row) => sum + row.records, 0), expected);
  assert.equal(aggregate.body.categories.reduce((sum, row) => sum + row.records, 0), expected);
  assert.equal(aggregate.body.geography.geocoded_records + aggregate.body.geography.omitted_missing_or_invalid_coordinates, expected);
  assert.equal(queries.length, 1);
  const aggregateQueries = queries.splice(0);
  await get('/aggregates?country=SY&from=2020-01-01&to=2025-12-31&actor=SDF');
  assert.equal(queries.length, 0);
  const refused = await get('/aggregates?country=SY&from=2012-01-01&to=2017-12-31');
  assert.equal(refused.status, 422);
  assert.equal(refused.body.error.code, 'QUERY_READ_BUDGET');
  assert.equal(queries.length, 0);
  const report = { passed: true, backend: 'local_sqlite_read_only', remote_calls: 0,
    snapshot: first.body.snapshot.id, total_events: db.prepare('SELECT count(*) AS records FROM events').get().records,
    matched: expected, candidate_records_upper_bound: first.body.candidate_records_upper_bound,
    first_page_queries: firstQueries, continuation_queries: continuationQueries, aggregate_queries: aggregateQueries,
    identical_aggregate_queries_after_cache: 0, over_budget_event_statements: 0,
    legacy_comparison: { sql: legacySQL, values: legacyValues, plan: db.prepare('EXPLAIN QUERY PLAN ' + legacySQL).all(...legacyValues).map((row) => row.detail) },
    limitation: 'SQLite query plans and counts are local evidence, not D1 billing measurements or remote readiness.' };
  await writeFile(output, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ passed: true, matched: expected, candidate_upper_bound: first.body.candidate_records_upper_bound, report: output }));
} finally { db.close(); }
