#!/usr/bin/env node
/** Offline development adapter: the same Worker module against read-only node:sqlite. */
import { DatabaseSync } from 'node:sqlite';
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { resolve, sep, extname } from 'node:path';
import { pathToFileURL } from 'node:url';
import worker from './research-worker.mjs';
export function sqliteBinding(database) {
    return {
        prepare(sql) {
            if (!/^\s*SELECT\b/i.test(sql))
                throw new Error('The local research adapter only permits SELECT statements.');
            const build = (values = []) => ({
                bind(...parameters) { return build(parameters); },
                async all() { return { success: true, results: database.prepare(sql).all(...values) }; },
                async first() { return database.prepare(sql).get(...values) || null; },
            });
            return build();
        },
        async batch(statements) { return Promise.all(statements.map((statement) => statement.all())); },
    };
}
export function localAssets(directory) {
    const root = resolve(directory);
    const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
        '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.gz': 'application/gzip',
        '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp' };
    return { async fetch(request) {
            let path;
            try {
                path = resolve(root, '.' + decodeURIComponent(new URL(request.url).pathname));
            }
            catch {
                return new Response('Invalid path', { status: 400 });
            }
            if (path !== root && !path.startsWith(root + sep))
                return new Response('Not found', { status: 404 });
            try {
                if ((await stat(path)).isDirectory())
                    path = resolve(path, 'index.html');
                const body = await readFile(path);
                return new Response(body, { headers: { 'Content-Type': types[extname(path)] || 'application/octet-stream' } });
            }
            catch {
                return new Response('Not found', { status: 404 });
            }
        } };
}
async function main() {
    const options = Object.fromEntries(process.argv.slice(2).reduce((items, value, index, all) => {
        if (value.startsWith('--'))
            items.push([value.slice(2), all[index + 1]]);
        return items;
    }, []));
    if (!options.database)
        throw new Error('Usage: node cloudflare/local-api.mjs --database path/research.sqlite3 [--assets output/site] [--port 8790]');
    const database = new DatabaseSync(resolve(options.database), { readOnly: true });
    const env = { RESEARCH_DB: sqliteBinding(database), RESEARCH_BACKEND: 'sqlite', RESEARCH_UI_ENABLED: 'enable-api-ui' in options ? 'true' : 'false',
        ASSETS: options.assets ? localAssets(options.assets) : { fetch: async () => new Response('Static assets not configured.', { status: 404 }) } };
    const port = Number(options.port || '8790');
    if (!Number.isSafeInteger(port) || port < 1024 || port > 65535)
        throw new Error('Invalid local port');
    const server = createServer(async (request, response) => {
        try {
            const url = `http://127.0.0.1:${port}${request.url}`;
            const result = await worker.fetch(new Request(url, { method: request.method, headers: request.headers }), env);
            response.writeHead(result.status, Object.fromEntries(result.headers));
            response.end(Buffer.from(await result.arrayBuffer()));
        }
        catch {
            response.writeHead(500, { 'Content-Type': 'text/plain' });
            response.end('Local adapter failed.');
        }
    });
    server.listen(port, '127.0.0.1', () => console.log(`Read-only SQLite research API: http://127.0.0.1:${port}/api/research/status`));
    const close = () => server.close(() => { database.close(); process.exit(0); });
    process.on('SIGINT', close);
    process.on('SIGTERM', close);
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href)
    await main();
