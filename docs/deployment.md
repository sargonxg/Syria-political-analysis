# Run the private analysis desk

This repository contains code and deployment instructions. No cloud resource, domain, account, secret, deployment integration or running cloud service was created. The default Compose port is loopback-only. Do not expose an unprotected instance to the internet.

## Architecture and intended use

The optional FastAPI application serves a small browser client and a SQLite research library. One database holds cases, typed records, explicit links, exact claim citations, revisions and hashed session tokens. The existing country CLI, qualified political ontology and offline source atlas remain available. There is no model service, automatic scraping, URL downloader, remote embedding index or paid API dependency.

This is a **single-operator / trusted-small-workspace** design, not a multi-tenant service. Anyone with the shared access key can read and edit every case. Cases organize research and prohibit cross-case references; they are not per-user access-control boundaries. The application does not provide SSO, per-user roles, end-to-end encryption or a tamper-proof audit log. Use an authenticated private network or identity-aware HTTPS proxy as an additional boundary for sensitive work. Do not store classified material, private source identities or precise locations of vulnerable people here without a separate security assessment.

SQLite WAL supports readers alongside a writer, but requires a local filesystem on one host. Run **one app replica and one Uvicorn worker**, with a persistent local/block disk. Do not use an ephemeral container filesystem, NFS/shared network filesystem, multi-region replicas or serverless functions for the live database. A future horizontally scaled service needs a tested PostgreSQL migration and a different authentication model.

## Local installation

Python 3.12 is the tested version. From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-desk.lock
python -m pip install -e '.[dev,test]'
syria-analysis validate
syria-analysis build-atlas
analysis-desk-admin --database var/desk.sqlite3 migrate
```

Windows: activate with `.venv\Scripts\Activate.ps1`; the other commands are identical. Runtime versions are pinned in `requirements-desk.lock`; the project itself and development tools are installed separately. Refresh dependencies deliberately, audit them and rerun tests. The lock pins versions, not package hashes or a container image digest.

Supply your own private random access key of **at least 32 characters** through `SYRIA_DESK_ACCESS_KEY` or an access-controlled file named by `SYRIA_DESK_ACCESS_KEY_FILE`. No key is supplied by the repository and none was provisioned for you. Prefer a secret file or your platform's secret manager in production; do not put keys in command history, GitHub, images, URLs or browser local storage.

For a Bash loopback-only test, read a key without echoing it:

```sh
read -rsp 'Private desk key: ' SYRIA_DESK_ACCESS_KEY; echo
export SYRIA_DESK_ACCESS_KEY
export SYRIA_DESK_DATABASE=var/desk.sqlite3
export SYRIA_DESK_SECURE_COOKIE=0  # HTTP LOOPBACK ONLY
uvicorn syria_analysis.desk.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

On Windows, set the same variables in the process environment, or use a private key file and set `$env:SYRIA_DESK_ACCESS_KEY_FILE` to its path. Open `http://127.0.0.1:8000`, sign in and create a case. Python does not automatically load `.env`. Uvicorn's `--no-access-log` avoids recording search queries or record paths in access logs; exception logs must still be treated as operational data.

The desk starts empty. To import the public Syria collection explicitly:

```sh
analysis-desk-admin --database var/desk.sqlite3 import-public --root .
```

This is repeat-safe, preserves analyst edits and records provenance. Source metadata and document references are imported. Existing paraphrases become attributed **notes**, not freshly verified claims, because original source passages are not bundled. Paste permitted document text before making a new claim. The country ontology remains available through `policy-analysis --country SY ontology`; the desk does not silently relabel historical normative drafts as current political facts.

## Generic cloud container path (instructions, not an executed deployment)

Use a private single-host VM or container service that supports a durable local/block volume and an HTTPS proxy. Docker must already be installed and approved by the operator. No vendor account is assumed.

1. Check out the reviewed commit. Review `Dockerfile`, `compose.yaml` and `.dockerignore`. Build-only: `docker compose build`. This does not create a cloud resource.
2. Copy `.env.example` to an untracked, access-restricted `.env`, and supply a private key. Set `SYRIA_DESK_ALLOWED_HOSTS` to the exact proxy hostname plus `localhost,127.0.0.1`. No wildcard is accepted. Keep `SYRIA_DESK_SECURE_COOKIE=1` for HTTPS.
3. Provision a private persistent disk/volume mounted at `/data`, owned by UID/GID `10001:10001`. Docker's named volume in the supplied Compose file initializes ownership from the image's `/data` directory. A host bind mount must be prepared by its administrator. Never bake a live database into the image.
4. Keep `127.0.0.1:8000:8000` as supplied and terminate HTTPS with the operator's approved reverse proxy on the same host/private network. Add identity-aware access where available. The application must not be directly reachable on an open public port. Enforce a request-body limit of 256 KiB and reasonable request/rate/time limits at the proxy. Do not trust arbitrary forwarded headers; configure proxy trust explicitly if needed.
5. When you separately authorize running it, `docker compose up -d` starts the service. This command has **not** been executed against a cloud host in this task. Verify `/healthz`, sign-in, unauthorized API rejection, a synthetic save/reload and a backup before retaining sensitive notes.
6. Optional explicit public import: `docker compose exec desk analysis-desk-admin --database /data/desk.sqlite3 import-public --root /app`. It imports only bundled public research; there is no scheduled refresh.

The image runs as a non-root user. Compose drops capabilities, enables no-new-privileges, mounts the application read-only and provides only `/data` and a temporary directory for writes. The health check returns only `{"status":"ok"}` and checks database access; it does not disclose case names or counts. Readiness fails if storage or schema initialization fails. No workflow publishes an image, invokes this Compose service, deploys infrastructure or grants cloud access.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SYRIA_DESK_DATABASE` | `var/desk.sqlite3` locally; `/data/desk.sqlite3` in image | Persistent SQLite path |
| `SYRIA_DESK_ACCESS_KEY` | absent; startup refuses | Operator-provided shared key, minimum 32 characters |
| `SYRIA_DESK_ACCESS_KEY_FILE` | absent | Read key from an operator-mounted private file instead |
| `SYRIA_DESK_SECURE_COOKIE` | `1` | Secure cookie required by default; `0` only on HTTP loopback |
| `SYRIA_DESK_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Explicit accepted hostnames, without schemes or ports |
| `SYRIA_DESK_ATLAS` | `exports/atlas/index.html` | Operator-controlled location of bundled public atlas |

Sessions last eight hours, are stored as hashes, use HttpOnly/SameSite=Strict cookies, and can be individually signed out. Sign-in failures are throttled per observed peer. Behind a proxy, peers may share that limit, so apply an appropriate identity/rate policy at the proxy. This is not an enterprise identity service. Mutations require a custom same-origin request header; no CORS policy opens the API to third-party origins. The app enforces a 256 KiB streamed request limit and validates record shapes and URLs. URLs are never fetched by this application, so they cannot invoke a server-side metadata/SSRF endpoint.

## Backups, restore and upgrades

The database is plaintext at the application layer. Encrypt the host disk and backups, restrict filesystem access and set an appropriate retention policy. Case JSON exports contain notes, excerpts and complete revision history; they are private documents. They exclude session credentials. An individual case can be restored offline into a clean database, preserving IDs, backlinks, citation revisions and history:

```sh
analysis-desk-admin --database var/clean-desk.sqlite3 restore-case --input PRIVATE_CASE_EXPORT.json
```

This validates the whole input before one transaction installs it, rejects unknown references and conflicting IDs, and never overwrites an existing case. It is not an HTTP upload endpoint. Use a full SQLite backup for complete disaster recovery, including other cases and operator state.

Use SQLite's consistent backup API, not a raw copy of only the live `.sqlite3` file while WAL writes are occurring:

```sh
analysis-desk-admin --database var/desk.sqlite3 backup --output backups/desk-2026-11-02.sqlite3
# Container example; then copy the resulting private backup off-host securely:
docker compose exec desk analysis-desk-admin --database /data/desk.sqlite3 backup --output /data/backup-2026-11-02.sqlite3
```

Choose a **new** filename for each backup; existing files are not overwritten. A backup includes session state and is as sensitive as the live database. Keep at least one encrypted off-host copy and periodically restore into a separate private test environment. This task tested backup equality and reopening a restored database.

Restore procedure: stop the app; preserve the current database and its `-wal`/`-shm` files in a private rollback directory; install a verified backup as the live database with the correct owner/permissions; ensure stale WAL/SHM files from the old database are not left beside it; run `analysis-desk-admin --database PATH migrate`; revoke sessions; restart one instance and verify a known record. Never overwrite a live open database. Restoring a backup restores its historical session state until sessions are revoked.

```sh
analysis-desk-admin --database PATH revoke-sessions
```

Rotate the operator key separately and restart after a suspected disclosure. Migration version is tracked by SQLite `PRAGMA user_version`. Version 1 is additive initialization; a database from a newer application version is refused. Back up before upgrading, run the migration with the **new** code, and only then start it. Rolling code backward does not reverse a schema migration: restore a matching backup and code version. There is no destructive automatic downgrade.

## Verification boundaries and primary references

See [desk verification](desk-verification.md) for the exact tested commit, commands and limitations. Local API/browser tests and CI container smoke tests are different from a real cloud deployment. No cloud deployment is claimed. CI is tests/build only and does not push images or use deployment credentials.

- [FastAPI's container guide](https://fastapi.tiangolo.com/deployment/docker/) informed the direct Uvicorn/container approach instead of an obsolete framework-specific base image.
- [SQLite WAL documentation](https://sqlite.org/wal.html) supports the single-host/local-filesystem constraint.
- [Python SQLite backup API](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection.backup) is the basis of the tested backup operation.
- [Docker production Compose guidance](https://docs.docker.com/compose/how-tos/production/) supports explicit production configuration and persistent storage planning.
- [Docker build guidance](https://docs.docker.com/build/building/best-practices/) informed non-root execution, minimal runtime dependencies and build-context exclusions. The base minor-version tag permits security rebuilds; operators requiring bit-for-bit images must pin and review a tested digest.
- [GitHub Actions secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use) informed read-only workflow permissions and separation of build checks from deployment.
