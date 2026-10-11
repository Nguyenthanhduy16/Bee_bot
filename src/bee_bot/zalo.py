"""Zalo Bot API transport primitives; not a registered/live bot or Hermes gateway.

Official contract: https://bot.zapps.me/docs/ . No token is loaded implicitly,
no network call occurs at import, and no outbound action is retried blindly.
"""

from dataclasses import asdict, dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
from pathlib import Path
import sqlite3
from urllib.parse import urlparse

import httpx

from .errors import BeeBotError


logger = logging.getLogger(__name__)


class _TokenRedactor(logging.Filter):
    def __init__(self, token):
        super().__init__()
        self._token = token

    def filter(self, record):
        message = record.getMessage()
        if self._token in message:
            record.msg = message.replace(self._token, "<redacted>")
            record.args = ()
        return True


class ZaloBotClient:
    """Small synchronous Bot API client. Callers explicitly authorize live use."""

    def __init__(self, token: str, *, transport=None, timeout=15):
        if not isinstance(token, str) or not token or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:_-" for c in token):
            raise BeeBotError("ZALO_CONFIG", "Bot token chưa được cấu hình đúng.")
        self._token = token
        self._redactor = _TokenRedactor(token)
        self._loggers = [logging.getLogger(name) for name in ("httpx", "httpcore.http11", "httpcore.http2", "httpcore.connection")]
        for logger in self._loggers:
            logger.addFilter(self._redactor)
        self._client = httpx.Client(transport=transport, timeout=timeout, follow_redirects=False)

    def close(self):
        self._client.close()
        for logger in self._loggers:
            logger.removeFilter(self._redactor)

    def __repr__(self):
        return "ZaloBotClient(token=<redacted>)"

    def _call(self, method, payload=None, *, timeout=None, changes_state=False):
        try:
            response = self._client.post(
                f"https://bot-api.zaloplatforms.com/bot{self._token}/{method}",
                json=payload or {}, timeout=timeout or self._client.timeout,
            )
        except httpx.RequestError:
            code = "ZALO_DELIVERY_UNCERTAIN" if changes_state else "ZALO_UNAVAILABLE"
            raise BeeBotError(code, "Không xác minh được phản hồi Zalo; không tự gửi lại thao tác.") from None
        # Do not expose upstream description, request URLs or token-containing exceptions.
        if not 200 <= response.status_code < 300:
            code = "ZALO_DELIVERY_UNCERTAIN" if changes_state and response.status_code >= 500 else "ZALO_API_ERROR"
            raise BeeBotError(code, "Zalo từ chối hoặc chưa xác minh được thao tác; cần kiểm tra trạng thái.")
        try:
            data = response.json()
        except ValueError:
            code = "ZALO_DELIVERY_UNCERTAIN" if changes_state else "ZALO_INVALID_RESPONSE"
            raise BeeBotError(code, "Phản hồi Zalo không hợp lệ; cần kiểm tra trước khi gửi lại.") from None
        if not isinstance(data, dict) or data.get("ok") not in (True, False) or (data.get("ok") is True and "result" not in data):
            code = "ZALO_DELIVERY_UNCERTAIN" if changes_state else "ZALO_INVALID_RESPONSE"
            raise BeeBotError(code, "Phản hồi Zalo thiếu kết quả xác minh; cần kiểm tra trước khi gửi lại.")
        if data.get("ok") is not True:
            # Fresh bots were observed to report absent webhook as this exact
            # API envelope (HTTP 200), not a successful empty result. Do not
            # treat transport 404, auth failures or other methods as empty.
            if (method == "getWebhookInfo" and response.status_code == 200
                    and data.get("ok") is False and type(data.get("error_code")) is int
                    and data["error_code"] == 404 and data.get("description") == "Not Found"):
                return {"url": ""}
            if (method == "getUpdates" and response.status_code == 200
                    and data.get("ok") is False and type(data.get("error_code")) is int
                    and data["error_code"] == 408 and data.get("description") == "Request timeout"):
                # The API completed an idle long poll. A transport timeout or
                # the same error on a send is still a failure/uncertain result.
                return None
            raise BeeBotError("ZALO_API_ERROR", "API Zalo không xác nhận thao tác thành công.")
        return data["result"]

    def get_me(self):
        return self._call("getMe")

    def get_webhook_info(self):
        return self._call("getWebhookInfo")

    def get_updates(self, timeout=30):
        if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 60:
            raise BeeBotError("ZALO_ARGUMENTS", "Timeout polling phải trong khoảng 1–60 giây.")
        # Unlike Telegram, the official Zalo contract does not document an offset.
        return self._call("getUpdates", {"timeout": str(timeout)}, timeout=timeout + 10)

    def send_message(self, chat_id: str, text: str):
        if not isinstance(chat_id, str) or not chat_id or not isinstance(text, str) or not 1 <= len(text) <= 2000:
            raise BeeBotError("ZALO_ARGUMENTS", "Cần chat_id và nội dung từ 1 tới 2000 ký tự.")
        return self._call("sendMessage", {"chat_id": chat_id, "text": text}, changes_state=True)

    def set_webhook(self, url: str, secret_token: str):
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise BeeBotError("ZALO_ARGUMENTS", "Webhook cần URL HTTPS công khai.")
        if not isinstance(secret_token, str) or not 8 <= len(secret_token) <= 256:
            raise BeeBotError("ZALO_ARGUMENTS", "Webhook secret phải từ 8 tới 256 ký tự.")
        return self._call("setWebhook", {"url": url, "secret_token": secret_token}, changes_state=True)

    def delete_webhook(self):
        return self._call("deleteWebhook", changes_state=True)


@dataclass(frozen=True)
class IncomingText:
    event_id: str
    sender_id: str
    chat_id: str
    message_id: str
    text: str
    received_at: str | None
    display_name: str | None = None


def parse_update(payload: dict) -> IncomingText:
    """Accept documented API envelope or its already-unwrapped result."""
    if not isinstance(payload, dict):
        raise BeeBotError("ZALO_INVALID_UPDATE", "Sự kiện Zalo không hợp lệ.")
    if "result" in payload:
        if payload.get("ok") is not True or not isinstance(payload["result"], dict):
            raise BeeBotError("ZALO_INVALID_UPDATE", "Sự kiện Zalo không hợp lệ.")
        payload = payload["result"]
    if payload.get("event_name") != "message.text.received":
        raise BeeBotError("ZALO_UNSUPPORTED_EVENT", "Bản thử chỉ tiếp nhận tin nhắn văn bản riêng.")
    message = payload.get("message")
    if not isinstance(message, dict):
        raise BeeBotError("ZALO_INVALID_UPDATE", "Sự kiện thiếu thông tin tin nhắn.")
    sender, chat = message.get("from"), message.get("chat")
    if not isinstance(sender, dict) or not isinstance(chat, dict):
        raise BeeBotError("ZALO_INVALID_UPDATE", "Sự kiện thiếu người gửi hoặc cuộc trò chuyện.")
    if sender.get("is_bot") is not False or chat.get("chat_type") != "PRIVATE":
        raise BeeBotError("ZALO_UNSUPPORTED_CHAT", "Chỉ tiếp nhận tin nhắn riêng từ người dùng.")
    sender_id, chat_id, message_id, text = sender.get("id"), chat.get("id"), message.get("message_id"), message.get("text")
    if not all(isinstance(value, str) and value for value in (sender_id, chat_id, message_id, text)):
        raise BeeBotError("ZALO_INVALID_UPDATE", "Tin nhắn thiếu định danh hoặc nội dung.")
    identity = json.dumps([sender_id, chat_id, message_id], separators=(",", ":"))
    event_id = "zalo:" + hashlib.sha256(identity.encode()).hexdigest()
    received_at = None
    if message.get("date") is not None:
        try:
            date = message["date"]
            if isinstance(date, bool) or not isinstance(date, (int, float)):
                raise ValueError
            received_at = datetime.fromtimestamp(date / 1000, timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            raise BeeBotError("ZALO_INVALID_UPDATE", "Thời gian tin nhắn Zalo không hợp lệ.") from None
    display_name = sender.get("display_name")
    if isinstance(display_name, str):
        display_name = " ".join(display_name.split())
        if not 1 <= len(display_name) <= 80 or not display_name.isprintable():
            display_name = None
    else:
        display_name = None
    return IncomingText(event_id, sender_id, chat_id, message_id, text, received_at, display_name)


class ZaloIngress:
    """Verified identity and durable inbound dedup, independent of conversation engine.

    A callback receives (trusted_actor_id, IncomingText) and returns JSON. The
    callback must bind Hermes tools to that actor and propagate event_id to
    service mutations. There is no live Hermes callback supplied in this module.
    """

    def __init__(self, db_path, *, identities: dict[str, str], webhook_secret: str):
        if not isinstance(webhook_secret, str) or not 8 <= len(webhook_secret) <= 256:
            raise BeeBotError("ZALO_CONFIG", "Cần cấu hình webhook secret riêng.")
        if not isinstance(identities, dict) or any(not isinstance(k, str) or not k or not isinstance(v, str) or not v for k, v in identities.items()):
            raise BeeBotError("ZALO_CONFIG", "Ánh xạ người dùng Zalo cần được quản trị viên cấu hình.")
        self._identities, self._secret = dict(identities), webhook_secret
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS zalo_inbox (event_id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, result TEXT)")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def verify_webhook_secret(self, secret_header):
        if not isinstance(secret_header, str) or not hmac.compare_digest(secret_header.encode(), self._secret.encode()):
            raise BeeBotError("ZALO_UNAUTHORIZED", "Webhook chưa được xác thực.")

    def receive_webhook(self, payload, secret_header):
        self.verify_webhook_secret(secret_header)
        return self._receive(parse_update(payload))

    def receive_polled(self, payload):
        """Only pass updates read by the trusted authenticated polling transport."""
        return self._receive(parse_update(payload))

    def _receive(self, event):
        actor_id = self._identities.get(event.sender_id)
        if actor_id is None:
            raise BeeBotError("ZALO_UNKNOWN_USER", "Tài khoản Zalo chưa được liên kết với labcoach hoặc vận hành.")
        encoded = json.dumps(asdict(event), ensure_ascii=False, sort_keys=True)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT actor_id,payload,status FROM zalo_inbox WHERE event_id=?", (event.event_id,)).fetchone()
            if old:
                previous = json.loads(old[1])
                current = asdict(event)
                # A display name is presentation data and may change between
                # deliveries of the same message. It does not define identity.
                previous.pop("display_name", None)
                current.pop("display_name", None)
                if old[0] != actor_id or previous != current:
                    raise BeeBotError("EVENT_CONFLICT", "Mã sự kiện trùng nhưng dữ liệu hoặc danh tính không khớp.")
                return {"event_id": event.event_id, "status": old[2], "duplicate": True}
            db.execute("INSERT INTO zalo_inbox VALUES (?,?,?,'pending',NULL)", (event.event_id, actor_id, encoded))
        return {"event_id": event.event_id, "status": "pending", "duplicate": False}

    def process(self, event_id, handler):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT actor_id,payload,status,result FROM zalo_inbox WHERE event_id=?", (event_id,)).fetchone()
            if row is None:
                raise BeeBotError("NOT_FOUND", "Không tìm thấy sự kiện Zalo.")
            event = IncomingText(**json.loads(row[1]))
            if self._identities.get(event.sender_id) != row[0]:
                raise BeeBotError("ZALO_IDENTITY_CHANGED", "Liên kết tài khoản đã thay đổi; cần xác minh trước khi xử lý.")
            if row[2] == "completed":
                return {"event_id": event_id, "status": "completed", "result": json.loads(row[3]), "duplicate": True}
            if row[2] != "pending":
                return {"event_id": event_id, "status": row[2], "requires_reconciliation": True}
            db.execute("UPDATE zalo_inbox SET status='processing' WHERE event_id=?", (event_id,))
        try:
            result = handler(row[0], event)
            encoded = json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            # Handler may already have committed a schedule mutation. Never replay blindly.
            # Keep only a redacted stage/code; a model that may have run is never called effect-free.
            diagnostic = {"stage": getattr(exc, "stage", "handler"),
                          "error": exc.code if isinstance(exc, BeeBotError) else type(exc).__name__,
                          "model_may_have_run": getattr(exc, "model_may_have_run", True)}
            logger.warning("Sự kiện Zalo %s chưa rõ kết quả ở bước %s (%s); không tự phát lại.",
                           event_id[:17], diagnostic["stage"], diagnostic["error"])
            with self._connect() as db:
                db.execute("UPDATE zalo_inbox SET status='uncertain',result=? WHERE event_id=?",
                           (json.dumps({"diagnostic": diagnostic}), event_id))
            return {"event_id": event_id, "status": "uncertain", "requires_reconciliation": True, "diagnostic": diagnostic}
        with self._connect() as db:
            db.execute("UPDATE zalo_inbox SET status='completed',result=? WHERE event_id=?", (encoded, event_id))
        return {"event_id": event_id, "status": "completed", "result": result, "duplicate": False}
