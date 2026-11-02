"""Private single-instance API. No URL fetching, model calls or deployment actions."""

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .models import CaseWrite, Login, RecordUpdate, RecordWrite
from .store import Conflict, Store

ASSETS = Path(__file__).parent / "web"


@dataclass(frozen=True)
class Settings:
    database: Path
    access_key: str
    secure_cookie: bool = True
    allowed_hosts: tuple = ("localhost", "127.0.0.1", "testserver")

    @classmethod
    def environment(cls):
        key_file = os.getenv("SYRIA_DESK_ACCESS_KEY_FILE")
        key = (
            Path(key_file).read_text(encoding="utf-8").strip()
            if key_file
            else os.getenv("SYRIA_DESK_ACCESS_KEY", "")
        )
        return cls(
            Path(os.getenv("SYRIA_DESK_DATABASE", "var/desk.sqlite3")),
            key,
            os.getenv("SYRIA_DESK_SECURE_COOKIE", "1") != "0",
            tuple(
                v.strip()
                for v in os.getenv(
                    "SYRIA_DESK_ALLOWED_HOSTS", "localhost,127.0.0.1"
                ).split(",")
                if v.strip()
            ),
        )


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def create_app(settings=None):
    settings = settings or Settings.environment()
    if len(settings.access_key) < 32:
        raise ValueError(
            "Provide a private access key of at least 32 characters through the environment or a mounted secret file"
        )
    if not settings.allowed_hosts or "*" in settings.allowed_hosts:
        raise ValueError(
            "Configure explicit allowed hostnames; wildcard hosts are not accepted"
        )
    store = Store(settings.database)
    app = FastAPI(
        title="Syria Analysis Desk", docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.store = store
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts)
    )

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        if request.method not in ("GET", "HEAD"):
            if request.headers.get("x-desk-request") != "1":
                return JSONResponse(
                    {
                        "error": {
                            "code": "same_origin_required",
                            "message": "Use the same-origin desk client",
                        }
                    },
                    403,
                )
            chunks, length = [], 0
            async for chunk in request.stream():
                length += len(chunk)
                if length > 262144:
                    return JSONResponse(
                        {
                            "error": {
                                "code": "too_large",
                                "message": "Request exceeds 256 KiB",
                            }
                        },
                        413,
                    )
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )
        if settings.secure_cookie:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(_, exc):
        return JSONResponse(
            {"error": {"code": str(exc.status_code), "message": str(exc.detail)}},
            exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_, exc):
        # Never reflect request bodies, keys or analyst notes in error logs/responses.
        return JSONResponse(
            {
                "error": {
                    "code": "invalid_input",
                    "message": "; ".join(
                        f"{'.'.join(map(str, e['loc'][1:]))}: {e['msg']}"
                        for e in exc.errors()
                    ),
                }
            },
            422,
        )

    @app.exception_handler(Conflict)
    async def conflict(_, exc):
        return JSONResponse(
            {"error": {"code": "revision_conflict", "message": str(exc)}}, 409
        )

    @app.exception_handler(ValueError)
    async def bad_value(_, exc):
        return JSONResponse(
            {"error": {"code": "invalid_record", "message": str(exc)}}, 422
        )

    @app.exception_handler(KeyError)
    async def missing(_, exc):
        return JSONResponse(
            {"error": {"code": "not_found", "message": str(exc).strip("'")}}, 404
        )

    @app.exception_handler(sqlite3.Error)
    async def database_error(_, exc):
        return JSONResponse(
            {
                "error": {
                    "code": "storage_unavailable",
                    "message": "Storage unavailable; your draft was not saved. Contact the operator.",
                }
            },
            503,
        )

    def authenticated(request: Request):
        token = request.cookies.get("desk_session", "")
        with store.connection() as con:
            valid = con.execute(
                "SELECT 1 FROM sessions WHERE token_hash=? AND expires_at>?",
                (digest(token), time.time()),
            ).fetchone()
        if not valid:
            raise HTTPException(401, "Sign in to open this private workspace")

    @app.get("/healthz")
    def health():
        with store.connection() as con:
            con.execute("SELECT 1 FROM cases LIMIT 1").fetchone()
        return {"status": "ok"}

    @app.get("/api/session")
    def session_status(request: Request):
        try:
            authenticated(request)
            return {"authenticated": True}
        except HTTPException:
            return {"authenticated": False}

    @app.get("/favicon.ico", status_code=204)
    def favicon():
        return Response(status_code=204)

    @app.post("/api/session")
    def login(body: Login, request: Request, response: Response):
        peer = request.client.host if request.client else "unknown"
        stamp = time.time()
        with store.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            attempt = con.execute(
                "SELECT * FROM login_attempts WHERE peer=?", (peer,)
            ).fetchone()
            if attempt and attempt["reset_at"] > stamp and attempt["failures"] >= 10:
                raise HTTPException(429, "Too many attempts; wait 15 minutes")
            if not hmac.compare_digest(
                digest(body.access_key), digest(settings.access_key)
            ):
                failures = (
                    attempt["failures"] + 1
                    if attempt and attempt["reset_at"] > stamp
                    else 1
                )
                con.execute(
                    "INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)",
                    (peer, failures, stamp + 900),
                )
                # Commit the failed attempt before the HTTP exception unwinds the transaction.
                con.commit()
                raise HTTPException(401, "Access key not accepted")
            con.execute("DELETE FROM login_attempts WHERE peer=?", (peer,))
            con.execute("DELETE FROM sessions WHERE expires_at<?", (stamp,))
            token = secrets.token_urlsafe(32)
            con.execute(
                "INSERT INTO sessions VALUES(?,?)", (digest(token), stamp + 8 * 3600)
            )
        response.set_cookie(
            "desk_session",
            token,
            max_age=8 * 3600,
            httponly=True,
            secure=settings.secure_cookie,
            samesite="strict",
        )
        return {"status": "signed_in"}

    @app.delete("/api/session", dependencies=[Depends(authenticated)])
    def logout(request: Request, response: Response):
        with store.connection() as con:
            con.execute(
                "DELETE FROM sessions WHERE token_hash=?",
                (digest(request.cookies.get("desk_session", "")),),
            )
        response.delete_cookie(
            "desk_session",
            secure=settings.secure_cookie,
            httponly=True,
            samesite="strict",
        )
        return {"status": "signed_out"}

    @app.get("/api/cases", dependencies=[Depends(authenticated)])
    def cases():
        return {"items": store.cases()}

    @app.post("/api/cases", status_code=201, dependencies=[Depends(authenticated)])
    def create_case(body: CaseWrite):
        return store.create_case(body.title)

    @app.get("/api/cases/{case_id}/records", dependencies=[Depends(authenticated)])
    def records(
        case_id: str,
        q: str = Query("", max_length=200),
        kind: str = "",
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
    ):
        return store.records(case_id, q, kind, offset, limit)

    @app.post(
        "/api/cases/{case_id}/records",
        status_code=201,
        dependencies=[Depends(authenticated)],
    )
    def create_record(case_id: str, body: RecordWrite):
        return store.write(case_id, body)

    @app.get("/api/records/{rid}", dependencies=[Depends(authenticated)])
    def record(rid: str):
        return store.get(rid)

    @app.put("/api/records/{rid}", dependencies=[Depends(authenticated)])
    def update_record(rid: str, body: RecordUpdate):
        old = store.get(rid)
        return store.write(
            old["case_id"],
            RecordWrite.model_validate(body.model_dump(exclude={"revision"})),
            rid,
            body.revision,
        )

    @app.get("/api/records/{rid}/history", dependencies=[Depends(authenticated)])
    def history(rid: str):
        return {"items": store.history(rid)}

    @app.get("/api/cases/{case_id}/export", dependencies=[Depends(authenticated)])
    def export(case_id: str):
        return JSONResponse(
            store.export(case_id),
            headers={
                "Content-Disposition": 'attachment; filename="analysis-case.json"'
            },
        )

    @app.get("/api/cases/{case_id}/graph", dependencies=[Depends(authenticated)])
    def network(case_id: str):
        bundle = store.export(case_id)
        return {
            "nodes": [
                {k: r[k] for k in ("id", "kind", "title", "confidence")}
                for r in bundle["records"]
            ],
            "edges": bundle["relationships"],
            "semantics": "Explicit analyst references and cited excerpts; no inferred influence, allegiance or corroboration.",
        }

    @app.get("/")
    def index():
        return FileResponse(ASSETS / "index.html")

    @app.get("/desk.js")
    def javascript():
        return FileResponse(ASSETS / "desk.js", media_type="application/javascript")

    @app.get("/desk.css")
    def stylesheet():
        return FileResponse(ASSETS / "desk.css", media_type="text/css")

    @app.get("/atlas", dependencies=[Depends(authenticated)])
    def atlas():
        # Only the bundled public-source atlas is served, never arbitrary filesystem paths.
        path = Path(os.getenv("SYRIA_DESK_ATLAS", "exports/atlas/index.html"))
        if not path.exists():
            raise HTTPException(404, "Atlas not built; run syria-analysis build-atlas")
        result = FileResponse(path)
        # This independently generated offline artifact embeds its own script/style assets.
        result.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        return result

    return app
