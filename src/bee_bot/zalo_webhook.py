"""Durable receive-only Zalo webhook. Does not call Hermes or send messages."""

import json
import logging
import os
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .errors import BeeBotError
from .zalo import ZaloIngress

logger = logging.getLogger(__name__)
MAX_BODY_BYTES = 64 * 1024


def create_app(ingress: ZaloIngress) -> Starlette:
    """Acknowledge only after authenticated update is committed to durable inbox."""

    async def health(request: Request):
        return JSONResponse({"ok": True})

    async def webhook(request: Request):
        secret = request.headers.get("X-Bot-Api-Secret-Token")
        try:
            # Authenticate before parsing/storing any untrusted JSON content.
            ingress.verify_webhook_secret(secret)
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_BODY_BYTES:
                    return JSONResponse({"ok": False, "error": "BODY_TOO_LARGE"}, status_code=413)
                body.extend(chunk)
            try:
                payload = json.loads(body)
            except (ValueError, UnicodeError, RecursionError):
                return JSONResponse({"ok": False, "error": "INVALID_JSON"}, status_code=400)
            await run_in_threadpool(ingress.receive_webhook, payload, secret)
        except BeeBotError as exc:
            if exc.code in {"ZALO_UNAUTHORIZED", "ZALO_UNKNOWN_USER", "ZALO_IDENTITY_CHANGED"}:
                status = 403
            elif exc.code in {"ZALO_UNSUPPORTED_CHAT", "ZALO_UNSUPPORTED_EVENT"}:
                status = 422
            elif exc.code == "EVENT_CONFLICT":
                status = 409
            else:
                status = 400
            return JSONResponse({"ok": False, "error": exc.code}, status_code=status)
        except Exception as exc:
            logger.error("Zalo inbox receive failed (%s)", type(exc).__name__)
            return JSONResponse({"ok": False, "error": "INBOX_UNAVAILABLE"}, status_code=503)
        # Do not echo text, identifiers, event ID, or connection configuration.
        # Duplicate deliveries get the same persisted acknowledgement.
        return JSONResponse({"ok": True})

    return Starlette(routes=[
        Route("/health", health, methods=["GET"]),
        Route("/zalo/webhook", webhook, methods=["POST"]),
    ])


def app_from_env() -> Starlette:
    """Uvicorn factory; reads only explicitly configured local ingress settings."""
    secret = os.environ.get("ZALO_WEBHOOK_SECRET", "")
    identities_path = os.environ.get("BEE_BOT_ZALO_IDENTITIES")
    if not identities_path:
        raise BeeBotError("ZALO_CONFIG", "Cần cấu hình tệp liên kết danh tính Zalo.")
    try:
        identities = json.loads(Path(identities_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise BeeBotError("ZALO_CONFIG", "Không đọc được tệp liên kết danh tính Zalo.") from None
    ingress = ZaloIngress(
        os.environ.get("BEE_BOT_ZALO_INBOX", ".bee-bot/zalo-inbox.db"),
        identities=identities, webhook_secret=secret,
    )
    return create_app(ingress)
