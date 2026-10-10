"""Receive-only HTTP boundary: no bot token, real webhook or external send."""

import json
import sqlite3

from starlette.testclient import TestClient

from bee_bot.zalo import ZaloIngress
from bee_bot.zalo_webhook import MAX_BODY_BYTES, app_from_env, create_app


def update(sender="sender-an", chat_type="PRIVATE", text="Nội dung riêng"):
    return {"ok": True, "result": {"event_name": "message.text.received", "message": {
        "from": {"id": sender, "is_bot": False}, "chat": {"id": "chat-an", "chat_type": chat_type},
        "message_id": "message-1", "date": 1750316131602, "text": text,
    }}}


def configured(tmp_path):
    db = tmp_path / "inbox.db"
    ingress = ZaloIngress(db, identities={"sender-an": "an"}, webhook_secret="test-secret-header")
    return db, ingress, TestClient(create_app(ingress))


def rows(db):
    with sqlite3.connect(db) as connection:
        return connection.execute("SELECT actor_id,status,payload FROM zalo_inbox").fetchall()


def test_wrong_secret_auth_before_bad_json_and_no_store(tmp_path):
    db, _, client = configured(tmp_path)
    response = client.post("/zalo/webhook", content="invalid json", headers={"X-Bot-Api-Secret-Token": "wrong"})
    assert response.status_code == 403
    assert response.json() == {"ok": False, "error": "ZALO_UNAUTHORIZED"}
    assert rows(db) == []


def test_nonprivate_message_rejected_without_store(tmp_path):
    db, _, client = configured(tmp_path)
    response = client.post("/zalo/webhook", json=update(chat_type="GROUP"), headers={"X-Bot-Api-Secret-Token": "test-secret-header"})
    assert response.status_code == 422
    assert rows(db) == []


def test_unlinked_sender_rejected_no_identifiers_echoed(tmp_path):
    db, _, client = configured(tmp_path)
    response = client.post("/zalo/webhook", json=update(sender="unknown-id"), headers={"X-Bot-Api-Secret-Token": "test-secret-header"})
    assert response.status_code == 403
    assert response.json() == {"ok": False, "error": "ZALO_UNKNOWN_USER"}
    assert "unknown-id" not in response.text
    assert rows(db) == []


def test_ack_after_persist_and_duplicate_survives_new_app(tmp_path):
    db, _, client = configured(tmp_path)
    response = client.post("/zalo/webhook", json=update(), headers={"X-Bot-Api-Secret-Token": "test-secret-header"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    stored = rows(db)
    assert len(stored) == 1
    assert stored[0][:2] == ("an", "pending")
    assert json.loads(stored[0][2])["text"] == "Nội dung riêng"
    restarted = TestClient(create_app(ZaloIngress(db, identities={"sender-an": "an"}, webhook_secret="test-secret-header")))
    duplicate = restarted.post("/zalo/webhook", json=update(), headers={"X-Bot-Api-Secret-Token": "test-secret-header"})
    assert duplicate.json() == {"ok": True}
    assert rows(db) == stored
    assert "sender-an" not in response.text
    assert "Nội dung riêng" not in response.text


def test_inbox_failure_never_returns_success(tmp_path):
    _, ingress, client = configured(tmp_path)
    def fail(payload, secret):
        raise sqlite3.OperationalError("secret/path/private content")
    ingress.receive_webhook = fail
    response = client.post("/zalo/webhook", json=update(), headers={"X-Bot-Api-Secret-Token": "test-secret-header"})
    assert response.status_code == 503
    assert response.json() == {"ok": False, "error": "INBOX_UNAVAILABLE"}
    assert "private" not in response.text


def test_conflicting_duplicate_rejected(tmp_path):
    db, _, client = configured(tmp_path)
    headers = {"X-Bot-Api-Secret-Token": "test-secret-header"}
    client.post("/zalo/webhook", json=update(), headers=headers)
    response = client.post("/zalo/webhook", json=update(text="changed"), headers=headers)
    assert response.status_code == 409
    assert len(rows(db)) == 1


def test_invalid_json_and_body_limit(tmp_path):
    db, _, client = configured(tmp_path)
    headers = {"X-Bot-Api-Secret-Token": "test-secret-header"}
    assert client.post("/zalo/webhook", content="invalid", headers=headers).status_code == 400
    assert client.post("/zalo/webhook", content=b"x" * (MAX_BODY_BYTES + 1), headers=headers).status_code == 413
    assert rows(db) == []


def test_health_no_private_info(tmp_path):
    _, _, client = configured(tmp_path)
    assert client.get("/health").json() == {"ok": True}


def test_environment_factory_needs_no_token(tmp_path, monkeypatch):
    mapping = tmp_path / "identities.json"
    mapping.write_text('{"sender-an":"an"}')
    monkeypatch.delenv("ZALO_BOT_TOKEN", raising=False)
    monkeypatch.setenv("ZALO_WEBHOOK_SECRET", "test-secret-header")
    monkeypatch.setenv("BEE_BOT_ZALO_IDENTITIES", str(mapping))
    monkeypatch.setenv("BEE_BOT_ZALO_INBOX", str(tmp_path / "inbox.db"))
    client = TestClient(app_from_env())
    response = client.post("/zalo/webhook", json=update(), headers={"X-Bot-Api-Secret-Token": "test-secret-header"})
    assert response.status_code == 200
