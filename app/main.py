from __future__ import annotations

import base64
import os
import secrets
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.auth import (
    SESSION_COOKIE_NAME,
    create_session_token,
    get_session_cookie_secure,
    get_session_max_age_seconds,
    validate_admin_secret,
    validate_session_token,
)
from app.config import AppConfig, WebhookConfig, load_config
from app.db import EventStore


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return load_config()


@lru_cache(maxsize=1)
def get_store() -> EventStore:
    return EventStore(db_path=os.getenv("DB_PATH", "data/webhooks.db"))


app = FastAPI(
    title="LightWebHook",
    description="Lightweight webhook receiver with status and event APIs.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def startup() -> None:
    get_store().init_db()
    get_config()


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    filtered_headers: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() == "x-webhook-secret":
            continue
        filtered_headers[key] = value
    return filtered_headers


def get_webhook_config(name: str) -> WebhookConfig:
    config = get_config()
    webhook = config.webhooks.get(name)
    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown webhook '{name}'",
        )
    return webhook


def has_admin_session(request: Request) -> bool:
    return validate_session_token(request.cookies.get(SESSION_COOKIE_NAME), get_config().admin_secret)


def require_admin(
    request: Request,
    admin_secret: Annotated[str | None, Header(alias="X-Admin-Secret")] = None,
) -> None:
    configured_secret = get_config().admin_secret
    if validate_admin_secret(admin_secret, configured_secret) or has_admin_session(request):
        return

    if admin_secret is None and not request.cookies.get(SESSION_COOKIE_NAME):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid admin authentication",
    )


class LoginRequest(BaseModel):
    username: str
    password: str


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)


@app.get("/admin/login", include_in_schema=False)
def admin_login_page(request: Request) -> FileResponse | RedirectResponse:
    if has_admin_session(request):
        return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/admin", include_in_schema=False)
def admin_panel_page(request: Request) -> FileResponse | RedirectResponse:
    if not has_admin_session(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    return FileResponse(STATIC_DIR / "admin.html")


@app.get("/auth/session")
def auth_session(request: Request) -> dict[str, str | bool]:
    if has_admin_session(request):
        return {
            "authenticated": True,
            "username": get_config().admin_username,
        }

    return {"authenticated": False}


@app.post("/auth/login")
def auth_login(payload: LoginRequest, response: Response) -> dict[str, str | bool]:
    config = get_config()
    valid_username = payload.username.strip() == config.admin_username
    valid_password = validate_admin_secret(payload.password, config.admin_secret)
    if not valid_username or not valid_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid username or password",
        )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_token(config.admin_secret),
        max_age=get_session_max_age_seconds(),
        httponly=True,
        samesite="strict",
        secure=get_session_cookie_secure(),
        path="/",
    )
    return {"authenticated": True, "username": config.admin_username}


@app.post("/auth/logout")
def auth_logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        samesite="strict",
        secure=get_session_cookie_secure(),
        httponly=True,
    )
    return {"authenticated": False}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/{name}", status_code=status.HTTP_202_ACCEPTED)
async def receive_webhook(name: str, request: Request) -> dict[str, str | int]:
    webhook = get_webhook_config(name)
    incoming_secret = request.headers.get("X-Webhook-Secret")
    if not incoming_secret or not secrets.compare_digest(incoming_secret, webhook.secret):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook secret",
        )

    body = await request.body()
    try:
        payload = body.decode("utf-8")
        payload_encoding = "utf-8"
    except UnicodeDecodeError:
        payload = base64.b64encode(body).decode("ascii")
        payload_encoding = "base64"

    received_at = utc_now_iso()
    event_id = get_store().record_event(
        webhook_name=name,
        received_at=received_at,
        payload=payload,
        payload_encoding=payload_encoding,
        content_type=request.headers.get("content-type"),
        headers=redact_headers(dict(request.headers)),
    )

    return {
        "accepted": True,
        "webhook": name,
        "event_id": event_id,
        "received_at": received_at,
    }


@app.get("/status/{name}", dependencies=[Depends(require_admin)])
def webhook_status(name: str) -> dict[str, str | int | bool | None]:
    get_webhook_config(name)
    return get_store().get_status(name)


@app.get("/events/{name}", dependencies=[Depends(require_admin)])
def webhook_events(
    name: str,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> dict[str, object]:
    get_webhook_config(name)
    events = get_store().get_events(name, limit)
    return {
        "webhook": name,
        "count": len(events),
        "events": events,
    }


@app.post("/reset/{name}", dependencies=[Depends(require_admin)])
def reset_webhook(name: str) -> dict[str, str | int]:
    get_webhook_config(name)
    deleted_events = get_store().reset(name)
    return {
        "webhook": name,
        "deleted_events": deleted_events,
        "reset_at": utc_now_iso(),
    }


@app.get("/list", dependencies=[Depends(require_admin)])
def list_webhooks() -> dict[str, object]:
    config = get_config()
    statuses = get_store().list_statuses(sorted(config.webhooks))
    for status_item in statuses:
        description = config.webhooks[status_item["webhook"]].description
        if description:
            status_item["description"] = description

    return {"webhooks": statuses}
